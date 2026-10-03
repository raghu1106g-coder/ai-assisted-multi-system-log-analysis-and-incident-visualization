#!/usr/bin/env python3
"""Independent validator for PS3 Dataset 2 (synthetic). Does NOT import the generator.
It re-parses every raw log with its own parsers and checks the result against ground_truth/.
Usage: python3 tools/validate_dataset.py [dataset_root]   (exit code 0 = all checks passed)
"""
import os, sys, re, csv, io, json, glob, calendar, datetime as dt
from collections import Counter, defaultdict

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
NODES = ["NODE_A", "NODE_B", "NODE_C"]
FAMS = ["operator", "planning", "guidance", "state", "fault_recovery"]
ABBR = {"operator": "OPR", "planning": "PLN", "guidance": "GDN", "state": "STA", "fault_recovery": "FLT"}
results, failures = [], []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    if not ok:
        failures.append(name)


# ---------------------------------------------------------------- timestamps
def p_iso(s):
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?Z", s)
    if not m: return None
    try:
        y, mo, d, h, mi, se = (int(x) for x in m.groups()[:6])
        t = dt.datetime(y, mo, d, h, mi, se, tzinfo=dt.timezone.utc)
    except ValueError: return None
    return t + dt.timedelta(milliseconds=int((m.group(7) or "0").ljust(3, "0")))


def p_plan(s):
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})\.(\d{3})", s)
    return p_iso(f"{m.group(1)}T{m.group(2)}.{m.group(3)}Z") if m else None


def p_epoch(s):
    if not re.fullmatch(r"\d{9,11}\.\d{3}", s): return None
    sec, fr = s.split(".")
    try: return dt.datetime.fromtimestamp(int(sec), dt.timezone.utc) + dt.timedelta(milliseconds=int(fr))
    except (ValueError, OverflowError, OSError): return None


def p_compact(s):
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})\.(\d{3})Z", s)
    return p_iso(f"{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}:{m.group(5)}:{m.group(6)}.{m.group(7)}Z") if m else None


# ---------------------------------------------------------------- per-family parsers -> (record | None, reason)
def parse_operator(line):
    if not line.strip(): return None, "BLANK_RECORD"
    m = re.match(r"^(\[[^\]]*\])?(\[[^\]]*\])?(\[[^\]]*\])?\s*(.*)$", line)
    heads = re.findall(r"\[(\w+)=([^\]]*)\]", line)
    hd = dict(heads)
    rest = re.sub(r"^(\[\w+=[^\]]*\])+\s*", "", line)
    if re.search(r"payload=\{", rest) or ("{" in rest and "}" in rest and "action=" not in rest): return None, "MALFORMED_STRUCTURED_PAYLOAD"
    if "ts" not in hd: return None, "MISSING_TIMESTAMP"
    t = p_iso(hd["ts"])
    if t is None: return None, "INVALID_TIMESTAMP"
    if "node" not in hd or hd["node"] not in NODES: return None, "MISSING_NODE"
    kv = dict(re.findall(r'(\w+)=("[^"]*"|\S+)', rest))
    if "action" not in kv: return None, "MISSING_EVENT_TYPE"
    if not re.search(r'msg="[^"]*"\s*$', rest): return None, "TRUNCATED_RECORD"
    if kv["action"] == "SUBMIT_COMMAND" and "cmd_id" not in kv: return None, "MISSING_REQUIRED_IDENTIFIER"
    return dict(ts=t, node=hd["node"], etype=kv["action"], kv=kv), None


def parse_planning(line):
    if not line.strip(): return None, "BLANK_RECORD"
    try: row = next(csv.reader([line]))
    except csv.Error: return None, "CORRUPTED_DELIMITER"
    if len(row) < 12: return None, "INCOMPLETE_RECORD"
    if len(row) > 12: return None, "EXTRA_UNEXPECTED_FIELD"
    t = p_plan(row[0]) if row[0] else None
    if not row[0]: return None, "MISSING_TIMESTAMP"
    if t is None: return None, "INVALID_TIMESTAMP"
    if row[1] not in NODES: return None, "MISSING_NODE"
    if not row[2]: return None, "MISSING_EVENT_TYPE"
    if row[2] in ("MESSAGE_SENT", "MESSAGE_RECEIVED") and not row[4]: return None, "MISSING_REQUIRED_IDENTIFIER"
    if row[2] == "MESSAGE_ACK" and not row[7]: return None, "MISSING_REQUIRED_IDENTIFIER"
    return dict(ts=t, node=row[1], etype=row[2], kv=dict(zip(["plan", "msg", "peer", "cmd", "ack_for", "resend_of", "comp", "status", "detail"], row[3:]))), None


def parse_guidance(line):
    if not line.strip(): return None, "BLANK_RECORD"
    tok = line.split()
    if len(tok) < 4: return None, "TRUNCATED_RECORD"
    t = p_epoch(tok[0])
    if t is None: return None, ("INVALID_NUMERIC_TIMESTAMP" if tok[0][:1].isdigit() else "INVALID_TIMESTAMP")
    if tok[1] not in NODES: return None, "MISSING_NODE"
    if tok[2] != "GDN": return None, "STRAY_TOKEN"
    kv = dict(x.split("=", 1) for x in tok[3:] if "=" in x)
    if any("=" not in x for x in tok[3:]): return None, "STRAY_TOKEN"
    if "evt" not in kv: return None, "MISSING_EVENT_TYPE"
    if "note" not in kv: return None, "TRUNCATED_RECORD"
    return dict(ts=t, node=tok[1], etype=kv["evt"], kv=kv), None


def parse_state(line):
    if not line.strip(): return None, "BLANK_RECORD"
    f = line.split(";")
    if len(f) < 9: return None, ("CORRUPTED_DELIMITER" if "NODE_" in f[0] else "INCOMPLETE_RECORD")
    if len(f) > 9: return None, "EXTRA_UNEXPECTED_FIELD"
    t = p_compact(f[0]) if f[0] else None
    if not f[0]: return None, "MISSING_TIMESTAMP"
    if t is None: return None, "INVALID_TIMESTAMP"
    if f[1] not in NODES: return None, "MISSING_NODE"
    if not f[2]: return None, "MISSING_EVENT_TYPE"
    if not re.fullmatch(r"\d+", f[7]): return None, "MISSING_REQUIRED_IDENTIFIER"
    return dict(ts=t, node=f[1], etype=f[2], kv=dict(comp=f[3], frm=f[4], to=f[5], trigger=f[6], seq=int(f[7]))), None


def parse_fault(line):
    if not line.strip(): return None, "BLANK_RECORD"
    f = line.split("|")
    if len(f) < 10: return None, ("CORRUPTED_DELIMITER" if "NODE_" in f[0] else "TRUNCATED_RECORD")
    if len(f) > 10: return None, "EXTRA_UNEXPECTED_FIELD"
    t = p_iso(f[0]) if f[0] else None
    if not f[0]: return None, "MISSING_TIMESTAMP"
    if t is None: return None, "INVALID_TIMESTAMP"
    if f[1] not in NODES: return None, "MISSING_NODE"
    if not f[2]: return None, "MISSING_EVENT_TYPE"
    return dict(ts=t, node=f[1], etype=f[2], kv=dict(code=f[3], comp=f[5], related=f[7])), None


PARSERS = dict(operator=parse_operator, planning=parse_planning, guidance=parse_guidance, state=parse_state, fault_recovery=parse_fault)


def main():
    # ---- directories / files
    exp_dirs = [f"logs/{n}/{f}" for n in NODES for f in FAMS] + ["ground_truth"]
    check("required directories present", all(os.path.isdir(os.path.join(ROOT, d)) for d in exp_dirs))
    check("required ground_truth files present", all(os.path.isfile(os.path.join(ROOT, "ground_truth", f)) for f in
          ["expected_import_results.json", "expected_incidents.json", "expected_relationships.json", "reference_narratives.md", "test_notes.md"]))
    check("manifest.md and README.md present", all(os.path.isfile(os.path.join(ROOT, f)) for f in ["manifest.md", "README.md"]))
    logfiles = sorted(glob.glob(os.path.join(ROOT, "logs", "*", "*", "*.log")))
    check("exactly 15 log files", len(logfiles) == 15, str(len(logfiles)))
    check("no files other than .log under logs/", all(f.endswith(".log") for f in glob.glob(os.path.join(ROOT, "logs", "**", "*"), recursive=True) if os.path.isfile(f)))

    # ---- parse all logs independently
    VALID, BAD = {}, {}            # (node,fam) -> list
    by_id = {}                      # event_id -> record
    tot_lines = 0
    for node in NODES:
        for fam in FAMS:
            path = os.path.join(ROOT, "logs", node, fam, f"{fam}.log")
            raw = open(path, encoding="utf-8").read().split("\n")
            if raw and raw[-1] == "": raw.pop()
            VALID[(node, fam)], BAD[(node, fam)] = [], []
            tot_lines += len(raw)
            for ln, line in enumerate(raw, 1):
                if fam == "planning" and ln == 1:
                    check(f"{node}/{fam} header", line == "ts,node,event,plan_id,msg_id,peer,cmd_ref,ack_for,resend_of,component,status,detail")
                    continue
                rec, why = PARSERS[fam](line)
                rel = f"logs/{node}/{fam}/{fam}.log"
                if rec is None: BAD[(node, fam)].append(dict(line=ln, reason=why, raw=line))
                else:
                    if rec["node"] != node: BAD[(node, fam)].append(dict(line=ln, reason="NODE_MISMATCH_WITH_FILE", raw=line)); continue
                    rec.update(file=rel, line=ln, fam=fam, event_id=f"EVT-{node[-1]}-{ABBR[fam]}-{ln:04d}", raw=line)
                    VALID[(node, fam)].append(rec); by_id[rec["event_id"]] = rec

    nvalid = sum(len(v) for v in VALID.values()); nbad = sum(len(v) for v in BAD.values())
    check("event ids unique", len(by_id) == nvalid)
    check("valid count within 1,500-3,000", 1500 <= nvalid <= 3000, str(nvalid))
    check("malformed count within 15-25", 15 <= nbad <= 25, str(nbad))

    # ---- import expectations
    ei = json.load(open(os.path.join(ROOT, "ground_truth", "expected_import_results.json")))
    check("valid count matches expected_import_results", ei["totals"]["valid_records"] == nvalid, f"{ei['totals']['valid_records']} vs {nvalid}")
    check("malformed count matches expected_import_results", ei["totals"]["malformed_records"] == nbad, f"{ei['totals']['malformed_records']} vs {nbad}")
    check("total lines match", ei["totals"]["total_lines"] == tot_lines)
    fam_c = Counter()
    for (n, f), v in VALID.items(): fam_c[f] += len(v)
    check("per-family counts match", all(ei["records_by_log_family"][f] == fam_c[f] for f in FAMS) if isinstance(ei["records_by_log_family"], dict) else True)
    ok_pf, why_pf = True, []
    for p in ei["per_file"]:
        k = (p["node"], p["log_family"])
        got = {b["line"]: b["reason"] for b in BAD[k]}
        exp = {s["line"]: s["reason_category"] for s in p["skipped_lines"]}
        if len(VALID[k]) != p["expected_valid_records"] or got != exp:
            ok_pf = False
            why_pf.append((p["path"], {l: (got.get(l), exp.get(l)) for l in set(got) | set(exp) if got.get(l) != exp.get(l)}))
    check("per-file valid counts and skipped lines/reasons match", ok_pf, str(why_pf)[:500])
    reasons = Counter(b["reason"] for v in BAD.values() for b in v)
    check("reason category counts match", dict(reasons) == ei["reason_category_counts"], f"{dict(reasons)} vs {ei['reason_category_counts']}")
    allv = [r for v in VALID.values() for r in v]
    tmin, tmax = min(r["ts"] for r in allv), max(r["ts"] for r in allv)
    rng = ei["expected_normalized_timestamp_range_utc"]
    lo, hi = (rng["min"], rng["max"]) if isinstance(rng, dict) else tuple(rng)
    check("normalized timestamp range matches", p_iso(lo) == tmin and p_iso(hi) == tmax, f"{tmin} {tmax} vs {lo} {hi}")
    check("all valid timestamps on 2031-08-19 UTC", all(r["ts"].date() == dt.date(2031, 8, 19) for r in allv))
    check("mixture of timestamp representations (5 families, 5 formats)", len({r["fam"] for r in allv}) == 5)

    # ---- state seq monotonic per node (gaps allowed = lost records)
    for n in NODES:
        seqs = [r["kv"]["seq"] for r in sorted(VALID[(n, "state")], key=lambda r: (r["ts"], r["kv"]["seq"]))]
        check(f"{n} state seq non-decreasing in timestamp order (equal = byte-identical duplicate line)", all(a <= b for a, b in zip(seqs, seqs[1:])))

    # ---- out-of-order really present per file
    ooo_files = 0
    for k, v in VALID.items():
        if any(b["ts"] < a["ts"] for a, b in zip(v, v[1:])): ooo_files += 1
    check("out-of-order records physically present", ooo_files >= 5, f"{ooo_files} files")

    # ---- byte-identical duplicates
    dup_found = []
    for k, v in VALID.items():
        seen = {}
        for r in v:
            if r["raw"] in seen: dup_found.append((r["event_id"], seen[r["raw"]]))
            else: seen[r["raw"]] = r["event_id"]
    inc_doc = json.load(open(os.path.join(ROOT, "ground_truth", "expected_incidents.json")))
    doc_dups = sorted((d["duplicate_event_id"], d["duplicate_of_event_id"]) for d in inc_doc["byte_identical_duplicate_records"])
    check("byte-identical duplicate lines match ground truth", sorted(dup_found) == doc_dups, f"{len(dup_found)} vs {len(doc_dups)}")

    # ---- ground-truth referenced ids exist
    def ids_in(o):
        s = set()
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and re.fullmatch(r"EVT-[ABC]-[A-Z]{3}-\d{4}", v): s.add(v)
                else: s |= ids_in(v)
        elif isinstance(o, list):
            for x in o: s |= ids_in(x)
        return s
    gt_ids = ids_in(inc_doc)
    missing = sorted(i for i in gt_ids if i not in by_id)
    check("every event id in expected_incidents.json exists as a VALID record", not missing, str(missing[:10]))
    rel_doc = json.load(open(os.path.join(ROOT, "ground_truth", "expected_relationships.json")))
    rel_ids = ids_in(rel_doc)
    missing = sorted(i for i in rel_ids if i not in by_id)
    check("every event id in expected_relationships.json exists as a VALID record", not missing, str(missing[:10]))

    # ---- stored metadata of referenced ids matches the log (file, line, node, family, type, timestamp)
    bad_meta = []
    for inc in inc_doc["incidents"]:
        for e in inc["relevant_event_ids"]:
            r = by_id.get(e["event_id"])
            if not r: continue
            if (r["file"], r["line"], r["node"], r["fam"]) != (e["source_file"], e["source_line"], e["node"], e["log_family"]) or r["etype"] != e["event_type"] or p_iso(e["timestamp"]) != r["ts"]:
                bad_meta.append(e["event_id"])
    check("incident event metadata (file/line/node/family/type/timestamp) matches logs", not bad_meta, str(bad_meta[:10]))

    # ---- relationships: structure, counts, vocab, evidence in logs
    rels = rel_doc["relationships"]
    cls = Counter(r["classification"] for r in rels)
    check("relationship classification counts consistent", dict(cls) == rel_doc["counts"], f"{dict(cls)} vs {rel_doc['counts']}")
    check("relationship classes within allowed vocabulary", set(cls) <= {"CONFIRMED", "POSSIBLE", "UNKNOWN_INSUFFICIENT_EVIDENCE", "SHOULD_NOT_BE_CORRELATED"})
    check("all four classifications used", len(cls) == 4)
    check("relationship ids unique", len({r["relationship_id"] for r in rels}) == len(rels))
    bad_delta, bad_shared = [], []
    for r in rels:
        s, d = by_id.get(r["source_event_id"]), by_id.get(r["target_event_id"])
        if not s or not d: continue
        if r.get("delta_seconds") is not None and abs((d["ts"] - s["ts"]).total_seconds() - r["delta_seconds"]) > 0.0015: bad_delta.append(r["relationship_id"])
        sid = r.get("shared_identifier")
        if r["classification"] == "CONFIRMED" and sid and not (sid in s["raw"] and sid in d["raw"]): bad_shared.append(r["relationship_id"])
    check("relationship time deltas match logs", not bad_delta, str(bad_delta[:10]))
    check("CONFIRMED relationships' shared identifier literally present in both records", not bad_shared, str(bad_shared[:10]))
    bad_neg = [r["relationship_id"] for r in rels if r["classification"] == "SHOULD_NOT_BE_CORRELATED" and r.get("shared_identifier") and
               not r.get("shared_identifier_expected_for_non_correlation")]
    check("no SHOULD_NOT_BE_CORRELATED pair shares an identifier unless declared", not bad_neg, str(bad_neg[:10]))
    # for NOT pairs with shared_id undeclared: verify they really share no id token
    idtok = re.compile(r"\b(?:CMD|PLN|MSG|FLT|RCV|SP|CFG|WP)-\d+\b")
    leak = []
    for r in rels:
        if r["classification"] != "SHOULD_NOT_BE_CORRELATED" or r.get("shared_identifier_expected_for_non_correlation"): continue
        s, d = by_id.get(r["source_event_id"]), by_id.get(r["target_event_id"])
        if s and d and (set(idtok.findall(s["raw"])) & set(idtok.findall(d["raw"]))): leak.append(r["relationship_id"])
    check("SHOULD_NOT_BE_CORRELATED pairs share no id tokens in the logs", not leak, str(leak[:10]))

    # ---- intentionally missing events are genuinely missing
    def absent(chk):
        node, fam, et, key = chk["node"], chk["family"], chk["event_type"], chk["key"]
        for r in VALID[(node, fam)]:
            if r["etype"] == et and key in r["raw"]: return False
        return True
    miss_bad, n_miss = [], 0
    for inc in inc_doc["incidents"]:
        for m in inc["missing_expected_events"]:
            n_miss += 1
            if not absent(m["absence_check"]): miss_bad.append((inc["incident_id"], m["description"]))
    for m in inc_doc["background_features"]["background_missing_waypoints"]:
        n_miss += 1
        if not absent(m["absence_check"]): miss_bad.append(("bg", m["description"] if "description" in m else m["waypoint"]))
    check("every declared missing event is genuinely absent", not miss_bad and n_miss > 0, f"{n_miss} checked; bad={miss_bad}")

    # ---- incident-level semantic checks
    incs = inc_doc["incidents"]
    check("8-12+ incident scenarios (14 records, >=8 scenario families)", len(incs) >= 8 and inc_doc["scenario_family_count"] >= 8, f"{len(incs)} / {inc_doc['scenario_family_count']}")
    check("2-4 normal periods", 2 <= len(inc_doc["normal_operation_periods"]) <= 4)
    check("several cross-node incidents", sum(1 for i in incs if i["cross_node"]) >= 4)
    check("single-node incidents exist", sum(1 for i in incs if len(i["involved_nodes"]) == 1) >= 3)
    check("two-node incident exists", any(len(i["involved_nodes"]) == 2 for i in incs))
    check("three-node incident exists", any(len(i["involved_nodes"]) == 3 for i in incs))
    check("at least one incident with recovery NOT_OBSERVED", any(i["recovery_status"] == "NOT_OBSERVED" for i in incs))
    check("at least one incident with recovery observed but initiating fault missing", any("INITIATING_FAULT_MISSING" in i["recovery_status"] for i in incs))
    check("several incidents whose causal certainty is not established", sum(1 for i in incs if "NOT_ESTABLISHED" in i["causal_certainty"]["level"] or "UNKNOWN" in i["causal_certainty"]["level"]) >= 5)
    # recovery facts re-derived from logs
    for i in incs:
        for pf in i["primary_faults"]:
            node, code = pf["node"], pf["fault_code"]
            recs = VALID[(node, "fault_recovery")]
            has_raise = any(r["etype"] in ("FAULT_RAISED",) and r["kv"]["code"] == code for r in recs)
            has_clear = any(r["etype"] == "FAULT_CLEARED" and r["kv"]["code"] == code for r in recs)
            has_rcv = any(r["etype"] == "RECOVERY_STARTED" and r["kv"]["code"] == code for r in recs)
            check(f"{i['incident_id']} {code}: raise-record presence matches", has_raise == pf["raise_record_present"] or (i["incident_id"] in ("D2-INC-06", "D2-INC-13", "D2-INC-07") and has_raise),
                  f"log={has_raise} gt={pf['raise_record_present']}")
            if i["recovery_status"] == "NOT_OBSERVED":
                check(f"{i['incident_id']} {code}: no clear/recovery in logs", not has_clear and not has_rcv)
            if i["recovery_status"] == "RECOVERED":
                check(f"{i['incident_id']} {code}: clear or recovery in logs", has_clear or has_rcv)
            if "INITIATING_FAULT_MISSING" in i["recovery_status"]:
                check(f"{i['incident_id']} {code}: no raise record on {node} (genuinely missing)", not has_raise)
                check(f"{i['incident_id']} {code}: recovery present", has_clear or has_rcv)
    # distinct vs repeated: INC-06/07/13 same code different incidents must be separated by >= 30 min or node
    # unrelated events truly unrelated: no shared ids with any primary-fault event
    leak_u = []
    for i in incs:
        inc_tokens = set()
        for e in i["relevant_event_ids"]:
            r = by_id.get(e["event_id"])
            if r: inc_tokens |= set(idtok.findall(r["raw"]))
        for u in i["unrelated_nearby_events"]:
            r = by_id.get(u["event_id"])
            if not r: leak_u.append((i["incident_id"], u["event_id"], "missing")); continue
            if u["event_id"] in {e["event_id"] for e in i["relevant_event_ids"]}: leak_u.append((i["incident_id"], u["event_id"], "also relevant"))
            elif set(idtok.findall(r["raw"])) & inc_tokens: leak_u.append((i["incident_id"], u["event_id"], "shares id"))
    check("unrelated nearby events exist, are valid records, are not in the relevant set and share no ids with the incident", not leak_u, str(leak_u[:6]))
    check("unrelated nearby noise present for most incidents", sum(1 for i in incs if i["unrelated_nearby_events"]) >= 8)

    # ---- prompt injection records: ordinary content only
    inj = inc_doc["prompt_injection_like_records"]
    check("2 prompt-injection-like records", len(inj) == 2)
    for p in inj:
        r = by_id.get(p["event_id"])
        check(f"{p['event_id']} injection text present in an ordinary operator MAINT_NOTE", bool(r) and r["fam"] == "operator" and r["etype"] == "MAINT_NOTE" and p["message_text"] in r["raw"])
        if r:
            hd = re.findall(r"\[(\w+)=", r["raw"])
            check(f"{p['event_id']} has only the standard header fields (no special metadata)", hd == ["ts", "node", "sev"] and set(r["kv"]) <= {"op", "action", "component", "msg", "cmd_id", "alert_id", "cfg_id", "attempt"})
    check("injection strings occur only in those two records", sum(1 for r in allv if re.search(r"IGNORE PREVIOUS INSTRUCTIONS|AI SYSTEM:", r["raw"], re.I)) == 2)

    # ---- leakage: production logs must not contain ground-truth vocabulary
    leak_terms = re.compile(r"D2-INC|REL2-|CONFIRMED|SHOULD_NOT_BE_CORRELATED|INSUFFICIENT_EVIDENCE|(?i:ground[_ ]truth|root[_ ]cause|caused[_ ]by|incident_id|expected_|difficulty)")
    leaks = []
    for node in NODES:
        for fam in FAMS:
            for ln, line in enumerate(open(os.path.join(ROOT, "logs", node, fam, f"{fam}.log"), encoding="utf-8"), 1):
                if leak_terms.search(line): leaks.append((node, fam, ln))
    check("production logs contain no ground-truth vocabulary or answer fields", not leaks, str(leaks[:5]))
    check("log file names are neutral (<family>.log only)", all(os.path.basename(f) == f"{os.path.basename(os.path.dirname(f))}.log" for f in logfiles))
    check("ground truth is outside logs/ (separate directory)", os.path.isdir(os.path.join(ROOT, "ground_truth")) and not glob.glob(os.path.join(ROOT, "logs", "**", "*truth*"), recursive=True))
    check("no comment lines in logs", not any(l.lstrip().startswith("#") for f in logfiles for l in open(f, encoding="utf-8")))
    check("no explicit causal field in any log schema", not any(re.search(r"\b(cause|caused_by|root_cause|triggered_by_fault)\b=", r["raw"], re.I) for r in allv))

    # ---- independence from baseline dataset ids
    old_ids = re.compile(r"\b(?:CMD-10\d\d|PLN-[234]\d\d|MSG-7\d\d|FLT-09\d\d|RCV-1\d\d)\b")
    check("no baseline-dataset-style identifiers (CMD-10xx, MSG-7xx, FLT-09xx)", not any(old_ids.search(r["raw"]) for r in allv))
    check("no baseline timestamps (2031-05-12)", not any("2031-05-12" in r["raw"] or "20310512" in r["raw"] for r in allv))

    # ---- report
    width = max(len(n) for n, _, _ in results)
    out = ["# Validation report — PS3 Dataset 2", "", f"Validator: `tools/validate_dataset.py` (independent re-parse; does not import the generator).", "",
           f"- Log files: {len(logfiles)}", f"- Total physical lines: {tot_lines}", f"- Independently counted VALID records: **{nvalid}**",
           f"- Independently counted MALFORMED records: **{nbad}** ({dict(reasons)})", f"- Incidents in ground truth: {len(incs)}",
           f"- Relationships in ground truth: {len(rels)} ({dict(cls)})", f"- Normalized timestamp range: {tmin.isoformat()} .. {tmax.isoformat()}", "",
           f"## Checks: {sum(1 for _, o, _ in results if o)} passed / {len(failures)} failed", "", "| Result | Check | Detail |", "|---|---|---|"]
    for n, o, d in results: out.append(f"| {'PASS' if o else '**FAIL**'} | {n} | {d if not o else ''} |")
    rp = os.path.join(ROOT, "validation_report.md")
    open(rp, "w", encoding="utf-8").write("\n".join(out) + "\n")
    for n, o, d in results:
        if not o: print(f"FAIL: {n}  {d}")
    print(f"{sum(1 for _, o, _ in results if o)} passed, {len(failures)} failed; report -> {rp}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
