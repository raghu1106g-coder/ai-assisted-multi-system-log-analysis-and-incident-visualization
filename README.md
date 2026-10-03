# AI-assisted multi-system log analysis and incident visualization

Dataset 1 is a fictional synthetic prototype; it is not the official dataset or real operational data.

> **This is synthetic prototype data.** It is NOT the official hackathon dataset, NOT real flight-management data, and contains no real aircraft, airport or system identifiers. Log-family names, raw formats, event vocabularies, IDs and fault codes are **prototype assumptions** that must be replaced when the official dataset arrives.

Purpose: exercise the whole PS3 pipeline end to end:

`RAW LOGS -> INGEST -> PARSE -> NORMALIZE -> CORRELATE -> TIMELINE -> INCIDENT MODEL -> 4-LEVEL VISUALIZATION -> EVIDENCE RETRIEVAL -> AI NARRATIVE`

Regenerate with `python3 tools/generate_dataset.py` (deterministic). Verify with `python3 tools/validate_dataset.py`.

## 1. Three tiers of content - keep them separate

### 1a. Facts explicitly specified by the problem statement

- Three cooperating instances (nodes) of a fictional flight-management system; treat as any distributed operational system.
- Five log families ingested from the three nodes into a common event model.
- Content themes: planning, guidance, operator interaction, state changes, faults, recovery.
- Correlate operator actions, state, guidance events and faults across nodes.
- Reconstruct the timeline through repetition, simultaneity and missing data.
- Evidence-linked conclusions with a plain-language narrative; uncertainty labels.
- Importer must report skipped records.
- Four visualization levels: 1 Flight overview (source/destination, time, phases, significant faults, recovery summary); 2 Fault/event detail (code, name, time, duration, impact, recovery, related events); 3 Operation context (aircraft conditions, system state, cross-node state); 4 Evidence detail (source record).
- Filters by node, time, log family, event/fault category.
- Minimum demo: record totals across families; overview-to-evidence navigation; isolate one fault with filters; import-to-narrative end to end.

### 1b. Prototype assumptions (NOT from the problem statement)

- The five family names `operator, planning, guidance, state, fault_recovery`, and which raw syntax each uses.
- Node roles (A = primary operator/planner, B = guidance/navigation, C = monitor/standby) - purely a storytelling device.
- All event types, fault codes (`FLT-*`), recovery codes (`RCV-*`), command/message/plan/setpoint ids (`CMD-/MSG-/PLN-/SP-`), component names, waypoint ids.
- Timestamp formats per family, UTC, a fictional date (2031-05-12), second-resolution for the fault family.
- Fictional route `ZZ-ALPHA -> ZZ-BRAVO`, session `SIM-S01`, phases `PREFLIGHT/CLIMB/CRUISE/DESCENT/APPROACH`, 'condition' fields (`alt_band`, `spd_band`, `fuel_state`).
- The normalized event schema, `incident_hint`, `category`, `attributes` and the event-id scheme.
- That records are one-per-line and that malformed lines are simply unparseable lines.

### 1c. Generated synthetic content

Everything under `data/synthetic/`, plus the three JSON references and the manifest. Ground truth lives in `ground_truth/` and must **never** be an input to ingest/correlation.

## 2. Layout

```
data/synthetic/node_{A,B,C}/{operator,planning,guidance,state,fault_recovery}.log   <- 15 raw files (the only pipeline input)
data/synthetic/SYNTHETIC_NOTICE.txt
dataset_manifest.json            <- expected counts per file (for import QA)
normalized_event_examples.json   <- 10 representative raw->normalized mappings (+ parsing rules)
reference/parser_expected_events.json  <- full parser answer key (test your parser; not for correlation)
ground_truth/incident_ground_truth.json
ground_truth/relationship_ground_truth.json
tools/generate_dataset.py, tools/validate_dataset.py
```

For convenient browsing, `data/dataset_1_bundle.txt` concatenates Dataset 1's 15 raw logs with source-file markers. It is a viewing aid only; ingest the original files under `data/synthetic/`, not the bundle. Future datasets should remain separately identified rather than merged into this Dataset 1 bundle.

**Totals:** 15 files, 379 raw lines = 366 valid records + 10 malformed + 1 CSV header.

| File | Format | Valid | Malformed | Lines |
|---|---|---:|---:|---:|
| `node_A/operator.log` | bracketed key=value | 20 | 1 | 21 |
| `node_A/planning.log` | CSV (12 columns, header on line 1) | 34 | 1 | 36 |
| `node_A/guidance.log` | whitespace-delimited key=value with epoch timestamp | 32 | 0 | 32 |
| `node_A/state.log` | semicolon-separated positional (9 fields) | 21 | 1 | 22 |
| `node_A/fault_recovery.log` | pipe-separated positional (10 fields) | 21 | 0 | 21 |
| `node_B/operator.log` | bracketed key=value | 21 | 1 | 22 |
| `node_B/planning.log` | CSV (12 columns, header on line 1) | 20 | 0 | 21 |
| `node_B/guidance.log` | whitespace-delimited key=value with epoch timestamp | 33 | 1 | 34 |
| `node_B/state.log` | semicolon-separated positional (9 fields) | 20 | 0 | 20 |
| `node_B/fault_recovery.log` | pipe-separated positional (10 fields) | 20 | 1 | 21 |
| `node_C/operator.log` | bracketed key=value | 20 | 0 | 20 |
| `node_C/planning.log` | CSV (12 columns, header on line 1) | 22 | 1 | 24 |
| `node_C/guidance.log` | whitespace-delimited key=value with epoch timestamp | 36 | 1 | 37 |
| `node_C/state.log` | semicolon-separated positional (9 fields) | 22 | 1 | 23 |
| `node_C/fault_recovery.log` | pipe-separated positional (10 fields) | 24 | 1 | 25 |

## 3. Raw formats (one real line each)

**operator** (`data/synthetic/node_A/operator.log:8`)
```
[ts=2031-05-12T09:41:02.120Z][node=NODE_A][sev=INFO] op=OP-07 action=SUBMIT_COMMAND cmd_id=CMD-1042 attempt=1 component=ROUTE_MGR msg="Operator requested alternate route profile ALT-2"
```
**planning** (`data/synthetic/node_A/planning.log:18`)
```
2031-05-12 09:41:06.350,NODE_A,MESSAGE_SENT,PLN-310,MSG-771,NODE_B,,,,PLAN_SYNC,SENT,plan PLN-310 distributed to peer
```
**guidance** (`data/synthetic/node_B/guidance.log:15`)
```
1936345268.300 NODE_B GDN evt=GUIDANCE_DEVIATION sev=WARN comp=NAV_FILTER xte=0.82 note=cross_track_error_above_soft_limit
```
**state** (`data/synthetic/node_A/state.log:10`)
```
20310512T094102.480Z;NODE_A;STATE_CHANGE;ROUTE_MGR;IDLE;REPLANNING;CMD-1042;109;replanning started
```
**fault_recovery** (`data/synthetic/node_B/fault_recovery.log:9`)
```
2031-05-12T09:41:09Z|NODE_B|FAULT_RAISED|FLT-2207|NAV_FILTER_DIVERGENCE|NAV_FILTER|ERROR|-|-|residual above divergence limit
```
Planning header (line 1 of every `planning.log`): `ts,node,event,plan_id,msg_id,peer,cmd_ref,ack_for,resend_of,component,status,detail`. Guidance uses epoch seconds; state uses compact `YYYYMMDDTHHMMSS.mmmZ`; operator uses `ts=` ISO; fault_recovery is second-resolution.

## 4. Incidents

| ID | Kind | Nodes | Window (UTC) | Purpose |
|---|---|---|---|---|
| INC-001 | INCIDENT | A, B, C | 09:41:02 - 09:41:30 | Plan distribution followed by NAV_FILTER divergence (NODE_B) and plan-sync timeout (NODE_C) |
| INC-002 | INCIDENT | A, C | 10:05:08 - 10:05:16 | Out-of-range speed setpoint rejected by NODE_C (smaller, two-node incident) |
| INC-003 | NON_INCIDENT_NORMAL_OPERATION | A, B, C | 09:25:10 - 09:25:40 | Routine altitude profile step and plan sync (NORMAL OPERATION - not a fault incident) |

## 5. Walkthrough - INC-001 (main demo incident)

Raw records in time order (`event_id` = `EVT-<node>-<family>-<line>`; the line number IS the evidence pointer). Fault records have second resolution, so ordering inside the same second relies on other families.

| Time (UTC) | Node | Family | Event type | Event ID | Source | What the record says |
|---|---|---|---|---|---|---|
| 09:41:02.120 | A | operator | SUBMIT_COMMAND | `EVT-A-OPR-0008` | `node_A/operator.log:8` | Operator requested alternate route profile ALT-2 |
| 09:41:02.480 | A | state | STATE_CHANGE | `EVT-A-STA-0010` | `node_A/state.log:10` | replanning started |
| 09:41:02.600 | A | planning | PLAN_REQUEST | `EVT-A-PLN-0017` | `node_A/planning.log:17` | plan request for alternate profile ALT-2 |
| 09:41:03.900 | A | operator | SUBMIT_COMMAND | `EVT-A-OPR-0009` | `node_A/operator.log:9` | Operator resubmitted route profile request (no feedback shown) |
| 09:41:05.900 | A | planning | PLAN_COMPUTED | `EVT-A-PLN-0019` | `node_A/planning.log:19` | 6 legs computed, 1 constraint relaxed |
| 09:41:06.350 | A | planning | MESSAGE_SENT | `EVT-A-PLN-0018` | `node_A/planning.log:18` | plan PLN-310 distributed to peer |
| 09:41:06.360 | A | planning | MESSAGE_SENT | `EVT-A-PLN-0020` | `node_A/planning.log:20` | plan PLN-310 distributed to peer |
| 09:41:06.700 | B | planning | MESSAGE_RECEIVED | `EVT-B-PLN-0011` | `node_B/planning.log:11` | plan PLN-310 received |
| 09:41:06.710 | C | planning | MESSAGE_RECEIVED | `EVT-C-PLN-0011` | `node_C/planning.log:11` | plan PLN-310 received |
| 09:41:06.980 | B | planning | MESSAGE_ACK | `EVT-B-PLN-0012` | `node_B/planning.log:12` | acknowledged |
| 09:41:07.250 | B | guidance | PROFILE_APPLY | `EVT-B-GDN-0014` | `node_B/guidance.log:14` | profile applied from received plan |
| 09:41:07.250 | C | guidance | PROFILE_APPLY | `EVT-C-GDN-0017` | `node_C/guidance.log:17` | profile applied from received plan |
| 09:41:07.600 | A | planning | EXCHANGE_COMPLETE | `EVT-A-PLN-0021` | `node_A/planning.log:21` | exchange closed |
| 09:41:07.900 | A | state | STATE_CHANGE | `EVT-A-STA-0011` | `node_A/state.log:11` | new plan active |
| 09:41:08.300 | B | guidance | GUIDANCE_DEVIATION | `EVT-B-GDN-0015` | `node_B/guidance.log:15` | cross track error above soft limit |
| 09:41:08.900 | B | state | STATE_CHANGE | `EVT-B-STA-0010` | `node_B/state.log:10` | filter degraded |
| 09:41:08.900 | B | guidance | GUIDANCE_DEVIATION | `EVT-B-GDN-0018` | `node_B/guidance.log:18` | cross track error above soft limit |
| 09:41:09.000 | B | fault_recovery | FAULT_RAISED | `EVT-B-FLT-0009` | `node_B/fault_recovery.log:9` | residual above divergence limit |
| 09:41:09.000 | B | fault_recovery | FAULT_NOTICE_SENT | `EVT-B-FLT-0010` | `node_B/fault_recovery.log:10` | fault notice sent to NODE_A |
| 09:41:09.500 | B | guidance | GUIDANCE_DEVIATION | `EVT-B-GDN-0017` | `node_B/guidance.log:17` | cross track error above soft limit |
| 09:41:10.000 | A | fault_recovery | PEER_FAULT_NOTICE | `EVT-A-FLT-0010` | `node_A/fault_recovery.log:10` | fault notice received from NODE_B |
| 09:41:10.100 | A | state | PEER_STATE | `EVT-A-STA-0012` | `node_A/state.log:12` | peer reported degraded |
| 09:41:12.500 | B | operator | STATUS_QUERY | `EVT-B-OPR-0010` | `node_B/operator.log:10` | Operator queried status of NAV_FILTER |
| 09:41:16.000 | C | fault_recovery | FAULT_RAISED | `EVT-C-FLT-0009` | `node_C/fault_recovery.log:9` | sync timer expired (10s) for MSG-772 |
| 09:41:16.100 | C | state | STATE_CHANGE | `EVT-C-STA-0013` | `node_C/state.log:13` | sync timed out |
| 09:41:16.500 | C | guidance | PLAN_HOLD | `EVT-C-GDN-0019` | `node_C/guidance.log:19` | holding previous plan |
| 09:41:17.000 | C | fault_recovery | FAULT_NOTICE_SENT | `EVT-C-FLT-0010` | `node_C/fault_recovery.log:10` | fault notice sent to NODE_A |
| 09:41:17.200 | A | state | PEER_STATE | `EVT-A-STA-0013` | `node_A/state.log:13` | peer reported degraded |
| 09:41:18.000 | A | fault_recovery | PEER_FAULT_NOTICE | `EVT-A-FLT-0011` | `node_A/fault_recovery.log:11` | fault notice received from NODE_C |
| 09:41:19.000 | C | fault_recovery | FAULT_RAISED | `EVT-C-FLT-0011` | `node_C/fault_recovery.log:11` | sync timer expired again (repeat 2) for MSG-772 |
| 09:41:21.000 | B | fault_recovery | RECOVERY_STARTED | `EVT-B-FLT-0011` | `node_B/fault_recovery.log:11` | filter reinit scheduled |
| 09:41:21.200 | B | state | STATE_CHANGE | `EVT-B-STA-0011` | `node_B/state.log:11` | filter recovering |
| 09:41:22.400 | B | guidance | FILTER_REINIT | `EVT-B-GDN-0019` | `node_B/guidance.log:19` | filter reinitialised |
| 09:41:24.000 | C | fault_recovery | RECOVERY_STARTED | `EVT-C-FLT-0013` | `node_C/fault_recovery.log:13` | request plan resend |
| 09:41:25.100 | A | planning | MESSAGE_SENT | `EVT-A-PLN-0022` | `node_A/planning.log:22` | plan PLN-310 resent after peer notice |
| 09:41:25.500 | C | planning | MESSAGE_RECEIVED | `EVT-C-PLN-0012` | `node_C/planning.log:12` | plan PLN-310 received (resend) |
| 09:41:25.800 | C | planning | MESSAGE_ACK | `EVT-C-PLN-0013` | `node_C/planning.log:13` | acknowledged |
| 09:41:26.100 | A | planning | EXCHANGE_COMPLETE | `EVT-A-PLN-0023` | `node_A/planning.log:23` | exchange closed |
| 09:41:26.300 | C | state | STATE_CHANGE | `EVT-C-STA-0012` | `node_C/state.log:12` | sync restored |
| 09:41:26.800 | C | guidance | PLAN_RESUME | `EVT-C-GDN-0020` | `node_C/guidance.log:20` | resuming with resent plan |
| 09:41:27.000 | C | fault_recovery | FAULT_CLEARED | `EVT-C-FLT-0014` | `node_C/fault_recovery.log:14` | sync restored |
| 09:41:27.400 | A | state | PEER_STATE | `EVT-A-STA-0014` | `node_A/state.log:14` | peer back to nominal |
| 09:41:28.600 | B | state | STATE_CHANGE | `EVT-B-STA-0012` | `node_B/state.log:12` | filter nominal |
| 09:41:28.900 | B | guidance | GUIDANCE_NOMINAL | `EVT-B-GDN-0020` | `node_B/guidance.log:20` | tracking restored |
| 09:41:29.000 | B | fault_recovery | FAULT_CLEARED | `EVT-B-FLT-0012` | `node_B/fault_recovery.log:12` | filter divergence cleared |
| 09:41:29.200 | A | state | PEER_STATE | `EVT-A-STA-0015` | `node_A/state.log:15` | peer back to nominal |
| 09:41:30.400 | A | operator | ACK_ALERT | `EVT-A-OPR-0011` | `node_A/operator.log:11` | Operator acknowledged alert FLT-2207 |

**Expected reconstructed story (what a good narrative may say):**

1. *Confirmed:* operator on A submitted CMD-1042 (twice: attempt 1 and 2); A started replanning and requested plan PLN-310 under that command. *Strong (explicit ids).*
2. *Confirmed:* A computed PLN-310 and sent it as MSG-771 to B and MSG-772 to C. B received and ACKed MSG-771; the exchange completed. *Strong (message flow + sequence).*
3. *Confirmed:* B and C applied the profile at the same instant (07.250), then B reported three GUIDANCE_DEVIATION records, NAV_FILTER went DEGRADED, and FLT-2207 NAV_FILTER_DIVERGENCE was raised at 09:41:09. B notified A (MSG-775).
4. *Possible, not provable:* the plan application and the divergence both involve NAV_FILTER within ~2 s, but no record links them - **causation is not established by the available records.**
5. *Missing information:* C received MSG-772 but no ACK exists; C raised FLT-2210 PLAN_SYNC_TIMEOUT (referencing MSG-772), repeated it, and one more repeat appears only as a malformed line. The reason for the missing ACK is unknown.
6. *Recovery (strong):* B started RCV-55 (filter reinit) -> NAV_FILTER RECOVERING -> NOMINAL -> FLT-2207 cleared after 20 s. C requested a resend; A sent MSG-779 (`resend_of=MSG-772`), C ACKed it, PLAN_SYNC SYNCED, FLT-2210 cleared after 11 s. The operator acknowledged FLT-2207.
7. *Insufficient evidence:* FLT-2207 and FLT-2210 are 7 s apart on different nodes/components; do not claim one caused the other. Unrelated nearby: C display brightness change, A link-jitter warning, routine waypoint WP-010.

Visualization mapping: **L1** session origin/dest (operator `SESSION_START`), phases (`PHASE_CHANGE`), the two faults and recoveries; **L2** code/name/duration/`related` fields in `fault_recovery`; **L3** `CONDITION_SAMPLE`, `STATE_CHANGE`, `PEER_STATE` (cross-node); **L4** `source_file:source_line` + `raw_record`.

## 6. Correlation opportunities (fields/patterns)

- **Shared identifiers:** `cmd_id`/`cmd_ref`/`cmd` (CMD-1042, 1018, 1030), `plan_id` (PLN-310), `sp` (SP-044, SP-039), fault code `FLT-*`, recovery code `RCV-*`.
- **Explicit references:** planning `ack_for`, `resend_of`; state `trigger`; guidance `ref`; fault `related`; operator `alert_id`.
- **Message flow:** `MESSAGE_SENT` (peer=dst) on one node <-> `MESSAGE_RECEIVED` (peer=src) on another with the same `msg_id`; fault-notice flow via `related=MSG-775/776` (`FAULT_NOTICE_SENT` -> `PEER_FAULT_NOTICE`); setpoint flow via `sp`.
- **Shared component:** `component` (NAV_FILTER, PLAN_SYNC, SPEED_CTRL, COMM_LINK...) and `PEER_NODE_x` components for cross-node state.
- **Temporal proximity:** weak by itself; use with a window (e.g. <= 10 s) and never as causation.
- **Sequences:** `SEND->RECV->ACK->COMPLETE` (planning), `SENT->RECV->ACK->APPLIED->COMPLETE` (guidance setpoints), `RAISED->RECOVERY_STARTED->CLEARED` (faults), state `from->to` chains. Absence of an expected step is itself a finding.
- **Repetition keys:** same node+family+type+key repeated (attempt counters, `repeat N` text, hb counters).
- **State `seq`:** per-node monotonic counter; gaps indicate lost records and out-of-order placement.

## 7. Edge-case index

- **Repeated:** INC-001 operator resubmit; 3x GUIDANCE_DEVIATION on B; FLT-2210 raised twice (+1 malformed); periodic SELFTEST_PASS / GUIDANCE_STATUS series (non-incident repeats).
- **Simultaneous:** `data/synthetic/node_B/guidance.log:14` & `data/synthetic/node_C/guidance.log:17` (same ms); WP-005 on A and C (`data/synthetic/node_A/guidance.log:7`, `data/synthetic/node_C/guidance.log:7`); phase change A/C (`data/synthetic/node_A/state.log:4`, `data/synthetic/node_C/state.log:6`); fault-family same-second ties.
- **Missing (absent from raw logs, no placeholder):** ACK + COMPLETE for MSG-772 (INC-001); SETPOINT_ACK/APPLIED for SP-044 and A's ADJUSTING->STABLE (INC-002); NODE_B WP-012 (background).
- **Malformed (skip + report):**
  - `node_A/operator.log:10` - missing_timestamp
  - `node_A/planning.log:7` - incomplete_fields
  - `node_A/state.log:16` - invalid_separator
  - `node_B/operator.log:4` - incomplete_key_value_pair_and_unterminated_quote
  - `node_B/guidance.log:21` - corrupted_timestamp_token
  - `node_B/fault_recovery.log:5` - invalid_separator
  - `node_C/planning.log:14` - missing_timestamp
  - `node_C/guidance.log:34` - truncated_record
  - `node_C/state.log:18` - incomplete_fields
  - `node_C/fault_recovery.log:12` - corrupted_event_name
- **Out-of-order (file order != time order):**
  - `data/synthetic/node_A/planning.log:19` is written after `data/synthetic/node_A/planning.log:18`
  - `data/synthetic/node_B/guidance.log:18` is written after `data/synthetic/node_B/guidance.log:17`
  - `data/synthetic/node_C/state.log:13` is written after `data/synthetic/node_C/state.log:12`
  - `data/synthetic/node_A/fault_recovery.log:9` is written before `data/synthetic/node_A/fault_recovery.log:10`
- **Normal activity / unrelated:** INC-003 control group, periodic selftests/heartbeats/refreshes/waypoints, transient self-cleared warnings (`FLT-0901`, `FLT-0420`).

## 8. Parser guidance (Python)

One small parser per family returning `None`/raising on malformed input; the importer counts and records skips with `(file, line, reason, raw)`.

```python
import csv, re, shlex
KV = re.compile(r'\s*(\w+)=("[^"]*"|[^\s"]+)')
def parse_operator(line):   # [ts=..][node=..][sev=..] k=v ... msg=".."
    m = re.match(r'^\[ts=([^\]]+)\]\[node=(NODE_[ABC])\]\[sev=(\w+)\] (.*)$', line)
    if not m: raise ValueError('bad_prefix')
    # scan k=v tokens; any leftover text => ValueError('incomplete_key_value')
def parse_planning(line):   # csv.reader, expect 12 columns, non-empty ts
def parse_guidance(line):   # split(); float(ts); node; 'GDN'; every other token must be k=v
def parse_state(line):      # split(';') -> 9 fields; int(seq)
def parse_fault(line):      # split('|') -> 10 fields; event matches ^[A-Z_]+$
```

Steps: (1) iterate files with `enumerate(f, 1)` so the line number is the evidence pointer; (2) skip the planning header; (3) parse -> normalize (UTC ms) -> `event_id = EVT-<n>-<fam>-<line>`; (4) on failure append to a skipped-record report (file, line, reason, raw); (5) sort by timestamp but keep `source_line` (and state `seq`) for tie-breaks and out-of-order detection; (6) compare your counts with `dataset_manifest.json`. `tools/validate_dataset.py` contains a complete reference implementation of the five parsers.

## 9. Using the ground truth (evaluation only)

Score your correlation engine by precision/recall on `relationship_ground_truth.json`; check that every pair in `relationships_that_should_not_be_inferred` is NOT presented as causal; check the narrative uses the right uncertainty label per `uncertainty_examples`; check INC-003 is not reported as a fault incident; check missing-event detection against `intentionally_missing_events`.

## 10. What to replace when the official dataset arrives

- Family names, raw formats, parsers and timestamp formats.
- Event vocabulary, categories, fault/recovery codes and their meaning, severity scale.
- Identifier schemes (CMD/MSG/PLN/SP) and which fields carry cross-node references.
- Node roles and component names.
- Phase model, route fields and aircraft-condition fields used for Level 1 and Level 3.
- The normalized schema and `event_id` scheme.
- All ground-truth files (re-derive from the official data), the manifest, and the incident definitions.
- Keep: the architecture, the relationship taxonomy, the uncertainty-label vocabulary, and the validator's *kinds* of checks.

## 11. Validation

`python3 tools/validate_dataset.py` independently re-parses every raw line and checks: manifest counts, line/ID references, shared ids, message flows, missing events really absent, repeats/simultaneity real, malformed lines really unparseable, out-of-order present, normal and unrelated events present, no ground-truth leakage into raw logs, no real-aviation markers.

