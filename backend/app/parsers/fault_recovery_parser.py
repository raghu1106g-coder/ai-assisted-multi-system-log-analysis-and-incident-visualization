"""Fault/Recovery log parser.

Format: <ISO-8601-s-Z>|<NODE>|<EVENT_TYPE>|<CODE>|<NAME>|<COMPONENT>|<SEVERITY>|<RELATED>|<DURATION>|<DETAIL>
10 pipe-separated positional fields.

Timestamp format: second-resolution ISO-8601 UTC e.g. 2031-05-12T09:41:09Z
(precision=second — same-second events cannot be time-ordered within this family)

Malformed cases:
- Wrong separator (semicolons instead of pipes) → ParseError("invalid_separator")
- Fewer than 10 fields → ParseError("incomplete_fields")
- Event type with non-ASCII bytes (corrupted) → ParseError("corrupted_event_name")
- Unparseable timestamp → ParseError("invalid_timestamp")
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

_TS_FMT_S = "%Y-%m-%dT%H:%M:%SZ"
_TS_FMT_MS = "%Y-%m-%dT%H:%M:%S.%fZ"

# Event type must match ASCII word characters only
_VALID_EVENT_RE = re.compile(r'^[A-Z_]+$')

_EVENT_CATEGORY: dict[str, EventCategory] = {
    "SELFTEST_PASS": EventCategory.SYSTEM,
    "TRANSIENT_WARN": EventCategory.ANOMALY,
    "FAULT_RAISED": EventCategory.FAULT,
    "FAULT_NOTICE_SENT": EventCategory.FAULT,
    "PEER_FAULT_NOTICE": EventCategory.FAULT,
    "RECOVERY_STARTED": EventCategory.RECOVERY,
    "FAULT_CLEARED": EventCategory.RECOVERY,
}


class FaultRecoveryParser(BaseLogParser):
    family = LogFamily.fault_recovery
    family_code = "FLT"

    def parse_line(
        self,
        line: str,
        line_no: int,
        node: str,
        source_file: str,
    ) -> Optional[NormalizedEvent]:
        # Check for wrong separator
        parts = line.split("|")
        if len(parts) < 10:
            # Maybe semicolon-delimited
            semi_parts = line.split(";")
            if len(semi_parts) >= 10:
                raise ParseError("invalid_separator")
            raise ParseError(f"incomplete_fields: got {len(parts)}, expected 10")

        ts_raw = parts[0].strip()
        node_raw = parts[1].strip()
        if not node_raw:
            raise ParseError("missing_node: empty node field")
        event_type = parts[2].strip()
        code = parts[3].strip()
        name = parts[4].strip()
        component = parts[5].strip()
        sev_raw = parts[6].strip()
        related = parts[7].strip()
        duration_raw = parts[8].strip()
        detail = parts[9].strip()

        # Validate event_type: must be ASCII word characters (no corrupted bytes)
        try:
            event_type_ascii = event_type.encode("ascii").decode("ascii")
            if not _VALID_EVENT_RE.match(event_type_ascii):
                raise ParseError(f"corrupted_event_name: {event_type!r}")
        except UnicodeEncodeError:
            raise ParseError(f"corrupted_event_name: {event_type!r}")

        # Parse timestamp (second resolution)
        ts: datetime
        try:
            ts = datetime.strptime(ts_raw, _TS_FMT_S).replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                ts = datetime.strptime(ts_raw, _TS_FMT_MS).replace(tzinfo=timezone.utc)
            except ValueError:
                raise ParseError(f"invalid_timestamp: {ts_raw!r}")

        # Duration
        duration: Optional[int] = None
        if duration_raw and duration_raw != "-":
            try:
                duration = int(duration_raw)
            except ValueError:
                pass

        # Attributes
        attrs: dict = {
            "code": code,
            "name": name,
        }
        if related and related != "-":
            attrs["related"] = related
        if duration is not None:
            attrs["duration_s"] = str(duration)

        # Entity: code is primary (FLT/RCV/ST code)
        entity = code

        hint = self.extract_incident_hint(attrs)

        return NormalizedEvent(
            event_id=self.make_event_id(node_raw, line_no),
            node=node_raw,
            log_family=self.family,
            event_type=event_type,
            category=_EVENT_CATEGORY.get(event_type, EventCategory.SYSTEM),
            severity=self.normalize_severity(sev_raw),
            timestamp=ts,
            timestamp_precision=TimestampPrecision.second,
            component=component,
            entity=entity,
            message=detail or None,
            incident_hint=hint,
            attributes=attrs,
            source_file=source_file,
            source_line=line_no,
            raw_record=line,
        )
