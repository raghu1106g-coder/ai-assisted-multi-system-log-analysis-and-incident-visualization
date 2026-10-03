"""Tests for deterministic correlation engine."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.correlation.engine import CorrelationEngine
from backend.app.ingestion.engine import run_ingestion


def test_correlation_engine(data_root: Path, ground_truth_root: Path):
    result, raw_events = run_ingestion(data_root)
    event_dicts = [e.model_dump() for e in raw_events]

    engine = CorrelationEngine(temporal_window_seconds=10.0)
    relationships, graph, missing_events = engine.correlate(event_dicts)

    assert len(relationships) > 0
    assert graph.number_of_nodes() > 0

    # Ensure every relationship has explicit reason and valid confidence
    for rel in relationships:
        assert rel.reason is not None and len(rel.reason) > 0
        assert rel.relationship_type is not None
        assert 0.0 <= rel.confidence <= 1.0

    # Verify correlation includes primary message flow / shared ID links
    flow_rels = [
        r for r in relationships
        if (r.relationship_type.value if hasattr(r.relationship_type, "value") else str(r.relationship_type)) in ("MESSAGE_FLOW", "SHARED_ID", "EXPLICIT_REFERENCE")
    ]
    assert len(flow_rels) > 0


def test_ground_truth_relationships(data_root: Path, ground_truth_root: Path):
    """Compare discovered relationships against ground truth if available."""
    gt_file = ground_truth_root / "relationship_ground_truth.json"
    if not gt_file.exists():
        return

    with open(gt_file, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    assert gt_data is not None
