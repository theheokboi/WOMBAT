# Task Checklist
- [x] Confirm requirement and identify full pipeline tests
- [x] Disable/remove full pipeline tests from active verification paths
- [~] Run local verification for impacted test paths
- [ ] Docs check and rationale
- [ ] Mistake replay confirmation

## 2026-03-04T22:31:50Z
- Status: in progress
- Checklist item: Disable/remove full pipeline tests from active verification paths
- Update: Identified full pipeline tests using `run_pipeline(...)` and disabled them with explicit pytest skip markers to keep development unblocked while polygon contracts are unsettled.
- Evidence: `tests/integration/test_api.py`, `tests/integration/test_end_to_end_pipeline.py`, `tests/property/test_rerun_determinism.py`, `tests/perf/test_perf_monitoring.py`
- Next: Run `make verify-dev` and targeted test commands to confirm stable dev verification behavior.

# Task Checklist
- [x] Confirm requirement and identify full pipeline tests
- [x] Disable/remove full pipeline tests from active verification paths
- [x] Run local verification for impacted test paths
- [x] Docs check and rationale
- [x] Mistake replay confirmation

## 2026-03-04T22:36:20Z
- Status: complete
- Checklist item: Run local verification for impacted test paths
- Update: Executed dev verification after disabling full-pipeline tests; active verification paths are stable and no longer blocked by polygon-contract volatility.
- Evidence: `make verify-dev` -> `6 passed, 1 skipped` for first stage and `1 passed` for UI smoke.
- Next: Final handoff with changed files and rationale.

## 2026-03-04T22:36:20Z
- Status: complete
- Checklist item: Docs check and rationale
- Update: Docs check: no changes required. This change only adjusts test execution policy (skip full pipeline tests) and does not change runtime API/data contracts, commands, or user-facing workflow.
- Evidence: Reviewed `README.md` and repository workflow expectations; no command/interface modifications applied.
- Next: Record mistake replay confirmation.

## 2026-03-04T22:36:20Z
- Status: complete
- Checklist item: Mistake replay confirmation
- Update: Replayed prevention rules from `logs/mistakes.md` before handoff; avoided shell interpolation pitfalls and scoped edits to targeted test files only.
- Evidence: `logs/mistakes.md` reviewed; edits limited to test modules and progress log.
- Next: Handoff.
