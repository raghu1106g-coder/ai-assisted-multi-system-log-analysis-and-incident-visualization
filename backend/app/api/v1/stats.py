"""Dataset and Ingestion statistics API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...core.dependencies import get_store
from ...storage.event_store import EventStore

router = APIRouter()


@router.get("")
async def get_system_statistics(
    store: EventStore = Depends(get_store),
) -> dict[str, Any]:
    """Get system-wide statistical aggregates and distribution metrics."""
    stats = store.get_statistics()
    incidents = store.get_incidents()
    relationships = store.get_relationships(limit=10000)

    incident_kinds = {}
    for inc in incidents:
        kind = inc.get("kind", "UNKNOWN")
        incident_kinds[kind] = incident_kinds.get(kind, 0) + 1

    return {
        "events": stats,
        "incidents": {
            "total": len(incidents),
            "by_kind": incident_kinds,
        },
        "relationships": {
            "total": len(relationships),
        },
    }
