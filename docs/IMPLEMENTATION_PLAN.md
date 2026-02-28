# Implementation Plan: H3 Infrastructure Map (Test-First, Clarity-First)

## Summary
Build the project from scratch as a Python + FastAPI backend with a simple Vite + MapLibre frontend, centered on deterministic run artifacts and a strong test suite.
Given your guidance, this plan optimizes for simplicity and clarity over performance, with explicit map support for both facility points and H3 grid layers.

## Scope and Priorities
- In scope:
- Deterministic agent pipeline (ingest, normalize, H3 index, layer compute, validate, publish).
- Read-only API for runs, layers, facilities, and tiles.
- Internal UI that clearly visualizes facilities and H3 cells (metro + country layers).
- Strong automated test suite with publish gating.
- Out of scope for initial implementation:
- Performance optimization and scale tuning.
- Advanced auth/RBAC and multi-tenant concerns.
- Complex cross-source entity resolution beyond explicit configured rules.

## Chosen Defaults (resolving vague areas)
- Stack: Python 3.11+, FastAPI, DuckDB + Parquet for local canonical storage, PostGIS optional later.
- Frontend: Vite + TypeScript + MapLibre GL JS; minimal UI components.
- Publish gates: strict core gates (unit + property + golden + invariants + integration are blocking); perf and UI smoke are non-blocking in CI initially.
- Country layer: Natural Earth Admin-0 polygons with `centroid_in_polygon` membership rule.
- Local-first operation: manual CSV input and deterministic local run directories.

## Repository Structure
- `configs/`
- `src/agent/`
- `src/ingest/`
- `src/normalize/`
- `src/layers/`
- `src/serve/`
- `frontend/`
- `tests/`
- `tests/fixtures/`
- `tests/golden/`
- `data/` (gitignored)
- `Makefile`
- `docker-compose.yml`

## Architecture and Implementation Steps

### 1) Core configuration and run manifest
- Implement versioned config loading from `configs/system.yaml` and `configs/layers.yaml`.
- Compute and persist:
- `inputs_hash`
- `config_hash`
- `code_hash`
- `run_id` format `YYYYMMDD-HHMMSS-<git_sha>-<config_hash_short>`
- Write `run_manifest.json` into each run.
- Enforce immutable published run directories.

### 2) Ingestion and canonicalization
- Implement CSV/TSV source adapter with required contract fields.
- Validate raw schema and coordinate bounds.
- Normalize into canonical facility schema with stable `facility_id`, `org_id`, and `record_hash`.
- Add H3 indices for configured resolutions into canonical data.
- Persist canonical artifacts:
- `canonical/facilities.parquet`
- `canonical/organizations.parquet`

### 3) Layer framework
- Build layer registry loader (`configs/layers.yaml`) with explicit plugin imports only.
- Implement plugin interface:
- `spec()`
- `compute(canonical_store, layer_store, params)`
- `validate(artifacts)`
- Implement initial layers:
- `metro_density_core` (M1) with deterministic tie-breaking and optional contiguity enforcement.
- `country_mask` using Natural Earth + centroid rule at configured H3 resolution.
- Persist `layer_metadata.json` + `cells.parquet` for each layer version.

### 4) Publish and failure policy
- Implement staging then atomic pointer flip:
- Stage under `data/staging/<run_id>/`
- Validate all blocking checks
- Publish under `data/runs/<run_id>/`
- Update `data/published/latest`
- Enforce fail-closed default policy.
- Critical layer failure blocks publish; optional layer failure is reported and excluded.

### 5) Serving API and tiles
- Implement FastAPI endpoints:
- `GET /v1/runs/latest`
- `GET /v1/layers`
- `GET /v1/layers/{layer}/metadata`
- `GET /v1/facilities`
- `GET /v1/tiles/{z}/{x}/{y}.mvt`
- `GET /v1/health`
- Ensure every response includes `run_id` and relevant `layer_version`.
- Implement simple vector tile strategy first from precomputed H3/facility data.

### 6) UI (internal clarity)
- Build a minimal map UI with:
- Layer toggles for facilities, metro H3 cells, country mask H3 cells.
- Filters for organization, source, run snapshot.
- Tooltip with facility/layer provenance.
- Click drill-down listing facilities in selected H3 cell.
- Stable zoom-to-H3 resolution mapping from backend config (not computed ad hoc in UI).
- Priority: clear legend, visible H3 boundaries, deterministic rendering behavior.

## Public APIs / Interfaces / Types

### API contracts
- Keep `/v1/*` versioning strict.
- Define OpenAPI schemas for:
- Run metadata (`run_id`, hashes, timestamps, status).
- Layer metadata (`layer_name`, `layer_version`, params, semantics, provenance).
- Facility record DTO (canonical fields + selected filters).
- Health response with readiness and active run.

### Internal plugin interfaces
- `LayerPlugin` protocol with `spec`, `compute`, `validate`.
- `SourceAdapter` protocol with `fetch`, `parse`, `normalize`, `source_provenance`.
- Shared typed models for `RunManifest`, `LayerMetadata`, and `ValidationReport`.

### Data contracts
- Canonical parquet schema aligned to project doc.
- Layer `cells.parquet` minimum fields:
- `h3`, `resolution`, `layer_value`, `layer_id`, `asof_date`

## Testing Strategy (Primary Focus)

### 1) Unit tests (blocking)
- Raw parser required fields and delimiter handling.
- Coordinate validation and normalization.
- H3 indexing for every configured resolution.
- Grid distance and error handling.
- Config/layer parameter hashing determinism.

### 2) Property-based tests (blocking)
- Deterministic point-to-H3 mapping.
- Identical inputs/config produce identical outputs and metadata hashes.
- M1 metro result is subset of candidate `Y` neighborhood.
- Contiguity enforcement always produces connected component containing seed.

### 3) Golden regression tests (blocking)
- Fixture CSV with known coordinates and expected canonical parquet checksum.
- Fixture metro parameters with exact expected H3 cell set.
- Fixture country polygon with expected country-cell membership.
- Metadata hash snapshots (`inputs_hash`, `config_hash`, layer metadata).

### 4) Invariant tests (blocking publish gates)
- Facility:
- No invalid lat/lon.
- No missing H3 at required resolutions.
- Unique `facility_id`.
- Layer:
- Metadata includes required provenance/hash fields.
- Cell resolutions match layer-declared resolution.
- Contiguous metro contains seed cell when contiguity is enabled.
- Country:
- At most one country per facility (unless explicitly configured exception).
- Non-empty cell sets for configured countries with polygon presence.
- System:
- Atomic publish pointer behavior.
- Published run immutability.

### 5) Integration tests (blocking)
- End-to-end fixture run from ingest to publish.
- API endpoints return valid data against published run.
- Tile endpoint returns non-empty tile for known fixture viewport.
- UI-backend contract smoke using fixture run.

### 6) UI smoke tests (non-blocking initially, required in CI report)
- Map load success.
- Facilities layer visible.
- Metro H3 layer visible.
- Tooltip appears for known fixture feature.

### 7) Performance/monitoring tests (non-blocking initially)
- Throughput baseline for H3 indexing.
- Layer compute duration trend capture.
- Health endpoint includes run metadata.
- Failure path test confirms publish is refused on gate failure.

## CI/CD and Quality Gates
- CI stages:
- `lint/typecheck`
- `unit`
- `property`
- `golden`
- `integration`
- `ui-smoke`
- `perf-monitor`
- Publish allowed only if blocking suites pass.
- Golden update process must be explicit and reviewable (no silent rebaseline).

## Milestone Execution Plan
1. Milestone 1: Config, ingest, canonical storage, H3 indexing, core invariants.
2. Milestone 2: Layer framework + metro M1 + golden tests.
3. Milestone 3: Country mask layer + semantics metadata + tests.
4. Milestone 4: Serving endpoints + tiles + integration coverage.
5. Milestone 5: Frontend map with facilities + H3 grid overlays + smoke tests.
6. Milestone 6: Observability + failure containment + hardened plugin contracts.

## Acceptance Criteria
- Deterministic reruns produce identical canonical/layer outputs for same inputs/config.
- Publish is atomic and never partial.
- UI clearly shows both facility points and H3 grid layers with toggles/filters.
- Test suite enforces correctness via blocking gates and catches output drift via goldens.
- All artifacts and API responses are traceable via `run_id`, `inputs_hash`, `config_hash`, and `code_hash`.

## Assumptions
- Initial repository starts from docs-only and is scaffolded from scratch.
- Initial input source is local CSV/TSV (PeeringDB-style schema).
- Internal use means simplicity and correctness are prioritized over throughput and latency.
- Natural Earth licensing and dataset availability are acceptable for internal use.
