"""Pytest fixtures for backend test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.storage.event_store import EventStore


@pytest.fixture(scope="session")
def data_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "synthetic"


@pytest.fixture(scope="session")
def ground_truth_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "ground_truth"


@pytest.fixture
def in_memory_store():
    store = EventStore(":memory:")
    store.connect()
    yield store
    store.close()
