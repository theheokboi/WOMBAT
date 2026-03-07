# Basemap Selector (OSM / Positron / Dark)

Checklist
- [x] Confirm current basemap wiring in UI
- [x] Add basemap selector control and switching logic
- [x] Update UI smoke coverage
- [x] Run impacted verification
- [x] Docs check and mistake replay check

## 2026-03-06T21:18:10Z
- Status: in progress
- Checklist item: Confirm current basemap wiring in UI
- Update: Confirmed basemap initialization is currently hardcoded in `frontend/main.js`. Implementing a lightweight selector in `frontend/index.html` with runtime switching in JS.
- Evidence: `frontend/main.js`; `frontend/index.html`
- Next: Apply frontend edits, then run `tests/ui/test_ui_smoke.py`.

## 2026-03-06T21:18:58Z
- Status: complete
- Checklist item: Run impacted verification
- Update: Added `basemap-selector` with `CARTO Positron`, `OSM Standard`, and `CARTO Dark` options. Implemented runtime tile-layer switching in Leaflet using a small `BASEMAP_STYLES` map and updated UI smoke coverage.
- Evidence: `frontend/index.html`; `frontend/main.js`; `frontend/styles.css`; `tests/ui/test_ui_smoke.py`; `pytest -q tests/ui/test_ui_smoke.py` -> `1 passed`
- Next: Final docs/mistake replay checks and handoff.

## 2026-03-06T21:18:58Z
- Status: complete
- Checklist item: Docs check and mistake replay check
- Update: Docs check: no changes required because this is a UI control enhancement that does not alter workflow/contracts/tooling. Mistake replay check completed against current ledger.
- Evidence: `README.md`; `AGENTS.md`; `tail -n 20 logs/mistakes.md`
- Next: None.
