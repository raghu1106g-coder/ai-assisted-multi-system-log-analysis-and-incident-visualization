"""Planning log parser.

Format: CSV with 12 columns, header on line 1.
Columns: ts,node,event,plan_id,msg_id,peer,cmd_ref,ack_for,resend_of,component,status,detail

Timestamp: "YYYY-MM-DD HH:MM:SS.mmm" — no timezone suffix, treated as UTC.

Malformed cases:
- Fewer than 12 columns → ParseError("incomplete_fields")
- Empty or unparseable timestamp → ParseError("missing_timestamp")
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Optional

from ..models.event import (
    EventCategory,
    LogFamily,
    NormalizedEvent,
    Severity,
    TimestampPrecision,
)
from .base import BaseLogParser, ParseError

# Header that appears on line 1 of every planning log
_PLANNING_HEADER = "ts,node,event,plan_id,msg_id,peer,cmd_ref,ack_for,resend_of,component,status,detail"

_EVENT_CATEGORY: dict[str, EventCategory] = {
    "MESSAGE_SENT": EventCategory.MESSAGE,
    "MESSAGE_RECEIVED": EventCategory.MESSAGE,
    "MESSAGE_ACK": EventCategory.MESSAGE,
    "EXCHANGE_COMPLETE": EventCategory.MESSAGE,
    "PLAN_REQUEST": EventCategory.COMMAND,
    "PLAN_COMPUTED": EventCategory.SYSTEM,
    "PLAN_REFRESH": EventCategory.SYSTEM,
}


def _derive_severity(event: str, status: str) -> Severity:
    """Planning logs have no explicit severity field; derive from status."""
    if status.upper() in ("FAILED", "TIMEOUT", "ERROR"):
        return Severity.ERROR
    if status.upper() in ("WARN",):
        return Severity.WARN
    return Severity.INFO


class PlanningParser(BaseLogParser):
    family = LogFamily.planning
    family_code = "PLN"

    def _should_skip_line(self, line: str, line_no: int) -> bool:
        # Skip the CSV header row
        stripped = line.strip()
        return stripped == _PLANNING_HEADER or (
            line_no == 1 and stripped.startswith("ts,")
        )

    def parse_line(
        self,
        line: str,
        line_no: int,
        node: str,
        source_file: str,
    ) -> Optional[NormalizedEvent]:
        # Use csv.reader to handle quoted fields properly
        try:
            rows = list(csv.reader(io.StringIO(line)))
            if not rows:
                raise ParseError("empty_line")
            fields = rows[0]
        except Exception as exc:
            raise ParseError(f"csv_parse_error: {exc}") from exc

        if len(fields) < 12:
            raise ParseError(f"incomplete_fields: got {len(fields)}, expected 12")
        if len(fields) > 12:
            raise ParseError(f"extra_unexpected_field: got {len(fields)}, expected 12")

        ts_raw = fields[0].strip()
        node_raw = fields[1].strip() or node
        event = fields[2].strip()
        plan_id = fields[3].strip()
        msg_id = fields[4].strip()
        peer = fields[5].strip()
        cmd_ref = fields[6].strip()
        ack_for = fields[7].strip()
        resend_of = fields[8].strip()
        component = fields[9].strip()
        status = fields[10].strip()
        detail = fields[11].strip()

        # Parse timestamp
        if not ts_raw:
            raise ParseError("missing_timestamp")
        try:
            ts = datetime.strptime(ts_raw, "%Y-%m-%d %H:%M:%S.%f").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            try:
                ts = datetime.strptime(ts_raw, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                raise ParseError(f"invalid_timestamp: {ts_raw!r}")

        # Validate: event field must be non-empty
        if not event:
            raise ParseError("missing_event_type: empty event field")

        # Validate: MESSAGE_SENT requires msg_id
        if event == "MESSAGE_SENT" and not msg_id:
            raise ParseError("missing_required_identifier: MESSAGE_SENT without msg_id")

        # Entity priority: msg_id > ack_for > cmd_ref > plan_id
        entity = msg_id or ack_for or cmd_ref or plan_id or None
        for e in [entity]:
            if e and e.startswith("-"):
                entity = None

        # Incident hint
        attrs: dict[str, str] = {}
        for k, v in [
            ("msg", msg_id), ("ack_for", ack_for), ("cmd", cmd_ref),
            ("resend_of", resend_of), ("plan", plan_id), ("peer", peer), ("status", status),
        ]:
            if v and v != "-":
                attrs[k] = v

        hint = self.extract_incident_hint(attrs)

        return NormalizedEvent(
            event_id=self.make_event_id(node_raw, line_no),
            node=node_raw,
            log_family=self.family,
            event_type=event,
            category=_EVENT_CATEGORY.get(event, EventCategory.SYSTEM),
            severity=_derive_severity(event, status),
            timestamp=ts,
            timestamp_precision=TimestampPrecision.millisecond,
            component=component or None,
            entity=entity,
            message=detail or None,
            incident_hint=hint,
            attributes=attrs,
            source_file=source_file,
            source_line=line_no,
            raw_record=line,
        )
