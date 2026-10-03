"""Incidents API endpoints."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...ai.narrative import AIIncidentNarrative, generate_narrative
from ...core.dependencies import get_store
from ...storage.event_store import EventStore

router = APIRouter()


def _deserialize_incident(inc: dict[str, Any]) -> dict[str, Any]:
    """Helper to deserialize JSON fields in incident record from DB."""
    json_fields = [
        "involved_nodes",
        "involved_families",
        "primary_faults",
        "recovery_codes",
        "event_ids",
        "relationship_ids",
        "evidence_ids",
        "missing_events",
        "uncertainty_findings",
    ]
    for f in json_fields:
        if isinstance(inc.get(f), str):
            try:
                inc[f] = json.loads(inc[f])
            except Exception:
                pass
    return inc


@router.get("")
async def list_incidents(
    store: EventStore = Depends(get_store),
) -> dict[str, Any]:
    """List all reconstructed incidents and non-incident operational clusters."""
    raw_incidents = store.get_incidents()
    incidents = [_deserialize_incident(inc) for inc in raw_incidents]
    return {
        "count": len(incidents),
        "incidents": incidents,
    }


@router.get("/{incident_id}")
async def get_incident_detail(
    incident_id: str,
    store: EventStore = Depends(get_store),
) -> dict[str, Any]:
    """Get full details of a specific incident, including associated timeline events and relationships."""
    raw_inc = store.get_incident_by_id(incident_id)
    if not raw_inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    incident = _deserialize_incident(raw_inc)

    # Fetch associated events
    event_ids = incident.get("event_ids", [])
    events = []
    if event_ids:
        events = store.get_events(event_ids=event_ids, limit=1000)
        for e in events:
            if isinstance(e.get("attributes"), str):
                try:
                    e["attributes"] = json.loads(e["attributes"])
                except Exception:
                    pass

    # Fetch incident relationships
    all_rels = store.get_relationships(limit=2000)
    event_id_set = set(event_ids)
    incident_rels = [
        r for r in all_rels
        if r.get("source_event_id") in event_id_set and r.get("target_event_id") in event_id_set
    ]

    return {
        "incident": incident,
        "events": events,
        "relationships": incident_rels,
        "event_count": len(events),
        "relationship_count": len(incident_rels),
    }


class NarrativeRequest(BaseModel):
    max_events: Optional[int] = 50


@router.post("/{incident_id}/narrative")
async def generate_incident_narrative(
    incident_id: str,
    req: NarrativeRequest = NarrativeRequest(),
    store: EventStore = Depends(get_store),
) -> dict[str, Any]:
    """Generate structured AI narrative with source citations and strict validation."""
    raw_inc = store.get_incident_by_id(incident_id)
    if not raw_inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    incident = _deserialize_incident(raw_inc)
    event_ids = incident.get("event_ids", [])
    events = store.get_events(event_ids=event_ids, limit=1000) if event_ids else []

    event_id_set = set(event_ids)
    all_rels = store.get_relationships(limit=2000)
    incident_rels = [
        r for r in all_rels
        if r.get("source_event_id") in event_id_set and r.get("target_event_id") in event_id_set
    ]

    missing_events = incident.get("missing_events", [])

    narrative: AIIncidentNarrative = await generate_narrative(
        incident=incident,
        events=events,
        relationships=incident_rels,
        missing_events=missing_events,
    )

    return {
        "incident_id": incident_id,
        "narrative": narrative.model_dump(),
    }
