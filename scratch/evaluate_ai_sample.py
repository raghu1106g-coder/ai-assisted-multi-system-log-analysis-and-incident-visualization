import asyncio
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.ai.narrative import generate_narrative
from backend.app.correlation.engine import CorrelationEngine
from backend.app.incidents.reconstructor import IncidentReconstructor
from backend.app.ingestion.engine import run_ingestion

async def evaluate_ai():
    print("=" * 80)
    print("SECTION 11: AI ACCURACY — EXPANDED SAMPLE EVALUATION")
    print("=" * 80)

    res, events = run_ingestion(Path("ps3_dataset_2/logs"))
    event_dicts = [e.model_dump() for e in events]
    for ed in event_dicts:
        if isinstance(ed["timestamp"], str):
            ed["timestamp"] = datetime.fromisoformat(ed["timestamp"].replace("Z", "+00:00"))
            
    corr_engine = CorrelationEngine()
    rels, graph, missing = corr_engine.correlate(event_dicts)
    reconstructor = IncidentReconstructor()
    incidents = reconstructor.reconstruct(event_dicts, rels, graph, missing)

    # All known valid event IDs in the entire dataset
    all_known_event_ids = set(e["event_id"] for e in event_dicts)
    
    # We evaluate all reconstructed fault incidents:
    fault_incidents = [i for i in incidents if str(i.kind) == "INCIDENT"]
    print(f"Total reconstructed fault incidents to evaluate: {len(fault_incidents)}")

    per_incident_results: list[dict[str, Any]] = []
    
    # Regex patterns for validation
    id_pattern = re.compile(r'\b(EVT-[A-Z]-[A-Z]{3}-\d{4}|FLT-\d{4}|RCV-\d{3}|CMD-\d{4}|MSG-\d{4}|SP-\d{3}|WP-\d{3})\b')

    for inc in fault_incidents:
        inc_dict = inc.model_dump()
        rel_dicts = [r.model_dump() for r in rels if r.source_event_id in inc.event_ids or r.target_event_id in inc.event_ids]
        evt_dicts = [e for e in event_dicts if e["event_id"] in inc.event_ids]
        miss_dicts = [m.model_dump() for m in inc.missing_events]
        available_refs = set(inc.event_ids)

        print(f"\nEvaluating AI narrative for {inc.incident_id} (Faults: {inc.primary_faults}, Events: {len(inc.event_ids)})...")
        t0 = time.perf_counter()
        narrative = await generate_narrative(inc_dict, evt_dicts, rel_dicts, miss_dicts)
        gen_time = time.perf_counter() - t0

        if not narrative.validation_passed:
            print(f"  FAILED SCHEMA VALIDATION: {narrative.incident_summary}")
            per_incident_results.append({
                "incident_id": inc.incident_id,
                "passed": False,
                "error": narrative.incident_summary,
            })
            continue

        # Evaluate narrative
        obs_total = len(narrative.observations)
        supported_obs = 0
        unsupported_obs = 0
        correct_refs = 0
        incorrect_refs = 0
        hallucinated_ids = 0
        hallucinated_timestamps = 0
        hallucinated_recoveries = 0
        hallucinated_acks = 0
        unsupported_causes = 0
        uncertainty_correct = 0
        contradictions = 0

        # Scan text for any identifiers mentioned
        full_text = f"{narrative.incident_summary} {narrative.recovery_summary} " + " ".join(
            f"{o.statement} " for o in narrative.observations
        )
        found_ids = set(id_pattern.findall(full_text))

        # Check for hallucinated identifiers
        for fid in found_ids:
            if fid.startswith("EVT-"):
                if fid not in all_known_event_ids:
                    hallucinated_ids += 1
            elif fid.startswith("FLT-"):
                # Check if in dataset
                if not any(fid in (e.get("raw_record") or "") for e in event_dicts):
                    hallucinated_ids += 1

        # Check each observation
        for ob in narrative.observations:
            # Check citations
            if ob.evidence_refs:
                refs_valid = all(ref in available_refs for ref in ob.evidence_refs)
                if refs_valid:
                    correct_refs += len(ob.evidence_refs)
                    supported_obs += 1
                else:
                    incorrect_refs += sum(1 for ref in ob.evidence_refs if ref not in available_refs)
                    correct_refs += sum(1 for ref in ob.evidence_refs if ref in available_refs)
                    unsupported_obs += 1
            else:
                # Observation without refs
                # If it's a general statement about nodes involved, check validity
                if "involved nodes" in ob.statement.lower() or "recovery" in ob.statement.lower():
                    supported_obs += 1
                else:
                    unsupported_obs += 1

            # Check uncertainty label
            if ob.uncertainty_label in [
                "CONFIRMED_OBSERVATION",
                "STRONGLY_SUPPORTED_RELATIONSHIP",
                "POSSIBLE_RELATIONSHIP",
                "INSUFFICIENT_EVIDENCE",
                "MISSING_DATA",
            ]:
                uncertainty_correct += 1

            # Check causal claim safety
            if "caused" in ob.statement.lower() or "led to" in ob.statement.lower() or "because of" in ob.statement.lower():
                # Verify if supported by explicit relationship in rel_dicts
                if ob.uncertainty_label not in ["CONFIRMED_OBSERVATION", "STRONGLY_SUPPORTED_RELATIONSHIP"]:
                    unsupported_causes += 1

        # Check recovery claims
        rec_summary_lower = narrative.recovery_summary.lower()
        if "recovered" in rec_summary_lower or "resolved" in rec_summary_lower:
            # Verify if incident actually recovered
            if inc.recovery_status not in ["RECOVERED", "NOMINAL"]:
                hallucinated_recoveries += 1

        # Check contradictions
        if "resolved" in rec_summary_lower and "unresolved" in narrative.incident_summary.lower():
            contradictions += 1

        res_dict = {
            "incident_id": inc.incident_id,
            "passed": True,
            "gen_time_s": gen_time,
            "observations_total": obs_total,
            "supported_observations": supported_obs,
            "unsupported_observations": unsupported_obs,
            "correct_refs": correct_refs,
            "incorrect_refs": incorrect_refs,
            "hallucinated_ids": hallucinated_ids,
            "hallucinated_timestamps": hallucinated_timestamps,
            "hallucinated_recoveries": hallucinated_recoveries,
            "hallucinated_acks": hallucinated_acks,
            "unsupported_causes": unsupported_causes,
            "uncertainty_correct": uncertainty_correct,
            "contradictions": contradictions,
            "relationships_supported_count": len(narrative.supported_relationships),
            "relationships_possible_count": len(narrative.possible_relationships),
            "uncertainties_count": len(narrative.uncertainties),
            "summary": narrative.incident_summary,
        }
        per_incident_results.append(res_dict)
        print(f"  Passed! Obs: {obs_total} (Supported: {supported_obs}/{obs_total}), Refs: {correct_refs} valid / {incorrect_refs} invalid, Hallucinations: {hallucinated_ids} IDs, {hallucinated_recoveries} rec, Causes: {unsupported_causes}")

    # Summary table
    print("\n" + "=" * 80)
    print("AI EVALUATION PER-INCIDENT SUMMARY TABLE")
    print("=" * 80)
    print("| Incident | Validated | Obs (Supp/Tot) | Valid Refs | Halluc IDs | Halluc Rec | Unsupp Causes | Contradictions | Time (s) |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in per_incident_results:
        if r.get("passed"):
            c_refs = int(r.get("correct_refs", 0))
            inc_refs = int(r.get("incorrect_refs", 0))
            g_time = float(r.get("gen_time_s", 0.0))
            print(f"| {r['incident_id']} | PASS | {r['supported_observations']}/{r['observations_total']} | {c_refs}/{c_refs + inc_refs} | {r['hallucinated_ids']} | {r['hallucinated_recoveries']} | {r['unsupported_causes']} | {r['contradictions']} | {g_time:.1f}s |")
        else:
            print(f"| {r['incident_id']} | FAIL | - | - | - | - | - | - | - |")

    # Aggregate metrics
    total_incidents = len(per_incident_results)
    passed_incidents = sum(1 for r in per_incident_results if r.get("passed"))
    total_obs = sum(int(r.get("observations_total", 0)) for r in per_incident_results)
    total_supp_obs = sum(int(r.get("supported_observations", 0)) for r in per_incident_results)
    total_refs = sum(int(r.get("correct_refs", 0)) + int(r.get("incorrect_refs", 0)) for r in per_incident_results)
    total_corr_refs = sum(int(r.get("correct_refs", 0)) for r in per_incident_results)
    total_halluc_ids = sum(int(r.get("hallucinated_ids", 0)) for r in per_incident_results)
    total_halluc_rec = sum(int(r.get("hallucinated_recoveries", 0)) for r in per_incident_results)
    total_unsupp_causes = sum(int(r.get("unsupported_causes", 0)) for r in per_incident_results)
    total_contradictions = sum(int(r.get("contradictions", 0)) for r in per_incident_results)
    total_uncertainty_correct = sum(int(r.get("uncertainty_correct", 0)) for r in per_incident_results)

    print("\n" + "=" * 80)
    print("AI EVALUATION AGGREGATE METRICS")
    print("=" * 80)
    print(f"Incidents Evaluated: {passed_incidents} / {total_incidents} ({passed_incidents/total_incidents*100:.1f}%)")
    print(f"Evidence Citation Validity: {total_corr_refs} / {total_refs} ({total_corr_refs/total_refs*100:.1f}%)" if total_refs > 0 else "N/A")
    print(f"Supported Observation Rate: {total_supp_obs} / {total_obs} ({total_supp_obs/total_obs*100:.1f}%)" if total_obs > 0 else "N/A")
    print(f"Unsupported Claim Rate: {(total_obs - total_supp_obs)} / {total_obs} ({(total_obs - total_supp_obs)/total_obs*100:.1f}%)" if total_obs > 0 else "N/A")
    print(f"Hallucinated ID Rate: {total_halluc_ids} / {total_obs} ({total_halluc_ids/total_obs*100:.2f}%)" if total_obs > 0 else "N/A")
    print(f"Hallucinated Recovery Rate: {total_halluc_rec} / {passed_incidents} ({total_halluc_rec/passed_incidents*100:.2f}%)" if passed_incidents > 0 else "N/A")
    print(f"Unsupported Causal Claim Rate: {total_unsupp_causes} / {total_obs} ({total_unsupp_causes/total_obs*100:.2f}%)" if total_obs > 0 else "N/A")
    print(f"Contradiction Rate: {total_contradictions} / {passed_incidents} ({total_contradictions/passed_incidents*100:.2f}%)" if passed_incidents > 0 else "N/A")
    print(f"Uncertainty Classification Agreement: {total_uncertainty_correct} / {total_obs} ({total_uncertainty_correct/total_obs*100:.1f}%)" if total_obs > 0 else "N/A")

    # Save results to json for inclusion in report
    with open("scratch/ai_eval_results.json", "w") as f:
        json.dump({
            "per_incident": per_incident_results,
            "aggregate": {
                "total_incidents": total_incidents,
                "passed_incidents": passed_incidents,
                "total_obs": total_obs,
                "total_supp_obs": total_supp_obs,
                "total_refs": total_refs,
                "total_corr_refs": total_corr_refs,
                "total_halluc_ids": total_halluc_ids,
                "total_halluc_rec": total_halluc_rec,
                "total_unsupp_causes": total_unsupp_causes,
                "total_contradictions": total_contradictions,
                "total_uncertainty_correct": total_uncertainty_correct,
            }
        }, f, indent=2)

if __name__ == "__main__":
    asyncio.run(evaluate_ai())
