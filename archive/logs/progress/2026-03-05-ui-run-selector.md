## Checklist snapshot
- [~] Add backend support to query layer/facility payloads by explicit `run_id`.
- [ ] Add backend endpoint to list recent runs with country-mask resolution metadata.
- [ ] Add UI run selector to switch between runs (and thus r-level outputs) without rerunning.
- [ ] Update UI smoke coverage for selector wiring.
- [ ] Run verification and record mistake replay confirmation.

## 2026-03-05T21:01:00Z
- Status: in progress
- Checklist item: Add backend support to query layer/facility payloads by explicit `run_id`.
- Update: Started implementation for UI run/r-level switching by adding explicit run-scoped API reads and a run catalog surface.
- Evidence: logs/progress/2026-03-05-ui-run-selector.md
- Next: Implement backend run-scoped endpoints and catalog, then wire frontend selector.

## 2026-03-05T21:13:14Z
- Status: complete
- Checklist item: Add backend support to query layer/facility payloads by explicit `run_id`.
- Update: Added optional `run_id` query support for layer list/metadata/cells and facilities endpoints; added run-scoped status endpoint `/v1/runs/{run_id}/status`.
- Evidence: src/inframap/serve/app.py
- Next: Add runs catalog endpoint and wire frontend run selector.

## 2026-03-05T21:13:14Z
- Status: complete
- Checklist item: Add backend endpoint to list recent runs with country-mask resolution metadata.
- Update: Added `/v1/runs/catalog` endpoint returning recent runs with country-mask mode/resolution and adaptive base metadata.
- Evidence: src/inframap/serve/app.py
- Next: Wire UI run selector and URL parameter handling.

## 2026-03-05T21:13:14Z
- Status: complete
- Checklist item: Add UI run selector to switch between runs (and thus r-level outputs) without rerunning.
- Update: Added `Run / r-level` selector in UI, introduced `run` URL parameter, and switched frontend API calls to run-scoped endpoints.
- Evidence: frontend/index.html, frontend/main.js
- Next: Update smoke coverage and run verification.

## 2026-03-05T21:13:14Z
- Status: complete
- Checklist item: Update UI smoke coverage for selector wiring.
- Update: Extended UI smoke assertions for `run-selector`, `/v1/runs/catalog`, and updated display-scope string expectations.
- Evidence: tests/ui/test_ui_smoke.py
- Next: Run full verification and log mistake replay confirmation.

## 2026-03-05T21:13:14Z
- Status: complete
- Checklist item: Run verification and record mistake replay confirmation.
- Update: `make verify-dev` passed; validated new endpoints with `TestClient` and recorded docs note for run selector behavior.
- Evidence: make verify-dev output (6 passed, 1 skipped; ui smoke 1 passed), python TestClient probe for `/v1/runs/catalog`.
- Next: Mistake replay check complete against logs/mistakes.md; ready for handoff.

## Checklist snapshot
- [x] Add backend support to query layer/facility payloads by explicit `run_id`.
- [x] Add backend endpoint to list recent runs with country-mask resolution metadata.
- [x] Add UI run selector to switch between runs (and thus r-level outputs) without rerunning.
- [x] Update UI smoke coverage for selector wiring.
- [x] Run verification and record mistake replay confirmation.
