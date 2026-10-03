"""Ingestion engine — discovers and processes all log files under a data root.

Features:
- Recursive file discovery by node directory and family name
- Streaming/line-by-line processing (no full file load into memory)
- Malformed record capture with reason and raw line
- Idempotent: can be run multiple times; stores run metadata
- File size limit check
- Encoding error handling (utf-8, errors=replace)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..core.logging import get_logger
from ..models.event import IngestionError, IngestionResult, LogFamily, NormalizedEvent
from ..parsers.registry import get_parser

logger = get_logger(__name__)

# Known log family file stems
_FAMILY_STEMS = {
    "operator": LogFamily.operator,
    "planning": LogFamily.planning,
    "guidance": LogFamily.guidance,
    "state": LogFamily.state,
    "fault_recovery": LogFamily.fault_recovery,
}

# Pattern: any directory component that looks like node_X or NODE_X (case-insensitive)
import re
_NODE_DIR_RE = re.compile(r'^node_([A-Za-z])$', re.IGNORECASE)


def _identify_node(path: Path) -> Optional[str]:
    """Try to identify node from directory name (case-insensitive).

    Supports: node_A, NODE_A, Node_A, node_b, etc.
    Always normalizes to uppercase canonical form NODE_X.
    """
    for part in path.parts:
        m = _NODE_DIR_RE.match(part)
        if m:
            return f"NODE_{m.group(1).upper()}"
    return None


def _identify_family(path: Path) -> Optional[str]:
    """Try to identify log family from filename stem."""
    return _FAMILY_STEMS.get(path.stem)


def discover_log_files(data_root: Path) -> list[Path]:
    """Recursively discover .log files under data_root."""
    return sorted(data_root.rglob("*.log"))


def run_ingestion(
    data_root: Path,
    max_file_size_bytes: int = 100 * 1024 * 1024,
) -> tuple[IngestionResult, list[NormalizedEvent]]:
    """
    Ingest all log files under data_root.

    Returns:
        (IngestionResult, list[NormalizedEvent]) — the result summary and all valid events.
    """
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    result = IngestionResult(
        run_id=run_id,
        started_at=started_at,
        data_root=str(data_root),
    )

    all_events: list[NormalizedEvent] = []
    log_files = discover_log_files(data_root)
    result.files_discovered = [str(p.relative_to(data_root)) for p in log_files]

    for path in log_files:
        rel_path = str(path.relative_to(data_root.parent))  # relative from project root

        # File size guard
        try:
            file_size = path.stat().st_size
        except OSError as exc:
            logger.warning("cannot_stat_file", path=str(path), error=str(exc))
            result.files_errored += 1
            continue

        if file_size > max_file_size_bytes:
            logger.warning(
                "file_too_large",
                path=str(path),
                size=file_size,
                limit=max_file_size_bytes,
            )
            result.files_errored += 1
            result.errors.append(
                IngestionError(
                    source_file=rel_path,
                    source_line=0,
                    reason=f"file_too_large: {file_size} bytes exceeds {max_file_size_bytes}",
                    raw_record="",
                )
            )
            continue

        node = _identify_node(path)
        family_name = path.stem  # e.g. "operator", "planning", etc.
        parser = get_parser(family_name)

        if parser is None:
            logger.info("no_parser_for_family", family=family_name, path=str(path))
            continue

        if node is None:
            logger.warning("cannot_identify_node", path=str(path))

        logger.info("ingesting", file=rel_path, node=node, family=family_name)

        try:
            events, errors = parser.parse_file(path, node or "UNKNOWN", rel_path)
        except OSError as exc:
            logger.error("file_read_error", path=str(path), error=str(exc))
            result.files_errored += 1
            result.errors.append(
                IngestionError(
                    source_file=rel_path,
                    source_line=0,
                    reason=f"file_read_error: {exc}",
                    raw_record="",
                )
            )
            continue

        all_events.extend(events)
        result.errors.extend(errors)
        result.valid_records += len(events)
        result.skipped_records += len(errors)
        result.files_processed += 1

        # Count total lines (re-open quickly just for lines)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                line_count = sum(1 for _ in fh)
        except OSError:
            line_count = 0
        result.total_lines_read += line_count

        result.file_stats.append(
            {
                "file": rel_path,
                "node": node,
                "family": family_name,
                "valid_records": len(events),
                "skipped_records": len(errors),
                "lines_read": line_count,
            }
        )

    # Sort events by timestamp (out-of-order records get sorted here)
    all_events.sort(key=lambda e: (e.timestamp, e.source_file, e.source_line))

    finished_at = datetime.now(timezone.utc)
    result.finished_at = finished_at
    result.processing_duration_seconds = (finished_at - started_at).total_seconds()

    logger.info(
        "ingestion_complete",
        run_id=run_id,
        valid=result.valid_records,
        skipped=result.skipped_records,
        files=result.files_processed,
        duration_s=result.processing_duration_seconds,
    )

    return result, all_events
