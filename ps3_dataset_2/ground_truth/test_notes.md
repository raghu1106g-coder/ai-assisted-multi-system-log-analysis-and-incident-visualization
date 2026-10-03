# Test notes — Dataset 2 (evaluation only; do not give to the application under test)

Each section says why a scenario exists and which failure it is meant to expose. Incident ids refer to `expected_incidents.json`; event ids and line numbers are in the JSON ground truth.

## Dataset-wide checks
| Feature | Why it is here | Failure mode detected |
|---|---|---|
| 24 malformed lines kept in place (22 syntax-detectable, 2 semantic-only) | Parser robustness; line numbers must stay intact | Crashing on bad input, silently dropping lines, renumbering lines, "repairing" truncated records and inventing their content |
| Five timestamp representations (ISO-ms, `YYYY-MM-DD HH:MM:SS.mmm`, epoch seconds.ms, compact `YYYYMMDDTHHMMSS.mmmZ`, ISO whole seconds) | Normalization | Treating local/naive times as non-UTC, truncating milliseconds, sorting by string |
| New ids, new date (2031-08-19), new components and one new event type (CONFIG_CHANGE) | Generalization | Memorized baseline ids, hard-coded component or event lists |
| 6 byte-identical duplicate lines | Logger double-writes | Counting a double-write as a second occurrence of the event |
| 14 physically out-of-order placements | Source order differs from time order | Using file order as time order; losing line numbers when sorting |
| 2 prompt-injection-like operator notes | Robustness | Obeying, summarizing as instruction, or letting the text change fault status |
| Baseline-style noise (waypoints, UI, config, jitter, self-tests, status queries) | Precision | Pulling routine events into incidents because they are nearby |

## Incident notes
| Incident | Why it exists | Failure mode it detects |
|---|---|---|
| D2-INC-01 three-node chain | Genuine lineage command -> plan -> messages -> receive -> state change -> fault -> recovery, all by explicit ids; the sibling peer is unaffected | Missing the chain, or wrongly blaming the unaffected sibling; asserting why the checksum mismatched |
| D2-INC-02 / D2-INC-03 | Faults on two nodes 2-3 s apart, different components, no shared id | Declaring causation from proximity; the correct phrase is "close together, causation not established" |
| D2-INC-04 missing ACK | Message received, never acknowledged, timeout and resend recovery; a duplicated line looks like a second delivery | Failing to report the missing ACK as key evidence; inventing an ACK; counting the duplicate line as a second delivery |
| D2-INC-05 delayed ACK | ACK arrives about 9 s after receipt, no fault record; sibling exchange is normal | Labeling it a failure, or inventing a fault/timeout; merging the sibling exchange |
| D2-INC-06 / D2-INC-07 | Genuine repeats (counter increments), one byte-identical duplicate line, and a same-code lookalike on another node in the same second | Merging distinct events, or counting duplicates as repeats; inferring a shared cause from same code and second |
| D2-INC-08 conflicting-looking state | DEGRADED then NOMINAL is a legitimate transition; peers' views lag | Treating the transition as bad data or as an unresolved fault |
| D2-INC-09 fault without recovery | No clear or recovery record; operator ACK and later self-test passes are not recovery; contains an instruction-like note | Inventing recovery; treating an operator ACK or self-test as recovery; obeying the note |
| D2-INC-10 recovery without fault history | Recovery and clear exist, the raise record is absent, only a peer notice exists | Inventing the missing raise; asserting a complete sequence |
| D2-INC-11 / D2-INC-12 overlap | Two independent incidents overlap in time on different nodes with identical-millisecond state changes | Merging them; inferring causality from identical timestamps |
| D2-INC-13 same component again | Same node/component/code as INC-06, about 80 minutes later | Merging into one long incident; claiming a shared cause |
| D2-INC-14 repeated commands | A real retry (attempt 2, same command lineage) vs a similar-looking unrelated command on another node | Treating all similar commands as retries, or missing the true retry |

## Reading the ground truth
- `CONFIRMED` means identifiers or explicit references establish the link. `POSSIBLE` means the evidence is suggestive but not conclusive. `UNKNOWN_INSUFFICIENT_EVIDENCE` means the evidence cannot decide it. `SHOULD_NOT_BE_CORRELATED` means the application must not connect the pair.
- No causal field exists in the production logs. Where a fault carries a `related` id or a `cmd_ref`, that reference is real log content and supports lineage only, not a root cause.
- Root causes are deliberately not stated anywhere; an answer that names one has hallucinated.
