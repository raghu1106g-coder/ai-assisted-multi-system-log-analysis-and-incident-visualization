"""DuckDB storage layer.

Creates and manages the analytical event store. All tables use DuckDB's
in-process columnar engine. The schema is designed for efficient filtering
by node, timestamp, log_family, event_type, and incident.

Tables:
  events            — normalized events from all families
  ingestion_errors  — skipped/malformed records
  ingestion_runs    — one row per ingestion run
  relationships     — correlation edges between events
  incidents         — grouped incident candidates
  evidence          — traceable source links

The storage class is abstract enough that a PostgreSQL adapter could be
added later by implementing the same interface.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import duckdb

from ..core.logging import get_logger
from ..models.event import IngestionError, IngestionResult, NormalizedEvent
from ..models.incident import Evidence, EventRelationship, Incident

logger = get_logger(__name__)

_CREATE_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    event_id        VARCHAR PRIMARY KEY,
    schema_version  INTEGER NOT NULL DEFAULT 1,
    node            VARCHAR NOT NULL,
    log_family      VARCHAR NOT NULL,
    event_type      VARCHAR NOT NULL,
    category        VARCHAR,
    severity        VARCHAR,
    timestamp       TIMESTAMPTZ NOT NULL,
    timestamp_precision VARCHAR,
    component       VARCHAR,
    entity          VARCHAR,
    message         VARCHAR,
    incident_hint   VARCHAR,
    attributes      JSON,
    source_file     VARCHAR NOT NULL,
    source_line     INTEGER NOT NULL,
    raw_record      VARCHAR NOT NULL,
    ingestion_run_id VARCHAR
);
"""

_CREATE_INGESTION_RUNS = """
CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id          VARCHAR PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    data_root       VARCHAR,
    files_processed INTEGER,
    valid_records   INTEGER,
    skipped_records INTEGER,
    duration_s      DOUBLE,
    summary_json    JSON
);
"""

_CREATE_INGESTION_ERRORS = """
CREATE SEQUENCE IF NOT EXISTS seq_ingestion_errors_id;
CREATE TABLE IF NOT EXISTS ingestion_errors (
    id              INTEGER PRIMARY KEY DEFAULT nextval('seq_ingestion_errors_id'),
    run_id          VARCHAR NOT NULL,
    source_file     VARCHAR NOT NULL,
    source_line     INTEGER NOT NULL,
    reason          VARCHAR NOT NULL,
    raw_record      VARCHAR,
    log_family      VARCHAR,
    node            VARCHAR
);
"""

_CREATE_RELATIONSHIPS = """
CREATE TABLE IF NOT EXISTS relationships (
    relationship_id     VARCHAR PRIMARY KEY,
    source_event_id     VARCHAR NOT NULL,
    target_event_id     VARCHAR NOT NULL,
    relationship_type   VARCHAR NOT NULL,
    strength            VARCHAR NOT NULL,
    reason              VARCHAR NOT NULL,
    supporting_evidence JSON,
    temporal_window_s   DOUBLE,
    confidence          DOUBLE,
    created_at          TIMESTAMPTZ
);
"""

_CREATE_INCIDENTS = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id         VARCHAR PRIMARY KEY,
    kind                VARCHAR,
    title               VARCHAR,
    description         VARCHAR,
    start_time          TIMESTAMPTZ,
    end_time            TIMESTAMPTZ,
    involved_nodes      JSON,
    involved_families   JSON,
    primary_faults      JSON,
    recovery_codes      JSON,
    event_ids           JSON,
    relationship_ids    JSON,
    evidence_ids        JSON,
    recovery_status     VARCHAR,
    missing_events      JSON,
    uncertainty_findings JSON,
    created_at          TIMESTAMPTZ
);
"""

_CREATE_EVIDENCE = """
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id             VARCHAR PRIMARY KEY,
    event_id                VARCHAR NOT NULL,
    source_file             VARCHAR NOT NULL,
    source_line             INTEGER NOT NULL,
    raw_record              VARCHAR NOT NULL,
    normalized_summary      VARCHAR NOT NULL,
    relationship_to_finding VARCHAR NOT NULL,
    finding_type            VARCHAR
);
"""


class EventStore:
    """DuckDB-backed event store with typed insert and query methods."""

    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    def connect(self) -> None:
        self._conn = duckdb.connect(self._db_path)
        self._ensure_schema()
        logger.info("duckdb_connected", path=self._db_path)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _ensure_schema(self) -> None:
        """Create all tables if they don't exist."""
        for ddl in [
            _CREATE_EVENTS,
            _CREATE_INGESTION_RUNS,
            _CREATE_INGESTION_ERRORS,
            _CREATE_RELATIONSHIPS,
            _CREATE_INCIDENTS,
            _CREATE_EVIDENCE,
        ]:
            self._conn.execute(ddl)

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            raise RuntimeError("EventStore not connected. Call connect() first.")
        return self._conn

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def store_ingestion_run(self, result: IngestionResult) -> None:
        summary = {
            "files_discovered": result.files_discovered,
            "file_stats": result.file_stats,
        }
        self.conn.execute(
            """
            INSERT OR REPLACE INTO ingestion_runs
            (run_id, started_at, finished_at, data_root, files_processed,
             valid_records, skipped_records, duration_s, summary_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                result.run_id,
                result.started_at,
                result.finished_at,
                result.data_root,
                result.files_processed,
                result.valid_records,
                result.skipped_records,
                result.processing_duration_seconds,
                json.dumps(summary),
            ],
        )

    def store_events(self, events: list[NormalizedEvent], run_id: str) -> int:
        """Bulk insert events; returns count inserted."""
        if not events:
            return 0
        rows = [
            (
                e.event_id,
                e.schema_version,
                e.node,
                e.log_family.value if hasattr(e.log_family, "value") else str(e.log_family),
                e.event_type,
                e.category.value if hasattr(e.category, "value") else str(e.category),
                e.severity.value if hasattr(e.severity, "value") else str(e.severity),
                e.timestamp,
                e.timestamp_precision.value if hasattr(e.timestamp_precision, "value") else str(e.timestamp_precision),
                e.component,
                e.entity,
                e.message,
                e.incident_hint,
                json.dumps(e.attributes),
                e.source_file,
                e.source_line,
                e.raw_record,
                run_id,
            )
            for e in events
        ]
        self.conn.executemany(
            """
            INSERT OR IGNORE INTO events
            (event_id, schema_version, node, log_family, event_type, category,
             severity, timestamp, timestamp_precision, component, entity, message,
             incident_hint, attributes, source_file, source_line, raw_record, ingestion_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return len(rows)

    def store_ingestion_errors(self, errors: list[IngestionError], run_id: str) -> None:
        if not errors:
            return
        rows = [
            (
                run_id,
                e.source_file,
                e.source_line,
                e.reason,
                e.raw_record,
                e.log_family.value if e.log_family and hasattr(e.log_family, "value") else str(e.log_family or ""),
                e.node,
            )
            for e in errors
        ]
        self.conn.executemany(
            """
            INSERT INTO ingestion_errors
            (run_id, source_file, source_line, reason, raw_record, log_family, node)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    # ------------------------------------------------------------------
    # Events Query
    # ------------------------------------------------------------------

    def get_events(
        self,
        node: Optional[str] = None,
        log_family: Optional[str] = None,
        event_type: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        incident_hint: Optional[str] = None,
        ts_from: Optional[datetime] = None,
        ts_to: Optional[datetime] = None,
        event_ids: Optional[list[str]] = None,
        limit: int = 5000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions = ["1=1"]
        params: list[Any] = []

        if node:
            conditions.append("node = ?")
            params.append(node)
        if log_family:
            conditions.append("log_family = ?")
            params.append(log_family)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if incident_hint:
            conditions.append("incident_hint = ?")
            params.append(incident_hint)
        if ts_from:
            conditions.append("timestamp >= ?")
            params.append(ts_from)
        if ts_to:
            conditions.append("timestamp <= ?")
            params.append(ts_to)
        if event_ids:
            placeholders = ",".join("?" * len(event_ids))
            conditions.append(f"event_id IN ({placeholders})")
            params.extend(event_ids)

        where = " AND ".join(conditions)
        params.extend([limit, offset])
        sql = f"""
            SELECT * FROM events
            WHERE {where}
            ORDER BY timestamp ASC, source_file, source_line
            LIMIT ? OFFSET ?
        """
        rows = self.conn.execute(sql, params).fetchall()
        cols = [d[0] for d in self.conn.description]
        return [dict(zip(cols, r)) for r in rows]

    def get_event_by_id(self, event_id: str) -> Optional[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM events WHERE event_id = ?", [event_id]
        ).fetchall()
        if not rows:
            return None
        cols = [d[0] for d in self.conn.description]
        return dict(zip(cols, rows[0]))

    def get_statistics(self) -> dict[str, Any]:
        stats: dict[str, Any] = {}

        total = self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        stats["total_events"] = total

        by_node = self.conn.execute(
            "SELECT node, COUNT(*) as cnt FROM events GROUP BY node ORDER BY node"
        ).fetchall()
        stats["by_node"] = {r[0]: r[1] for r in by_node}

        by_family = self.conn.execute(
            "SELECT log_family, COUNT(*) as cnt FROM events GROUP BY log_family ORDER BY log_family"
        ).fetchall()
        stats["by_family"] = {r[0]: r[1] for r in by_family}

        by_category = self.conn.execute(
            "SELECT category, COUNT(*) as cnt FROM events GROUP BY category ORDER BY category"
        ).fetchall()
        stats["by_category"] = {r[0]: r[1] for r in by_category}

        time_range = self.conn.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM events"
        ).fetchone()
        stats["time_range"] = {
            "start": time_range[0].isoformat() if time_range[0] else None,
            "end": time_range[1].isoformat() if time_range[1] else None,
        }

        error_count = self.conn.execute("SELECT COUNT(*) FROM ingestion_errors").fetchone()[0]
        stats["ingestion_errors"] = error_count

        return stats

    def get_ingestion_errors(
        self, run_id: Optional[str] = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        if run_id:
            rows = self.conn.execute(
                "SELECT * FROM ingestion_errors WHERE run_id = ? ORDER BY id LIMIT ?",
                [run_id, limit],
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM ingestion_errors ORDER BY id LIMIT ?", [limit]
            ).fetchall()
        cols = [d[0] for d in self.conn.description]
        return [dict(zip(cols, r)) for r in rows]

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    def store_relationship(self, rel: EventRelationship) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO relationships
            (relationship_id, source_event_id, target_event_id, relationship_type,
             strength, reason, supporting_evidence, temporal_window_s, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                rel.relationship_id,
                rel.source_event_id,
                rel.target_event_id,
                rel.relationship_type.value if hasattr(rel.relationship_type, "value") else str(rel.relationship_type),
                rel.strength.value if hasattr(rel.strength, "value") else str(rel.strength),
                rel.reason,
                json.dumps(rel.supporting_evidence),
                rel.temporal_window_seconds,
                rel.confidence,
                rel.created_at,
            ],
        )

    def get_relationships(
        self,
        event_id: Optional[str] = None,
        relationship_type: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        conditions = ["1=1"]
        params: list[Any] = []
        if event_id:
            conditions.append("(source_event_id = ? OR target_event_id = ?)")
            params.extend([event_id, event_id])
        if relationship_type:
            conditions.append("relationship_type = ?")
            params.append(relationship_type)
        where = " AND ".join(conditions)
        params.append(limit)
        rows = self.conn.execute(
            f"SELECT * FROM relationships WHERE {where} ORDER BY confidence DESC LIMIT ?",
            params,
        ).fetchall()
        cols = [d[0] for d in self.conn.description]
        return [dict(zip(cols, r)) for r in rows]

    # ------------------------------------------------------------------
    # Incidents
    # ------------------------------------------------------------------

    def store_incident(self, incident: Incident) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO incidents
            (incident_id, kind, title, description, start_time, end_time,
             involved_nodes, involved_families, primary_faults, recovery_codes,
             event_ids, relationship_ids, evidence_ids, recovery_status,
             missing_events, uncertainty_findings, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                incident.incident_id,
                incident.kind.value if hasattr(incident.kind, "value") else str(incident.kind),
                incident.title,
                incident.description,
                incident.start_time,
                incident.end_time,
                json.dumps(incident.involved_nodes),
                json.dumps(incident.involved_families),
                json.dumps(incident.primary_faults),
                json.dumps(incident.recovery_codes),
                json.dumps(incident.event_ids),
                json.dumps(incident.relationship_ids),
                json.dumps(incident.evidence_ids),
                incident.recovery_status,
                json.dumps([m.model_dump() for m in incident.missing_events]),
                json.dumps(incident.uncertainty_findings),
                incident.created_at,
            ],
        )

    def get_incidents(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM incidents ORDER BY start_time ASC"
        ).fetchall()
        cols = [d[0] for d in self.conn.description]
        return [dict(zip(cols, r)) for r in rows]

    def get_incident_by_id(self, incident_id: str) -> Optional[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ?", [incident_id]
        ).fetchall()
        if not rows:
            return None
        cols = [d[0] for d in self.conn.description]
        return dict(zip(cols, rows[0]))

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def store_evidence(self, ev: Evidence) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO evidence
            (evidence_id, event_id, source_file, source_line, raw_record,
             normalized_summary, relationship_to_finding, finding_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ev.evidence_id,
                ev.event_id,
                ev.source_file,
                ev.source_line,
                ev.raw_record,
                ev.normalized_summary,
                ev.relationship_to_finding,
                ev.finding_type,
            ],
        )

    def get_evidence_for_event(self, event_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM evidence WHERE event_id = ? ORDER BY evidence_id",
            [event_id],
        ).fetchall()
        cols = [d[0] for d in self.conn.description]
        return [dict(zip(cols, r)) for r in rows]

    def reset(self) -> None:
        """Drop and recreate all tables. Use with care."""
        for table in ["events", "ingestion_errors", "ingestion_runs", "relationships", "incidents", "evidence"]:
            self.conn.execute(f"DROP TABLE IF EXISTS {table}")
        self.conn.execute("DROP SEQUENCE IF EXISTS seq_ingestion_errors_id")
        self._ensure_schema()
        logger.warning("event_store_reset")
