import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.correlation.engine import CorrelationEngine
from backend.app.incidents.reconstructor import IncidentReconstructor
from backend.app.ingestion.engine import run_ingestion, discover_log_files
from backend.app.storage.event_store import EventStore

def measure_stages():
    print("=" * 80)
    print("SECTION 13: PERFORMANCE BENCHMARKING")
    print("=" * 80)

    # Stage 1: Discovery
    t0 = time.perf_counter()
    files = discover_log_files(Path("ps3_dataset_2/logs"))
    t_discovery = time.perf_counter() - t0

    # Stage 2: Parsing / Ingestion
    t0 = time.perf_counter()
    res, events = run_ingestion(Path("ps3_dataset_2/logs"))
    t_parsing = time.perf_counter() - t0

    # Stage 3: DB Insertion (in-memory)
    store = EventStore(":memory:")
    store.connect()
    t0 = time.perf_counter()
    store.store_ingestion_run(res)
    store.store_events(events, res.run_id)
    store.store_ingestion_errors(res.errors, res.run_id)
    t_db = time.perf_counter() - t0
    store.close()

    # Convert events to dicts
    event_dicts = [e.model_dump() for e in events]
    for ed in event_dicts:
        if isinstance(ed["timestamp"], str):
            ed["timestamp"] = datetime.fromisoformat(ed["timestamp"].replace("Z", "+00:00"))

    # Stage 4: Correlation
    corr_engine = CorrelationEngine()
    t0 = time.perf_counter()
    rels, graph, missing = corr_engine.correlate(event_dicts)
    t_correlation = time.perf_counter() - t0

    # Stage 5: Incident Reconstruction
    reconstructor = IncidentReconstructor()
    t0 = time.perf_counter()
    incidents = reconstructor.reconstruct(event_dicts, rels, graph, missing)
    t_reconstruct = time.perf_counter() - t0

    total_no_ai = t_discovery + t_parsing + t_db + t_correlation + t_reconstruct

    print(f"Discovery:                 {t_discovery*1000:.2f} ms ({len(files)} files)")
    print(f"Parsing & Ingestion:       {t_parsing*1000:.2f} ms ({res.valid_records} valid, {res.skipped_records} skipped)")
    print(f"DB Insertion:              {t_db*1000:.2f} ms ({len(events)} events + errors)")
    print(f"Correlation:               {t_correlation*1000:.2f} ms ({len(rels)} rels, {graph.number_of_edges()} edges)")
    print(f"Incident Reconstruction:   {t_reconstruct*1000:.2f} ms ({len(incidents)} incidents)")
    print(f"Total Pipeline (No AI):    {total_no_ai:.3f} s")

    return {
        "discovery_ms": t_discovery * 1000,
        "parsing_ms": t_parsing * 1000,
        "db_insertion_ms": t_db * 1000,
        "correlation_ms": t_correlation * 1000,
        "reconstruction_ms": t_reconstruct * 1000,
        "total_no_ai_s": total_no_ai,
    }

def repeatability_test():
    print("\n" + "=" * 80)
    print("SECTION 14: REPEATABILITY (3 RUNS)")
    print("=" * 80)
    runs = []
    for i in range(1, 4):
        print(f"Starting Run {i}...")
        res, events = run_ingestion(Path("ps3_dataset_2/logs"))
        event_dicts = [e.model_dump() for e in events]
        for ed in event_dicts:
            if isinstance(ed["timestamp"], str):
                ed["timestamp"] = datetime.fromisoformat(ed["timestamp"].replace("Z", "+00:00"))
        corr_engine = CorrelationEngine()
        rels, graph, missing = corr_engine.correlate(event_dicts)
        reconstructor = IncidentReconstructor()
        incidents = reconstructor.reconstruct(event_dicts, rels, graph, missing)

        run_summary = {
            "run": i,
            "parsed_records": res.valid_records,
            "skipped_records": res.skipped_records,
            "correlations": len(rels),
            "graph_edges": graph.number_of_edges(),
            "missing_event_findings": len(missing),
            "incidents_total": len(incidents),
            "fault_incidents": sum(1 for inc in incidents if str(inc.kind) == "INCIDENT"),
            "normal_ops": sum(1 for inc in incidents if str(inc.kind) == "NON_INCIDENT_NORMAL_OPERATION"),
            "incident_ids": [inc.incident_id for inc in incidents],
            "missing_event_keys": [f"{m.expected_event_type}@{m.expected_at_node}:{m.expected_after_event_id}" for m in missing],
        }
        runs.append(run_summary)
        print(f"  Run {i}: Valid={run_summary['parsed_records']}, Skipped={run_summary['skipped_records']}, Rels={run_summary['correlations']}, Incidents={run_summary['incidents_total']}, Missing={run_summary['missing_event_findings']}")

    # Check equality across runs
    print("\nComparing Run 1, Run 2, Run 3:")
    r1, r2, r3 = runs[0], runs[1], runs[2]
    all_identical = (
        r1["parsed_records"] == r2["parsed_records"] == r3["parsed_records"] and
        r1["skipped_records"] == r2["skipped_records"] == r3["skipped_records"] and
        r1["correlations"] == r2["correlations"] == r3["correlations"] and
        r1["graph_edges"] == r2["graph_edges"] == r3["graph_edges"] and
        r1["missing_event_findings"] == r2["missing_event_findings"] == r3["missing_event_findings"] and
        r1["incidents_total"] == r2["incidents_total"] == r3["incidents_total"] and
        r1["incident_ids"] == r2["incident_ids"] == r3["incident_ids"] and
        r1["missing_event_keys"] == r2["missing_event_keys"] == r3["missing_event_keys"]
    )
    print(f"Deterministic Consistency: {'100% PERFECT MATCH ACROSS ALL 3 RUNS' if all_identical else 'MISMATCH FOUND'}")
    return runs

if __name__ == "__main__":
    perf = measure_stages()
    runs = repeatability_test()
    with open("scratch/perf_and_repeatability.json", "w") as f:
        json.dump({"perf": perf, "repeatability": runs}, f, indent=2)
