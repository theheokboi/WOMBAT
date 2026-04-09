# Adaptive Mainline Primary Only And Node Prune

Checklist
- [~] Confirm requirement in docs/PROJECT.md
- [ ] Add/update tests for changed behavior
- [ ] Implement minimal code changes
- [ ] Run local verification for impacted paths
- [ ] Update docs/config examples if needed
- [ ] Mistake replay check logged

## 2026-03-07T22:14:03Z
- Status: in progress
- Checklist item: Confirm requirement in docs/PROJECT.md
- Update: Started task to enforce `motorway`/`trunk`/`primary` filtering for adaptive portal variants across all cells and prune nodes not connected to retained edges.
- Evidence: User request with screenshot showing orphan node artifacts.
- Next: Update ingest filters, node selection, tests, and docs.

## 2026-03-07T22:16:12Z
- Status: in progress
- Checklist item: Add/update tests for changed behavior
- Update: Updated ingest unit tests to assert both fixed and adaptive-mask filters keep only `motorway`/`trunk`/`primary`; added node-connectivity helper test and updated UI smoke assertions to only require `OSM primary` (not secondary/tertiary/unclassified/residential legend rows).
- Evidence: tests/unit/test_major_road_graph_contraction.py, tests/ui/test_ui_smoke.py
- Next: Finalize code wiring and run focused pytest.

## 2026-03-07T22:16:12Z
- Status: in progress
- Checklist item: Implement minimal code changes
- Update: Switched adaptive class filters to a single allow-list for all cells and added connected-node intersection when writing adaptive portal nodes, preventing orphan nodes without edges.
- Evidence: src/inframap/ingest/major_road_graph.py
- Next: Validate with focused pytest and update docs wording.

## 2026-03-07T22:16:12Z
- Status: in progress
- Checklist item: Run local verification for impacted paths
- Update: Focused pytest passed for updated filter behavior, node connectivity helper, and UI smoke assertions.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_fixed_resolution_keeps_only_motorway_trunk_primary tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_adaptive_mask_uses_cell_resolution tests/unit/test_major_road_graph_contraction.py::test_connected_node_ids_contains_only_edge_endpoints tests/ui/test_ui_smoke.py::test_ui_static_smoke` -> `4 passed in 0.94s`.
- Next: Finalize docs note and run mistake replay check.

## 2026-03-07T22:16:12Z
- Status: complete
- Checklist item: Update docs/config examples if needed
- Update: Updated `docs/PROJECT.md` and `README.md` to reflect `motorway`/`trunk`/`primary` adaptive filtering for all cells and connected-anchor node pruning semantics.
- Evidence: docs/PROJECT.md, README.md
- Next: Run mistake replay check and finalize checklist snapshot.

## 2026-03-07T22:16:29Z
- Status: complete
- Checklist item: Mistake replay check logged
- Update: Replayed recent mistake ledger entries and confirmed this task used apply_patch log updates and focused verification only.
- Evidence: `rg -n "^## " logs/mistakes.md | tail -n 5`
- Next: Finalize checklist snapshot and handoff.

## 2026-03-07T22:16:29Z
- Status: complete
- Checklist item: Checklist snapshot
- Update: `[x] Confirm requirement in docs/PROJECT.md`, `[x] Add/update tests for changed behavior`, `[x] Implement minimal code changes`, `[x] Run local verification for impacted paths`, `[x] Update docs/config examples if needed`, `[x] Mistake replay check logged`.
- Evidence: See entries above in this log.
- Next: None.

## 2026-03-07T22:29:12Z
- Status: in progress
- Checklist item: Add/update tests for changed behavior
- Update: Updated adaptive mainline test expectations to include `secondary` in fixed-resolution and adaptive-mask filters; updated UI smoke assertions for `OSM secondary` legend/style.
- Evidence: tests/unit/test_major_road_graph_contraction.py, tests/ui/test_ui_smoke.py
- Next: Run focused pytest for changed tests.

## 2026-03-07T22:29:12Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: Focused pytest passed for changed adaptive class filter and UI smoke coverage.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_fixed_resolution_keeps_only_motorway_trunk_primary_secondary tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_adaptive_mask_uses_cell_resolution tests/ui/test_ui_smoke.py::test_ui_static_smoke` -> `3 passed in 0.82s`.
- Next: Finalize docs wording for adaptive portal class list and handoff.

## 2026-03-07T22:29:12Z
- Status: complete
- Checklist item: Update docs/config examples if needed
- Update: Updated README and PROJECT docs to state `adaptive_portal`/`adaptive_portal_run` now retain `motorway`/`trunk`/`primary`/`secondary` classes.
- Evidence: README.md, docs/PROJECT.md
- Next: Handoff summary with files changed.

## 2026-03-07T22:31:20Z
- Status: in progress
- Checklist item: Implement minimal code changes
- Update: Updated country-mask tooltip content in UI to include cell resolution and adaptive portal polygon resolution context derived from run status (`country_mask_resolution`) with fallback to feature resolution.
- Evidence: frontend/main.js
- Next: Run UI smoke test for impacted behavior.

## 2026-03-07T22:31:20Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: UI smoke test passed after tooltip update.
- Evidence: `pytest -q tests/ui/test_ui_smoke.py::test_ui_static_smoke` -> `1 passed in 0.91s`.
- Next: Handoff summary.

## 2026-03-07T22:36:24Z
- Status: complete
- Checklist item: Implement minimal code changes
- Update: Changed country H3 UI rendering to target `r6` display polygons by expanding/collapsing source country-mask cells client-side; added viewport-aware expansion and a feature-count safety cap fallback to coarse cells.
- Evidence: frontend/main.js
- Next: Validate UI smoke for impacted frontend path.

## 2026-03-07T22:36:24Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: UI smoke test passes after country-layer rendering update.
- Evidence: `pytest -q tests/ui/test_ui_smoke.py::test_ui_static_smoke` -> `1 passed in 0.73s`.
- Next: Handoff summary.

## 2026-03-07T22:40:53Z
- Status: complete
- Checklist item: Implement minimal code changes
- Update: Changed `scripts/build_major_roads_graph.py` default `--adaptive-resolution` from `6` to `3`, so fixed-resolution `adaptive_portal` builds now run on `r3` unless overridden.
- Evidence: scripts/build_major_roads_graph.py
- Next: Verify CLI default value and refresh docs note.

## 2026-03-07T22:40:53Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: Verified CLI parse default resolves to `3` with a direct parse check.
- Evidence: `python - <<'PY' ... parse_args().adaptive_resolution -> 3`.
- Next: Handoff summary.

## 2026-03-07T22:40:53Z
- Status: complete
- Checklist item: Update docs/config examples if needed
- Update: Added README note that fixed-resolution adaptive outputs default to `--adaptive-resolution 3`.
- Evidence: README.md
- Next: None.

## 2026-03-07T22:51:00Z
- Status: complete
- Checklist item: Implement minimal code changes
- Update: Added early per-cell class-priority filtering for `adaptive_portal` before portal splitting/contraction (`motorway` > `trunk` > `primary` > `secondary`) to cut contraction workload in coarse fixed resolutions.
- Evidence: src/inframap/ingest/major_road_graph.py
- Next: Add focused unit coverage and run targeted pytest.

## 2026-03-07T22:51:00Z
- Status: complete
- Checklist item: Add/update tests for changed behavior
- Update: Added a unit test that verifies per-cell highest-priority class retention for early filtering.
- Evidence: tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_by_cell_priority_keeps_highest_class_per_cell
- Next: Verify focused unit set.

## 2026-03-07T22:51:00Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: Focused unit tests passed for new early priority filter plus existing fixed/adaptive class filters.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_by_cell_priority_keeps_highest_class_per_cell tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_fixed_resolution_keeps_only_motorway_trunk_primary_secondary tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_adaptive_mask_uses_cell_resolution` -> `3 passed in 0.16s`.
- Next: Keep docs wording aligned.

## 2026-03-07T22:51:00Z
- Status: complete
- Checklist item: Update docs/config examples if needed
- Update: Updated README/PROJECT wording to document early per-cell priority filtering for `adaptive_portal` and clarified `adaptive_portal_run` filtering wording.
- Evidence: README.md, docs/PROJECT.md
- Next: Handoff summary.

## 2026-03-07T22:58:03Z
- Status: complete
- Checklist item: Implement minimal code changes
- Update: Added sub-step progress events and CLI logs for long-running adaptive portal stages (`early_class_priority_filter`, split, contract, post-filter) with elapsed time and counts.
- Evidence: src/inframap/ingest/major_road_graph.py, scripts/build_major_roads_graph.py
- Next: Verify progress-event tests.

## 2026-03-07T22:58:03Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: Focused tests passed for progress-event emission and adaptive portal priority filtering.
- Evidence: `pytest -q tests/unit/test_major_road_graph_progress.py::test_build_major_road_graph_variants_emits_progress_events tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_by_cell_priority_keeps_highest_class_per_cell` -> `2 passed in 0.15s`.
- Next: Handoff summary.

## 2026-03-07T22:53:24Z
- Status: complete
- Checklist item: Log timestamp correction
- Update: Corrected prior entry timestamp mismatch; this entry records the actual UTC append time.
- Evidence: shell UTC timestamp at append time.
- Next: None.

## 2026-03-07T22:59:12Z
- Status: complete
- Checklist item: Implement minimal code changes
- Update: Added adaptive-portal fixed-resolution metadata to graph features/API payload and UI overlay for country cells at that resolution when  + .
- Evidence: src/inframap/ingest/major_road_graph.py, src/inframap/serve/app.py, frontend/main.js, frontend/index.html, frontend/styles.css
- Next: Run focused UI/serve tests.

## 2026-03-07T22:59:12Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: Focused tests passed for adaptive-portal transport payload metadata and UI static smoke.
- Evidence: ..                                                                       [100%]
2 passed in 0.77s -> .
- Next: Handoff summary.

## 2026-03-07T22:59:20Z
- Status: complete
- Checklist item: Log append correction
- Update: Corrected previous append command quoting issue and recorded this update with plain-text evidence.
- Evidence: pytest -q tests/unit/test_serve_osm_transport.py::test_osm_transport_overlay_source_graph_variant_adaptive_portal_loads_adaptive_portal_files tests/ui/test_ui_smoke.py::test_ui_static_smoke -> 2 passed in 0.87s.
- Next: None.

## 2026-03-07T22:59:28Z
- Status: complete
- Checklist item: Implement minimal code changes
- Update: Added adaptive-portal fixed-resolution metadata to graph features/API payload and UI overlay for country cells at that resolution when source=graph and graph_variant=adaptive_portal.
- Evidence: src/inframap/ingest/major_road_graph.py, src/inframap/serve/app.py, frontend/main.js, frontend/index.html, frontend/styles.css.
- Next: Run focused UI and serve tests.

## 2026-03-07T22:59:28Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: Focused tests passed for adaptive-portal transport payload metadata and UI static smoke.
- Evidence: pytest -q tests/unit/test_serve_osm_transport.py::test_osm_transport_overlay_source_graph_variant_adaptive_portal_loads_adaptive_portal_files tests/ui/test_ui_smoke.py::test_ui_static_smoke -> 2 passed in 0.87s.
- Next: Handoff summary.
