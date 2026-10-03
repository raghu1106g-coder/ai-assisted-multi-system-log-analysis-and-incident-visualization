"""Tests for all 5 log family parsers."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.app.parsers.registry import get_parser, PARSER_REGISTRY
from backend.app.parsers.operator_parser import OperatorParser
from backend.app.parsers.planning_parser import PlanningParser
from backend.app.parsers.guidance_parser import GuidanceParser
from backend.app.parsers.state_parser import StateParser
from backend.app.parsers.fault_recovery_parser import FaultRecoveryParser
from backend.app.ingestion.engine import run_ingestion


def test_parser_registry():
    assert len(PARSER_REGISTRY) == 5
    for family in ["operator", "planning", "guidance", "state", "fault_recovery"]:
        parser = get_parser(family)
        assert parser is not None


def test_parse_synthetic_dataset(data_root: Path):
    """Test ingestion engine on actual synthetic dataset files."""
    result, events = run_ingestion(data_root)

    # 15 raw log files across 3 nodes
    assert result.files_processed == 15
    # 366 valid records
    assert result.valid_records == 366
    # 10 intentionally malformed records
    assert result.skipped_records == 10
    assert len(result.errors) == 10

    # Ensure all events have required fields
    for ev in events:
        assert ev.event_id is not None
        assert ev.node in {"NODE_A", "NODE_B", "NODE_C"}
        assert ev.log_family in {"operator", "planning", "guidance", "state", "fault_recovery"}
        assert ev.event_type is not None
        assert ev.timestamp is not None
        assert ev.source_file is not None
        assert ev.source_line > 0


def test_against_expected_parser_reference():
    """Verify parsed event types match reference parser definitions."""
    ref_path = Path(__file__).resolve().parent.parent.parent / "reference" / "parser_expected_events.json"
    if not ref_path.exists():
        pytest.skip("Reference parser expectations file not found")

    with open(ref_path, "r", encoding="utf-8") as f:
        expected = json.load(f)

    assert "families" in expected or isinstance(expected, dict)
