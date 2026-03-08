# Adaptive Portal Run Middle Node Prune

Checklist
- [x] Reproduce/confirm requirement against `docs/PROJECT.md`
- [x] Add/update tests for changed behavior
- [x] Implement minimal code change
- [x] Run focused verification for impacted paths
- [x] Docs check (`docs/PROJECT.md`, `README.md`, `AGENTS.md`)
- [x] Mistake replay check (`logs/mistakes.md`)

## 2026-03-08T00:20:00Z
- Status: in progress
- Checklist item: Reproduce/confirm requirement against `docs/PROJECT.md`
- Update: User-reported map evidence showed many interior nodes still present in `adaptive_portal_run`; root cause identified as adaptive-mask contraction path still using degree-2+junction-preserving contraction instead of boundary-node proxy contraction.
- Evidence: `src/inframap/ingest/major_road_graph.py::contract_edges_within_adaptive_mask_preserving_portals`.
- Next: patch adaptive-mask contraction to use boundary proxy edges for cells with >=2 portal nodes.

## 2026-03-08T00:20:00Z
- Status: in progress
- Checklist item: Add/update tests for changed behavior
- Update: Added adaptive-mask regression test proving multi-portal cell contraction now emits boundary-to-boundary proxy edge even with interior branch/junction.
- Evidence: `tests/unit/test_major_road_graph_contraction.py::test_contract_edges_within_adaptive_mask_preserving_portals_uses_boundary_proxy_for_multi_portal_cell`.
- Next: implement patch and verify deterministic/progress behaviors remain valid.

## 2026-03-08T00:20:00Z
- Status: in progress
- Checklist item: Implement minimal code change
- Update: Updated adaptive-mask contraction loop to use `_cell_metric_proxy_edges` when a cell has at least two portal nodes; preserved fallback degree-2 contraction otherwise and retained per-cell progress callback.
- Evidence: `src/inframap/ingest/major_road_graph.py`.
- Next: run focused tests.

## 2026-03-08T00:20:00Z
- Status: in progress
- Checklist item: Run focused verification for impacted paths
- Update: Ran focused tests for new adaptive-mask proxy behavior, existing deterministic/uncovered behavior, and progress event emission.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py::test_contract_edges_within_adaptive_mask_preserving_portals_uses_boundary_proxy_for_multi_portal_cell tests/unit/test_major_road_graph_contraction.py::test_adaptive_mask_portal_split_and_contract_is_deterministic tests/unit/test_major_road_graph_contraction.py::test_contract_edges_within_adaptive_mask_preserving_portals_keeps_uncovered_segments tests/unit/test_major_road_graph_progress.py::test_build_major_road_graph_variants_emits_progress_events` -> `4 passed in 0.18s`.
- Next: docs/mistake checks and handoff.

## 2026-03-08T00:20:00Z
- Status: complete
- Checklist item: Docs check (`docs/PROJECT.md`, `README.md`, `AGENTS.md`)
- Update: Docs check: no changes required; behavior refinement remains within existing adaptive-run graph-generation pipeline.
- Evidence: no API/workflow contract changes.
- Next: mistake replay check and handoff.

## 2026-03-08T00:20:00Z
- Status: complete
- Checklist item: Mistake replay check (`logs/mistakes.md`)
- Update: Reviewed recent mistake ledger entries and used `apply_patch` for markdown updates.
- Evidence: `logs/mistakes.md` tail review.
- Next: handoff summary and rerun guidance.
