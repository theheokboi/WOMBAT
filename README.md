# Physical Network Infrastructure Map

Deterministic, test-first pipelines for building a multi-resolution map of physical network infrastructure using H3.

## Status

This repository is currently bootstrap-stage. The design and implementation intent are defined in:

- `docs/PROJECT.md`
- `docs/IMPLEMENTATION_PLAN.md`

## Project Goals

- Ingest facility-level datasets (initially CSV/TSV, PeeringDB-style).
- Normalize into canonical facility and organization datasets.
- Index facilities into configured H3 resolutions.
- Compute derived layers (metro clusters and country masks).
- Publish immutable, versioned run artifacts.
- Serve API/tile endpoints and an internal map UI.
- Enforce correctness with strict automated tests and publish gates.

## Core Principles

- Geometry-first: spatial logic comes from coordinates, H3 cells, and polygon rules.
- Determinism: identical inputs and config produce identical outputs.
- Explicit versioning: all outputs are traceable by `run_id`, `inputs_hash`, `config_hash`, and `code_hash`.
- Fail-closed quality: blocking tests and invariants gate publish.
- Simplicity-first UX: internal map clarity over aggressive optimization.

## Planned Architecture

- Pipeline and agent: Python 3.11+
- Spatial indexing: H3 (`h3-py`)
- Geometry tooling: `shapely`, `pyproj`
- Local analytics storage: DuckDB + Parquet
- API: FastAPI
- Map UI: Vite + TypeScript + MapLibre GL JS

## Intended Repository Layout

```text
configs/
src/agent/
src/ingest/
src/normalize/
src/layers/
src/serve/
frontend/
tests/
tests/fixtures/
tests/golden/
docs/
data/                  # gitignored
Makefile
docker-compose.yml
```

## Data and Run Artifacts

Per-run outputs are versioned under:

```text
data/runs/<run_id>/
  inputs/
  canonical/
  layers/
  reports/
```

Publish flow is atomic via staging and a single `data/published/latest` pointer update.

## API Contract (Minimum)

- `GET /v1/runs/latest`
- `GET /v1/layers`
- `GET /v1/layers/{layer}/metadata`
- `GET /v1/facilities`
- `GET /v1/tiles/{z}/{x}/{y}.mvt`
- `GET /v1/health`

## Testing Strategy (Publish-Critical)

Blocking suites:

- Unit tests
- Property-based tests
- Golden regression tests
- Invariant tests
- Integration tests

Non-blocking initially (reported in CI):

- UI smoke tests
- Performance/monitoring tests

## Agentic Development Workflow

- Use `docs/PROJECT.md` as source-of-truth contracts.
- Use `docs/IMPLEMENTATION_PLAN.md` as implementation sequence.
- Build incrementally by milestone with tests added before publish path wiring.
- Treat schema and API contracts as versioned interfaces.
- Keep `README.md` and `AGENTS.md` synchronized with current workflow and contracts in every relevant change.

Detailed operational rules for contributors and coding agents are in `AGENTS.md`.

## Documentation Maintenance

- `README.md` and `AGENTS.md` must be reviewed on every non-trivial change.
- If behavior, contracts, tests, commands, or workflow changed, both files must be updated in the same change set.
- If no update is needed, the change log/progress note must explicitly say docs were reviewed and why no edits were required.

## Next Bootstrap Steps

1. Scaffold Python package and config loader.
2. Implement ingest + canonical normalization + H3 indexing.
3. Add layer plugin registry and `metro_density_core`.
4. Add invariant and golden tests.
5. Expose minimal read-only API.
6. Build internal map with facility and H3 overlays.
