"""Common Event Model — canonical representation of a parsed log record.

Every parsed record from any log family is normalized to this model before
being stored or analyzed. Source traceability is mandatory.

Version: 1 (increment when the schema changes incompatibly).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class NodeId(str, Enum):
    NODE_A = "NODE_A"
    NODE_B = "NODE_B"
    NODE_C = "NODE_C"


class LogFamily(str, Enum):
    operator = "operator"
    planning = "planning"
    guidance = "guidance"
    state = "state"
    fault_recovery = "fault_recovery"
    # Adapter slot: add new families here without breaking existing code
    unknown = "unknown"


class Severity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    WARNING = "WARNING"  # alias
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def normalize(cls, raw: str) -> "Severity":
        """Case-insensitive lookup with fallback."""
        upper = raw.strip().upper()
        mapping = {
            "DEBUG": cls.DEBUG,
            "INFO": cls.INFO,
            "WARN": cls.WARN,
            "WARNING": cls.WARN,
            "ERROR": cls.ERROR,
            "ERR": cls.ERROR,
            "CRITICAL": cls.CRITICAL,
            "CRIT": cls.CRITICAL,
        }
        return mapping.get(upper, cls.UNKNOWN)


class EventCategory(str, Enum):
    COMMAND = "COMMAND"
    MESSAGE = "MESSAGE"
    STATE_CHANGE = "STATE_CHANGE"
    PHASE = "PHASE"
    GUIDANCE = "GUIDANCE"
    ANOMALY = "ANOMALY"
    FAULT = "FAULT"
    RECOVERY = "RECOVERY"
    SYSTEM = "SYSTEM"
    CONDITION = "CONDITION"
    AUDIT = "AUDIT"
    UNKNOWN = "UNKNOWN"


class TimestampPrecision(str, Enum):
    millisecond = "ms"
    second = "s"
    unknown = "unknown"


# ---------------------------------------------------------------------------
# Core Event Model
# ---------------------------------------------------------------------------


class NormalizedEvent(BaseModel):
    """Canonical representation of one parsed log record.

    All timestamps are UTC. source_file and source_line provide
    exact traceability back to the raw log.
    """

    # --- Identity ---
    event_id: str = Field(
        ...,
        description="Unique: EVT-<node_letter>-<family_code>-<4digit_line>",
        examples=["EVT-B-FLT-0009"],
    )
    schema_version: int = Field(default=1, description="Event model schema version")

    # --- Classification ---
    node: str = Field(..., description="Source node identifier, e.g. NODE_A")
    log_family: LogFamily
    event_type: str = Field(..., description="Raw event type token from the log")
    category: EventCategory = EventCategory.UNKNOWN
    severity: Severity = Severity.UNKNOWN

    # --- Timing ---
    timestamp: datetime = Field(..., description="Normalized UTC timestamp")
    timestamp_precision: TimestampPrecision = TimestampPrecision.millisecond

    # --- Domain ---
    component: Optional[str] = None
    entity: Optional[str] = Field(
        None,
        description="Primary domain identifier in this record (fault code, msg id, cmd id, etc.)",
    )
    message: Optional[str] = None

    # --- Correlation hints (derived from raw record, not ground truth) ---
    incident_hint: Optional[str] = Field(
        None,
        description=(
            "First correlation key found in this record "
            "(CMD/MSG/FLT/RCV/SP/PLN id). Derived from raw record only."
        ),
    )

    # --- Attributes: family-specific parsed fields ---
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Family-specific fields that don't fit the canonical schema",
    )

    # --- Source traceability (MANDATORY) ---
    source_file: str = Field(..., description="Relative path to source log file")
    source_line: int = Field(..., description="1-based line number in source file")
    raw_record: str = Field(..., description="Exact raw line as read from file")

    model_config = {"use_enum_values": True}

    @model_validator(mode="after")
    def _ensure_utc(self) -> "NormalizedEvent":
        from datetime import timezone

        if self.timestamp.tzinfo is None:
            object.__setattr__(
                self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc)
            )
        return self

    def timestamp_iso(self) -> str:
        """Return ISO-8601 string with ms precision."""
        return self.timestamp.strftime("%Y-%m-%dT%H:%M:%S.") + f"{self.timestamp.microsecond // 1000:03d}Z"


# ---------------------------------------------------------------------------
# Ingestion Error Model
# ---------------------------------------------------------------------------


class IngestionError(BaseModel):
    """A record that could not be parsed — kept for reporting, never silently dropped."""

    source_file: str
    source_line: int
    reason: str
    raw_record: str
    log_family: Optional[LogFamily] = None
    node: Optional[str] = None


# ---------------------------------------------------------------------------
# Ingestion Result Model
# ---------------------------------------------------------------------------


class IngestionResult(BaseModel):
    """Summary produced by one complete ingestion run."""

    run_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    data_root: str

    files_discovered: list[str] = Field(default_factory=list)
    files_processed: int = 0
    files_errored: int = 0

    total_lines_read: int = 0
    valid_records: int = 0
    skipped_records: int = 0

    errors: list[IngestionError] = Field(default_factory=list)
    processing_duration_seconds: Optional[float] = None

    # Per-file breakdown
    file_stats: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def success_rate(self) -> float:
        total = self.valid_records + self.skipped_records
        if total == 0:
            return 1.0
        return self.valid_records / total
