"""Incident, Relationship, and Evidence models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Relationship Model
# ---------------------------------------------------------------------------


class RelationshipType(str, Enum):
    SHARED_ID = "SHARED_ID"
    MESSAGE_FLOW = "MESSAGE_FLOW"
    EXPLICIT_REFERENCE = "EXPLICIT_REFERENCE"
    RECOVERY = "RECOVERY"
    SEQUENCE = "SEQUENCE"
    SHARED_COMPONENT = "SHARED_COMPONENT"
    TEMPORAL = "TEMPORAL"
    REPETITION = "REPETITION"
    MISSING_EVENT = "MISSING_EVENT"
    POSSIBLE_RELATIONSHIP = "POSSIBLE_RELATIONSHIP"


class RelationshipStrength(str, Enum):
    CONFIRMED = "CONFIRMED"       # Explicit shared identifier or direct reference
    STRONG = "STRONG"             # Message flow or sequence with multiple signals
    MODERATE = "MODERATE"         # Shared component + temporal
    WEAK = "WEAK"                 # Temporal proximity only
    INFERRED = "INFERRED"         # Possible, not confirmed


class EventRelationship(BaseModel):
    """A directional relationship between two events with full explanation."""

    relationship_id: str
    source_event_id: str
    target_event_id: str
    relationship_type: RelationshipType
    strength: RelationshipStrength
    reason: str = Field(..., description="Human-readable explanation of why this relationship exists")
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="List of shared identifiers, field names, or values that support this relationship",
    )
    temporal_window_seconds: Optional[float] = None
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="0.0-1.0 confidence score (1.0 = confirmed by explicit identifier)"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"use_enum_values": True}


# ---------------------------------------------------------------------------
# Evidence Model
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    """Source evidence linking a finding to a raw log record."""

    evidence_id: str
    event_id: str
    source_file: str
    source_line: int
    raw_record: str
    normalized_summary: str = Field(..., description="Human-readable decoded form of the raw record")
    relationship_to_finding: str = Field(
        ..., description="Why this record supports the finding it is attached to"
    )
    finding_type: str = ""  # e.g. "FAULT", "RECOVERY", "OPERATOR_ACTION"


# ---------------------------------------------------------------------------
# Incident Model
# ---------------------------------------------------------------------------


class UncertaintyLevel(str, Enum):
    CONFIRMED_OBSERVATION = "CONFIRMED_OBSERVATION"
    STRONGLY_SUPPORTED = "STRONGLY_SUPPORTED_RELATIONSHIP"
    POSSIBLE_RELATIONSHIP = "POSSIBLE_RELATIONSHIP"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    MISSING_DATA = "MISSING_DATA"


class MissingEventFinding(BaseModel):
    """Records an expected event that was not found."""

    description: str
    expected_at_node: Optional[str] = None
    expected_after_event_id: Optional[str] = None
    expected_event_type: Optional[str] = None
    related_incident_id: Optional[str] = None
    uncertainty: UncertaintyLevel = UncertaintyLevel.MISSING_DATA


class IncidentKind(str, Enum):
    INCIDENT = "INCIDENT"
    NON_INCIDENT_NORMAL_OPERATION = "NON_INCIDENT_NORMAL_OPERATION"
    CANDIDATE = "CANDIDATE"


class Incident(BaseModel):
    """A reconstructed incident grouping correlated events."""

    incident_id: str
    kind: IncidentKind = IncidentKind.CANDIDATE
    title: str = ""
    description: str = ""

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    involved_nodes: list[str] = Field(default_factory=list)
    involved_families: list[str] = Field(default_factory=list)

    primary_faults: list[str] = Field(
        default_factory=list, description="Primary fault codes (FLT-*)"
    )
    recovery_codes: list[str] = Field(
        default_factory=list, description="Recovery codes (RCV-*)"
    )

    event_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    recovery_status: str = "UNKNOWN"  # RECOVERED, ONGOING, PARTIAL, NOT_APPLICABLE

    missing_events: list[MissingEventFinding] = Field(default_factory=list)
    uncertainty_findings: list[dict[str, Any]] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"use_enum_values": True}

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
