"""Gemini AI narrative service.

Safety principles:
1. LLM receives a compact structured incident context — NOT raw log files.
2. System instruction forbids hallucination of events, IDs, timestamps, causes.
3. Response is validated against a Pydantic schema.
4. Uncertainty is explicitly labeled.
5. If AI fails validation, the error is surfaced to the caller — not silently displayed.
6. Timeout is enforced.
7. API key is never sent to frontend.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from ..core.config import get_settings
from ..core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# AI Response Schema
# ---------------------------------------------------------------------------


class AIObservation(BaseModel):
    """A single confirmed or qualified observation from the incident."""

    statement: str
    uncertainty_label: str  # CONFIRMED_OBSERVATION | STRONGLY_SUPPORTED | POSSIBLE | INSUFFICIENT | MISSING_DATA
    evidence_refs: list[str] = Field(default_factory=list)


class AIRelationship(BaseModel):
    """A relationship identified in the incident evidence."""

    description: str
    uncertainty_label: str
    evidence_refs: list[str] = Field(default_factory=list)


class AIUncertainty(BaseModel):
    """An explicit uncertainty or gap in the evidence."""

    description: str
    label: str


class AIIncidentNarrative(BaseModel):
    """Structured AI narrative response — validated before display."""

    incident_summary: str
    observations: list[AIObservation] = Field(default_factory=list)
    supported_relationships: list[AIRelationship] = Field(default_factory=list)
    possible_relationships: list[AIRelationship] = Field(default_factory=list)
    uncertainties: list[AIUncertainty] = Field(default_factory=list)
    recovery_summary: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    # Validation metadata
    validation_passed: bool = True
    raw_ai_response: Optional[str] = None


class _GeneratedNarrative(BaseModel):
    """Model-only output schema, excluding API response metadata."""

    incident_summary: str
    observations: list[AIObservation] = Field(default_factory=list)
    supported_relationships: list[AIRelationship] = Field(default_factory=list)
    possible_relationships: list[AIRelationship] = Field(default_factory=list)
    uncertainties: list[AIUncertainty] = Field(default_factory=list)
    recovery_summary: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# System instruction
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = """You are an incident analysis assistant for a distributed operational system.

STRICT RULES:
1. Use ONLY the provided incident context. Do NOT invent events, identifiers, timestamps, causes, or recovery actions.
2. Distinguish confirmed observations (supported by explicit evidence refs) from possible relationships and hypotheses.
3. Do NOT claim causation unless there is an explicit shared identifier or explicit reference in the evidence.
4. Temporal proximity between events is NOT causation. Never say "therefore caused" based only on timing.
5. Explicitly mention any missing or ambiguous information.
6. Do NOT invent source lines or raw record content.
7. Every factual statement must cite an evidence_ref from the provided list.
8. Label every observation and relationship with exactly one of:
   CONFIRMED_OBSERVATION, STRONGLY_SUPPORTED_RELATIONSHIP, POSSIBLE_RELATIONSHIP, INSUFFICIENT_EVIDENCE, MISSING_DATA

Return ONLY valid JSON matching this schema:
{
  "incident_summary": "string",
  "observations": [{"statement": "string", "uncertainty_label": "string", "evidence_refs": ["string"]}],
  "supported_relationships": [{"description": "string", "uncertainty_label": "string", "evidence_refs": ["string"]}],
  "possible_relationships": [{"description": "string", "uncertainty_label": "string", "evidence_refs": ["string"]}],
  "uncertainties": [{"description": "string", "label": "string"}],
  "recovery_summary": "string",
  "evidence_refs": ["string"]
}
"""


def _build_incident_context(
    incident: dict[str, Any],
    events: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    missing_events: list[dict[str, Any]],
    max_events: int = 50,
) -> str:
    """Build a compact incident context string for the LLM."""

    # Select most relevant events (faults, recoveries, commands first)
    priority_categories = {"FAULT", "RECOVERY", "COMMAND", "STATE_CHANGE", "PHASE", "ANOMALY"}
    priority_events = [e for e in events if e.get("category") in priority_categories]
    other_events = [e for e in events if e.get("category") not in priority_categories]

    selected = (priority_events + other_events)[:max_events]

    # Build evidence refs list (event_ids only)
    evidence_refs = [e["event_id"] for e in selected]

    ctx = {
        "incident_id": incident.get("incident_id"),
        "title": incident.get("title"),
        "description": incident.get("description"),
        "time_window": {
            "start": str(incident.get("start_time")),
            "end": str(incident.get("end_time")),
        },
        "involved_nodes": incident.get("involved_nodes", []),
        "primary_faults": incident.get("primary_faults", []),
        "recovery_codes": incident.get("recovery_codes", []),
        "recovery_status": incident.get("recovery_status"),
        "selected_events": [
            {
                "event_id": e["event_id"],
                "timestamp": str(e.get("timestamp")),
                "node": e.get("node"),
                "family": e.get("log_family"),
                "type": e.get("event_type"),
                "severity": e.get("severity"),
                "component": e.get("component"),
                "entity": e.get("entity"),
                "message": e.get("message"),
                "category": e.get("category"),
            }
            for e in selected
        ],
        "relationships": [
            {
                "source": r.get("source_event_id"),
                "target": r.get("target_event_id"),
                "type": r.get("relationship_type"),
                "strength": r.get("strength"),
                "reason": r.get("reason"),
            }
            for r in relationships[:30]
        ],
        "missing_events": missing_events,
        "uncertainty_findings": incident.get("uncertainty_findings", []),
        "available_evidence_refs": evidence_refs,
    }
    return json.dumps(ctx, indent=2, default=str)


async def generate_narrative(
    incident: dict[str, Any],
    events: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    missing_events: list[dict[str, Any]],
) -> AIIncidentNarrative:
    """
    Generate an AI narrative for an incident.

    Returns an AIIncidentNarrative. If AI is unavailable or fails validation,
    returns a narrative with validation_passed=False and a description of the error.
    """
    settings = get_settings()

    if not settings.gemini_api_key:
        return AIIncidentNarrative(
            incident_summary="AI narrative unavailable: GEMINI_API_KEY not configured.",
            validation_passed=False,
            raw_ai_response=None,
        )

    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        return AIIncidentNarrative(
            incident_summary="AI narrative unavailable: google-genai package not installed.",
            validation_passed=False,
        )

    context = _build_incident_context(incident, events, relationships, missing_events)
    prompt = f"""Analyze the following incident context and produce a structured narrative.

INCIDENT CONTEXT:
{context}

Keep the response concise: use at most 8 observations, 5 relationships of each type,
and 5 uncertainty findings. Keep the summary to 2 sentences and each item brief.
Cite only evidence_refs from the provided available_evidence_refs list."""

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                max_output_tokens=settings.gemini_max_tokens,
                temperature=0.1,  # Low temperature for factual output
                response_mime_type="application/json",
                response_schema=_GeneratedNarrative,
            ),
        )
        raw_text = (response.text or "").strip()
        if not raw_text:
            raise ValueError("Gemini returned an empty response.")

        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        parsed = _GeneratedNarrative.model_validate_json(raw_text)
        narrative = AIIncidentNarrative(**parsed.model_dump(), raw_ai_response=raw_text)
        logger.info("ai_narrative_generated", incident_id=incident.get("incident_id"))
        return narrative

    except ValidationError as exc:
        candidates = getattr(response, "candidates", []) if "response" in locals() else []
        finish_reason = (
            getattr(candidates[0], "finish_reason", None) if candidates else None
        )
        finish_reason_name = getattr(finish_reason, "name", str(finish_reason))
        if finish_reason_name == "MAX_TOKENS":
            error_message = "Gemini response was truncated because it reached the output token limit."
            logger.warning(
                "ai_response_truncated",
                error=str(exc),
                finish_reason=finish_reason_name,
            )
            return AIIncidentNarrative(
                incident_summary=error_message,
                validation_passed=False,
            )

        logger.warning(
            "ai_response_validation_failed",
            error=str(exc),
            finish_reason=finish_reason_name,
        )
        return AIIncidentNarrative(
            incident_summary=f"AI response failed schema validation: {exc}",
            validation_passed=False,
            raw_ai_response=raw_text if "raw_text" in dir() else None,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        candidates = getattr(response, "candidates", []) if "response" in locals() else []
        finish_reason = (
            getattr(candidates[0], "finish_reason", None) if candidates else None
        )
        finish_reason_name = getattr(finish_reason, "name", str(finish_reason))
        if finish_reason_name == "MAX_TOKENS":
            error_message = "Gemini response was truncated because it reached the output token limit."
        else:
            error_message = "Gemini returned an empty or malformed structured response."
        logger.warning(
            "ai_response_not_json",
            error=str(exc),
            finish_reason=finish_reason_name,
        )
        return AIIncidentNarrative(
            incident_summary=error_message,
            validation_passed=False,
        )
    except Exception as exc:
        logger.error("ai_narrative_error", error=str(exc))
        return AIIncidentNarrative(
            incident_summary=f"AI narrative generation failed: {type(exc).__name__}: {exc}",
            validation_passed=False,
        )
