# Adaptive Portal Run Boundary Connectivity

Checklist
- [x] Reproduce/confirm requirement against `docs/PROJECT.md`
- [x] Add/update tests for changed behavior
- [x] Implement minimal code change
- [x] Run focused verification for impacted paths
- [x] Docs check (`docs/PROJECT.md`, `README.md`, `AGENTS.md`)
- [x] Mistake replay check (`logs/mistakes.md`)

## 2026-03-07T23:47:00Z
- Status: in progress
- Checklist item: Reproduce/confirm requirement against `docs/PROJECT.md`
- Update: Confirmed `adaptive_portal_run` contract and split/portal path in ingest pipeline; identified likely boundary portal ID directionality issue causing duplicate near-coincident boundary nodes and apparent disconnects.
- Evidence: `docs/PROJECT.md:71`; `src/inframap/ingest/major_road_graph.py` (`split_edges_with_adaptive_mask_portals`, `_build_portal_node_id_for_mask`).
- Next: Add regression test that enforces direction-invariant portal node ID behavior.

## 2026-03-07T23:29:21Z
- Status: in progress
- Checklist item: Add/update tests for changed behavior
- Update: Added a targeted regression test to require direction-invariant mask portal IDs for opposite traversal across the same boundary point.
- Evidence: `tests/unit/test_major_road_graph_contraction.py::test_build_portal_node_id_for_mask_is_direction_invariant`.
- Next: Implement minimal ID normalization in `_build_portal_node_id_for_mask`.

## 2026-03-07T23:29:21Z
- Status: in progress
- Checklist item: Implement minimal code change
- Update: Normalized mask boundary cell pair ordering before hashing portal node IDs so reverse traversal reuses the same portal node.
- Evidence: `src/inframap/ingest/major_road_graph.py` (`_build_portal_node_id_for_mask`).
- Next: Run focused unit tests for adaptive mask portal split/contract behavior.

## 2026-03-07T23:29:21Z
- Status: in progress
- Checklist item: Run focused verification for impacted paths
- Update: Executed focused pytest set covering the new test and adjacent adaptive-mask split/contract determinism behavior.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py::test_build_portal_node_id_for_mask_is_direction_invariant tests/unit/test_major_road_graph_contraction.py::test_split_edges_with_adaptive_mask_portals_and_contract_keeps_mask_membership tests/unit/test_major_road_graph_contraction.py::test_adaptive_mask_portal_split_and_contract_is_deterministic` -> `3 passed in 0.16s`.
- Next: Complete docs and mistake replay checks, then hand off summary.

## 2026-03-07T23:29:21Z
- Status: complete
- Checklist item: Docs check (`docs/PROJECT.md`, `README.md`, `AGENTS.md`)
- Update: Docs check: no changes required; behavior/interface contract unchanged (bugfix only for boundary portal node identity stability in existing `adaptive_portal_run` flow).
- Evidence: Existing contract still satisfied by `docs/PROJECT.md:71`.
- Next: Perform mistake replay check and finalize handoff.

## 2026-03-07T23:29:21Z
- Status: complete
- Checklist item: Mistake replay check (`logs/mistakes.md`)
- Update: Reviewed recent ledger entries and confirmed this task used `apply_patch` for markdown log edits to avoid prior shell interpolation mistakes.
- Evidence: `logs/mistakes.md` tail review and this file append history.
- Next: Handoff with changed files and focused test results.
