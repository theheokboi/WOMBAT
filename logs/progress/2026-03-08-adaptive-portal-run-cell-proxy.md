# Adaptive Portal Run Cell Proxy

Checklist
- [x] Reproduce/confirm requirement against `docs/PROJECT.md`
- [x] Add/update tests for changed behavior
- [x] Implement minimal code change
- [x] Run focused verification for impacted paths
- [x] Docs check (`docs/PROJECT.md`, `README.md`, `AGENTS.md`)
- [x] Mistake replay check (`logs/mistakes.md`)

## 2026-03-08T00:12:00Z
- Status: in progress
- Checklist item: Reproduce/confirm requirement against `docs/PROJECT.md`
- Update: Interpreted request as per-cell boundary-node proxying for `adaptive_portal_run`: keep shortest-path connectivity between portal/boundary nodes, drop interior middle edges where possible, and bias to larger roads.
- Evidence: in-thread request and `src/inframap/ingest/major_road_graph.py::contract_edges_within_adaptive_mask_preserving_portals`.
- Next: Add tests for boundary-chain collapse and class-biased path preference.

## 2026-03-08T00:12:00Z
- Status: in progress
- Checklist item: Add/update tests for changed behavior
- Update: Added unit tests for cell metric proxy behavior (portal-to-portal collapse and larger-road preference).
- Evidence: `tests/unit/test_major_road_graph_contraction.py::test_cell_metric_proxy_edges_collapses_boundary_chain`, `tests/unit/test_major_road_graph_contraction.py::test_cell_metric_proxy_edges_prefers_larger_roads_with_bias`.
- Next: Implement per-cell metric proxy generation and wire it into adaptive-mask contraction.

## 2026-03-08T00:12:00Z
- Status: in progress
- Checklist item: Implement minimal code change
- Update: Implemented distance/cost helpers and `_cell_metric_proxy_edges`; updated `contract_edges_within_adaptive_mask_preserving_portals` to use portal-to-portal proxy edges for cells with at least two portal nodes, while retaining previous contraction behavior for low-terminal cells.
- Evidence: `src/inframap/ingest/major_road_graph.py`.
- Next: Run focused pytest set for new and adjacent adaptive-mask behavior.

## 2026-03-08T00:12:00Z
- Status: in progress
- Checklist item: Run focused verification for impacted paths
- Update: Executed focused tests covering new proxy behavior and existing adaptive-mask split/contract/filter behavior.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py::test_cell_metric_proxy_edges_collapses_boundary_chain tests/unit/test_major_road_graph_contraction.py::test_cell_metric_proxy_edges_prefers_larger_roads_with_bias tests/unit/test_major_road_graph_contraction.py::test_split_edges_with_adaptive_mask_portals_and_contract_keeps_mask_membership tests/unit/test_major_road_graph_contraction.py::test_contract_edges_within_adaptive_mask_preserving_portals_keeps_uncovered_segments tests/unit/test_major_road_graph_contraction.py::test_adaptive_mask_portal_split_and_contract_is_deterministic tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_adaptive_mask_uses_cell_resolution tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_adaptive_mask_uncovered_uses_coarsest_neighbor_resolution` -> `7 passed in 0.17s`.
- Next: Docs check and mistake replay check then handoff.

## 2026-03-08T00:12:00Z
- Status: complete
- Checklist item: Docs check (`docs/PROJECT.md`, `README.md`, `AGENTS.md`)
- Update: Docs check: no changes required; this is an internal adaptive-run contraction strategy update without API/workflow contract changes.
- Evidence: no interface/path changes.
- Next: Mistake replay check.

## 2026-03-08T00:12:00Z
- Status: complete
- Checklist item: Mistake replay check (`logs/mistakes.md`)
- Update: Reviewed recent mistake ledger entries; all markdown updates in this task were applied via `apply_patch`.
- Evidence: `logs/mistakes.md` tail review.
- Next: Handoff summary with changed files and validation.
