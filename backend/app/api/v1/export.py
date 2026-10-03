"""Export API endpoints for exporting events and incidents as CSV or JSON."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from ...core.dependencies import get_store
from ...storage.event_store import EventStore

router = APIRouter()


@router.get("/events")
async def export_events(
    format: str = Query("json", pattern="^(json|csv)$"),
    node: str | None = None,
    log_family: str | None = None,
    store: EventStore = Depends(get_store),
) -> Response:
    """Export normalized events as JSON or CSV."""
    events = store.get_events(node=node, log_family=log_family, limit=50000)

    if format == "json":
        # Format datetimes
        formatted = []
        for e in events:
            item = dict(e)
            if hasattr(item.get("timestamp"), "isoformat"):
                item["timestamp"] = item["timestamp"].isoformat()
            formatted.append(item)

        content = json.dumps(formatted, indent=2, default=str)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=ps3_events_export.json"},
        )
    else:
        # CSV Export
        if not events:
            return Response(content="", media_type="text/csv")

        output = io.StringIO()
        fieldnames = [
            "event_id", "timestamp", "node", "log_family", "event_type",
            "category", "severity", "component", "entity", "message",
            "incident_hint", "source_file", "source_line", "raw_record"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for e in events:
            row = dict(e)
            if hasattr(row.get("timestamp"), "isoformat"):
                row["timestamp"] = row["timestamp"].isoformat()
            writer.writerow(row)

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=ps3_events_export.csv"},
        )


@router.get("/incidents")
async def export_incidents(
    format: str = Query("json", pattern="^(json|csv)$"),
    store: EventStore = Depends(get_store),
) -> Response:
    """Export reconstructed incidents as JSON or CSV."""
    incidents = store.get_incidents()

    if format == "json":
        content = json.dumps(incidents, indent=2, default=str)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=ps3_incidents_export.json"},
        )
    else:
        if not incidents:
            return Response(content="", media_type="text/csv")

        output = io.StringIO()
        fieldnames = [
            "incident_id", "kind", "title", "description", "start_time",
            "end_time", "involved_nodes", "involved_families", "primary_faults",
            "recovery_codes", "recovery_status"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for inc in incidents:
            row = dict(inc)
            for k in ["start_time", "end_time"]:
                if hasattr(row.get(k), "isoformat"):
                    row[k] = row[k].isoformat()
            writer.writerow(row)

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=ps3_incidents_export.csv"},
        )
