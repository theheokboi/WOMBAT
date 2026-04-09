## Checklist
- [x] Confirm current `R7 Network Regions` polygon/tooltip rendering path
- [x] Add representative region markers to the map under the existing toggle
- [x] Verify the UI change and capture a screenshot

## 2026-03-08T07:13:23Z
- Status: in progress
- Checklist item: Confirm current `R7 Network Regions` polygon/tooltip rendering path
- Update: Confirmed that the current overlay renders only polygon cells plus tooltip text, so representative region points can be added as a second Leaflet sublayer without any backend changes.
- Evidence: `frontend/main.js`; `tests/ui/test_ui_smoke.py`
- Next: Add a deduplicated marker layer from `region_lat`/`region_lon`, tie it to the existing `toggle-r7-regions`, and verify visually.

## 2026-03-08T07:16:43Z
- Status: complete
- Checklist item: Add representative region markers to the map under the existing toggle
- Update: Added a deduplicated point layer for representative `r7` region markers using `region_lat`/`region_lon`, rendered as `L.circleMarker` features alongside the existing region polygons under the same `R7 Network Regions` toggle.
- Evidence: `frontend/main.js`
- Next: Run UI smoke, capture a screenshot, and replay mistake-prevention rules before handoff.

## 2026-03-08T07:16:43Z
- Status: complete
- Checklist item: Verify the UI change and capture a screenshot
- Update: Verified the new marker-layer wiring with UI smoke and captured a screenshot showing the `R7 Network Regions` overlay with region points visible at the representative coordinates.
- Evidence: `pytest -q tests/ui/test_ui_smoke.py`; `artifacts/screenshots/2026-03-08-r7-region-markers.png`; `logs/mistakes.md`
- Next: Handoff completed.
