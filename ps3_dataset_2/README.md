# PS3 Dataset 2 (synthetic, fictional)

An unseen evaluation dataset for an AI-assisted multi-system log analysis application. **All data is synthetic**; no real aircraft or operational data. Three fictional nodes (NODE_A/B/C), five log families.

## Layout
```
logs/<NODE_A|NODE_B|NODE_C>/<operator|planning|guidance|state|fault_recovery>/<family>.log   <- the ONLY input for the application
ground_truth/   expected_import_results.json, expected_incidents.json, expected_relationships.json, reference_narratives.md, test_notes.md   <- evaluation only
manifest.md, validation_report.md, tools/
```
**Do not give `ground_truth/`, `manifest.md`, `validation_report.md` or `tools/` to the application under test.** `tools/generate_dataset2.py` contains the scenario definitions (i.e. the answers).

## Raw formats (same architecture as the baseline dataset)
- operator: `[ts=ISO][node=..][sev=..] op=.. action=.. k=v .. component=.. msg="..."`
- planning: 12-column CSV, header on line 1 (`ts,node,event,plan_id,msg_id,peer,cmd_ref,ack_for,resend_of,component,status,detail`)
- guidance: `epoch NODE_x GDN evt=.. sev=.. comp=.. k=v .. note=..`
- state: `compactTS;node;kind;component;from;to;trigger;seq;note` (9 fields; `seq` is a per-node counter, gaps indicate lost records)
- fault_recovery: `ISO-seconds|node|event|code|name|component|severity|related|duration_s|text` (10 fields)

Every record is traceable by `source_file` + `source_line`; ground truth uses event ids `EVT-<node letter>-<family code>-<line>` derived from the line number in that file (the line in the log file is authoritative).

## Differences from the baseline dataset
New date/time window (2031-08-19 12:00-15:00 UTC), new route/session, new ID ranges (CMD-73xx, PLN-5xx..9xx, MSG-90xx..95xx, SP-2xx, FLT-84xx..85xx, RCV-30x..31x, CFG-04xx), new components and one new event type (CONFIG_CHANGE), new sequences, new timing relationships and orderings.

## Validation
`python3 tools/validate_dataset.py` independently re-parses all logs and checks them against the ground truth; see `validation_report.md`.
