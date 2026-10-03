"""Operator log parser.

Format: [ts=<ISO-8601-ms-Z>][node=<NODE_X>][sev=<LEVEL>] k=v ... msg="..."

Malformed cases handled:
- Missing [ts=...] bracket → ParseError("missing_timestamp")
- Truncated line / unterminated quote → ParseError("incomplete_key_value_pair")
"""

from __future__ import annotations

import re
import shlex
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


# [ts=2031-05-12T09:41:02.120Z][node=NODE_A][sev=INFO] k=v... msg="..."
_PREFIX_RE = re.compile(
    r'^\[ts=([^\]]+)\]\[node=(NODE_[A-Z]+)\]\[sev=(\w+)\]\s+(.*)',
)

# k=value or k="quoted value" tokens
_KV_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|[^\s"]+)')


# Map action → category
_ACTION_CATEGORY: dict[str, str] = {
    "SESSION_START": EventCategory.AUDIT,
    "SUBMIT_COMMAND": EventCategory.COMMAND,
    "STATUS_QUERY": EventCategory.AUDIT,
    "ACK_ALERT": EventCategory.COMMAND,
    "ADJUST_DISPLAY": EventCategory.AUDIT,
    "VIEW_CHANGE": EventCategory.AUDIT,
    "MAINT_NOTE": EventCategory.AUDIT,
}


class OperatorParser(BaseLogParser):
    family = LogFamily.operator
    family_code = "OPR"

    def parse_line(
        self,
        line: str,
        line_no: int,
        node: str,
        source_file: str,
    ) -> Optional[NormalizedEvent]:
        # Must start with [ts=...][node=...][sev=...]
        m = _PREFIX_RE.match(line)
        if not m:
            raise ParseError("missing_timestamp" if not line.startswith("[ts=") else "bad_prefix")

        ts_raw, node_raw, sev_raw, rest = m.group(1), m.group(2), m.group(3), m.group(4)

        # Parse timestamp
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            ts = self.utc(ts)
        except ValueError:
            raise ParseError(f"invalid_timestamp: {ts_raw!r}")

        # Parse k=v pairs from rest
        attrs: dict[str, str] = {}
        pos = 0
        rest_stripped = rest.strip()
        for kv in _KV_RE.finditer(rest_stripped):
            key = kv.group(1)
            val = kv.group(2)
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            attrs[key] = val
            pos = kv.end()

        # Check for leftover text that didn't parse (signals truncation)
        leftover = rest_stripped[pos:].strip()
        if leftover and not leftover.startswith('"'):
            # Some leftover is OK if it's the end of a quoted msg that shlex would catch
            # Try shlex as a fallback for unterminated quotes
            try:
                shlex.split(rest_stripped)
            except ValueError:
                raise ParseError("incomplete_key_value_pair_and_unterminated_quote")

        action = attrs.get("action", "")
        component = attrs.get("component")
        message = attrs.get("msg", "")

        # Validate: action field must be non-empty
        if not action:
            raise ParseError("missing_event_type: no action= field")

        # Validate: SUBMIT_COMMAND requires cmd_id
        if action == "SUBMIT_COMMAND" and not attrs.get("cmd_id"):
            raise ParseError("missing_required_identifier: SUBMIT_COMMAND without cmd_id")

        # Validate: reject malformed JSON payloads
        payload = attrs.get("payload", "")
        if payload:
            # Check for incomplete JSON (starts with { but doesn't end with })
            stripped = payload.strip()
            if stripped.startswith("{") and not stripped.endswith("}"):
                raise ParseError("malformed_structured_payload: incomplete JSON")
            if stripped.startswith("[") and not stripped.endswith("]"):
                raise ParseError("malformed_structured_payload: incomplete JSON array")

        # Build entity
        entity = attrs.get("cmd_id") or attrs.get("alert_id") or component

        # Incident hint
        hint = attrs.get("cmd_id") or attrs.get("alert_id")

        return NormalizedEvent(
            event_id=self.make_event_id(node_raw, line_no),
            node=node_raw,
            log_family=self.family,
            event_type=action,
            category=_ACTION_CATEGORY.get(action, EventCategory.AUDIT),
            severity=self.normalize_severity(sev_raw),
            timestamp=ts,
            timestamp_precision=TimestampPrecision.millisecond,
            component=component,
            entity=entity,
            message=message,
            incident_hint=hint,
            attributes={k: v for k, v in attrs.items() if k not in ("action", "component", "msg")},
            source_file=source_file,
            source_line=line_no,
            raw_record=line,
        )
