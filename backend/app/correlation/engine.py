"""Correlation Engine — deterministic, explainable event relationship detection.

Every relationship has a type, strength, and explicit reason.
Temporal proximity alone is NEVER sufficient to create a relationship.

Supported relationship signals (in strength order):
1. SHARED_ID       — exact shared identifier (CMD/MSG/FLT/RCV/SP/PLN)
2. MESSAGE_FLOW    — MESSAGE_SENT↔MESSAGE_RECEIVED matching msg_id across nodes
3. EXPLICIT_REF    — ack_for, resend_of, alert_id, ref, related fields
4. RECOVERY        — fault code → recovery code → cleared code
5. SEQUENCE        — state from→to chain; planning SEND→RECV→ACK→COMPLETE
6. SHARED_COMP     — same component, same node, within temporal window
7. TEMPORAL        — proximity within window (always labeled POSSIBLE_RELATIONSHIP)
8. REPETITION      — same event type+key repeated
9. MISSING_EVENT   — expected step absent from sequence
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import networkx as nx  # type: ignore

from ..core.logging import get_logger
from ..models.incident import (
    EventRelationship,
    MissingEventFinding,
    RelationshipStrength,
    RelationshipType,
    UncertaintyLevel,
)

logger = get_logger(__name__)


def _make_rel_id() -> str:
    return f"REL-{uuid.uuid4().hex[:8].upper()}"


def _json_val(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return v
    return v


def _ts_parse(v: Any) -> Optional[datetime]:
    """Parse a timestamp value from an event dict (may be datetime or ISO string)."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


class CorrelationEngine:
    """
    Analyzes a list of normalized event dicts and builds a NetworkX graph
    of typed, explained relationships.

    Input: list of event dicts (from EventStore.get_events())
    Output:
      - relationships: list[EventRelationship]
      - graph: nx.DiGraph
      - missing_events: list[MissingEventFinding]
    """

    def __init__(self, temporal_window_seconds: float = 10.0):
        self.temporal_window = timedelta(seconds=temporal_window_seconds)

    def correlate(
        self, events: list[dict[str, Any]]
    ) -> tuple[list[EventRelationship], nx.DiGraph, list[MissingEventFinding]]:
        relationships: list[EventRelationship] = []
        missing: list[MissingEventFinding] = []

        # Build lookup indexes
        by_id: dict[str, dict] = {e["event_id"]: e for e in events}

        # Index: incident_hint → list of events
        hint_index: dict[str, list[dict]] = {}
        for e in events:
            h = e.get("incident_hint")
            if h:
                hint_index.setdefault(h, []).append(e)

        # Index: msg_id → events that sent/received it
        msg_sent: dict[str, dict] = {}   # msg_id → SENT event
        msg_recv: dict[str, dict] = {}   # msg_id → RECEIVED event
        msg_ack: dict[str, dict] = {}    # acked msg_id → ACK event
        # Fault/recovery indexes keyed by (code, node) → list of events
        # to handle repeated/reusable codes across nodes and time
        fault_raised: dict[tuple[str, str], list[dict]] = {}
        fault_cleared: dict[tuple[str, str], list[dict]] = {}
        recovery_started: dict[str, dict] = {}  # recovery code → RECOVERY_STARTED

        for e in events:
            attrs = _json_val(e.get("attributes") or {})
            et = e.get("event_type", "")
            fam = e.get("log_family", "")

            if fam == "planning":
                msg = attrs.get("msg", "")
                ack_for = attrs.get("ack_for", "")
                if et == "MESSAGE_SENT" and msg:
                    msg_sent[msg] = e
                elif et == "MESSAGE_RECEIVED" and msg:
                    msg_recv[msg] = e
                elif et == "MESSAGE_ACK" and ack_for:
                    msg_ack[ack_for] = e

            if fam == "fault_recovery":
                code = attrs.get("code", "")
                e_node = e.get("node", "")
                if et == "FAULT_RAISED" and code:
                    fault_raised.setdefault((code, e_node), []).append(e)
                elif et == "FAULT_CLEARED" and code:
                    fault_cleared.setdefault((code, e_node), []).append(e)
                elif et == "RECOVERY_STARTED" and code:
                    recovery_started[code] = e

        # ----------------------------------------------------------------
        # 1. SHARED_ID relationships
        #    Distinguish instance-specific IDs (MSG-*, CMD-*, PLN-*, SP-*, WP-*)
        #    from reusable IDs (FLT-*, RCV-*).
        #    Reusable IDs require: same node + temporal proximity + no
        #    intervening FAULT_CLEARED to link events.
        # ----------------------------------------------------------------

        # Pre-build index of FAULT_CLEARED events keyed by (code, node)
        # for temporal separation of reusable fault codes
        cleared_index: dict[tuple[str, str], list[datetime]] = {}
        for e in events:
            if e.get("event_type") == "FAULT_CLEARED":
                c_attrs = _json_val(e.get("attributes") or {})
                c_code = c_attrs.get("code", "")
                c_node = e.get("node", "")
                c_ts = _ts_parse(e.get("timestamp"))
                if c_code and c_node and c_ts:
                    cleared_index.setdefault((c_code, c_node), []).append(c_ts)
        for k in cleared_index:
            cleared_index[k].sort()

        _REUSABLE_PREFIXES = ("FLT-", "RCV-")
        _REUSABLE_WINDOW_S = 300.0  # 5-minute window for reusable IDs

        def _is_reusable_id(hint_val: str) -> bool:
            return any(hint_val.startswith(p) for p in _REUSABLE_PREFIXES)

        def _separated_by_clear(code: str, node: str, ts_a: datetime, ts_b: datetime) -> bool:
            """Check if a FAULT_CLEARED for this code on this node occurred between ts_a and ts_b."""
            early, late = (ts_a, ts_b) if ts_a < ts_b else (ts_b, ts_a)
            clears = cleared_index.get((code, node), [])
            for ct in clears:
                if early < ct < late:
                    return True
            return False

        for hint, evts in hint_index.items():
            if len(evts) < 2:
                continue

            is_reusable = _is_reusable_id(hint)

            for i, src in enumerate(evts):
                for tgt in evts[i + 1:]:
                    # --- Reusable ID guards ---
                    if is_reusable:
                        # Guard 1: must be same node
                        if src["node"] != tgt["node"]:
                            continue

                        # Guard 2: must be within temporal window
                        src_ts = _ts_parse(src.get("timestamp"))
                        tgt_ts = _ts_parse(tgt.get("timestamp"))
                        if src_ts and tgt_ts:
                            if abs((src_ts - tgt_ts).total_seconds()) > _REUSABLE_WINDOW_S:
                                continue
                            # Guard 3: not separated by a FAULT_CLEARED
                            # The underlying fault code for a RCV-* is in the 'related' field
                            check_code = hint
                            if hint.startswith("RCV-"):
                                src_attrs = _json_val(src.get("attributes") or {})
                                check_code = src_attrs.get("related", hint)
                            if _separated_by_clear(check_code, src["node"], src_ts, tgt_ts):
                                continue

                    # --- Determine strength ---
                    if src["node"] == tgt["node"] and src["log_family"] == tgt["log_family"]:
                        rtype = RelationshipType.SHARED_ID
                        strength = RelationshipStrength.MODERATE
                    else:
                        rtype = RelationshipType.SHARED_ID
                        strength = RelationshipStrength.CONFIRMED

                    relationships.append(EventRelationship(
                        relationship_id=_make_rel_id(),
                        source_event_id=src["event_id"],
                        target_event_id=tgt["event_id"],
                        relationship_type=rtype,
                        strength=strength,
                        reason=f"Both events share identifier '{hint}'",
                        supporting_evidence=[hint],
                        confidence=1.0 if strength == RelationshipStrength.CONFIRMED else 0.8,
                    ))

        # ----------------------------------------------------------------
        # 2. MESSAGE_FLOW relationships
        # ----------------------------------------------------------------
        for msg_id, sent_evt in msg_sent.items():
            if msg_id in msg_recv:
                recv_evt = msg_recv[msg_id]
                relationships.append(EventRelationship(
                    relationship_id=_make_rel_id(),
                    source_event_id=sent_evt["event_id"],
                    target_event_id=recv_evt["event_id"],
                    relationship_type=RelationshipType.MESSAGE_FLOW,
                    strength=RelationshipStrength.STRONG,
                    reason=f"MESSAGE_SENT on {sent_evt['node']} matches MESSAGE_RECEIVED on {recv_evt['node']} via msg_id={msg_id}",
                    supporting_evidence=[msg_id],
                    confidence=0.99,
                ))
                # Check for ACK
                if msg_id in msg_ack:
                    ack_evt = msg_ack[msg_id]
                    relationships.append(EventRelationship(
                        relationship_id=_make_rel_id(),
                        source_event_id=recv_evt["event_id"],
                        target_event_id=ack_evt["event_id"],
                        relationship_type=RelationshipType.SEQUENCE,
                        strength=RelationshipStrength.STRONG,
                        reason=f"MESSAGE_RECEIVED acknowledged by MESSAGE_ACK for msg_id={msg_id}",
                        supporting_evidence=[msg_id],
                        confidence=0.99,
                    ))

        # ----------------------------------------------------------------
        # 3. EXPLICIT_REFERENCE — ack_for, resend_of, alert_id, related
        # ----------------------------------------------------------------
        for e in events:
            attrs = _json_val(e.get("attributes") or {})

            # resend_of: links a resent message back to original
            resend_of = attrs.get("resend_of", "")
            if resend_of and resend_of in msg_sent:
                orig = msg_sent[resend_of]
                relationships.append(EventRelationship(
                    relationship_id=_make_rel_id(),
                    source_event_id=orig["event_id"],
                    target_event_id=e["event_id"],
                    relationship_type=RelationshipType.EXPLICIT_REFERENCE,
                    strength=RelationshipStrength.STRONG,
                    reason=f"Message {e['event_id']} is a resend of original {resend_of}",
                    supporting_evidence=[resend_of],
                    confidence=0.98,
                ))

            # related: fault notice links to original fault
            related = attrs.get("related", "")
            if related and related.startswith("FLT-"):
                # Find the nearest fault event on the same node for this code
                e_node = e.get("node", "")
                e_ts = _ts_parse(e.get("timestamp"))
                candidates = fault_raised.get((related, e_node), [])
                if not candidates:
                    # Try any node (for cross-node fault notices like PEER_FAULT_NOTICE)
                    for (fc, fn), fl in fault_raised.items():
                        if fc == related:
                            candidates.extend(fl)
                if candidates and e_ts:
                    # Pick the closest fault event in time
                    best = min(candidates, key=lambda f: abs((_ts_parse(f.get("timestamp")) or e_ts) - e_ts).total_seconds())
                    relationships.append(EventRelationship(
                        relationship_id=_make_rel_id(),
                        source_event_id=best["event_id"],
                        target_event_id=e["event_id"],
                        relationship_type=RelationshipType.EXPLICIT_REFERENCE,
                        strength=RelationshipStrength.CONFIRMED,
                        reason=f"Event {e['event_id']} explicitly references fault {related}",
                        supporting_evidence=[related],
                        confidence=1.0,
                    ))

            # related: recovery event references fault
            if related and related.startswith("MSG-") and related in msg_sent:
                orig_msg = msg_sent[related]
                relationships.append(EventRelationship(
                    relationship_id=_make_rel_id(),
                    source_event_id=orig_msg["event_id"],
                    target_event_id=e["event_id"],
                    relationship_type=RelationshipType.EXPLICIT_REFERENCE,
                    strength=RelationshipStrength.STRONG,
                    reason=f"Event {e['event_id']} explicitly references message {related}",
                    supporting_evidence=[related],
                    confidence=0.97,
                ))

        # ----------------------------------------------------------------
        # 4. RECOVERY chain: FAULT_RAISED → RECOVERY_STARTED → FAULT_CLEARED
        # ----------------------------------------------------------------
        for (fault_code, fault_node), fault_evt_list in fault_raised.items():
            for fault_evt in fault_evt_list:
                # Find recovery that references this fault code on the same node
                for rcv_code, rcv_evt in recovery_started.items():
                    rcv_attrs = _json_val(rcv_evt.get("attributes") or {})
                    rcv_related = rcv_attrs.get("related", "")
                    if rcv_related == fault_code and rcv_evt["node"] == fault_evt["node"]:
                        # Ensure recovery is temporally after the fault (within reasonable window)
                        f_ts = _ts_parse(fault_evt.get("timestamp"))
                        r_ts = _ts_parse(rcv_evt.get("timestamp"))
                        if f_ts and r_ts and (r_ts - f_ts).total_seconds() > 300:
                            continue  # Too far apart — likely a different occurrence
                        if f_ts and r_ts and r_ts < f_ts:
                            continue  # Recovery before fault — wrong pairing
                        relationships.append(EventRelationship(
                            relationship_id=_make_rel_id(),
                            source_event_id=fault_evt["event_id"],
                            target_event_id=rcv_evt["event_id"],
                            relationship_type=RelationshipType.RECOVERY,
                            strength=RelationshipStrength.CONFIRMED,
                            reason=f"RECOVERY_STARTED {rcv_code} explicitly references fault {fault_code}",
                            supporting_evidence=[fault_code, rcv_code],
                            confidence=1.0,
                        ))

                        # Link recovery to cleared on same node
                        clr_list = fault_cleared.get((fault_code, fault_evt["node"]), [])
                        for clr_evt in clr_list:
                            clr_attrs = _json_val(clr_evt.get("attributes") or {})
                            if clr_attrs.get("related") == rcv_code or clr_attrs.get("code") == fault_code:
                                # Ensure cleared is after recovery
                                c_ts = _ts_parse(clr_evt.get("timestamp"))
                                if r_ts and c_ts and c_ts < r_ts:
                                    continue
                                if r_ts and c_ts and (c_ts - r_ts).total_seconds() > 300:
                                    continue
                                relationships.append(EventRelationship(
                                    relationship_id=_make_rel_id(),
                                    source_event_id=rcv_evt["event_id"],
                                    target_event_id=clr_evt["event_id"],
                                    relationship_type=RelationshipType.RECOVERY,
                                    strength=RelationshipStrength.STRONG,
                                    reason=f"FAULT_CLEARED {fault_code} follows RECOVERY_STARTED {rcv_code}",
                                    supporting_evidence=[rcv_code, fault_code],
                                    confidence=0.95,
                                ))
                                break  # Only link to the first matching clear

        # ----------------------------------------------------------------
        # 5. REPETITION — same family+event_type+entity cluster
        #    Added: temporal guard to prevent linking events far apart
        # ----------------------------------------------------------------
        rep_index: dict[tuple, list[dict]] = {}
        for e in events:
            key = (e.get("node"), e.get("log_family"), e.get("event_type"), e.get("entity"))
            rep_index.setdefault(key, []).append(e)

        for key, evts in rep_index.items():
            if len(evts) < 2:
                continue
            # Only create repetition links for non-trivial groups
            # (avoid linking all 15 SELFTEST_PASS records to each other)
            if len(evts) > 10:
                continue
            # Sort by timestamp within the group for consecutive pairing
            sorted_evts = sorted(evts, key=lambda x: str(x.get("timestamp", "")))
            for i in range(len(sorted_evts) - 1):
                # Temporal guard: only link repetitions within 30 minutes
                ts_a = _ts_parse(sorted_evts[i].get("timestamp"))
                ts_b = _ts_parse(sorted_evts[i + 1].get("timestamp"))
                if ts_a and ts_b and abs((ts_b - ts_a).total_seconds()) > 1800:
                    continue  # Too far apart — likely separate operational sessions
                relationships.append(EventRelationship(
                    relationship_id=_make_rel_id(),
                    source_event_id=sorted_evts[i]["event_id"],
                    target_event_id=sorted_evts[i + 1]["event_id"],
                    relationship_type=RelationshipType.REPETITION,
                    strength=RelationshipStrength.MODERATE,
                    reason=f"Repeated {key[2]} for entity {key[3]} on {key[0]}",
                    supporting_evidence=list(filter(None, [str(k) for k in key])),
                    confidence=0.85,
                ))

        # ----------------------------------------------------------------
        # 5b. PLAN → MESSAGE linking
        #     A planning event with both plan_id and msg_id links the plan
        #     to message events sharing that msg_id.
        # ----------------------------------------------------------------
        plan_to_msgs: dict[str, set] = {}  # plan_id → set of msg_ids
        for e in events:
            if e.get("log_family") != "planning":
                continue
            attrs = _json_val(e.get("attributes") or {})
            plan_id = attrs.get("plan", "")
            msg_id = attrs.get("msg", "")
            if plan_id and msg_id and plan_id != "-" and msg_id != "-":
                plan_to_msgs.setdefault(plan_id, set()).add(msg_id)

        # Link events sharing a plan_id to events sharing any of its msg_ids
        for plan_id, msg_ids in plan_to_msgs.items():
            plan_events = hint_index.get(plan_id, [])
            for mid in msg_ids:
                msg_events = hint_index.get(mid, [])
                for pe in plan_events:
                    for me in msg_events:
                        if pe["event_id"] == me["event_id"]:
                            continue
                        relationships.append(EventRelationship(
                            relationship_id=_make_rel_id(),
                            source_event_id=pe["event_id"],
                            target_event_id=me["event_id"],
                            relationship_type=RelationshipType.SEQUENCE,
                            strength=RelationshipStrength.STRONG,
                            reason=f"Plan {plan_id} distributed via message {mid}",
                            supporting_evidence=[plan_id, mid],
                            confidence=0.95,
                        ))

        # ----------------------------------------------------------------
        # 5c. STATE → FAULT linking
        #     A STATE_CHANGE with trigger matching a fault code or on the
        #     same component/node within a close window of a FAULT_RAISED.
        # ----------------------------------------------------------------
        for e in events:
            if e.get("event_type") != "STATE_CHANGE":
                continue
            attrs = _json_val(e.get("attributes") or {})
            trigger = attrs.get("trigger", "")
            # If trigger directly references a fault code
            if trigger and trigger.startswith("FLT-"):
                e_node = e.get("node", "")
                e_ts = _ts_parse(e.get("timestamp"))
                candidates = fault_raised.get((trigger, e_node), [])
                if candidates and e_ts:
                    best = min(candidates, key=lambda f: abs((_ts_parse(f.get("timestamp")) or e_ts) - e_ts).total_seconds())
                    relationships.append(EventRelationship(
                        relationship_id=_make_rel_id(),
                        source_event_id=best["event_id"],
                        target_event_id=e["event_id"],
                        relationship_type=RelationshipType.EXPLICIT_REFERENCE,
                        strength=RelationshipStrength.CONFIRMED,
                        reason=f"STATE_CHANGE triggered by fault {trigger}",
                        supporting_evidence=[trigger],
                        confidence=1.0,
                    ))
            # If trigger references a recovery code
            elif trigger and trigger.startswith("RCV-") and trigger in recovery_started:
                rcv_evt = recovery_started[trigger]
                relationships.append(EventRelationship(
                    relationship_id=_make_rel_id(),
                    source_event_id=rcv_evt["event_id"],
                    target_event_id=e["event_id"],
                    relationship_type=RelationshipType.EXPLICIT_REFERENCE,
                    strength=RelationshipStrength.STRONG,
                    reason=f"STATE_CHANGE triggered by recovery {trigger}",
                    supporting_evidence=[trigger],
                    confidence=0.95,
                ))
            # Same component + same node + close time window → link state to fault
            elif e.get("node") and e.get("component"):
                e_ts = _ts_parse(e.get("timestamp"))
                if e_ts:
                    for (fcode, fnode), fault_evt_list in fault_raised.items():
                        for fault_evt in fault_evt_list:
                            if (fault_evt.get("node") == e.get("node")
                                    and fault_evt.get("component") == e.get("component")):
                                f_ts = _ts_parse(fault_evt.get("timestamp"))
                                if f_ts and abs((e_ts - f_ts).total_seconds()) <= 15:
                                    relationships.append(EventRelationship(
                                        relationship_id=_make_rel_id(),
                                        source_event_id=fault_evt["event_id"],
                                        target_event_id=e["event_id"],
                                        relationship_type=RelationshipType.SHARED_COMPONENT,
                                        strength=RelationshipStrength.MODERATE,
                                        reason=f"STATE_CHANGE on same component {e.get('component')} within 15s of fault {fcode}",
                                        supporting_evidence=[fcode, e.get("component", "")],
                                        confidence=0.75,
                                    ))

        # ----------------------------------------------------------------
        # 6. MISSING_EVENT detection — GENERIC (no hardcoded IDs)
        # ----------------------------------------------------------------

        # 6a. Missing MESSAGE_ACK: any MESSAGE_SENT without a corresponding ACK
        for msg_id, sent_evt in msg_sent.items():
            if msg_id not in msg_ack:
                # Check if there's at least a RECEIVED
                has_recv = msg_id in msg_recv
                if has_recv:
                    # Received but not acknowledged — noteworthy
                    missing.append(MissingEventFinding(
                        description=f"Expected MESSAGE_ACK for {msg_id} is absent from all logs (message was received but not acknowledged)",
                        expected_at_node=msg_recv[msg_id].get("node"),
                        expected_after_event_id=msg_recv[msg_id]["event_id"],
                        expected_event_type="MESSAGE_ACK",
                        uncertainty=UncertaintyLevel.MISSING_DATA,
                    ))

        # 6b. Missing EXCHANGE_COMPLETE: MESSAGE_SENT without EXCHANGE_COMPLETE
        all_exchange_events = [
            e for e in events
            if e.get("event_type") == "EXCHANGE_COMPLETE"
        ]
        exchange_msgs = set()
        for ee in all_exchange_events:
            attrs = _json_val(ee.get("attributes") or {})
            exchange_msgs.add(attrs.get("msg", ""))
        for msg_id, sent_evt in msg_sent.items():
            if msg_id not in exchange_msgs:
                # Only flag if there's a receive but no exchange complete
                if msg_id in msg_recv:
                    missing.append(MissingEventFinding(
                        description=f"Expected EXCHANGE_COMPLETE for {msg_id} is absent — message exchange did not complete normally",
                        expected_at_node=sent_evt.get("node"),
                        expected_after_event_id=sent_evt["event_id"],
                        expected_event_type="EXCHANGE_COMPLETE",
                        uncertainty=UncertaintyLevel.MISSING_DATA,
                    ))

        # 6c. Missing SETPOINT_ACK: any SETPOINT_SENT without corresponding ACK
        sp_sent_index: dict[str, dict] = {}  # sp_id → SETPOINT_SENT event
        sp_ack_ids: set[str] = set()
        for e in events:
            et = e.get("event_type", "")
            entity = e.get("entity", "") or ""
            if et == "SETPOINT_SENT" and entity.startswith("SP-"):
                sp_sent_index[entity] = e
            elif et == "SETPOINT_ACK" and entity.startswith("SP-"):
                sp_ack_ids.add(entity)
        for sp_id, sp_evt in sp_sent_index.items():
            if sp_id not in sp_ack_ids:
                missing.append(MissingEventFinding(
                    description=f"Expected SETPOINT_ACK for {sp_id} is absent from logs",
                    expected_at_node=sp_evt.get("node"),
                    expected_after_event_id=sp_evt["event_id"],
                    expected_event_type="SETPOINT_ACK",
                    uncertainty=UncertaintyLevel.MISSING_DATA,
                ))

        # 6d. Missing FAULT_CLEARED: any FAULT_RAISED without FAULT_CLEARED
        for (fault_code, fault_node), fault_evt_list in fault_raised.items():
            if (fault_code, fault_node) not in fault_cleared:
                for fault_evt in fault_evt_list:
                    missing.append(MissingEventFinding(
                        description=f"FAULT_RAISED {fault_code} on {fault_node} has no corresponding FAULT_CLEARED — fault may be unresolved",
                        expected_at_node=fault_node,
                        expected_after_event_id=fault_evt["event_id"],
                        expected_event_type="FAULT_CLEARED",
                        uncertainty=UncertaintyLevel.MISSING_DATA,
                    ))
                    break  # One finding per (code, node) group is enough

        # ----------------------------------------------------------------
        # Build NetworkX graph
        # ----------------------------------------------------------------
        G = nx.DiGraph()
        for e in events:
            G.add_node(
                e["event_id"],
                node=e.get("node"),
                log_family=e.get("log_family"),
                event_type=e.get("event_type"),
                timestamp=str(e.get("timestamp")),
                severity=e.get("severity"),
                component=e.get("component"),
            )

        for rel in relationships:
            G.add_edge(
                rel.source_event_id,
                rel.target_event_id,
                relationship_id=rel.relationship_id,
                relationship_type=rel.relationship_type.value if hasattr(rel.relationship_type, "value") else str(rel.relationship_type),
                strength=rel.strength.value if hasattr(rel.strength, "value") else str(rel.strength),
                reason=rel.reason,
                confidence=rel.confidence,
            )

        logger.info(
            "correlation_complete",
            relationships=len(relationships),
            missing_events=len(missing),
            graph_nodes=G.number_of_nodes(),
            graph_edges=G.number_of_edges(),
        )

        return relationships, G, missing
