"""Relationships and Graph API endpoints."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from ...core.dependencies import get_store
from ...storage.event_store import EventStore

router = APIRouter()


@router.get("")
async def list_relationships(
    event_id: Optional[str] = Query(None, description="Filter relationships involving this event ID"),
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type (SHARED_PLAN_ID, CMD_ACK, FAULT_STATE, etc.)"),
    limit: int = Query(1000, ge=1, le=5000),
    store: EventStore = Depends(get_store),
) -> dict[str, Any]:
    """List event relationships with explainable reasons and confidence scores."""
    relationships = store.get_relationships(
        event_id=event_id,
        relationship_type=relationship_type,
        limit=limit,
    )

    for r in relationships:
        if isinstance(r.get("supporting_evidence"), str):
            try:
                r["supporting_evidence"] = json.loads(r["supporting_evidence"])
            except Exception:
                pass

    return {
        "count": len(relationships),
        "relationships": relationships,
    }


@router.get("/graph")
async def get_correlation_graph(
    incident_id: Optional[str] = Query(None, description="Optional incident ID to filter graph"),
    limit: int = Query(1000, ge=1, le=5000),
    store: EventStore = Depends(get_store),
) -> dict[str, Any]:
    """
    Get correlation graph nodes and edges structured for interactive visualization (D3 / force graph).
    """
    if incident_id:
        raw_inc = store.get_incident_by_id(incident_id)
        if raw_inc:
            event_ids = raw_inc.get("event_ids", [])
            if isinstance(event_ids, str):
                try:
                    event_ids = json.loads(event_ids)
                except Exception:
                    event_ids = []
            events = store.get_events(event_ids=event_ids, limit=1000)
            event_id_set = set(event_ids)
            all_rels = store.get_relationships(limit=limit)
            relationships = [
                r for r in all_rels
                if r.get("source_event_id") in event_id_set and r.get("target_event_id") in event_id_set
            ]
        else:
            events = []
            relationships = []
    else:
        events = store.get_events(limit=limit)
        relationships = store.get_relationships(limit=limit)

    # Format nodes
    nodes = []
    for e in events:
        nodes.append({
            "id": e["event_id"],
            "node": e.get("node"),
            "log_family": e.get("log_family"),
            "event_type": e.get("event_type"),
            "category": e.get("category"),
            "severity": e.get("severity"),
            "timestamp": e.get("timestamp").isoformat() if hasattr(e.get("timestamp"), "isoformat") else str(e.get("timestamp")),
            "component": e.get("component"),
            "entity": e.get("entity"),
            "message": e.get("message"),
            "source_file": e.get("source_file"),
            "source_line": e.get("source_line"),
        })

    # Format links
    links = []
    for r in relationships:
        links.append({
            "id": r["relationship_id"],
            "source": r["source_event_id"],
            "target": r["target_event_id"],
            "type": r["relationship_type"],
            "strength": r["strength"],
            "reason": r["reason"],
            "confidence": r.get("confidence", 1.0),
            "temporal_window_s": r.get("temporal_window_s"),
        })

    return {
        "nodes": nodes,
        "links": links,
        "node_count": len(nodes),
        "link_count": len(links),
    }
