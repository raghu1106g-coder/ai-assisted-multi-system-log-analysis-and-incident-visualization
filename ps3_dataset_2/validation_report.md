# Validation report — PS3 Dataset 2

Validator: `tools/validate_dataset.py` (independent re-parse; does not import the generator).

- Log files: 15
- Total physical lines: 1595
- Independently counted VALID records: **1568**
- Independently counted MALFORMED records: **24** ({'MISSING_TIMESTAMP': 1, 'MISSING_REQUIRED_IDENTIFIER': 2, 'INCOMPLETE_RECORD': 2, 'INVALID_NUMERIC_TIMESTAMP': 1, 'STRAY_TOKEN': 1, 'BLANK_RECORD': 1, 'CORRUPTED_DELIMITER': 2, 'MISSING_EVENT_TYPE': 3, 'INVALID_TIMESTAMP': 3, 'EXTRA_UNEXPECTED_FIELD': 2, 'TRUNCATED_RECORD': 2, 'MISSING_NODE': 3, 'MALFORMED_STRUCTURED_PAYLOAD': 1})
- Incidents in ground truth: 14
- Relationships in ground truth: 275 ({'CONFIRMED': 172, 'POSSIBLE': 20, 'UNKNOWN_INSUFFICIENT_EVIDENCE': 10, 'SHOULD_NOT_BE_CORRELATED': 73})
- Normalized timestamp range: 2031-08-19T12:00:08.400000+00:00 .. 2031-08-19T14:59:41.545000+00:00

## Checks: 86 passed / 0 failed

| Result | Check | Detail |
|---|---|---|
| PASS | required directories present |  |
| PASS | required ground_truth files present |  |
| PASS | manifest.md and README.md present |  |
| PASS | exactly 15 log files |  |
| PASS | no files other than .log under logs/ |  |
| PASS | NODE_A/planning header |  |
| PASS | NODE_B/planning header |  |
| PASS | NODE_C/planning header |  |
| PASS | event ids unique |  |
| PASS | valid count within 1,500-3,000 |  |
| PASS | malformed count within 15-25 |  |
| PASS | valid count matches expected_import_results |  |
| PASS | malformed count matches expected_import_results |  |
| PASS | total lines match |  |
| PASS | per-family counts match |  |
| PASS | per-file valid counts and skipped lines/reasons match |  |
| PASS | reason category counts match |  |
| PASS | normalized timestamp range matches |  |
| PASS | all valid timestamps on 2031-08-19 UTC |  |
| PASS | mixture of timestamp representations (5 families, 5 formats) |  |
| PASS | NODE_A state seq non-decreasing in timestamp order (equal = byte-identical duplicate line) |  |
| PASS | NODE_B state seq non-decreasing in timestamp order (equal = byte-identical duplicate line) |  |
| PASS | NODE_C state seq non-decreasing in timestamp order (equal = byte-identical duplicate line) |  |
| PASS | out-of-order records physically present |  |
| PASS | byte-identical duplicate lines match ground truth |  |
| PASS | every event id in expected_incidents.json exists as a VALID record |  |
| PASS | every event id in expected_relationships.json exists as a VALID record |  |
| PASS | incident event metadata (file/line/node/family/type/timestamp) matches logs |  |
| PASS | relationship classification counts consistent |  |
| PASS | relationship classes within allowed vocabulary |  |
| PASS | all four classifications used |  |
| PASS | relationship ids unique |  |
| PASS | relationship time deltas match logs |  |
| PASS | CONFIRMED relationships' shared identifier literally present in both records |  |
| PASS | no SHOULD_NOT_BE_CORRELATED pair shares an identifier unless declared |  |
| PASS | SHOULD_NOT_BE_CORRELATED pairs share no id tokens in the logs |  |
| PASS | every declared missing event is genuinely absent |  |
| PASS | 8-12+ incident scenarios (14 records, >=8 scenario families) |  |
| PASS | 2-4 normal periods |  |
| PASS | several cross-node incidents |  |
| PASS | single-node incidents exist |  |
| PASS | two-node incident exists |  |
| PASS | three-node incident exists |  |
| PASS | at least one incident with recovery NOT_OBSERVED |  |
| PASS | at least one incident with recovery observed but initiating fault missing |  |
| PASS | several incidents whose causal certainty is not established |  |
| PASS | D2-INC-01 FLT-8412: raise-record presence matches |  |
| PASS | D2-INC-01 FLT-8412: clear or recovery in logs |  |
| PASS | D2-INC-02 FLT-8433: raise-record presence matches |  |
| PASS | D2-INC-02 FLT-8433: clear or recovery in logs |  |
| PASS | D2-INC-03 FLT-8434: raise-record presence matches |  |
| PASS | D2-INC-03 FLT-8434: clear or recovery in logs |  |
| PASS | D2-INC-04 FLT-8451: raise-record presence matches |  |
| PASS | D2-INC-04 FLT-8451: clear or recovery in logs |  |
| PASS | D2-INC-06 FLT-8470: raise-record presence matches |  |
| PASS | D2-INC-06 FLT-8470: clear or recovery in logs |  |
| PASS | D2-INC-07 FLT-8470: raise-record presence matches |  |
| PASS | D2-INC-07 FLT-8470: clear or recovery in logs |  |
| PASS | D2-INC-09 FLT-8493: raise-record presence matches |  |
| PASS | D2-INC-09 FLT-8493: no clear/recovery in logs |  |
| PASS | D2-INC-10 FLT-8502: raise-record presence matches |  |
| PASS | D2-INC-10 FLT-8502: no raise record on NODE_B (genuinely missing) |  |
| PASS | D2-INC-10 FLT-8502: recovery present |  |
| PASS | D2-INC-11 FLT-8520: raise-record presence matches |  |
| PASS | D2-INC-11 FLT-8520: clear or recovery in logs |  |
| PASS | D2-INC-12 FLT-8524: raise-record presence matches |  |
| PASS | D2-INC-12 FLT-8524: clear or recovery in logs |  |
| PASS | D2-INC-13 FLT-8470: raise-record presence matches |  |
| PASS | D2-INC-13 FLT-8470: clear or recovery in logs |  |
| PASS | D2-INC-14 FLT-8560: raise-record presence matches |  |
| PASS | D2-INC-14 FLT-8560: clear or recovery in logs |  |
| PASS | unrelated nearby events exist, are valid records, are not in the relevant set and share no ids with the incident |  |
| PASS | unrelated nearby noise present for most incidents |  |
| PASS | 2 prompt-injection-like records |  |
| PASS | EVT-A-OPR-0015 injection text present in an ordinary operator MAINT_NOTE |  |
| PASS | EVT-A-OPR-0015 has only the standard header fields (no special metadata) |  |
| PASS | EVT-C-OPR-0038 injection text present in an ordinary operator MAINT_NOTE |  |
| PASS | EVT-C-OPR-0038 has only the standard header fields (no special metadata) |  |
| PASS | injection strings occur only in those two records |  |
| PASS | production logs contain no ground-truth vocabulary or answer fields |  |
| PASS | log file names are neutral (<family>.log only) |  |
| PASS | ground truth is outside logs/ (separate directory) |  |
| PASS | no comment lines in logs |  |
| PASS | no explicit causal field in any log schema |  |
| PASS | no baseline-dataset-style identifiers (CMD-10xx, MSG-7xx, FLT-09xx) |  |
| PASS | no baseline timestamps (2031-05-12) |  |
