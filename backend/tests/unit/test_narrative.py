from __future__ import annotations

from types import SimpleNamespace

import pytest
from google import genai

from backend.app.ai import narrative


@pytest.mark.asyncio
async def test_generate_narrative_uses_json_schema(monkeypatch):
    response_text = (
        '{"incident_summary":"Fault observed.",'
        '"observations":[],"supported_relationships":[],'
        '"possible_relationships":[],"uncertainties":[],'
        '"recovery_summary":"","evidence_refs":[]}'
    )
    call: dict = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            call.update(kwargs)
            return SimpleNamespace(text=response_text, candidates=[])

    class FakeClient:
        def __init__(self, *, api_key):
            assert api_key == "test-key"
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)
    monkeypatch.setattr(
        narrative,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="test-key",
            gemini_model="gemini-2.5-flash",
            gemini_max_tokens=8192,
        ),
    )

    result = await narrative.generate_narrative({}, [], [], [])

    assert result.validation_passed is True
    assert result.incident_summary == "Fault observed."
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_schema is narrative._GeneratedNarrative


@pytest.mark.asyncio
async def test_generate_narrative_reports_truncated_response(monkeypatch):
    class FakeModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(
                text='{"incident_summary":"cut off',
                candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="MAX_TOKENS"))],
            )

    class FakeClient:
        def __init__(self, *, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)
    monkeypatch.setattr(
        narrative,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="test-key",
            gemini_model="gemini-2.5-flash",
            gemini_max_tokens=8192,
        ),
    )

    result = await narrative.generate_narrative({}, [], [], [])

    assert result.validation_passed is False
    assert "truncated" in result.incident_summary
