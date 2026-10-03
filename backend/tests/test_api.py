"""API route integration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.core.dependencies import get_store
from backend.app.main import app
from backend.app.services.analysis import AnalysisService
from backend.app.storage.event_store import EventStore


@pytest.fixture(scope="module")
def shared_store(data_root):
    store = EventStore(":memory:")
    store.connect()
    service = AnalysisService(store)
    service.run_full_pipeline(data_root=data_root, reset_first=True)
    yield store
    store.close()


@pytest.fixture
def client(shared_store: EventStore):
    # Override store dependency with populated test store
    app.dependency_overrides[get_store] = lambda: shared_store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_list_events(client):
    res = client.get("/api/v1/events?limit=50")
    assert res.status_code == 200
    data = res.json()
    assert "events" in data
    assert len(data["events"]) > 0


def test_event_filter_by_node(client):
    res = client.get("/api/v1/events?node=NODE_A")
    assert res.status_code == 200
    for ev in res.json()["events"]:
        assert ev["node"] == "NODE_A"


def test_list_errors(client):
    res = client.get("/api/v1/events/errors")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 10
    assert len(data["errors"]) == 10


def test_list_incidents(client):
    res = client.get("/api/v1/incidents")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] > 0


def test_graph_endpoint(client):
    res = client.get("/api/v1/relationships/graph")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "links" in data
    assert len(data["nodes"]) > 0


def test_system_stats(client):
    res = client.get("/api/v1/stats")
    assert res.status_code == 200
    data = res.json()
    assert "events" in data
    assert data["events"]["total_events"] == 366
    assert data["events"]["ingestion_errors"] == 10
