# Facility Gated Fine Classes

Checklist
- [~] Confirm requirement in docs/PROJECT.md
- [ ] Add/update tests for changed behavior
- [ ] Implement minimal code changes
- [ ] Run local verification for impacted paths
- [ ] Update docs/config examples if needed
- [ ] Mistake replay check logged

## 2026-03-07T21:54:54Z
- Status: in progress
- Checklist item: Confirm requirement in docs/PROJECT.md
- Update: Started task to gate `r6+` fine classes by facility/landing presence for adaptive portal run filtering.
- Evidence: User requirement in chat; `build_major_roads_graph.py` currently loads adaptive mask cells from `facility_density_adaptive`.
- Next: Add tests and wire occupied-cell context from run layer into ingest filter.

## 2026-03-07T21:56:52Z
- Status: in progress
- Checklist item: Add/update tests for changed behavior
- Update: Updated adaptive-mask filter unit test to require occupied-cell gating for fine classes and to verify unoccupied fine cells fall back to coarse classes.
- Evidence: tests/unit/test_major_road_graph_contraction.py (test_filter_mainline_edges_adaptive_mask_uses_cell_resolution)
- Next: Implement occupied-cell-aware filtering and pass occupied-cell context from run data loader.

## 2026-03-07T21:56:52Z
- Status: in progress
- Checklist item: Implement minimal code changes
- Update: Added optional `occupied_cells` handling in adaptive-mask class filtering, threaded `adaptive_occupied_cells` through graph variant builder, and updated run graph build script to load occupied cells from `facility_density_adaptive` where `layer_value > 0`.
- Evidence: src/inframap/ingest/major_road_graph.py, scripts/build_major_roads_graph.py
- Next: Run focused pytest and update docs wording.

## 2026-03-07T21:56:52Z
- Status: in progress
- Checklist item: Run local verification for impacted paths
- Update: Focused pytest passed for changed ingest behavior plus affected serve/UI smoke checks.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_fixed_resolution_applies_coarse_and_fine_class_sets tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_adaptive_mask_uses_cell_resolution tests/unit/test_serve_osm_transport.py::test_osm_transport_overlay_filters_mainline_classes_and_includes_railway tests/unit/test_serve_osm_transport.py::test_osm_transport_overlay_skips_missing_files_and_lists_available_countries tests/ui/test_ui_smoke.py::test_ui_static_smoke` -> `5 passed in 0.97s`.
- Next: Finalize docs update note and mistake replay check.

## 2026-03-07T21:56:52Z
- Status: complete
- Checklist item: Update docs/config examples if needed
- Update: Updated project and README contract text to clarify facility-gated fine classes for `adaptive_portal_run`.
- Evidence: docs/PROJECT.md, README.md
- Next: Run mistake replay check and finalize checklist.

## 2026-03-07T21:57:11Z
- Status: complete
- Checklist item: Mistake replay check logged
- Update: Replayed latest mistake ledger entries and confirmed log updates used apply_patch and verification remained focused to changed behavior.
- Evidence: `rg -n "^## " logs/mistakes.md | tail -n 5`
- Next: Finalize checklist snapshot and handoff.

## 2026-03-07T21:57:11Z
- Status: complete
- Checklist item: Checklist snapshot
- Update: `[x] Confirm requirement in docs/PROJECT.md`, `[x] Add/update tests for changed behavior`, `[x] Implement minimal code changes`, `[x] Run local verification for impacted paths`, `[x] Update docs/config examples if needed`, `[x] Mistake replay check logged`.
- Evidence: See entries above in this log.
- Next: None.
