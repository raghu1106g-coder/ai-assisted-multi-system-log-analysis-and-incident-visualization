import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.app.ai.narrative import generate_narrative
from backend.app.correlation.engine import CorrelationEngine
from backend.app.incidents.reconstructor import IncidentReconstructor
from backend.app.ingestion.engine import run_ingestion
from backend.app.models.event import NormalizedEvent
from backend.app.models.incident import Incident, IncidentKind

def run_pipeline(data_root: str):
    res, events = run_ingestion(Path(data_root))
    # Convert events to dicts for correlation & incident reconstructor
    event_dicts = [e.model_dump() for e in events]
    # Ensure timestamp is datetime or isoformat
    for ed in event_dicts:
        if isinstance(ed["timestamp"], str):
            ed["timestamp"] = datetime.fromisoformat(ed["timestamp"].replace("Z", "+00:00"))
            
    corr_engine = CorrelationEngine()
    rels, graph, missing = corr_engine.correlate(event_dicts)
    reconstructor = IncidentReconstructor()
    incidents = reconstructor.reconstruct(event_dicts, rels, graph, missing)
    return res, events, event_dicts, rels, graph, missing, incidents

def main():
    print("Running Full Dataset 2 Evaluation Pipeline...")
    t0 = time.perf_counter()
    res, events, event_dicts, rels, graph, missing, incidents = run_pipeline("ps3_dataset_2/logs")
    t_pipeline = time.perf_counter() - t0
    print(f"Ingested {len(events)} events, generated {len(rels)} relationships, {len(missing)} missing events, {len(incidents)} incidents in {t_pipeline:.2f}s")
    
    # Save intermediate results for detailed analysis
    with open("ps3_dataset_2/ground_truth/expected_incidents.json", "r") as f:
        gt_inc_data = json.load(f)
    with open("ps3_dataset_2/ground_truth/expected_relationships.json", "r") as f:
        gt_rel_data = json.load(f)
        
    print("\n" + "="*80)
    print("SECTION 3: INCIDENT DETECTION ACCURACY")
    print("="*80)
    gt_incidents = gt_inc_data["incidents"]
    detected_incidents = incidents
    
    # Build event-id set mapping for detected incidents
    # Note: incident.evidence.event_ids gives the event ids included in the incident
    det_map = {}
    for inc in detected_incidents:
        ev_ids = set(inc.event_ids)
        det_map[inc.incident_id] = {
            "inc": inc,
            "event_ids": ev_ids,
            "kind": inc.kind.value if hasattr(inc.kind, "value") else str(inc.kind),
            "title": inc.title,
            "primary_faults": inc.primary_faults,
            "nodes": inc.involved_nodes,
            "start": inc.start_time,
            "end": inc.end_time,
        }
        
    print(f"Total GT incidents: {len(gt_incidents)}")
    print(f"Total Detected incidents: {len(detected_incidents)}")
    kind_counts = defaultdict(int)
    for inc in detected_incidents:
        kind_counts[str(inc.kind)] += 1
    print(f"Detected breakdown by kind: {dict(kind_counts)}")
    
    # Explicit Matching Table
    # For each GT incident, calculate event overlap with all detected incidents
    matching_table = []
    matched_det_ids = set()
    
    for gt in gt_incidents:
        gt_id = gt["incident_id"]
        gt_title = gt.get("title", "")
        gt_faults = gt.get("primary_faults", [])
        gt_nodes = gt.get("involved_nodes", [])
        gt_ev_raw = gt.get("relevant_event_ids", [])
        gt_ev_ids = set(e["event_id"] if isinstance(e, dict) else e for e in gt_ev_raw)
        
        best_match_id = None
        best_jaccard = 0.0
        best_overlap_count = 0
        best_precision = 0.0
        best_recall = 0.0
        
        for det_id, dinfo in det_map.items():
            intersection = gt_ev_ids.intersection(dinfo["event_ids"])
            if len(intersection) > 0:
                jaccard = len(intersection) / len(gt_ev_ids.union(dinfo["event_ids"]))
                rec = len(intersection) / len(gt_ev_ids)
                prec = len(intersection) / len(dinfo["event_ids"])
                if jaccard > best_jaccard or (jaccard == best_jaccard and len(intersection) > best_overlap_count):
                    best_jaccard = jaccard
                    best_match_id = det_id
                    best_overlap_count = len(intersection)
                    best_precision = prec
                    best_recall = rec
                    
        match_quality = "NONE"
        notes = ""
        if best_match_id:
            matched_det_ids.add(best_match_id)
            dinfo = det_map[best_match_id]
            if best_jaccard >= 0.8:
                match_quality = f"EXCELLENT (J={best_jaccard:.2f}, Rec={best_recall:.2f}, Prec={best_precision:.2f})"
            elif best_recall >= 0.7:
                match_quality = f"HIGH_RECALL (J={best_jaccard:.2f}, Rec={best_recall:.2f}, Prec={best_precision:.2f})"
            elif best_precision >= 0.7:
                match_quality = f"HIGH_PRECISION (J={best_jaccard:.2f}, Rec={best_recall:.2f}, Prec={best_precision:.2f})"
            else:
                match_quality = f"PARTIAL (J={best_jaccard:.2f}, Rec={best_recall:.2f}, Prec={best_precision:.2f})"
            notes = f"Det Kind: {dinfo['kind']}, Primary Faults: {dinfo['primary_faults']}, Overlap: {best_overlap_count}/{len(gt_ev_ids)} GT events"
        else:
            notes = f"No event overlap found. GT Faults: {gt_faults}, GT Nodes: {gt_nodes}"
            
        matching_table.append({
            "gt_id": gt_id,
            "expected_type": gt.get("scenario_family", "INCIDENT"),
            "detected_match": best_match_id or "NO MATCH",
            "match_quality": match_quality,
            "notes": notes,
            "gt_event_count": len(gt_ev_ids),
            "overlap_count": best_overlap_count,
            "jaccard": best_jaccard,
            "recall": best_recall,
            "precision": best_precision,
        })

    # Print matching table
    print("\n| Ground Truth Incident | Expected Type | Detected Match | Match Quality | Notes |")
    print("| --- | --- | --- | --- | --- |")
    for r in matching_table:
        print(f"| {r['gt_id']} | {r['expected_type']} | {r['detected_match']} | {r['match_quality']} | {r['notes']} |")

    # Evaluate TP, FP, FN
    # A GT incident is a True Positive (TP) if a detected incident recovered significant core evidence (e.g. recall > 0.3 or Jaccard > 0.2)
    tp_incidents = [r for r in matching_table if r["detected_match"] != "NO MATCH" and r["recall"] >= 0.3]
    fn_incidents = [r for r in matching_table if r not in tp_incidents]
    # Unmatched detected fault incidents:
    unmatched_detected_faults = [
        det_id for det_id, dinfo in det_map.items() 
        if dinfo["kind"] == "INCIDENT" and det_id not in [r["detected_match"] for r in tp_incidents]
    ]
    
    tp = len(tp_incidents)
    fn = len(fn_incidents)
    fp = len(unmatched_detected_faults)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / len(gt_incidents)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    print(f"\n--- Incident Metrics ---")
    print(f"GT Incidents: {len(gt_incidents)}")
    print(f"TP: {tp} / {len(gt_incidents)}")
    print(f"FN: {fn} / {len(gt_incidents)}")
    print(f"FP (Spurious Fault Incidents): {fp}")
    print(f"Precision: {precision:.4f} ({tp}/{tp+fp})")
    print(f"Recall: {recall:.4f} ({tp}/{len(gt_incidents)})")
    print(f"F1 Score: {f1:.4f}")
    print(f"Explicit Answer: Reconstructor recovered {tp} of {len(gt_incidents)} ground-truth incidents.")

    print("\n" + "="*80)
    print("SECTION 4: NORMAL OPERATION VS INCIDENT CLASSIFICATION")
    print("="*80)
    gt_normal_periods = gt_inc_data.get("normal_operation_periods", [])
    print(f"GT normal operation periods: {len(gt_normal_periods)}")
    for i, p in enumerate(gt_normal_periods):
        print(f"  GT Normal Period {i+1}: {p.get('period_id', p.get('title', ''))} | Time: {p.get('time_range_utc')}")
        
    detected_normals = [inc for inc in detected_incidents if str(inc.kind) == "NON_INCIDENT_NORMAL_OPERATION"]
    print(f"Detected normal-operation clusters: {len(detected_normals)}")
    for inc in detected_normals:
        print(f"  {inc.incident_id}: {inc.title} | Nodes: {inc.involved_nodes} | Events: {len(inc.event_ids)}")

    print("\n" + "="*80)
    print("SECTION 5 & 6: CORRELATION ACCURACY & FORBIDDEN RELATIONSHIPS")
    print("="*80)
    gt_rels = gt_rel_data["relationships"]
    print(f"Total GT relationships: {len(gt_rels)}")
    print(f"Total Generated relationships: {len(rels)}")
    
    # Map generated relationships by (source, target)
    gen_rel_map = {}
    for r in rels:
        key = (r.source_event_id, r.target_event_id)
        gen_rel_map[key] = r
        # Also map undirected
        gen_rel_map[(r.target_event_id, r.source_event_id)] = r
        
    # Group GT relationships by classification and relationship_type
    gt_by_class = defaultdict(list)
    gt_by_type = defaultdict(list)
    for r in gt_rels:
        cls_ = r.get("classification")
        gt_by_class[cls_].append(r)
        gt_by_type[r.get("relationship_type")].append(r)
        
    print("\nGT Relationships by classification:")
    for cls_, rlist in gt_by_class.items():
        print(f"  {cls_}: {len(rlist)}")
        
    # Section 6: Forbidden Relationships
    forbidden_rels = gt_by_class.get("SHOULD_NOT_BE_CORRELATED", [])
    print(f"\nEvaluating {len(forbidden_rels)} FORBIDDEN (SHOULD_NOT_BE_CORRELATED) relationships...")
    forbidden_fp = []
    forbidden_correct = []
    
    # Also check the specific 6 previous false positives:
    prev_6_pairs = [
        ("EVT-B-FLT-0040", "EVT-C-FLT-0035"),
        ("EVT-B-FLT-0039", "EVT-B-FLT-0081"),
        ("EVT-B-FLT-0039", "EVT-C-FLT-0035"),
        ("EVT-B-FLT-0044", "EVT-B-FLT-0081"),
        ("EVT-B-STA-0060", "EVT-B-STA-0061"),
        ("EVT-C-FLT-0048", "EVT-A-OPR-0042"),
    ]
    
    for r in forbidden_rels:
        s = r["source_event_id"]
        t = r["target_event_id"]
        if (s, t) in gen_rel_map or (t, s) in gen_rel_map:
            actual = gen_rel_map.get((s, t)) or gen_rel_map.get((t, s))
            forbidden_fp.append((r, actual))
        else:
            forbidden_correct.append(r)
            
    print(f"Total forbidden pairs: {len(forbidden_rels)}")
    print(f"Correctly kept separate: {len(forbidden_correct)} / {len(forbidden_rels)}")
    print(f"False-positive correlations: {len(forbidden_fp)} / {len(forbidden_rels)}")
    fp_rate = len(forbidden_fp) / len(forbidden_rels) if len(forbidden_rels) > 0 else 0.0
    print(f"False-positive rate: {fp_rate:.4f} ({len(forbidden_fp)}/{len(forbidden_rels)})")
    
    print("\nStatus of Previous 6 False Positives:")
    for s, t in prev_6_pairs:
        matched = gen_rel_map.get((s, t)) or gen_rel_map.get((t, s))
        if matched:
            print(f"  STILL FP: {s} <-> {t} | Type: {matched.relationship_type}, Reason: {matched.reason}")
        else:
            print(f"  NOW FIXED: {s} <-> {t} (Kept separate)")

    # If there are new false positives:
    print(f"\nAll current false positives on forbidden relationships ({len(forbidden_fp)} total):")
    for r, actual in forbidden_fp:
        print(f"  FP: {r['relationship_id']} ({r['source_event_id']} <-> {r['target_event_id']}) Type in GT: {r['relationship_type']} | Actual: {actual.relationship_type} ({actual.reason})")

    # Section 5: Accuracy by category
    print("\n" + "-"*60)
    print("SECTION 5: ACCURACY BY CATEGORY")
    print("-" * 60)
    # Expected categories to evaluate:
    # Command -> Plan, Plan -> Message, Message -> ACK, State -> Fault, Fault -> Recovery, Repetition
    eval_categories = {
        "Command -> Plan": ["COMMAND_TO_PLAN"],
        "Plan -> Message": ["PLAN_TO_MESSAGE"],
        "Message -> ACK": ["MESSAGE_TO_ACK"],
        "State -> Fault": ["STATE_TO_FAULT"],
        "Fault -> Recovery": ["FAULT_TO_RECOVERY", "RECOVERY_TO_CLEAR"],
        "Repetition": ["REPEATED_FAULT_SAME_CONDITION", "REPEATED_WARNING", "RECURRENCE"],
        "Message Flow": ["MESSAGE_FLOW", "MESSAGE_COMPLETION"],
    }
    
    for cat_name, gt_types in eval_categories.items():
        cat_gt = [r for r in gt_rels if r.get("relationship_type") in gt_types and r.get("classification") in ["CONFIRMED", "POSSIBLE"]]
        tp_cat = 0
        fn_cat = 0
        for r in cat_gt:
            s, t = r["source_event_id"], r["target_event_id"]
            if (s, t) in gen_rel_map or (t, s) in gen_rel_map:
                tp_cat += 1
            else:
                fn_cat += 1
        # For FP, count generated edges corresponding to this logic that are either forbidden or ungrounded
        # A simple approximation: edges of this type that conflict with SHOULD_NOT_BE_CORRELATED
        fp_cat = sum(1 for r, actual in forbidden_fp if cat_name.upper() in str(actual.relationship_type).upper() or cat_name.upper() in actual.reason.upper())
        rec = tp_cat / len(cat_gt) if len(cat_gt) > 0 else 1.0
        prec = tp_cat / (tp_cat + fp_cat) if (tp_cat + fp_cat) > 0 else 1.0
        f1_cat = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        print(f"{cat_name}: GT={len(cat_gt)}, TP={tp_cat}, FN={fn_cat}, FP={fp_cat} | Precision={prec:.4f}, Recall={rec:.4f}, F1={f1_cat:.4f}")

    print("\n" + "="*80)
    print("SECTION 7: SAME-FAULT-CODE TEST")
    print("="*80)
    # Test FLT-8470 cases:
    # Case A: Same fault code, same incident
    # Case B: Same fault code, separate incident 1 hour later
    # Case C: Same fault code on different nodes
    print("Evaluating FLT-8470 occurrences across incidents...")
    flt_8470_events = [e for e in event_dicts if "FLT-8470" in (e.get("raw_record") or "")]
    print(f"Found {len(flt_8470_events)} events with FLT-8470:")
    for e in flt_8470_events:
        print(f"  {e['event_id']} on {e['node']} at {e['timestamp']} (line {e['source_line']})")
        
    # Check which incidents contain FLT-8470 events
    for inc in detected_incidents:
        flt_in_inc = [eid for eid in inc.event_ids if any(e['event_id'] == eid for e in flt_8470_events)]
        if flt_in_inc:
            print(f"  Incident {inc.incident_id} ({inc.kind}) contains FLT-8470 events: {flt_in_inc} on nodes {inc.involved_nodes}")

    print("\n" + "="*80)
    print("SECTION 8: TEMPORAL PROXIMITY SAFETY")
    print("="*80)
    # Check edges with STATE_TO_FAULT or 15-second proximity
    prox_edges = [r for r in rels if "15s proximity" in (r.reason or "").lower() or str(r.relationship_type) == "STATE_TO_FAULT"]
    print(f"Total temporal proximity / STATE_TO_FAULT edges: {len(prox_edges)}")
    for pe in prox_edges[:10]:
        print(f"  {pe.source_event_id} -> {pe.target_event_id} | Type: {pe.relationship_type} | Strength: {pe.strength} | Uncertainty: {pe.uncertainty} | Reason: {pe.reason}")

    print("\n" + "="*80)
    print("SECTION 9: MISSING-EVENT DETECTION")
    print("="*80)
    print(f"Total missing event findings generated: {len(missing)}")
    for m in missing:
        print(f"  Expected: {m.expected_event_type} at {m.expected_at_node} | After: {m.expected_after_event_id} | Desc: {m.description}")
        
    # Check GT missing events
    gt_missing_all = []
    for inc in gt_incidents:
        for me in inc.get("missing_expected_events", []):
            gt_missing_all.append((inc["incident_id"], me))
    print(f"\nGT missing expected events across all incidents: {len(gt_missing_all)}")
    for inc_id, me in gt_missing_all:
        print(f"  GT {inc_id}: {me}")

    print("\n" + "="*80)
    print("SECTION 12: PROMPT-INJECTION TEST")
    print("="*80)
    # Look for prompt injection records in GT and parsed events
    pi_gt = gt_inc_data.get("prompt_injection_like_records", [])
    print(f"GT prompt injection records: {len(pi_gt)}")
    for pi in pi_gt:
        print(f"  PI Record: {pi.get('raw_record')} (Line {pi.get('line')} in {pi.get('path')})")
        # Check if parsed as ordinary event
        matched_evt = next((e for e in event_dicts if e.get("source_line") == pi.get("line") and pi.get("path") in e.get("source_file", "").replace('\\', '/')), None)
        if matched_evt:
            print(f"    -> Parsed safely as: {matched_evt['event_id']}, event_type={matched_evt['event_type']}, severity={matched_evt['severity']}")
        else:
            print(f"    -> Not found in valid events (or skipped as malformed)")

if __name__ == "__main__":
    main()
