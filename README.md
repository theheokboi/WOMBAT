# Physical Network Infrastructure Map

Deterministic, geometry-first pipelines for building a multi-resolution map of physical network infrastructure using H3.

## Implemented Bootstrap

This repository now includes a working bootstrap stack:

- Deterministic agent pipeline (ingest -> canonicalize -> layer compute -> invariants -> atomic publish)
- Layer plugins: `metro_density_core` (M1), `country_mask` (centroid rule over Natural Earth admin-0 countries with deterministic neighboring-country color classes), and `facility_density_adaptive` (`v3` adaptive hierarchical partition over `country_mask` r4 domain: coarse empty interiors, detailed refinement at boundaries and near occupied cells, with neighbor-resolution smoothing)
- Immutable run artifacts and single latest-pointer publish semantics
- FastAPI read-only API under `/v1`
- Internal map UI at `/ui` with facility and H3 overlays, toggles, tooltips, drill-down, and viewport-based global H3 multi-resolution overlays
- Blocking and non-blocking test suites with explicit make targets

## Run and Serve

```bash
make run
make serve
make ui
```

- `make run` executes the agent pipeline using `configs/system.yaml` and `configs/layers.yaml`.
- `make serve` starts FastAPI on `http://localhost:8000`.
- `make ui` prints the UI URL (`/ui`).

## Quality Gates

```bash
make test-blocking
make test-nonblocking
make test
```

Blocking suites:

- Unit
- Property-based
- Golden regression
- Invariants/publish-gate checks
- Integration

Non-blocking suites:

- UI smoke (`ui_smoke` marker)
- Performance/monitoring (`perf_monitoring` marker)

## API Endpoints

- `GET /v1/runs/latest`
- `GET /v1/layers`
- `GET /v1/layers/{layer}/metadata`
- `GET /v1/layers/{layer}/cells` (`facility_density_adaptive` serves published `v3` cells; deprecated `split_threshold` is rejected with `400`)
- `GET /v1/facilities`
- `GET /v1/tiles/{z}/{x}/{y}.mvt`
- `GET /v1/health`
- `GET /v1/ui/config` (additive helper for UI center/zoom/resolution mapping)

## Data and Artifacts

Input staging:

- `data/facilities/peeringdb_facility.tsv` (PeeringDB facility export schema is normalized during ingest)

Run artifacts:

```text
data/runs/<run_id>/
  inputs/
  canonical/
    facilities.parquet
    organizations.parquet
  layers/
    metro_density_core/m1/
    country_mask/v1/
    facility_density_adaptive/v3/
  reports/
    run_manifest.json
    metrics.json
```

Publish pointer:

- `data/published/latest` (atomic single-file flip)

## Determinism and Safety

- `run_id`, `inputs_hash`, `config_hash`, and `code_hash` are persisted in `reports/run_manifest.json`.
- Canonical outputs and layers are deterministic for identical inputs/config/code.
- Publish is fail-closed and atomic.
- Published run directories are immutable.

## Adaptive Layer Migration (v2 -> v3)

- `facility_density_adaptive` now uses `v3` adaptive partition behavior.
- Empty-space handling is now tiered: interior empty regions stay coarse (up to configured `empty_interior_max_resolution`), while empty cells near country boundaries (`empty_refine_boundary_band_k`) or near occupied cells (`empty_refine_near_occupied_k`) refine in more detail.
- Occupied-cell behavior remains deterministic with floor/cap controls (`facility_floor_resolution`, `facility_max_resolution`, `target_facilities_per_leaf`).
- Resolution transitions are smoothed by `max_neighbor_resolution_delta` to avoid abrupt detail jumps between adjacent cells.
- Update any downstream assumptions that expected aggressive empty-space compaction in `v2`; in `v3`, empty interiors remain readable/coarse while edge and near-activity regions intentionally retain higher detail.
- `split_threshold` remains deprecated and rejected with `400`.

## Agent Quality Workflow

- Agents must maintain an append-only mistake ledger at `logs/mistakes.md`.
- Each mistake must include root cause, corrective action, and a prevention rule.
- Before handoff, agents must perform a mistake replay check to confirm no logged mistake was repeated.

## References

- `docs/PROJECT.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/HANDOVER.md`
- `docs/LOGS.md`
- `docs/NEXT_STEPS.md`
- `AGENTS.md`
