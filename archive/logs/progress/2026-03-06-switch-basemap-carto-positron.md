# Switch Basemap to CARTO Positron

Checklist
- [x] Confirm UI basemap location
- [x] Implement CARTO Positron basemap
- [x] Run impacted verification
- [x] Docs check and mistake replay check

## 2026-03-06T21:16:10Z
- Status: in progress
- Checklist item: Confirm UI basemap location
- Update: Located current basemap tile configuration in `frontend/main.js`; preparing a direct switch from OSM standard tiles to CARTO Positron with proper attribution.
- Evidence: `frontend/main.js`
- Next: Apply tile URL + attribution change and run UI smoke.

## 2026-03-06T21:16:31Z
- Status: complete
- Checklist item: Run impacted verification
- Update: Switched Leaflet basemap to CARTO Positron (`light_all`) with CARTO+OSM attribution and required subdomains; UI smoke remains green.
- Evidence: `frontend/main.js`; `pytest -q tests/ui/test_ui_smoke.py` -> `1 passed`
- Next: Complete docs/mistake replay checks and handoff.

## 2026-03-06T21:16:31Z
- Status: complete
- Checklist item: Docs check and mistake replay check
- Update: Docs check: no changes required because this is a frontend basemap style swap only and does not alter workflow/contracts/tooling. Mistake replay check completed against current ledger.
- Evidence: `README.md`; `AGENTS.md`; `tail -n 20 logs/mistakes.md`
- Next: None.
