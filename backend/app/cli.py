"""Command-line interface for running log ingestion and generating incident reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core.config import get_settings
from .core.logging import configure_logging
from .services.analysis import AnalysisService
from .storage.event_store import EventStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PS3 Multi-System Log Analyzer & Incident Reconstructor CLI"
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default="data/synthetic",
        help="Path to dataset root folder containing node directories",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="ps3_events.duckdb",
        help="Path to DuckDB database file",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database before ingestion",
    )
    parser.add_argument(
        "--window",
        type=float,
        default=10.0,
        help="Temporal correlation window in seconds",
    )
    parser.add_argument(
        "--export-incidents",
        type=str,
        help="Optional path to export reconstructed incidents JSON",
    )

    args = parser.parse_args()
    configure_logging("INFO")

    data_path = Path(args.data_root)
    if not data_path.exists():
        print(f"Error: Data path {data_path} not found.")
        return

    store = EventStore(Path(args.db))
    store.connect()

    try:
        service = AnalysisService(store, temporal_window_seconds=args.window)
        summary = service.run_full_pipeline(data_root=data_path, reset_first=args.reset)

        print("\n" + "=" * 60)
        print("PS3 ANALYSIS PIPELINE COMPLETE")
        print("=" * 60)
        print(f"Run ID:            {summary['run_id']}")
        print(f"Files Processed:   {summary['ingestion']['files_processed']}")
        print(f"Valid Records:     {summary['ingestion']['valid_records']}")
        print(f"Malformed Skipped: {summary['ingestion']['skipped_records']}")
        print(f"Correlations:      {summary['correlation']['relationships']}")
        print(f"Missing Events:    {summary['correlation']['missing_events']}")
        print(f"Incidents:         {summary['incidents']['total']} ({', '.join(summary['incidents']['ids'])})")
        print("=" * 60 + "\n")

        if args.export_incidents:
            incidents = store.get_incidents()
            with open(args.export_incidents, "w", encoding="utf-8") as f:
                json.dump(incidents, f, indent=2, default=str)
            print(f"Exported incidents to {args.export_incidents}")

    finally:
        store.close()


if __name__ == "__main__":
    main()
