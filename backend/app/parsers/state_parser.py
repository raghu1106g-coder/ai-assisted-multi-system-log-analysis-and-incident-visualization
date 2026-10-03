"""State log parser.

Format: <YYYYMMDDTHHMMSS.mmmZ>;<NODE>;<EVENT_TYPE>;<COMPONENT>;<FROM>;<TO>;<TRIGGER>;<SEQ>;<DETAIL>
9 semicolon-separated positional fields.

Timestamp format: compact ISO UTC e.g. 20310512T094102.480Z

Malformed cases:
- Fewer than 9 fields → ParseError("incomplete_fields")
- Wrong separator (comma instead of semicolon) → detected by field count check
- Unparseable timestamp → ParseError("invalid_timestamp")

Note: seq field is a monotonic per-node counter used for gap/out-of-order detection.
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

_TS_FMT = "%Y%m%dT%H%M%S.%fZ"
_TS_FMT_NOMS = "%Y%m%dT%H%M%SZ"

_EVENT_CATEGORY: dict[str, EventCategory] = {
    "CONDITION_SAMPLE": EventCategory.CONDITION,
    "PHASE_CHANGE": EventCategory.PHASE,
    "STATE_CHANGE": EventCategory.STATE_CHANGE,
    "PEER_STATE": EventCategory.STATE_CHANGE,
}


def _derive_severity(event_type: str, to_state: str) -> Severity:
    """Derive severity from state transition target."""
    if event_type == "PEER_STATE":
        if to_state in ("DEGRADED", "TIMEOUT", "FAILED"):
            return Severity.WARN
        if to_state == "NOMINAL":
            return Severity.INFO
    if event_type == "STATE_CHANGE":
        if to_state in ("DEGRADED", "TIMEOUT", "RETRY", "RECOVERING"):
            return Severity.WARN
        if to_state in ("FAILED",):
            return Severity.ERROR
    return Severity.INFO


# Regex to parse key=value pairs from CONDITION_SAMPLE detail
_COND_KV = re.compile(r'(\w+)=(\S+)')


class StateParser(BaseLogParser):
    family = LogFamily.state
    family_code = "STA"

    def parse_line(
        self,
        line: str,
        line_no: int,
        node: str,
        source_file: str,
    ) -> Optional[NormalizedEvent]:
        # First check for wrong delimiter — a line with commas where semicolons expected
        # If it splits by semicolon to < 9 but has 9 commas, it's wrong separator
        parts = line.split(";")
        if len(parts) < 9:
            # Maybe comma-delimited
            comma_parts = line.split(",")
            if len(comma_parts) >= 9:
                raise ParseError("invalid_separator")
            # Genuinely incomplete
            raise ParseError(f"incomplete_fields: got {len(parts)}, expected 9")
        if len(parts) > 9:
            raise ParseError(f"extra_unexpected_field: got {len(parts)}, expected 9")

        ts_raw = parts[0].strip()
        node_raw = parts[1].strip() or node
        event_type = parts[2].strip()
        component = parts[3].strip()
        from_state = parts[4].strip()
        to_state = parts[5].strip()
        trigger = parts[6].strip()
        seq_raw = parts[7].strip()
        detail = parts[8].strip()

        # Parse timestamp
        ts: datetime
        try:
            ts = datetime.strptime(ts_raw, _TS_FMT).replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                ts = datetime.strptime(ts_raw, _TS_FMT_NOMS).replace(tzinfo=timezone.utc)
            except ValueError:
                raise ParseError(f"invalid_timestamp: {ts_raw!r}")

        # Sequence number
        seq: Optional[int] = None
        if seq_raw and seq_raw != "-":
            try:
                seq = int(seq_raw)
            except ValueError:
                pass  # non-fatal

        severity = _derive_severity(event_type, to_state)

        # Build attributes
        attrs: dict = {}
        if from_state and from_state != "-":
            attrs["frm"] = from_state
        if to_state and to_state != "-":
            attrs["to"] = to_state
        if trigger and trigger != "-":
            attrs["trigger"] = trigger
        if seq is not None:
            attrs["seq"] = str(seq)

        # For CONDITION_SAMPLE, also parse the detail key=values
        if event_type == "CONDITION_SAMPLE":
            for m in _COND_KV.finditer(detail):
                attrs[m.group(1)] = m.group(2)

        # Entity: trigger id or component
        entity = (trigger if trigger and trigger != "-" else None) or component

        # Incident hint
        hint = self.extract_incident_hint(attrs)

        return NormalizedEvent(
            event_id=self.make_event_id(node_raw, line_no),
            node=node_raw,
            log_family=self.family,
            event_type=event_type,
            category=_EVENT_CATEGORY.get(event_type, EventCategory.STATE_CHANGE),
            severity=severity,
            timestamp=ts,
            timestamp_precision=TimestampPrecision.millisecond,
            component=component,
            entity=entity,
            message=detail or None,
            incident_hint=hint,
            attributes=attrs,
            source_file=source_file,
            source_line=line_no,
            raw_record=line,
        )
