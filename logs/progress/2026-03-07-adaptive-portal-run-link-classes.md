# Adaptive Portal Run Link Classes

Checklist
- [x] Reproduce/confirm requirement against `docs/PROJECT.md`
- [x] Add/update tests for changed behavior
- [x] Implement minimal code change
- [x] Run focused verification for impacted paths
- [x] Docs check (`docs/PROJECT.md`, `README.md`, `AGENTS.md`)
- [x] Mistake replay check (`logs/mistakes.md`)

## 2026-03-07T23:44:00Z
- Status: in progress
- Checklist item: Reproduce/confirm requirement against `docs/PROJECT.md`
- Update: Requirement is scoped to `adaptive_portal_run` post-contract class filter; include `motorway_link` and `trunk_link` in addition to existing mainline classes.
- Evidence: `src/inframap/ingest/major_road_graph.py::_filter_mainline_edges_for_adaptive_mask`.
- Next: Update/extend unit test for adaptive-mask filtering class behavior.

## 2026-03-07T23:43:29Z
- Status: in progress
- Checklist item: Add/update tests for changed behavior
- Update: Extended adaptive-mask class filter test to include `motorway_link`, `trunk_link`, and `primary_link` control case.
- Evidence: `tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_adaptive_mask_uses_cell_resolution`.
- Next: Implement adaptive-mask filter allowance for `motorway_link` and `trunk_link`.

## 2026-03-07T23:43:29Z
- Status: in progress
- Checklist item: Implement minimal code change
- Update: Updated `adaptive_portal_run` mainline filter to keep existing mainline classes plus `motorway_link` and `trunk_link`.
- Evidence: `src/inframap/ingest/major_road_graph.py::_filter_mainline_edges_for_adaptive_mask`.
- Next: Run focused unit test.

## 2026-03-07T23:43:29Z
- Status: in progress
- Checklist item: Run focused verification for impacted paths
- Update: Ran targeted pytest for adaptive-mask class filtering behavior.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_adaptive_mask_uses_cell_resolution` -> `1 passed in 0.16s`.
- Next: Docs and mistake replay checks, then handoff.

## 2026-03-07T23:43:29Z
- Status: complete
- Checklist item: Docs check (`docs/PROJECT.md`, `README.md`, `AGENTS.md`)
- Update: Docs check: no changes required; this is a narrow class inclusion change for existing `adaptive_portal_run` filtering behavior.
- Evidence: no API/workflow contract changes.
- Next: Mistake replay check.

## 2026-03-07T23:43:29Z
- Status: complete
- Checklist item: Mistake replay check (`logs/mistakes.md`)
- Update: Reviewed latest mistake ledger entries and continued using `apply_patch` for markdown log updates.
- Evidence: `logs/mistakes.md` tail review.
- Next: Handoff summary with files changed and test result.
