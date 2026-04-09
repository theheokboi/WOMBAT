# UI Remove OSM Visualization

Checklist
- [x] Reproduce/confirm requirement against `docs/PROJECT.md`
- [x] Add/update tests for changed behavior
- [x] Implement minimal code change
- [x] Run focused verification for impacted paths
- [x] Docs check (`docs/PROJECT.md`, `README.md`, `AGENTS.md`)
- [x] Mistake replay check (`logs/mistakes.md`)

## 2026-03-08T06:08:19Z
- Status: in progress
- Checklist item: Reproduce/confirm requirement against `docs/PROJECT.md`
- Update: Confirmed the request is a frontend simplification only: remove OSM overlay rendering, remove UI toggles and legend, and stop loading `/v1/osm/transport`.
- Evidence: `docs/PROJECT.md` transport graph contract reviewed; `frontend/index.html`, `frontend/main.js`, and `frontend/styles.css` inspected.
- Next: update the UI smoke test expectations before editing frontend code.

## 2026-03-08T06:08:19Z
- Status: in progress
- Checklist item: Add/update tests for changed behavior
- Update: Identified `tests/ui/test_ui_smoke.py` as the only direct assertion set tied to the OSM overlay controls and legend text.
- Evidence: `tests/ui/test_ui_smoke.py`
- Next: revise smoke assertions to reflect the simplified UI and removed OSM frontend fetch.

## 2026-03-08T06:08:19Z
- Status: in progress
- Checklist item: Implement minimal code change
- Update: Removed OSM overlay markup, legend markup, toggle controls, and `/v1/osm/transport` loading from the frontend; the UI now renders only the facility, country-mask, and adaptive layers by default.
- Evidence: `frontend/index.html`, `frontend/main.js`, `frontend/styles.css`
- Next: run focused verification and update any stale UI smoke assertions.

## 2026-03-08T06:08:19Z
- Status: in progress
- Checklist item: Run focused verification for impacted paths
- Update: Ran targeted UI verification after updating the smoke test and checked frontend JavaScript syntax.
- Evidence: `python -m pytest -q tests/ui/test_ui_smoke.py` -> `1 passed in 0.81s`; `node --check frontend/main.js` -> success.
- Next: finish docs and mistake-log checks, then hand off.

## 2026-03-08T06:08:19Z
- Status: complete
- Checklist item: Docs check (`docs/PROJECT.md`, `README.md`, `AGENTS.md`)
- Update: Updated `README.md` for the simplified frontend behavior; `docs/PROJECT.md` and `AGENTS.md` need no changes because the backend transport contract and workflow rules are unchanged.
- Evidence: `README.md`
- Next: complete mistake replay check.

## 2026-03-08T06:08:19Z
- Status: complete
- Checklist item: Mistake replay check (`logs/mistakes.md`)
- Update: Reviewed the recent ledger entries and kept log edits on `apply_patch` paths to avoid shell interpolation mistakes while updating markdown logs.
- Evidence: `logs/mistakes.md`; `logs/progress/2026-03-08-ui-remove-osm-visualization.md`
- Next: handoff summary.
