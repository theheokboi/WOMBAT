# Mainline Class Constant And Distinct Colors

Checklist
- [~] Confirm requirement in docs/PROJECT.md
- [ ] Add/update tests for changed behavior
- [ ] Implement minimal code changes
- [ ] Run local verification for impacted paths
- [ ] Update docs/config examples if needed
- [ ] Mistake replay check logged

## 2026-03-07T21:32:29Z
- Status: in progress
- Checklist item: Confirm requirement in docs/PROJECT.md
- Update: Started follow-up task to centralize editable mainline class list and ensure distinct UI colors across transport classes.
- Evidence: User request in chat after primary-road support update.
- Next: Introduce shared backend constant and patch frontend class-style mapping with clear per-class colors.

## 2026-03-07T21:33:40Z
- Status: in progress
- Checklist item: Add/update tests for changed behavior
- Update: Existing focused tests already cover ingest mainline filtering, serve shapefile class filtering, and UI smoke expectations; no new behavior branch requires additional test file.
- Evidence: tests/unit/test_major_road_graph_contraction.py, tests/unit/test_serve_osm_transport.py, tests/ui/test_ui_smoke.py
- Next: Implement shared backend class constant and distinct frontend colors, then rerun focused pytest.

## 2026-03-07T21:33:40Z
- Status: in progress
- Checklist item: Implement minimal code changes
- Update: Added `src/inframap/osm_transport.py` as single source for mainline class list and switched both ingest and serve filters to use it; updated OSM class palette to use clearly distinct per-class colors.
- Evidence: src/inframap/osm_transport.py, src/inframap/ingest/major_road_graph.py, src/inframap/serve/app.py, frontend/main.js, frontend/styles.css
- Next: Run focused pytest for impacted test set.

## 2026-03-07T21:33:59Z
- Status: in progress
- Checklist item: Run local verification for impacted paths
- Update: Focused pytest completed successfully for impacted ingest/serve/UI tests after shared-constant and color changes.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_keeps_only_motorway_trunk_and_primary tests/unit/test_serve_osm_transport.py::test_osm_transport_overlay_filters_mainline_classes_and_includes_railway tests/unit/test_serve_osm_transport.py::test_osm_transport_overlay_skips_missing_files_and_lists_available_countries tests/ui/test_ui_smoke.py::test_ui_static_smoke` -> `4 passed in 1.27s`.
- Next: Confirm docs freshness requirement and run mistake replay check before handoff.

## 2026-03-07T21:33:59Z
- Status: complete
- Checklist item: Update docs/config examples if needed
- Update: Docs check: no changes required because API behavior/contracts and class set semantics are unchanged; this task only centralizes constants and updates visual palette.
- Evidence: Contract text already updated in prior task for primary-road support; no new API parameter or output shape changed here.
- Next: Run mistake replay check.

## 2026-03-07T21:33:59Z
- Status: complete
- Checklist item: Mistake replay check logged
- Update: Reviewed latest mistake ledger entries and confirmed this task used `apply_patch` for log edits and focused pytest verification commands.
- Evidence: `rg -n "^## " logs/mistakes.md | tail -n 5`
- Next: Finalize checklist snapshot and handoff.

## 2026-03-07T21:33:59Z
- Status: complete
- Checklist item: Checklist snapshot
- Update: `[x] Confirm requirement in docs/PROJECT.md`, `[x] Add/update tests for changed behavior`, `[x] Implement minimal code changes`, `[x] Run local verification for impacted paths`, `[x] Update docs/config examples if needed`, `[x] Mistake replay check logged`.
- Evidence: See entries above in this log.
- Next: None.
