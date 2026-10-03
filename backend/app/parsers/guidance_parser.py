"""Guidance log parser.

Format: <epoch_seconds.ms> <NODE_X> GDN evt=<TYPE> sev=<LEVEL> comp=<COMP> [key=value ...]

Timestamp: Unix epoch float seconds → converted to UTC datetime.
Reference epoch confirmed from normalized_event_examples.json:
  1936342990.034 → 2031-05-12T09:03:10.034Z

Malformed cases:
- Non-numeric/corrupted timestamp token → ParseError("corrupted_timestamp_token")
- Missing 'GDN' token → ParseError("bad_prefix")
- Truncated record (no evt= token) → ParseError("truncated_record")
"""

from __future__ import annotations

import re
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

# k=value token (value may contain dots/dashes but no spaces)
_KV_RE = re.compile(r'(\w+)=([^\s]+)')

_EVENT_CATEGORY: dict[str, EventCategory] = {
    "WAYPOINT_REACHED": EventCategory.GUIDANCE,
    "GUIDANCE_STATUS": EventCategory.SYSTEM,
    "SETPOINT_SENT": EventCategory.COMMAND,
    "SETPOINT_RECEIVED": EventCategory.COMMAND,
    "SETPOINT_ACK": EventCategory.COMMAND,
    "SETPOINT_APPLIED": EventCategory.COMMAND,
    "SETPOINT_COMPLETE": EventCategory.COMMAND,
    "SETPOINT_REJECTED": EventCategory.ANOMALY,
    "GUIDANCE_DEVIATION": EventCategory.ANOMALY,
    "PROFILE_APPLY": EventCategory.GUIDANCE,
    "FILTER_REINIT": EventCategory.RECOVERY,
    "GUIDANCE_NOMINAL": EventCategory.GUIDANCE,
    "PLAN_HOLD": EventCategory.ANOMALY,
    "PLAN_RESUME": EventCategory.GUIDANCE,
}


class GuidanceParser(BaseLogParser):
    family = LogFamily.guidance
    family_code = "GDN"

    def parse_line(
        self,
        line: str,
        line_no: int,
        node: str,
        source_file: str,
    ) -> Optional[NormalizedEvent]:
        tokens = line.split()
        if len(tokens) < 3:
            raise ParseError("truncated_record")

        # Token 0: epoch timestamp
        epoch_str = tokens[0]
        try:
            epoch_float = float(epoch_str)
        except ValueError:
            raise ParseError(f"corrupted_timestamp_token: {epoch_str!r}")

        # Token 1: node
        node_raw = tokens[1]

        # Token 2: must be 'GDN'
        if tokens[2] != "GDN":
            raise ParseError(f"bad_prefix: expected GDN, got {tokens[2]!r}")

        # Convert epoch to UTC datetime
        ts = datetime.utcfromtimestamp(epoch_float).replace(tzinfo=timezone.utc)

        # Parse k=v tokens from position 3 onward
        rest = " ".join(tokens[3:])
        attrs: dict[str, str] = {}
        for m in _KV_RE.finditer(rest):
            attrs[m.group(1)] = m.group(2)

        # Detect stray tokens: text fragments that are not valid k=v pairs
        # Remove all matched k=v pairs from rest and check what's left
        remaining = _KV_RE.sub("", rest).strip()
        if remaining:
            # Non-whitespace remnants after removing all k=v pairs → stray tokens
            raise ParseError(f"stray_token: unexpected text '{remaining}'")

        for need in ("evt", "sev", "comp", "note"):
            if need not in attrs:
                raise ParseError(f"missing_field_{need}")

        evt = attrs["evt"]
        if not re.match(r"^[A-Z_]+$", evt):
            raise ParseError("bad_event")

        sev = attrs["sev"]
        comp = attrs["comp"]

        # Build entity: cmd > sp > plan > wp > ack_for > comp
        entity = (
            attrs.get("cmd")
            or attrs.get("sp")
            or attrs.get("plan")
            or attrs.get("wp")
            or attrs.get("ack_for")
            or comp
        )

        hint = self.extract_incident_hint(attrs)

        # Build note/message from 'note' field
        message = attrs.get("note", "").replace("_", " ") if attrs.get("note") else None

        return NormalizedEvent(
            event_id=self.make_event_id(node_raw, line_no),
            node=node_raw,
            log_family=self.family,
            event_type=evt,
            category=_EVENT_CATEGORY.get(evt, EventCategory.GUIDANCE),
            severity=self.normalize_severity(sev),
            timestamp=ts,
            timestamp_precision=TimestampPrecision.millisecond,
            component=comp,
            entity=entity,
            message=message,
            incident_hint=hint,
            attributes={k: v for k, v in attrs.items() if k not in ("evt", "sev", "comp", "note")},
            source_file=source_file,
            source_line=line_no,
            raw_record=line,
        )
