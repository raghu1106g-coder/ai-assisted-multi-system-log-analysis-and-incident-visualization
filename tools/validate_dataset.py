#!/usr/bin/env python3
"""
Independent validator for the PS3 SYNTHETIC PROTOTYPE dataset.
Re-parses raw logs with its OWN parsers (also usable as a reference importer) and checks the
dataset against the manifest, the parser answer key and the ground-truth files.
Exit code 0 = all checks passed.
"""
import os, sys, re, csv, json, glob, datetime as dt

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
NODES = ("NODE_A", "NODE_B", "NODE_C")
EVT = re.compile(r"^[A-Z_]+$")
KV = re.compile(r'\s*(\w+)=("[^"]*"|[^\s"]+)')
UTC = dt.timezone.utc


class Bad(ValueError):
    pass


def _dt(s, fmt):
    try:
        return dt.datetime.strptime(s, fmt).replace(tzinfo=UTC)
    except ValueError:
        raise Bad("bad_timestamp")


def parse_kv(rest):
    out, pos = {}, 0
    rest = rest.rstrip()
    while pos < len(rest):
        m = KV.match(rest, pos)
        if not m:
            raise Bad("incomplete_key_value")
        out[m.group(1)] = m.group(2).strip('"')
        pos = m.end()
    return out


def parse_operator(line):
    m = re.match(r"^\[ts=([^\]]+)\]\[node=(NODE_[ABC])\]\[sev=(INFO|WARN|ERROR)\] (.*)$", line)
    if not m:
        raise Bad("bad_prefix_or_missing_timestamp")
    kv = parse_kv(m.group(4))
    if "action" not in kv or not EVT.match(kv["action"]):
        raise Bad("missing_action")
    return dict(ts=_dt(m.group(1), "%Y-%m-%dT%H:%M:%S.%fZ"), node=m.group(2), etype=kv["action"], comp=kv.get("component"), kv=kv)


def parse_planning(line):
    row = next(csv.reader([line]))
    if len(row) != 12:
        raise Bad("wrong_column_count")
    if not row[0]:
        raise Bad("missing_timestamp")
    if row[1] not in NODES or not EVT.match(row[2]):
        raise Bad("bad_node_or_event")
    return dict(ts=_dt(row[0], "%Y-%m-%d %H:%M:%S.%f"), node=row[1], etype=row[2], comp=row[9] or None, kv=dict(zip(
        ["ts", "node", "event", "plan_id", "msg_id", "peer", "cmd_ref", "ack_for", "resend_of", "component", "status", "detail"], row)))


def parse_guidance(line):
    toks = line.split(" ")
    if len(toks) < 7 or toks[2] != "GDN" or toks[1] not in NODES:
        raise Bad("bad_header")
    try:
        ts = dt.datetime.fromtimestamp(float(toks[0]), UTC)
    except ValueError:
        raise Bad("bad_timestamp")
    kv = {}
    for t in toks[3:]:
        if "=" not in t:
            raise Bad("incomplete_key_value")
        k, v = t.split("=", 1)
        kv[k] = v
    for need in ("evt", "sev", "comp", "note"):
        if need not in kv:
            raise Bad("missing_field_" + need)
    if not EVT.match(kv["evt"]):
        raise Bad("bad_event")
    return dict(ts=ts.replace(microsecond=round(ts.microsecond / 1000) * 1000 % 1000000), node=toks[1], etype=kv["evt"], comp=kv["comp"], kv=kv)


def parse_state(line):
    f = line.split(";")
    if len(f) != 9:
        raise Bad("wrong_field_count")
    if f[1] not in NODES or not EVT.match(f[2]):
        raise Bad("bad_node_or_event")
    if not f[7].isdigit():
        raise Bad("bad_seq")
    return dict(ts=_dt(f[0], "%Y%m%dT%H%M%S.%fZ"), node=f[1], etype=f[2], comp=f[3], kv=dict(frm=f[4], to=f[5], trigger=f[6], seq=f[7]))


def parse_fault(line):
    f = line.split("|")
    if len(f) != 10:
        raise Bad("wrong_field_count")
    if f[1] not in NODES or not EVT.match(f[2]):
        raise Bad("bad_node_or_event")
    return dict(ts=_dt(f[0], "%Y-%m-%dT%H:%M:%SZ"), node=f[1], etype=f[2], comp=f[5], kv=dict(code=f[3], name=f[4], sev=f[6], related=f[7], dur=f[8]))


PARSERS = {"operator": parse_operator, "planning": parse_planning, "guidance": parse_guidance, "state": parse_state, "fault_recovery": parse_fault}


def load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return fh.read().split("\n")[:-1]


FAILS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


manifest = json.load(open(os.path.join(ROOT, "dataset_manifest.json")))
ref = json.load(open(os.path.join(ROOT, "reference/parser_expected_events.json")))["events"]
inc_gt = json.load(open(os.path.join(ROOT, "ground_truth/incident_ground_truth.json")))
rel_gt = json.load(open(os.path.join(ROOT, "ground_truth/relationship_ground_truth.json")))["relationships"]
by_id = {e["event_id"]: e for e in ref}

# ---- 1. re-parse everything, compare with manifest and answer key
parsed, skipped = {}, []
for fe in manifest["files"]:
    lines = load(fe["path"])
    fam = fe["log_family"]
    valid = bad = 0
    for i, line in enumerate(lines, 1):
        if fam == "planning" and i == 1:
            continue
        try:
            p = PARSERS[fam](line)
            p["line"], p["raw"], p["file"] = i, line, fe["path"]
            parsed[(fe["path"], i)] = p
            valid += 1
        except Bad as ex:
            skipped.append((fe["path"], i, str(ex), line)); bad += 1
    check(len(lines) == fe["total_raw_lines"], f"{fe['path']}: total_raw_lines {len(lines)}")
    check(valid == fe["expected_valid_records"] and bad == fe["expected_malformed_records"],
          f"{fe['path']}: parsed valid={valid} malformed={bad} (manifest {fe['expected_valid_records']}/{fe['expected_malformed_records']})")
    check(sorted(s[1] for s in skipped if s[0] == fe["path"]) == fe["malformed_line_numbers"], f"{fe['path']}: malformed line numbers match")

ok_ref = True
for e in ref:
    p = parsed.get((e["source_file"], e["source_line"]))
    if not p or p["raw"] != e["raw_record"] or p["etype"] != e["event_type"] or p["node"] != e["node"] \
            or p["ts"].strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z" != e["timestamp"]:
        ok_ref = False; print("   mismatch:", e["event_id"])
    if e["event_id"] != f"EVT-{e['node'][-1]}-{ {'operator':'OPR','planning':'PLN','guidance':'GDN','state':'STA','fault_recovery':'FLT'}[e['log_family']] }-{e['source_line']:04d}":
        ok_ref = False; print("   bad id:", e["event_id"])
check(ok_ref, "answer key: every reference event re-parses identically (timestamp, node, type, raw_record, source_line, id scheme)")
check(len(parsed) == len(ref), f"parsed record count {len(parsed)} == reference {len(ref)}")
tot = sum(f["expected_valid_records"] for f in manifest["files"]); badn = sum(f["expected_malformed_records"] for f in manifest["files"])
check(200 <= tot <= 400, f"valid records {tot} within 200-400"); check(5 <= badn <= 10, f"malformed {badn} within 5-10")
check(len(manifest["files"]) == 15, "15 raw files")
check(len({os.path.dirname(f["path"]) for f in manifest["files"]}) == 3, "3 node directories")

# ---- 2. malformed truly malformed; claimed malformed list
mal = [m for i in inc_gt["incidents"] for m in i["malformed_records"]] + inc_gt["background_features"]["malformed_records_not_in_incidents"]
check(len(mal) == badn, f"ground truth lists all {badn} malformed lines")
check(all((m["source_file"], m["source_line"]) not in parsed for m in mal), "every ground-truth malformed line fails to parse")
check(len(skipped) == badn, "importer skipped exactly the malformed lines")

# ---- 3. relationships
ids_ok = True
for r in rel_gt:
    s, t = by_id.get(r["source_event_id"]), by_id.get(r["target_event_id"])
    if not s or not t:
        ids_ok = False; print("   missing event for", r["relationship_id"]); continue
    if r["shared_key"] and not (r["shared_key"] in s["raw_record"] and r["shared_key"] in t["raw_record"]):
        ids_ok = False; print("   shared key not in both:", r["relationship_id"], r["shared_key"])
    if r["relationship_type"] == "SHARED_COMPONENT" and s["component"] != t["component"]:
        ids_ok = False; print("   component mismatch:", r["relationship_id"])
    if r["relationship_type"] in ("TEMPORAL", "SHARED_COMPONENT") and abs(r["delta_seconds"]) > 12:
        ids_ok = False; print("   window too large:", r["relationship_id"])
    if r["relationship_type"] == "MESSAGE_FLOW" and s["node"] == t["node"]:
        ids_ok = False; print("   flow within one node:", r["relationship_id"])
    if r["causation_established"] is not False:
        ids_ok = False
    if r["relationship_type"] == "TEMPORAL" and r["strength"] == "strong":
        ids_ok = False; print("   temporal labelled strong:", r["relationship_id"])
check(ids_ok, f"{len(rel_gt)} relationships: events exist, shared ids/components match, windows sane, no causation, no strong-temporal")
types = {r["relationship_type"] for r in rel_gt}
check({"EXPLICIT_ID", "MESSAGE_FLOW", "SHARED_COMPONENT", "TEMPORAL", "SEQUENCE", "RECOVERY"} <= types, "all six relationship types represented")
labels = {r["uncertainty_label"] for r in rel_gt}
check({"STRONG_SUPPORTED", "POSSIBLE", "INSUFFICIENT_EVIDENCE"} <= labels, "strong / possible / insufficient-evidence labels all present")

# ---- 4. incidents
for inc in inc_gt["incidents"]:
    evs = [by_id[e["event_id"]] for e in inc["event_ids"]]
    check(sorted({e["node"] for e in evs}) == inc["involved_nodes"], f"{inc['incident_id']}: events on intended nodes {inc['involved_nodes']}")
    for e in inc["event_ids"]:
        x = by_id[e["event_id"]]
        assert (x["source_file"], x["source_line"]) == (e["source_file"], e["source_line"])
    check(True, f"{inc['incident_id']}: {len(evs)} events, source_file/source_line references consistent")
    for sim in inc["simultaneous_events"]:
        ts = [by_id[i]["timestamp"] for i in sim["event_ids"]]
        if sim.get("tolerance_ms"):
            ds = [dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S.%fZ") for t in ts]
            check((max(ds) - min(ds)).total_seconds() * 1000 <= sim["tolerance_ms"], f"{inc['incident_id']}: near-simultaneous within tolerance")
        else:
            same = len(set(ts)) == 1
            check(same, f"{inc['incident_id']}: simultaneous events share timestamp ({ts[0]})")
    for rep in inc["repeated_events"]:
        g = [by_id[i] for i in rep["event_ids"]]
        check(len(g) >= 2 and len({(e["node"], e["log_family"], e["event_type"]) for e in g}) == 1, f"{inc['incident_id']}: repeated group real - {rep['description'][:50]}")
    for un in inc["unrelated_events_nearby"]:
        u = by_id[un["event_id"]]
        w0 = dt.datetime.strptime(inc["time_window_utc"][0], "%Y-%m-%dT%H:%M:%S.%fZ"); w1 = dt.datetime.strptime(inc["time_window_utc"][1], "%Y-%m-%dT%H:%M:%S.%fZ")
        t = dt.datetime.strptime(u["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ")
        check(w0 - dt.timedelta(seconds=60) <= t <= w1 + dt.timedelta(seconds=60) and u["event_id"] not in {e["event_id"] for e in inc["event_ids"]},
              f"{inc['incident_id']}: unrelated event {u['event_id']} is near but not a member")
check(inc_gt["incidents"][2]["kind"] == "NON_INCIDENT_NORMAL_OPERATION" and inc_gt["incidents"][2]["primary_fault"] is None, "INC-003 is a normal-operation control with no fault")
check(not any(by_id[e["event_id"]]["event_type"] in ("FAULT_RAISED",) for e in inc_gt["incidents"][2]["event_ids"]), "INC-003 contains no FAULT_RAISED")

# ---- 5. missing events genuinely absent
miss = [m for i in inc_gt["incidents"] for m in i["intentionally_missing_events"]] + inc_gt["background_features"]["intentionally_missing_events"]
for m in miss:
    c = m["absence_check"]
    hits = [p for (f, _), p in parsed.items() if f"{c['node'][-1]}/" in f and f.endswith(c["log_family"] + ".log") and p["etype"] == c["event_type"] and c["key"] in p["raw"]]
    check(not hits, f"missing event genuinely absent: {c['node']} {c['event_type']} key={c['key']}")
    node_file = f"data/synthetic/node_{c['node'][-1]}/{c['log_family']}.log"
    check(not any(c["key"] in s[3] and s[0] == node_file for s in skipped if c["event_type"] in s[3]), f"   ...and not hidden in a malformed line ({c['event_type']})")
for m in [m for i in inc_gt["incidents"] for m in i["intentionally_missing_events"] if m.get("expected_after_event_id")]:
    check(m["expected_after_event_id"] in by_id, "missing-event anchor event exists")

# ---- 6. background features
bf = inc_gt["background_features"]
for sim in bf["simultaneous_events"]:
    check(len({by_id[i]["timestamp"] for i in sim["event_ids"]}) == 1, f"background simultaneous real: {sim['description'][:55]}")
for g in bf["repeated_event_groups"]:
    check(all(len(v) >= 8 for v in g["event_ids"].values()), f"background repeated series real: {g['description'][:45]}")

# ---- 7. out of order
oo = 0
for fe in manifest["files"]:
    prev = None
    for (f, i), p in sorted(((k, v) for k, v in parsed.items() if k[0] == fe["path"]), key=lambda kv: kv[0][1]):
        if prev and p["ts"] < prev:
            oo += 1
        prev = p["ts"]
check(oo >= 3, f"out-of-order records present ({oo} inversions)")
check(len(bf["out_of_order_records"]) >= 3, "out-of-order records documented in ground truth")

# ---- 8. normal and unrelated activity outside incidents
inc_ids = {e["event_id"] for i in inc_gt["incidents"] for e in i["event_ids"]}
outside = [e for e in ref if e["event_id"] not in inc_ids]
check(len(outside) > 0.6 * len(ref), f"normal/background events outside incidents: {len(outside)}/{len(ref)}")
check(len(inc_gt["incidents"]) >= 3, "at least 3 incidents")
check(sum(1 for e in ref if e["event_type"] == "FAULT_RAISED") >= 3, "multiple FAULT_RAISED records exist")

# ---- 9. complete sequences exist elsewhere (so the missing ACK is a deviation)
acks = {p["kv"].get("ack_for") for p in parsed.values() if p["etype"] == "MESSAGE_ACK"}
recvs = {p["kv"].get("msg_id") for p in parsed.values() if p["etype"] == "MESSAGE_RECEIVED"}
check(len(recvs - acks) == 1 and "MSG-772" in (recvs - acks), f"exactly one received message lacks an ACK: {sorted(recvs - acks)}")

# ---- 10. no ground-truth / meta leakage into raw logs; no real-aviation markers
leak = re.compile(r"INC-\d|incident|ground.?truth|synthetic|expected|malformed|missing_event|TODO|REL-\d", re.I)
real = re.compile(r"Boeing|Airbus|ICAO|IATA|FAA|\bN\d{3}[A-Z]{2}\b|KJFK|EGLL", re.I)
leaks = [(f, i) for (f, i), p in parsed.items() if leak.search(p["raw"])] + [(s[0], s[1]) for s in skipped if leak.search(s[3])]
check(not leaks, "no ground-truth/meta words in any raw log line" + (f" {leaks[:3]}" if leaks else ""))
check(not any(real.search(p["raw"]) for p in parsed.values()), "no real aviation identifiers in raw logs")
check(os.path.exists(os.path.join(ROOT, "data/synthetic/SYNTHETIC_NOTICE.txt")), "synthetic notice present")
dups = len(parsed) - len({(p["file"], p["raw"]) for p in parsed.values()})
check(dups == 0, "no byte-identical duplicate records within a file (every repeat is distinguishable by content and line)")

print("\n==== %s ====" % ("ALL CHECKS PASSED" if not FAILS else f"{len(FAILS)} CHECK(S) FAILED"))
print(f"parsed={len(parsed)} skipped={len(skipped)}")
for s in skipped:
    print(f"  skipped {s[0].replace('data/synthetic/', '')}:{s[1]}  [{s[2]}]")
sys.exit(1 if FAILS else 0)
