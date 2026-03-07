# Secondary Class Support

Checklist
- [~] Confirm requirement in docs/PROJECT.md
- [ ] Add/update tests for changed behavior
- [ ] Implement minimal code changes
- [ ] Run local verification for impacted paths
- [ ] Update docs/config examples if needed
- [ ] Mistake replay check logged

## 2026-03-07T21:39:50Z
- Status: in progress
- Checklist item: Confirm requirement in docs/PROJECT.md
- Update: Started task to complete `secondary` support after shared mainline constant was changed from `primary` to `secondary`.
- Evidence: src/inframap/osm_transport.py currently sets `MAINLINE_ROAD_CLASSES = (\"motorway\", \"trunk\", \"secondary\")`.
- Next: Align ingest parser, UI legend/styles, tests, and docs with `secondary`.

## 2026-03-07T21:41:27Z
- Status: in progress
- Checklist item: Add/update tests for changed behavior
- Update: Updated impacted unit/UI assertions from `primary` to `secondary` and adjusted ingest mainline filter test case names/fixtures accordingly.
- Evidence: tests/unit/test_major_road_graph_contraction.py, tests/unit/test_serve_osm_transport.py, tests/ui/test_ui_smoke.py
- Next: Finish code alignment in ingest + frontend and run focused pytest.

## 2026-03-07T21:41:27Z
- Status: in progress
- Checklist item: Implement minimal code changes
- Update: Added `secondary` parsing in major-road ingest classes (including `secondary_link`) and replaced frontend primary legend/style bindings with secondary equivalents.
- Evidence: src/inframap/ingest/major_road_graph.py, frontend/main.js, frontend/index.html, frontend/styles.css
- Next: Verify with focused pytest and update docs wording.

## 2026-03-07T21:41:27Z
- Status: in progress
- Checklist item: Run local verification for impacted paths
- Update: Focused pytest passed for changed ingest/serve/UI tests.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_keeps_only_motorway_trunk_and_secondary tests/unit/test_serve_osm_transport.py::test_osm_transport_overlay_filters_mainline_classes_and_includes_railway tests/unit/test_serve_osm_transport.py::test_osm_transport_overlay_skips_missing_files_and_lists_available_countries tests/ui/test_ui_smoke.py::test_ui_static_smoke` -> `4 passed in 0.93s`.
- Next: Update docs wording and complete mistake replay check.

## 2026-03-07T21:41:27Z
- Status: complete
- Checklist item: Update docs/config examples if needed
- Update: Updated transport graph contract wording and README legend wording to reflect `secondary` as the mainline class instead of `primary`.
- Evidence: docs/PROJECT.md, README.md
- Next: Run mistake replay check and finalize checklist.

## 2026-03-07T21:41:44Z
- Status: complete
- Checklist item: Mistake replay check logged
- Update: Replayed the latest mistake ledger entries and confirmed this task used apply_patch for log updates and targeted pytest verification.
- Evidence: `rg -n "^## " logs/mistakes.md | tail -n 5`
- Next: Finalize checklist snapshot and handoff.

## 2026-03-07T21:41:44Z
- Status: complete
- Checklist item: Checklist snapshot
- Update: `[x] Confirm requirement in docs/PROJECT.md`, `[x] Add/update tests for changed behavior`, `[x] Implement minimal code changes`, `[x] Run local verification for impacted paths`, `[x] Update docs/config examples if needed`, `[x] Mistake replay check logged`.
- Evidence: See entries above in this log.
- Next: None.
