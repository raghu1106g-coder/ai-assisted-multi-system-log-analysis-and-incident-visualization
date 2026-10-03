"""Base parser interface. All family-specific parsers inherit from this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..models.event import (
    EventCategory,
    IngestionError,
    LogFamily,
    NormalizedEvent,
    Severity,
    TimestampPrecision,
)


class ParseError(Exception):
    """Raised by a parser when a line is malformed and cannot be recovered."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class BaseLogParser(ABC):
    """Abstract base parser. One subclass per log family.

    Subclasses implement `parse_line`. The base class provides shared
    utilities: timestamp normalization, event_id generation, error capture.
    """

    family: LogFamily
    family_code: str  # OPR, PLN, GDN, STA, FLT

    # ---------------------------------------------------------------------------
    # Public interface
    # ---------------------------------------------------------------------------

    def parse_file(
        self,
        path: Path,
        node: str,
        relative_path: str,
    ) -> tuple[list[NormalizedEvent], list[IngestionError]]:
        """Parse all lines in a file. Returns (valid_events, errors)."""
        events: list[NormalizedEvent] = []
        errors: list[IngestionError] = []

        with open(path, encoding="utf-8", errors="replace") as fh:
            for line_no, raw_line in enumerate(fh, start=1):
                line = raw_line.rstrip("\n").rstrip("\r")
                if not line.strip():
                    errors.append(
                        IngestionError(
                            source_file=relative_path,
                            source_line=line_no,
                            reason="BLANK_RECORD",
                            raw_record=line,
                            log_family=self.family,
                            node=node,
                        )
                    )
                    continue  # skip blank lines

                skip = self._should_skip_line(line, line_no)
                if skip:
                    continue  # e.g. CSV header

                try:
                    event = self.parse_line(line, line_no, node, relative_path)
                    if event is not None:
                        events.append(event)
                except ParseError as exc:
                    errors.append(
                        IngestionError(
                            source_file=relative_path,
                            source_line=line_no,
                            reason=exc.reason,
                            raw_record=line,
                            log_family=self.family,
                            node=node,
                        )
                    )
                except Exception as exc:
                    errors.append(
                        IngestionError(
                            source_file=relative_path,
                            source_line=line_no,
                            reason=f"unexpected_error: {type(exc).__name__}: {exc}",
                            raw_record=line,
                            log_family=self.family,
                            node=node,
                        )
                    )

        return events, errors

    @abstractmethod
    def parse_line(
        self,
        line: str,
        line_no: int,
        node: str,
        source_file: str,
    ) -> Optional[NormalizedEvent]:
        """Parse one non-blank line. Raise ParseError if malformed."""

    def _should_skip_line(self, line: str, line_no: int) -> bool:  # noqa: ARG002
        """Override to skip header lines etc."""
        return False

    # ---------------------------------------------------------------------------
    # Shared utilities
    # ---------------------------------------------------------------------------

    def make_event_id(self, node: str, line_no: int) -> str:
        """EVT-<node_letter>-<family_code>-<4digit_line>"""
        letter = node.replace("NODE_", "")  # A, B, or C
        return f"EVT-{letter}-{self.family_code}-{line_no:04d}"

    @staticmethod
    def utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def normalize_severity(raw: str) -> Severity:
        return Severity.normalize(raw)

    @staticmethod
    def extract_incident_hint(attributes: dict) -> Optional[str]:
        """Find the first correlation key present in attributes dict.

        Priority: fault_code > msg_id > ack_for > cmd > sp > plan > wp > alert
        """
        priority = [
            ("code", lambda v: v.startswith("FLT-") or v.startswith("RCV-")),
            ("msg", lambda v: v.startswith("MSG-")),
            ("ack_for", lambda v: v.startswith("MSG-")),
            ("cmd", lambda v: v.startswith("CMD-")),
            ("sp", lambda v: v.startswith("SP-")),
            ("plan", lambda v: v.startswith("PLN-")),
            ("wp", lambda v: v.startswith("WP-")),
            ("alert", lambda v: v.startswith("FLT-")),
        ]
        for key, check in priority:
            val = attributes.get(key, "")
            if val and val != "-" and check(val):
                return val
        return None
