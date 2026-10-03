import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.ingestion.engine import run_ingestion
from backend.app.models.event import LogFamily

def eval_d2():
    print("=" * 60)
    print("SECTION 1: DATASET 2 IMPORT VALIDATION")
    print("=" * 60)
    
    res_d2, events_d2 = run_ingestion(Path("ps3_dataset_2/logs"))
    
    with open("ps3_dataset_2/ground_truth/expected_import_results.json", "r") as f:
        gt_d2 = json.load(f)
        
    print(f"Total files processed: {res_d2.files_processed} (Expected: {gt_d2['totals']['files']})")
    print(f"Total physical lines: {res_d2.total_lines_read} (Expected: {gt_d2['totals']['total_lines']})")
    print(f"CSV headers: 3 (Expected: {gt_d2['totals']['header_lines']})")
    print(f"Valid records expected: {gt_d2['totals']['valid_records']}")
    print(f"Valid records actual: {res_d2.valid_records}")
    print(f"Malformed records expected: {gt_d2['totals']['malformed_records']}")
    print(f"Malformed records caught: {res_d2.skipped_records}")
    
    # Calculate malformed detection recall
    tp_malformed = res_d2.skipped_records
    total_malformed = gt_d2['totals']['malformed_records']
    fn_malformed = total_malformed - tp_malformed
    # Note: valid records actual is 1568. GT valid is 1568.
    # Wait, if 1 malformed record was accepted, how many valid records were expected?
    # Notice: GT says valid_records: 1568, malformed: 24.
    # Total lines: 1595. Headers: 3. 1595 - 3 = 1592 total data records!
    # 1568 + 24 = 1592!
    # If 23 malformed caught and valid records actual = 1568:
    # Wait, did we reject a valid record or what?
    # Let's check per-file!
    print("\n--- Per File Comparison ---")
    gt_map = {item['path'].replace('\\', '/'): item for item in gt_d2['per_file']}
    
    for f_info in res_d2.file_stats:
        rel_path = f_info['file'].replace('\\', '/')
        # Find matching GT entry
        gt_entry = None
        for gt_path, entry in gt_map.items():
            if gt_path in rel_path or rel_path.endswith(gt_path):
                gt_entry = entry
                break
        
        ev_exp = gt_entry.get('expected_valid_records') if gt_entry else '?'
        em_exp = gt_entry.get('expected_malformed_records') if gt_entry else '?'
        lines_exp = gt_entry.get('total_lines') if gt_entry else '?'
        
        status = "MATCH"
        if f_info['valid_records'] != ev_exp or f_info['skipped_records'] != em_exp:
            status = "MISMATCH"
            
        print(f"[{status}] {rel_path}:")
        print(f"   Actual: valid={f_info['valid_records']}, skipped={f_info['skipped_records']}, lines={f_info['lines_read']}")
        print(f"   GT:     valid={ev_exp}, malformed={em_exp}, lines={lines_exp}")

    # Find the undetected malformed record
    print("\n--- Ground Truth Malformed vs Caught ---")
    all_caught_lines = set()
    for err in res_d2.errors:
        clean_file = err.source_file.replace('\\', '/')
        all_caught_lines.add((clean_file, err.source_line))
        
    undetected = []
    for item in gt_d2['per_file']:
        gt_p = item['path'].replace('\\', '/')
        for sk in item.get('skipped_lines', []):
            line_no = sk['line']
            # see if caught
            matched = any(gt_p in cf and cl == line_no for cf, cl in all_caught_lines)
            if not matched:
                undetected.append((gt_p, line_no, sk))
                
    print(f"Total GT malformed: {gt_d2['totals']['malformed_records']}")
    print(f"Total caught: {len(res_d2.errors)}")
    print(f"Undetected count: {len(undetected)}")
    for p, l, sk in undetected:
        print(f"UNDETECTED: {p}:{l}")
        print(f"   Category: {sk.get('reason_category')}")
        print(f"   Detection Level: {sk.get('detection_level')}")
        print(f"   Raw: {sk.get('raw_record')}")

    # Let's inspect errors caught
    print("\n--- Errors Caught Breakdown by Family & Reason ---")
    for err in res_d2.errors:
        print(f"Line {err.source_line} in {err.source_file}: {err.reason}")

    # Check node counts
    node_counts = {}
    family_counts = {}
    for ev in events_d2:
        node_counts[ev.node] = node_counts.get(ev.node, 0) + 1
        fam = ev.log_family.value if hasattr(ev.log_family, 'value') else str(ev.log_family)
        family_counts[fam] = family_counts.get(fam, 0) + 1
        
    print("\n--- Node Counts ---")
    print("Actual:", node_counts)
    print("Expected:", gt_d2['records_by_node'])
    
    print("\n--- Family Counts ---")
    print("Actual:", family_counts)
    print("Expected:", gt_d2['records_by_log_family'])

    # Source-file traceability check
    all_traced = all(ev.source_file and ev.source_line > 0 for ev in events_d2)
    print(f"\nSource-file traceability: {'100% VERIFIED' if all_traced else 'FAILED'}")

def eval_d1():
    print("\n" + "=" * 60)
    print("SECTION 2: DATASET 1 REGRESSION TEST")
    print("=" * 60)
    
    res_d1, events_d1 = run_ingestion(Path("data/synthetic"))
    print(f"Dataset 1 Processed: {res_d1.files_processed} files")
    print(f"Total lines read: {res_d1.total_lines_read}")
    print(f"Valid records actual: {res_d1.valid_records}")
    print(f"Skipped records actual: {res_d1.skipped_records}")
    
    # Check D1 ground truth if present
    gt_d1_path = Path("ground_truth/expected_import_results.json")
    if gt_d1_path.exists():
        with open(gt_d1_path, "r") as f:
            gt_d1 = json.load(f)
        print("D1 GT:", json.dumps(gt_d1.get("totals", gt_d1.get("summary", {})), indent=2))
        print("D1 GT per family:", json.dumps(gt_d1.get("records_by_log_family", {}), indent=2))
        print("D1 GT per node:", json.dumps(gt_d1.get("records_by_node", {}), indent=2))
    
    # Node counts and family counts for D1
    node_counts = {}
    family_counts = {}
    for ev in events_d1:
        node_counts[ev.node] = node_counts.get(ev.node, 0) + 1
        fam = ev.log_family.value if hasattr(ev.log_family, 'value') else str(ev.log_family)
        family_counts[fam] = family_counts.get(fam, 0) + 1
        
    print("D1 Node counts:", node_counts)
    print("D1 Family counts:", family_counts)
    
    all_traced = all(ev.source_file and ev.source_line > 0 for ev in events_d1)
    print(f"D1 Source-file traceability: {'100% VERIFIED' if all_traced else 'FAILED'}")

if __name__ == "__main__":
    eval_d2()
    eval_d1()
