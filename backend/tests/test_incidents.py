"""Tests for incident reconstruction and classification."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.correlation.engine import CorrelationEngine
from backend.app.incidents.reconstructor import IncidentReconstructor, build_evidence
from backend.app.ingestion.engine import run_ingestion
from backend.app.models.incident import IncidentKind


def test_incident_reconstruction(data_root: Path, ground_truth_root: Path):
    result, raw_events = run_ingestion(data_root)
    event_dicts = [e.model_dump() for e in raw_events]

    engine = CorrelationEngine(temporal_window_seconds=10.0)
    relationships, graph, missing_events = engine.correlate(event_dicts)

    reconstructor = IncidentReconstructor()
    incidents = reconstructor.reconstruct(event_dicts, relationships, graph, missing_events)

    assert len(incidents) > 0

    # Ensure INC-001 (or primary incident) is found
    incident_ids = [i.incident_id for i in incidents]
    assert "INC-001" in incident_ids

    inc_001 = next(i for i in incidents if i.incident_id == "INC-001")
    assert inc_001.kind == IncidentKind.INCIDENT
    assert "NODE_A" in inc_001.involved_nodes
    assert "NODE_B" in inc_001.involved_nodes
    assert "NODE_C" in inc_001.involved_nodes
    assert len(inc_001.primary_faults) > 0

    # Evidence generation
    evidence = build_evidence(event_dicts)
    assert len(evidence) == len(event_dicts)
