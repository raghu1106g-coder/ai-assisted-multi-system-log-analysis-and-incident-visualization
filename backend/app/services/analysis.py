"""Main analysis pipeline service.

Orchestrates: ingestion → storage → correlation → incident reconstruction → evidence building.

This is the single entry point for running the full PS3 analysis pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.logging import get_logger
from ..correlation.engine import CorrelationEngine
from ..incidents.reconstructor import IncidentReconstructor, build_evidence
from ..ingestion.engine import run_ingestion
from ..models.event import IngestionResult, NormalizedEvent
from ..storage.event_store import EventStore

logger = get_logger(__name__)


class AnalysisService:
    """Orchestrates the full ingestion-to-incident pipeline."""

    def __init__(self, store: EventStore, temporal_window_seconds: float = 10.0):
        self.store = store
        self._correlation_engine = CorrelationEngine(temporal_window_seconds)
        self._reconstructor = IncidentReconstructor()

    def run_full_pipeline(
        self,
        data_root: Path,
        max_file_size_bytes: int = 100 * 1024 * 1024,
        reset_first: bool = False,
    ) -> dict[str, Any]:
        """
        Run the complete analysis pipeline.

        Steps:
        1. Ingest all log files
        2. Store normalized events and errors
        3. Correlate events
        4. Store relationships
        5. Reconstruct incidents
        6. Store incidents + evidence

        Returns a summary dict.
        """
        if reset_first:
            self.store.reset()

        # --- Step 1: Ingest ---
        logger.info("pipeline_step", step="ingestion", data_root=str(data_root))
        result, events = run_ingestion(data_root, max_file_size_bytes)

        # --- Step 2: Store events ---
        logger.info("pipeline_step", step="storage", events=len(events))
        self.store.store_ingestion_run(result)
        stored_count = self.store.store_events(events, result.run_id)
        self.store.store_ingestion_errors(result.errors, result.run_id)

        # Fetch events back as dicts for correlation
        event_dicts = self.store.get_events(limit=100_000)

        # --- Step 3: Correlate ---
        logger.info("pipeline_step", step="correlation", event_count=len(event_dicts))
        relationships, graph, missing_events = self._correlation_engine.correlate(event_dicts)

        # --- Step 4: Store relationships ---
        for rel in relationships:
            self.store.store_relationship(rel)

        # --- Step 5: Reconstruct incidents ---
        logger.info("pipeline_step", step="incident_reconstruction")
        incidents = self._reconstructor.reconstruct(
            event_dicts, relationships, graph, missing_events
        )

        # --- Step 6: Store incidents + evidence ---
        for incident in incidents:
            self.store.store_incident(incident)

        evidence_list = build_evidence(event_dicts)
        for ev in evidence_list:
            self.store.store_evidence(ev)

        stats = self.store.get_statistics()

        summary = {
            "run_id": result.run_id,
            "ingestion": {
                "files_processed": result.files_processed,
                "valid_records": result.valid_records,
                "skipped_records": result.skipped_records,
                "duration_seconds": result.processing_duration_seconds,
            },
            "correlation": {
                "relationships": len(relationships),
                "missing_events": len(missing_events),
                "graph_nodes": graph.number_of_nodes(),
                "graph_edges": graph.number_of_edges(),
            },
            "incidents": {
                "total": len(incidents),
                "ids": [i.incident_id for i in incidents],
            },
            "statistics": stats,
        }

        logger.info("pipeline_complete", **{k: str(v)[:80] for k, v in summary.items()})
        return summary
