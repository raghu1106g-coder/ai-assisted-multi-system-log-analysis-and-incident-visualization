"""FastAPI dependency injection utilities."""

from __future__ import annotations

from typing import Optional

from ..storage.event_store import EventStore

_store: Optional[EventStore] = None


def set_global_store(store: Optional[EventStore]) -> None:
    global _store
    _store = store


def get_store() -> EventStore:
    global _store
    if _store is None:
        raise RuntimeError("Event store not initialized")
    return _store
