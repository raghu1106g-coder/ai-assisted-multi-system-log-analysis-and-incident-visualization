"""Events API endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...core.dependencies import get_store
from ...storage.event_store import EventStore

router = APIRouter()


class EventFilterParams:
    def __init__(
        self,
        node: Optional[str] = Query(None, description="Filter by node (e.g. NODE_A, NODE_B, NODE_C)"),
        log_family: Optional[str] = Query(None, description="Filter by log family (operator, planning, guidance, state, fault_recovery)"),
        event_type: Optional[str] = Query(None, description="Filter by event type"),
        category: Optional[str] = Query(None, description="Filter by category (FAULT, RECOVERY, COMMAND, STATE_CHANGE, etc.)"),
        severity: Optional[str] = Query(None, description="Filter by severity level"),
        incident_hint: Optional[str] = Query(None, description="Filter by incident hint (e.g. INC-001)"),
        ts_from: Optional[datetime] = Query(None, description="Filter events on or after timestamp (ISO 8601)"),
        ts_to: Optional[datetime] = Query(None, description="Filter events on or before timestamp (ISO 8601)"),
        search: Optional[str] = Query(None, description="Free text search on message, component, entity, raw record"),
        limit: int = Query(500, ge=1, le=5000, description="Max records to return"),
        offset: int = Query(0, ge=0, description="Offset for pagination"),
    ):
        self.node = node
        self.log_family = log_family
        self.event_type = event_type
        self.category = category
        self.severity = severity
        self.incident_hint = incident_hint
        self.ts_from = ts_from
        self.ts_to = ts_to
        self.search = search
        self.limit = limit
        self.offset = offset


@router.get("")
async def list_events(
    params: EventFilterParams = Depends(),
    store: EventStore = Depends(get_store),
) -> dict[str, Any]:
    """List normalized events with flexible filtering."""
    events = store.get_events(
        node=params.node,
        log_family=params.log_family,
        event_type=params.event_type,
        category=params.category,
        incident_hint=params.incident_hint,
        ts_from=params.ts_from,
        ts_to=params.ts_to,
        limit=params.limit,
        offset=params.offset,
    )

    # Optional client-side search filtering if search term is provided
    if params.search:
        q = params.search.lower()
        events = [
            e for e in events
            if (e.get("message") and q in str(e["message"]).lower())
            or (e.get("component") and q in str(e["component"]).lower())
            or (e.get("entity") and q in str(e["entity"]).lower())
            or (e.get("raw_record") and q in str(e["raw_record"]).lower())
            or (e.get("event_type") and q in str(e["event_type"]).lower())
        ]

    # Parse JSON attributes if stringified
    for e in events:
        if isinstance(e.get("attributes"), str):
            try:
                e["attributes"] = json.loads(e["attributes"])
            except Exception:
                pass

    return {
        "count": len(events),
        "limit": params.limit,
        "offset": params.offset,
        "events": events,
    }


@router.get("/errors")
async def list_ingestion_errors(
    run_id: Optional[str] = Query(None, description="Optional ingestion run ID"),
    limit: int = Query(500, ge=1, le=1000),
    store: EventStore = Depends(get_store),
) -> dict[str, Any]:
    """List ingestion/malformed record errors with source traceability."""
    errors = store.get_ingestion_errors(run_id=run_id, limit=limit)
    return {
        "count": len(errors),
        "errors": errors,
    }


@router.get("/{event_id}")
async def get_event_detail(
    event_id: str,
    store: EventStore = Depends(get_store),
) -> dict[str, Any]:
    """Get single normalized event by ID with evidence links and relationships."""
    event = store.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    if isinstance(event.get("attributes"), str):
        try:
            event["attributes"] = json.loads(event["attributes"])
        except Exception:
            pass

    evidence = store.get_evidence_for_event(event_id)
    relationships = store.get_relationships(event_id=event_id)

    return {
        "event": event,
        "evidence": evidence,
        "relationships": relationships,
    }
