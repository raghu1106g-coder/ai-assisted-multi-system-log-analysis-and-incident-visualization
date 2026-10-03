"""Incident reconstruction — groups correlated events into named incidents.

Uses the correlation graph to find connected components and classify them
as INCIDENT, NON_INCIDENT_NORMAL_OPERATION, or CANDIDATE.

The incident definitions are derived from observed patterns in the data,
NOT from ground_truth files.

GENERIC ALGORITHM (dataset-independent):
1. Identify all FAULT_RAISED events as "incident seeds"
2. Expand each seed through the correlation graph to find related events
3. Merge overlapping clusters (shared events)
4. Classify each cluster based on fault presence and recovery status
5. Generate dynamic incident IDs, titles, and descriptions from event data
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

import networkx as nx  # type: ignore

from ..core.logging import get_logger
from ..models.incident import (
    Evidence,
    Incident,
    IncidentKind,
    MissingEventFinding,
    EventRelationship,
    UncertaintyLevel,
)

logger = get_logger(__name__)


def _json_val(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def _ts(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


class IncidentReconstructor:
    """
    Groups events into incident candidates based on:
    1. Fault events (FAULT_RAISED) as seeds — dataset-independent
    2. Correlation graph connectivity (expand seeds via graph edges)
    3. Operator commands initiating operational sequences
    4. Classification: INCIDENT (has faults), NORMAL_OPERATION (no faults), CANDIDATE

    No hardcoded fault codes, timestamps, or entity IDs.
    """

    # Time window for expanding incident clusters beyond direct graph edges
    _CLUSTER_EXPAND_WINDOW_S = 60.0

    # Maximum time gap between events in a single incident
    _MAX_INCIDENT_DURATION_S = 600.0  # 10 minutes

    def reconstruct(
        self,
        events: list[dict[str, Any]],
        relationships: list[EventRelationship],
        graph: nx.DiGraph,
        missing_events: list[MissingEventFinding],
    ) -> list[Incident]:
        """Reconstruct incidents from events and their correlation graph.

        Algorithm:
        1. Find fault seeds (FAULT_RAISED events)
        2. Expand each seed through the correlation graph
        3. Merge overlapping clusters
        4. Find command-initiated sequences (non-fault operational groups)
        5. Classify and build Incident objects
        """
        incidents: list[Incident] = []

        # Build event lookup
        by_id: dict[str, dict] = {e["event_id"]: e for e in events}

        # Build undirected view of graph for reachability
        undirected = graph.to_undirected()

        # Helper to expand a cluster temporally on involved nodes
        def expand_cluster(c: set[str]) -> set[str]:
            c_evts = [by_id[eid] for eid in c if eid in by_id]
            if not c_evts:
                return c
            ts_list = [t for e in c_evts if (t := _ts(e.get("timestamp"))) is not None]
            if not ts_list:
                return c
            t_min = min(ts_list)
            t_max = max(ts_list)
            nodes = {str(e.get("node")) for e in c_evts if e.get("node")}
            expanded = set(c)
            for e in events:
                if e["event_id"] in expanded:
                    continue
                ets = _ts(e.get("timestamp"))
                if ets and str(e.get("node")) in nodes:
                    if (t_min.timestamp() - 3.0) <= ets.timestamp() <= (t_max.timestamp() + 3.0):
                        if e.get("event_type") in (
                            "STATE_CHANGE", "GUIDANCE_DEVIATION", "TRANSIENT_WARN",
                            "CONFIG_CHANGE", "VIEW_CHANGE", "PEER_STATE",
                        ):
                            expanded.add(e["event_id"])
            return expanded

        clusters: list[set[str]] = []
        used_event_ids: set[str] = set()

        # -------------------------------------------------------------------
        # Step 1: Fault seeds
        # -------------------------------------------------------------------
        fault_events = [
            e for e in events
            if e.get("event_type") == "FAULT_RAISED"
            or e.get("category") == "FAULT"
        ]

        # Group faults by code and node to handle repeated faults
        fault_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for fe in fault_events:
            attrs = _json_val(fe.get("attributes") or {})
            code = attrs.get("code", "") or fe.get("entity", "")
            node = fe.get("node", "")
            fault_groups[(code, node)].append(fe)

        for (code, node), faults in fault_groups.items():
            sorted_faults = sorted(faults, key=lambda e: str(e.get("timestamp", "")))
            for fault_evt in sorted_faults:
                if fault_evt["event_id"] in used_event_ids:
                    continue
                c: set[str] = set()
                if fault_evt["event_id"] in undirected:
                    c.update(str(x) for x in nx.node_connected_component(undirected, fault_evt["event_id"]))
                else:
                    c.add(fault_evt["event_id"])
                c = expand_cluster(c)
                clusters.append(c)
                used_event_ids.update(c)

        # -------------------------------------------------------------------
        # Step 2: Orphan recovery actions & fault notices without local FAULT_RAISED
        # -------------------------------------------------------------------
        for e in events:
            eid = e["event_id"]
            if eid in used_event_ids:
                continue
            if e.get("event_type") in ("RECOVERY_STARTED", "FAULT_NOTICE_SENT", "PEER_FAULT_NOTICE"):
                c = set()
                if eid in undirected:
                    c.update(str(x) for x in nx.node_connected_component(undirected, eid))
                else:
                    c.add(eid)
                c = expand_cluster(c)
                clusters.append(c)
                used_event_ids.update(c)

        # -------------------------------------------------------------------
        # Step 3: Degraded state transitions & deviations
        # -------------------------------------------------------------------
        for e in events:
            eid = e["event_id"]
            if eid in used_event_ids:
                continue
            if e.get("event_type") == "STATE_CHANGE" and "DEGRADED" in str(e.get("message", "")) + str(e.get("attributes", "")):
                c = set()
                if eid in undirected:
                    c.update(str(x) for x in nx.node_connected_component(undirected, eid))
                else:
                    c.add(eid)
                c = expand_cluster(c)
                clusters.append(c)
                used_event_ids.update(c)

        # -------------------------------------------------------------------
        # Step 4: Delayed sequence exchanges (delta > 3s)
        # -------------------------------------------------------------------
        for r in relationships:
            src = by_id.get(r.source_event_id)
            tgt = by_id.get(r.target_event_id)
            if src and tgt and ("acknowledged by MESSAGE_ACK" in (r.reason or "") or "MESSAGE_FLOW" in str(r.relationship_type)):
                ts1 = _ts(src.get("timestamp"))
                ts2 = _ts(tgt.get("timestamp"))
                if ts1 and ts2 and abs((ts2 - ts1).total_seconds()) > 3.0:
                    c = set()
                    if src["event_id"] in undirected:
                        c.update(str(x) for x in nx.node_connected_component(undirected, src["event_id"]))
                    if tgt["event_id"] in undirected:
                        c.update(str(x) for x in nx.node_connected_component(undirected, tgt["event_id"]))
                    if c and not (c & used_event_ids):
                        c = expand_cluster(c)
                        clusters.append(c)
                        used_event_ids.update(c)

        # -------------------------------------------------------------------
        # Step 5: Command-initiated operational sequences (non-fault)
        # -------------------------------------------------------------------
        cmd_events = [
            e for e in events
            if e.get("event_type") == "SUBMIT_COMMAND"
            and e["event_id"] not in used_event_ids
        ]

        for ce in cmd_events:
            eid = ce["event_id"]
            if eid in undirected:
                comp: set[str] = set(str(x) for x in nx.node_connected_component(undirected, eid))
                if len(comp) >= 3:
                    comp_exp = expand_cluster(comp)
                    clusters.append(comp_exp)
                    used_event_ids.update(comp_exp)

        # -------------------------------------------------------------------
        # Step 6: Merge overlapping clusters
        # -------------------------------------------------------------------
        merged = self._merge_overlapping(clusters)

        # -------------------------------------------------------------------
        # Step 6: Build Incident objects
        # -------------------------------------------------------------------
        def cluster_start_time(cluster: set[str]) -> str:
            times = []
            for eid in cluster:
                evt = by_id.get(eid)
                if evt:
                    t = _ts(evt.get("timestamp"))
                    if t:
                        times.append(t.isoformat())
            return min(times) if times else ""

        # Sort clusters: incidents first, then candidates, then routine operations, by start time
        def cluster_sort_key(cluster: set[str]) -> tuple:
            has_fault = any(by_id.get(eid, {}).get("event_type") == "FAULT_RAISED" for eid in cluster)
            is_cmd = any(by_id.get(eid, {}).get("event_type") == "SUBMIT_COMMAND" for eid in cluster)
            priority = 0 if has_fault else (2 if is_cmd else 1)
            return (priority, cluster_start_time(cluster))

        sorted_clusters = sorted(merged, key=cluster_sort_key)

        inc_counter = 0
        for cluster in sorted_clusters:
            if len(cluster) < 2:
                continue  # Skip trivial single-event clusters

            cluster_events = [by_id[eid] for eid in cluster if eid in by_id]
            if not cluster_events:
                continue

            inc_counter += 1
            incident = self._build_incident(
                incident_num=inc_counter,
                cluster_events=cluster_events,
                all_relationships=relationships,
                missing_events=missing_events,
            )
            incidents.append(incident)

        logger.info(
            "incident_reconstruction_complete",
            total_incidents=len(incidents),
            fault_incidents=sum(1 for i in incidents if i.kind == IncidentKind.INCIDENT),
            normal_ops=sum(1 for i in incidents if i.kind == IncidentKind.NON_INCIDENT_NORMAL_OPERATION),
            candidates=sum(1 for i in incidents if i.kind == IncidentKind.CANDIDATE),
        )

        return incidents

    @staticmethod
    def _merge_overlapping(clusters: list[set[str]]) -> list[set[str]]:
        """Merge clusters that share any event IDs."""
        if not clusters:
            return []

        merged: list[set[str]] = []
        for cluster in clusters:
            # Find all existing merged clusters that overlap
            overlapping_indices = []
            for i, existing in enumerate(merged):
                if cluster & existing:
                    overlapping_indices.append(i)

            if overlapping_indices:
                # Merge all overlapping clusters together with the new one
                combined = set(cluster)
                for i in sorted(overlapping_indices, reverse=True):
                    combined.update(merged.pop(i))
                merged.append(combined)
            else:
                merged.append(set(cluster))

        return merged

    def _build_incident(
        self,
        incident_num: int,
        cluster_events: list[dict],
        all_relationships: list[EventRelationship],
        missing_events: list[MissingEventFinding],
    ) -> Incident:
        """Build an Incident object from a cluster of events."""

        event_ids = [e["event_id"] for e in cluster_events]
        event_id_set = set(event_ids)

        # Timestamps
        ts_list = [t for e in cluster_events if (t := _ts(e.get("timestamp"))) is not None]
        start = min(ts_list) if ts_list else None
        end = max(ts_list) if ts_list else None

        # Nodes and families involved
        nodes = sorted({e["node"] for e in cluster_events if e.get("node")})
        families = sorted({e["log_family"] for e in cluster_events if e.get("log_family")})

        # Find fault codes in this cluster
        fault_codes = []
        fault_names = []
        for e in cluster_events:
            if e.get("event_type") == "FAULT_RAISED":
                attrs = _json_val(e.get("attributes") or {})
                code = attrs.get("code", "") or e.get("entity", "")
                name = attrs.get("name", "")
                if code and code not in fault_codes:
                    fault_codes.append(code)
                if name and name not in fault_names:
                    fault_names.append(name)

        # Find recovery codes
        recovery_codes = []
        for e in cluster_events:
            if e.get("event_type") == "RECOVERY_STARTED":
                attrs = _json_val(e.get("attributes") or {})
                code = attrs.get("code", "") or e.get("entity", "")
                if code and code not in recovery_codes:
                    recovery_codes.append(code)

        # Determine recovery status
        has_fault_cleared = any(
            e.get("event_type") == "FAULT_CLEARED" for e in cluster_events
        )
        has_recovery = len(recovery_codes) > 0
        has_fault = len(fault_codes) > 0

        if has_fault and has_fault_cleared:
            recovery_status = "RECOVERED"
        elif has_fault and has_recovery and not has_fault_cleared:
            recovery_status = "PARTIAL"
        elif has_fault and not has_recovery:
            recovery_status = "ONGOING"
        else:
            recovery_status = "NOT_APPLICABLE"

        # Classify incident
        if has_fault:
            kind = IncidentKind.INCIDENT
        elif any(e.get("event_type") == "SUBMIT_COMMAND" for e in cluster_events):
            kind = IncidentKind.NON_INCIDENT_NORMAL_OPERATION
        else:
            kind = IncidentKind.CANDIDATE

        # Build title from fault names or primary event types
        title = self._generate_title(fault_names, fault_codes, nodes, kind, cluster_events)

        # Build description from events
        description = self._generate_description(
            cluster_events, fault_codes, fault_names, recovery_codes, nodes, recovery_status
        )

        # Find related relationships
        rel_ids = [
            r.relationship_id for r in all_relationships
            if r.source_event_id in event_id_set or r.target_event_id in event_id_set
        ]

        # Find related missing events
        cluster_missing = [
            m for m in missing_events
            if m.expected_after_event_id in event_id_set
        ]

        # Build uncertainty findings
        uncertainty = self._derive_uncertainty(cluster_events, recovery_status, cluster_missing)

        incident_id = f"INC-{incident_num:03d}"

        return Incident(
            incident_id=incident_id,
            kind=kind,
            title=title,
            description=description,
            start_time=start,
            end_time=end,
            involved_nodes=nodes,
            involved_families=families,
            primary_faults=fault_codes,
            recovery_codes=recovery_codes,
            event_ids=event_ids,
            relationship_ids=rel_ids,
            recovery_status=recovery_status,
            missing_events=cluster_missing,
            uncertainty_findings=uncertainty,
        )

    @staticmethod
    def _generate_title(
        fault_names: list[str],
        fault_codes: list[str],
        nodes: list[str],
        kind: IncidentKind,
        events: list[dict],
    ) -> str:
        """Generate a human-readable title from incident content."""
        if kind == IncidentKind.NON_INCIDENT_NORMAL_OPERATION:
            # Find the operator command that started this sequence
            cmd_events = [e for e in events if e.get("event_type") == "SUBMIT_COMMAND"]
            if cmd_events:
                cmd_msg = cmd_events[0].get("message", "")
                entity = cmd_events[0].get("entity", "")
                return f"Routine operation ({entity}): {cmd_msg}" if cmd_msg else f"Routine operation ({entity})"
            return "Routine operational sequence (normal operation)"

        node_str = ", ".join(nodes) if len(nodes) <= 3 else f"{len(nodes)} nodes"
        cross = "multi-node" if len(nodes) > 1 else "single-node"

        if fault_names:
            primary = fault_names[0].replace("_", " ").title()
            if len(fault_names) > 1:
                return f"{primary} and {len(fault_names)-1} related fault(s) ({cross}, {node_str})"
            return f"{primary} ({cross}, {node_str})"
        elif fault_codes:
            return f"Fault {fault_codes[0]} ({cross}, {node_str})"
        else:
            return f"Candidate incident cluster ({cross}, {node_str})"

    @staticmethod
    def _generate_description(
        events: list[dict],
        fault_codes: list[str],
        fault_names: list[str],
        recovery_codes: list[str],
        nodes: list[str],
        recovery_status: str,
    ) -> str:
        """Generate a human-readable description from incident events."""
        parts = []

        # Describe the primary faults
        for i, code in enumerate(fault_codes):
            name = fault_names[i] if i < len(fault_names) else "UNKNOWN"
            fault_events = [e for e in events if e.get("event_type") == "FAULT_RAISED"]
            for fe in fault_events:
                attrs = _json_val(fe.get("attributes") or {})
                if attrs.get("code") == code or fe.get("entity") == code:
                    component = fe.get("component", "UNKNOWN")
                    node = fe.get("node", "UNKNOWN")
                    parts.append(
                        f"{code} ({name}) raised on {node} component {component}."
                    )
                    break

        # Describe recovery
        if recovery_codes:
            parts.append(
                f"Recovery actions: {', '.join(recovery_codes)}. "
                f"Recovery status: {recovery_status}."
            )
        elif fault_codes and recovery_status == "ONGOING":
            parts.append("No recovery action observed. Fault may be unresolved.")

        # Describe scope
        if len(nodes) > 1:
            parts.append(f"Affected nodes: {', '.join(nodes)}.")

        # Count events
        parts.append(f"Total events in cluster: {len(events)}.")

        return " ".join(parts)

    @staticmethod
    def _derive_uncertainty(
        events: list[dict],
        recovery_status: str,
        missing: list[MissingEventFinding],
    ) -> list[dict]:
        """Generate uncertainty findings from incident content."""
        findings = []

        if recovery_status == "RECOVERED":
            findings.append({
                "label": UncertaintyLevel.CONFIRMED_OBSERVATION,
                "description": "Fault raised, recovery observed, and fault cleared.",
            })
        elif recovery_status == "ONGOING":
            findings.append({
                "label": UncertaintyLevel.MISSING_DATA,
                "description": "Fault raised but no FAULT_CLEARED observed. Fault may be unresolved.",
            })
        elif recovery_status == "PARTIAL":
            findings.append({
                "label": UncertaintyLevel.INSUFFICIENT_EVIDENCE,
                "description": "Recovery started but fault not yet cleared.",
            })

        if missing:
            for m in missing:
                findings.append({
                    "label": UncertaintyLevel.MISSING_DATA,
                    "description": m.description,
                })

        # Check for multi-node incidents with possible but unconfirmed causal links
        nodes_in_faults: set[str] = set()
        for e in events:
            if e.get("event_type") == "FAULT_RAISED":
                n = e.get("node")
                if n:
                    nodes_in_faults.add(str(n))
        if len(nodes_in_faults) > 1:
            findings.append({
                "label": UncertaintyLevel.POSSIBLE_RELATIONSHIP,
                "description": (
                    f"Faults on {len(nodes_in_faults)} different nodes "
                    f"({', '.join(sorted(nodes_in_faults))}) are correlated by "
                    f"shared identifiers but causation is not established."
                ),
            })

        return findings


def build_evidence(events: list[dict[str, Any]]) -> list[Evidence]:
    """Create Evidence objects for all events (source traceability)."""
    evidence_list = []
    for e in events:
        attrs = _json_val(e.get("attributes") or {})
        summary_parts = [
            f"[{e.get('node')}]",
            f"[{e.get('log_family')}]",
            f"{e.get('event_type', '')}",
        ]
        if e.get("component"):
            summary_parts.append(f"component={e['component']}")
        if e.get("entity"):
            summary_parts.append(f"entity={e['entity']}")
        if e.get("message"):
            summary_parts.append(f"— {e['message']}")

        severity = e.get("severity", "INFO")
        finding_type = {
            "FAULT": "FAULT",
            "RECOVERY": "RECOVERY",
            "COMMAND": "OPERATOR_ACTION",
            "STATE_CHANGE": "STATE",
            "PHASE": "PHASE",
            "MESSAGE": "MESSAGE_FLOW",
        }.get(e.get("category", ""), "OBSERVATION")

        evidence_list.append(Evidence(
            evidence_id=f"EV-{e['event_id']}",
            event_id=e["event_id"],
            source_file=e.get("source_file", ""),
            source_line=e.get("source_line", 0),
            raw_record=e.get("raw_record", ""),
            normalized_summary=" ".join(summary_parts),
            relationship_to_finding=f"Source record for event {e['event_id']}",
            finding_type=finding_type,
        ))
    return evidence_list
