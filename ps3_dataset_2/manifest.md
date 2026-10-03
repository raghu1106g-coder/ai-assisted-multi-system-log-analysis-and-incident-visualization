# Dataset 2 manifest (SYNTHETIC / FICTIONAL)

**Purpose:** an unseen evaluation dataset for an existing application (parsing, correlation, incident reconstruction, AI explanation, hallucination resistance). It uses the same five-family log architecture and raw syntaxes as the baseline dataset but contains entirely new timestamps, identifiers, scenarios and orderings. It is fictional; it is not real flight data.

- Raw log files: 15 (3 nodes x 5 families), under `logs/<NODE>/<family>/<family>.log`
- Nodes: 3 (NODE_A, NODE_B, NODE_C)
- Valid records: 1568
- Malformed records: 24 (22 syntax-detectable + 2 semantic-only)
- Total physical lines: 1595 (includes 3 CSV header lines; blank lines counted as malformed records)
- Byte-identical duplicate lines (valid): 6
- Out-of-order placements documented: 14
- Normalized timestamp range (UTC): 2031-08-19T12:00:08.400Z .. 2031-08-19T14:59:41.545Z (single day, 2031-08-19)

## Records by log family (valid)

| Family | Valid records |
|---|---:|
| operator | 172 |
| planning | 351 |
| guidance | 475 |
| state | 314 |
| fault_recovery | 256 |

## Records by node (valid)

| Node | Valid |
|---|---:|
| NODE_A | 565 |
| NODE_B | 499 |
| NODE_C | 504 |

## Timestamp formats (all UTC)

| Family | Representation |
|---|---|
| operator | ISO-8601 with milliseconds and `Z` |
| planning | `YYYY-MM-DD HH:MM:SS.mmm` (UTC implied) |
| guidance | numeric Unix epoch seconds with milliseconds |
| state | compact `YYYYMMDDTHHMMSS.mmmZ` |
| fault_recovery | ISO-8601 whole seconds (no milliseconds in this schema) |

## Per-file counts

| File | Valid | Malformed | Lines |
|---|---:|---:|---:|
| `logs/NODE_A/operator/operator.log` | 70 | 2 | 72 |
| `logs/NODE_A/planning/planning.log` | 152 | 2 | 155 |
| `logs/NODE_A/guidance/guidance.log` | 156 | 2 | 158 |
| `logs/NODE_A/state/state.log` | 107 | 2 | 109 |
| `logs/NODE_A/fault_recovery/fault_recovery.log` | 80 | 1 | 81 |
| `logs/NODE_B/operator/operator.log` | 52 | 2 | 54 |
| `logs/NODE_B/planning/planning.log` | 95 | 1 | 97 |
| `logs/NODE_B/guidance/guidance.log` | 158 | 2 | 160 |
| `logs/NODE_B/state/state.log` | 105 | 2 | 107 |
| `logs/NODE_B/fault_recovery/fault_recovery.log` | 89 | 1 | 90 |
| `logs/NODE_C/operator/operator.log` | 50 | 2 | 52 |
| `logs/NODE_C/planning/planning.log` | 104 | 2 | 107 |
| `logs/NODE_C/guidance/guidance.log` | 161 | 1 | 162 |
| `logs/NODE_C/state/state.log` | 102 | 1 | 103 |
| `logs/NODE_C/fault_recovery/fault_recovery.log` | 87 | 1 | 88 |

## Incidents (14 incident records from 10 scenario families) and normal periods

| ID | Nodes | Time (UTC) | Scenario | Recovery |
|---|---|---|---|---|
| D2-INC-01 | A, B, C | 12:14:02-12:14:24 | Plan distributed to two peers; one peer's plan cache faults (checksum mismatch) and recovers via resend | RECOVERED |
| D2-INC-02 | A | 12:31:36-12:31:50 | NODE_A time-sync drift fault (recovers) - co-occurs within 2 s with an unrelated fault on NODE_C | RECOVERED |
| D2-INC-03 | C | 12:31:33-12:31:45 | NODE_C actuator range warning after a local trim command (recovers) - 2 s after an unrelated NODE_A fault | RECOVERED |
| D2-INC-04 | A, B, C | 12:47:04-12:47:20 | Plan message received by NODE_C but never acknowledged; NODE_A raises an ACK timeout and recovers by resend | RECOVERED |
| D2-INC-05 | A, B, C | 13:05:09-13:05:20 | Plan message acknowledged unusually late (9.3 s after receipt) with no fault raised | NOT_APPLICABLE_NO_FAULT |
| D2-INC-06 | B | 13:21:04-13:21:20 | NODE_B sensor-bus CRC fault re-reported three times (plus one duplicated log line) then cleared | RECOVERED |
| D2-INC-07 | C | 13:21:11-13:21:15 | NODE_C sensor-bus CRC fault (same code, same second as a NODE_B repeat) - separate event | RECOVERED |
| D2-INC-08 | A, B, C | 13:34:10-13:34:19 | NAV_FILTER on NODE_B degrades and returns to nominal; peers' views lag and briefly disagree (no fault record) | NOT_APPLICABLE_NO_FAULT_RECORD |
| D2-INC-09 | A, C | 13:48:21-13:49:05 | NODE_C power-rail sag fault, re-reported, acknowledged by an operator, never cleared; contains an instruction-like operator note | NOT_OBSERVED |
| D2-INC-10 | A, B | 14:05:34-14:05:50 | Recovery and clear observed on NODE_B for FLT-8502 but the raise record is absent (only a peer notice exists) | RECOVERY_OBSERVED_INITIATING_FAULT_MISSING |
| D2-INC-11 | A, B | 14:20:08-14:20:45 | NODE_A plan to NODE_B followed by a profile range fault on B (recovers); overlaps an independent incident on C | RECOVERED |
| D2-INC-12 | C | 14:20:22-14:20:56 | NODE_C telemetry backlog fault tied to a local config change (recovers); overlaps INC-11 on NODE_A/NODE_B | RECOVERED |
| D2-INC-13 | B | 14:41:29-14:41:40 | NODE_B sensor-bus CRC fault recurs 80 minutes later (same node/component/code) and clears | RECOVERED |
| D2-INC-14 | A, B, C | 14:52:10-14:52:27 | Operator command retried (attempt 2) leading to a setpoint and a slew-rate fault on NODE_C (recovers); similar-looking command on NODE_B is unrelated | RECOVERED |
| NP-1 | A,B,C | 12:00:00-12:12:00 | NP-1 start-up / climb routine period | n/a (normal) |
| NP-2 | A,B,C | 13:08:00-13:18:00 | NP-2 mid-cruise routine period | n/a (normal) |
| NP-3 | A,B,C | 14:26:00-14:38:00 | NP-3 pre-descent routine period | n/a (normal) |

## Special tricky cases included

- Temporal proximity without causality (INC-02/INC-03, INC-07 vs INC-06, INC-11 vs INC-12)
- Genuine three-node chain with explicit ids (INC-01); NODE_A -> NODE_B plan chain (INC-11, INC-14 via setpoint)
- Received-but-never-acknowledged message with believable timeout and recovery (INC-04)
- Delayed ACK with no fault (INC-05)
- Repeated fault vs byte-identical duplicate line vs same-code lookalike (INC-06/INC-07)
- Out-of-order physical records, including an ACK physically before its RECEIVED line (INC-11, INC-14)
- Simultaneous timestamps across independent incidents (INC-11/INC-12, INC-06/INC-07, phase changes, waypoints)
- Degraded-then-nominal legitimate state pair with lagging peer views (INC-08)
- Fault with no recovery (INC-09)
- Recovery with missing initiating fault record (INC-10)
- Same component, same fault code, different incidents (INC-06 / INC-13)
- Overlapping independent incidents on different nodes (INC-11 / INC-12)
- Real command retry vs look-alike command (INC-14)
- Prompt-injection-like free text in two operator notes (INC-09 area and an unrelated period)
- New event type CONFIG_CHANGE, new components (TIME_SYNC, ACTUATOR_SIM, CFG_STORE, TELEMETRY_SVC, PWR_MON, WPT_DB), new id ranges
- Deliberately malformed lines kept in place: missing/invalid timestamp, missing node/event type, incomplete CSV, extra field, corrupted delimiter, truncation, blank line, stray token, JSON-like fragment, missing required identifier
