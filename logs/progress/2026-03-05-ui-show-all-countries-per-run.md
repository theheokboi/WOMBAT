# Task: UI show all countries per run

Checklist
- [x] Confirm current country-scoped rendering behavior
- [x] Update UI to render all countries for selected run
- [x] Remove country selector control and related script hooks
- [x] Update UI smoke tests
- [x] Run targeted verification
- [x] Docs check and mistake replay confirmation

## 2026-03-05T21:35:53Z
- Status: in progress
- Checklist item: Confirm current country-scoped rendering behavior
- Update: Verified UI currently filters facilities/country/adaptive layers by requested/effective country and exposes a country selector.
- Evidence: `frontend/main.js`, `frontend/index.html`, `tests/ui/test_ui_smoke.py`
- Next: Refactor frontend to keep run selector but render all countries for each selected run.

## 2026-03-05T21:37:19Z
- Status: complete
- Checklist item: Run targeted verification
- Update: Removed per-country selector UI and country fallback/filter path; selected run now renders all facilities and country-mask cells, while adaptive cells remain filtered only by configured resolution bounds. Updated UI smoke assertions and README note.
- Evidence: `frontend/index.html`, `frontend/main.js`, `tests/ui/test_ui_smoke.py`, `README.md`, `pytest -q tests/ui/test_ui_smoke.py` (1 passed), `ReadLints` (no errors)
- Next: Handoff behavior change and usage notes.
