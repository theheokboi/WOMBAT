# Hierarchical Adaptive Facility Layer Plan (v2)

## Summary
This plan replaces the current `facility_density_adaptive` threshold policy with a deterministic hierarchical partition policy:
- Base from `country_mask` land cells at `r4`.
- Empty branches compact upward to `r0`.
- Facility-bearing branches are never coarser than `r9`.
- Any leaf with `>1` facilities keeps splitting to `r13` max.

This version of the plan is designed for parallel implementation by spawning one agent per task, waiting for all, then validating each result.

## Locked Decisions
- Coverage domain: `country_mask` `r4` land cells.
- Partition mode: complete non-overlapping partition.
- Layer migration: keep name `facility_density_adaptive`, bump to `v2`.
- Facility branch rule: recursive split to at least `r9`.
- Dense leaf rule: split until count `<=1` or resolution `13`.
- Compaction: coastline expansion allowed.
- Borders: cross-border compaction allowed.

## Interface Changes
- Layer config (`configs/layers.yaml`) for `facility_density_adaptive`:
  - `version: v2`
  - `base_resolution: 4`
  - `empty_compact_min_resolution: 0`
  - `facility_floor_resolution: 9`
  - `facility_max_resolution: 13`
  - `target_facilities_per_leaf: 1`
  - `allow_domain_expansion: true`
  - `allow_cross_border_compaction: true`
- Layer metadata additions:
  - `policy_name: facility_hierarchical_partition_v2`
  - `coverage_domain: country_mask_r4`
  - stopping-rule fields for empty/facility branches
- API behavior:
  - `/v1/layers/facility_density_adaptive/cells` serves published `v2` cells only.
  - deprecated preview param `split_threshold` should be rejected for this layer with explicit `400`.

## Task Breakdown for Parallel Agents

### Task A: Core algorithm (`src/inframap/layers/facility_density_adaptive.py`)
- Implement recursive/top-down partition over base domain hierarchy.
- Guarantee deterministic ordering and non-overlap.
- Enforce facility floor (`r9`) and max (`r13`) rules.
- Update metadata payload and validation logic.

### Task B: Config + manifest compatibility
- Update `configs/layers.yaml` to `v2` params.
- Ensure manifest/config hash remains deterministic with new params.
- Update tests that assert layer names/versions/params.

### Task C: API contract updates (`src/inframap/serve/app.py`)
- Remove old recompute-on-query behavior for adaptive layer.
- Return explicit error for deprecated preview param on adaptive layer.
- Keep response structure stable (`run_id`, `FeatureCollection`, properties).

### Task D: Tests (unit/integration/golden/invariants)
- Unit tests for:
  - empty compaction to coarse levels,
  - facility floor at `r9`,
  - split-to-singleton or `r13` cap,
  - no ancestor/descendant overlap.
- Integration tests for adaptive endpoint and metadata fields.
- Golden regression updates for deterministic fixture outputs.
- Invariant tests for mixed-resolution partition correctness.

### Task E: UI compatibility check (`frontend/main.js`)
- Ensure existing UI toggle still renders adaptive layer with new metadata/values.
- Update tooltip wording if needed (`layer_value` as leaf facility count).
- Keep controls unchanged (no threshold UI).

### Task F: Documentation and release notes
- Update `README.md` section describing adaptive policy.
- Add migration note (`v1` threshold -> `v2` hierarchical).
- Confirm `AGENTS.md` unchanged unless workflow/contracts changed.

## Parallel Orchestration Procedure
1. Spawn one agent per task (`A` through `F`) with explicit file ownership.
2. For each spawned agent message, include:
   - required files,
   - exact acceptance criteria,
   - instruction to ignore unrelated concurrent edits.
3. Wait for all agents to complete.
4. Collect each agent’s output summary and changed-file list.
5. Run merge pass in main thread:
   - reconcile overlaps,
   - resolve conflicts,
   - ensure final behavior matches locked decisions.
6. Run full verification in main thread (single source of truth):
   - `make run`
   - `make test-blocking`
   - `make test-nonblocking`
7. Result checks before handoff:
   - all agent tasks marked complete,
   - acceptance criteria satisfied per task,
   - no contract drift in API/layer metadata,
   - progress log and mistake replay check updated.

## Result Validation Checklist (post-agent)
- [ ] Adaptive layer emits deterministic mixed-resolution partition.
- [ ] Facility-bearing leaves are never coarser than `r9`.
- [ ] Collisions split to `r13` cap.
- [ ] No overlapping ancestor/descendant leaves.
- [ ] API returns expected metadata and cells schema.
- [ ] Full test suites pass.
- [ ] Docs and logs updated.

## Rollout and Risk Controls
- Keep layer name stable; version bump to `v2` in metadata.
- Preserve country layer unchanged for visual context.
- Treat any failure in new invariants/goldens as blocking.
- If outputs explode in size, investigate domain pruning before relaxing rules.
