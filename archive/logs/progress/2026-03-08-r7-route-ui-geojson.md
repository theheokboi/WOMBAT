## 2026-03-08T07:56:22Z
- Status: in progress
- Checklist item: [~] Generate lightweight UI route GeoJSON artifacts and make the UI route overlay prefer them
- Update: Confirmed the current full route artifacts are too large for direct UI rendering, especially the Argentina route JSON.
- Evidence: `artifacts/derived/2026-03-08-r7-regions-tw-routes.json`; `artifacts/derived/2026-03-08-r7-regions-ar-routes.json`
- Next: Implement a compaction script, generate `*-routes-ui.geojson`, update the serving path to prefer the compact artifacts, and verify size reduction plus endpoint/tests.

## 2026-03-08T08:00:14Z
- Status: complete
- Checklist item: [x] Generate lightweight UI route GeoJSON artifacts and make the UI route overlay prefer them
- Update: Added a streaming compaction script that emits simplified, rounded, non-self, non-null, unordered-pair route GeoJSON for UI use; generated compact TW/AR artifacts; and updated `/v1/r7-region-routes` to prefer the compact files when `include_self=false`.
- Evidence: `scripts/build_r7_route_ui_geojson.py`; `artifacts/derived/2026-03-08-r7-regions-tw-routes-ui.geojson`; `artifacts/derived/2026-03-08-r7-regions-ar-routes-ui.geojson`; refreshed endpoint check on `http://127.0.0.1:8003/v1/r7-region-routes?country=TW` and `country=AR`; `python -m pytest -q tests/unit/test_serve_r7_region_routes.py tests/ui/test_ui_smoke.py`
- Next: Handoff complete.

## 2026-03-08T08:00:14Z
- Status: complete
- Checklist item: Docs check
- Update: Updated the contract and contributor docs to describe compact `*-routes-ui.geojson` artifacts and the endpoint preference behavior.
- Evidence: `docs/PROJECT.md`; `README.md`; `AGENTS.md`
- Next: Handoff complete.

## 2026-03-08T08:00:14Z
- Status: complete
- Checklist item: Mistake replay check
- Update: Replayed the route-overlay task assumptions and confirmed no new mistake-ledger entry was required for this change.
- Evidence: `logs/mistakes.md`
- Next: Handoff complete.

## 2026-03-08T08:03:22Z
- Status: in progress
- Checklist item: [~] Retune compact route GeoJSON simplification tolerance
- Update: Started regenerating the visualization route artifacts with a tighter `--simplify-tolerance 0.001` so the displayed lines stay closer to the original OSRM routes.
- Evidence: `scripts/build_r7_route_ui_geojson.py`
- Next: Rebuild the compact TW/AR artifacts and verify the resulting sizes and coordinate counts.

## 2026-03-08T08:03:22Z
- Status: complete
- Checklist item: [x] Retune compact route GeoJSON simplification tolerance
- Update: Rebuilt both compact UI route artifacts with `--simplify-tolerance 0.001`, increasing shape fidelity while keeping the visualization files far smaller than the raw route JSON.
- Evidence: `artifacts/derived/2026-03-08-r7-regions-tw-routes-ui.geojson` (`86060` bytes, `7560` coordinates); `artifacts/derived/2026-03-08-r7-regions-ar-routes-ui.geojson` (`5023768` bytes, `445869` coordinates)
- Next: Handoff complete.
