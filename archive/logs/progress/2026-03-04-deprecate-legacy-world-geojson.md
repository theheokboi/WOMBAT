# Task Checklist
- [x] Add soft deprecation behavior for legacy world GeoJSON dataset path
- [x] Add/update tests for deprecation behavior
- [x] Run impacted tests
- [x] Record mistake replay/docs check and finalize

## 2026-03-04T22:08:11Z
- Status: in progress
- Checklist item: Add soft deprecation behavior for legacy world GeoJSON dataset path
- Update: Started implementing deprecation of legacy world polygon dataset path in country mask layer.
- Evidence: /Users/hyes92121/Desktop/h3-experiment/src/inframap/layers/country_mask.py
- Next: Add warning+metadata deprecation signaling and validate with tests.

## 2026-03-04T22:09:01Z
- Status: in progress
- Checklist item: Add/update tests for deprecation behavior
- Update: Added deprecation unit test asserting warning emission and metadata flags for legacy world dataset path.
- Evidence: /Users/hyes92121/Desktop/h3-experiment/tests/unit/test_country_mask.py
- Next: Run impacted unit tests.

## 2026-03-04T22:09:02Z
- Status: in progress
- Checklist item: Run impacted tests
- Update: Ran country mask unit tests successfully (2 passed).
- Evidence: pytest -q tests/unit/test_country_mask.py
- Next: Record final workflow checks and commit changes.

## 2026-03-04T22:09:08Z
- Status: complete
- Checklist item: Record mistake replay/docs check and finalize
- Update: Mistake replay check complete with no repeated ledger issues; docs check complete with no README/AGENTS update required because this change adds deprecation signaling only and does not alter run commands/workflow.
- Evidence: /Users/hyes92121/Desktop/h3-experiment/logs/mistakes.md
- Next: Commit and handoff.

## 2026-03-04T22:09:31Z
- Status: complete
- Checklist item: Record mistake replay/docs check and finalize
- Update: Recorded required git checkpoint hash for legacy dataset deprecation.
- Evidence: commit 3ea4106
- Next: Handoff complete.
