# Task: GB-first calibration and world runtime estimator

## Checklist
- [x] Define GB calibration workflow and artifact schema
- [x] Implement non-publish calibration command (`make calibrate COUNTRY=GB`)
- [x] Implement runtime estimator from calibration artifacts
- [x] Add calibration API endpoints and UI status integration
- [x] Add unit/integration/perf tests for calibration and estimation
- [x] Update README/AGENTS docs for calibration workflow
- [~] Run verification suites and capture evidence
- [x] Docs freshness + mistake replay check
- [ ] Git checkpoint commit recorded

## 2026-02-28T06:26:56Z
- Status: in progress
- Checklist item: Define GB calibration workflow and artifact schema
- Update: Started implementation from current v3 runtime-status branch state; proceeding with multi-agent parallel ownership for calibration runner, estimator, and API/UI/tests.
- Evidence: `git status --short`, `configs/system.yaml`, `src/inframap/agent/runner.py`, `src/inframap/serve/app.py`.
- Next: Spawn worker agents with explicit file ownership and merge outputs.

## 2026-02-28T06:29:49Z
- Status: in progress
- Checklist item: Implement non-publish calibration command (`make calibrate COUNTRY=GB`)
- Update: Completed multi-agent implementation for calibration runner/CLI target and estimator/API/UI scaffolding; started merge reconciliation and fixed estimator integration path/signature mismatch.
- Evidence: `src/inframap/agent/calibrate.py`, `src/inframap/agent/runtime_estimator.py`, `src/inframap/serve/app.py`, `frontend/main.js`, `tests/integration/test_calibration_workflow.py`, `tests/unit/test_runtime_estimator.py`.
- Next: Run targeted verification and update docs (`README.md`, `AGENTS.md`) for calibration command and endpoints.

## 2026-02-28T06:51:30Z
- Status: in progress
- Checklist item: Run verification suites and capture evidence
- Update: Verified new calibration command path and artifact emission; fixed package import side effect causing calibrate runtime warning.
- Evidence: `COUNTRY=GB make calibrate` -> `artifacts/calibration/20260228T065114453993Z-GB/report.json`.
- Next: Complete targeted test verification for new estimator/calibration/API-UI surfaces.

## 2026-02-28T06:51:56Z
- Status: in progress
- Checklist item: Add unit/integration/perf tests for calibration and estimation
- Update: Targeted suites passed for new estimator and calibration workflow plus UI smoke assertions for calibration status and endpoint wiring.
- Evidence: `pytest -q tests/unit/test_runtime_estimator.py tests/integration/test_calibration_workflow.py tests/ui/test_ui_smoke.py` -> `6 passed`.
- Next: Finalize docs freshness and mistake replay check, then create git checkpoint commit.

## 2026-02-28T06:52:14Z
- Status: in progress
- Checklist item: Docs freshness + mistake replay check
- Update: Updated `README.md` and `AGENTS.md` for `make calibrate` workflow and calibration endpoints. Mistake replay check completed against `logs/mistakes.md` entries; no repeated unresolved mistake patterns remain in this change.
- Evidence: `README.md`, `AGENTS.md`, `logs/mistakes.md` (new 2026-02-28 entry).
- Next: Commit task files and record commit hash in this progress log.
