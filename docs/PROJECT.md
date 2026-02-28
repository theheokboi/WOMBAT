# Physical Network Infrastructure Map
## Design Document for a Long-Running Agent (Bootstrap from Scratch)

### Document status
Version: v0.1
Owner: <TBD>
Last updated: <YYYY-MM-DD>

---

## 1. Problem description

This project builds a reproducible, multi-resolution map of physical network infrastructure from heterogeneous sources. The system must support interactive visualization and analysis at multiple spatial granularities, including facility-level points, functional “metro” clusters, and country-level partitions.

The primary difficulty is inconsistent and non-canonical “geolocation” labels across sources. Place names (CITY/STATE) are treated as metadata, not as geometry. All spatial decisions must be derived from explicit geometry (latitude/longitude) and from explicit region definitions (H3 cell sets or polygon datasets).

The project explicitly supports operational geographies used by networks (for example “ORD” as a metro label). It does not require administrative boundaries for metros.

The system must be driven by a long-running agent that ingests data, normalizes it, computes derived layers, validates outputs, and publishes artifacts for an interactive web map. The agent must be deterministic, versioned, observable, and testable.

### 1.1 Goals
A. Ingest facility-level datasets (initially PeeringDB-style exports) and normalize them into a canonical facility store.
B. Index facilities into an H3 grid for fast joins, aggregation, and multi-resolution visualization.
C. Support user-defined functional metros as H3 cell sets, including density-derived cluster definitions.
D. Support country-level membership using polygon-to-grid assignment.
E. Provide a deployable interactive web interface that can visualize and filter facilities and derived layers.
F. Provide explicit extension contracts for new sources and new layers.
G. Provide a rigorous automated test suite for the agent, including regression and invariant tests.

### 1.2 Non-goals
A. Administrative city boundary accuracy for metros.
B. Drawing geopolitical conclusions. Country boundaries are a technical input choice.
C. Inferring facility locations from IP geolocation. This system is geometry-first and facility-first.
D. Fiber route inference or router-level inference unless explicitly added later as new layers.

### 1.3 Terms and definitions
Facility: A physical site represented by a point geometry (lat/lon). A “facility” may represent a single building or a campus centroid if the source aggregates multiple buildings.
Layer: A derived dataset intended for visualization or analysis (for example metro clusters, country masks, density heatmaps).
Metro (operational): A functional cluster of infrastructure defined by a rule over H3 cells and/or facilities. This is not an administrative city.
Canonical geometry: The explicit geometry or cell-set representation that this system declares as the reference for a region or entity.

---

## 2. Inputs, outputs, and data contracts

### 2.1 Raw input format (minimum contract)
The minimum supported input is a delimited text file (CSV or TSV) with the following columns.

| Column | Type | Required | Semantics |
|---|---:|---:|---|
| ORGANIZATION | string | yes | Operator or owner label from source |
| NODE_NAME | string | yes | Facility label from source |
| LATITUDE | float | yes | WGS84 latitude |
| LONGITUDE | float | yes | WGS84 longitude |
| CITY | string | no | Source label only |
| STATE | string | no | Source label only |
| COUNTRY | string | no | Source label only (not authoritative unless source is trusted for this field) |
| SOURCE | string | yes | Source name (e.g., PeeringDB) |
| ASOF_DATE | date | yes | Effective date for snapshot |

### 2.2 Canonical internal representations
All canonical datasets must be stored in an explicit, versioned snapshot directory. Storage format is Parquet for analytics and a database representation for serving.

Canonical file layout for a run:
`data/runs/<run_id>/`
`data/runs/<run_id>/inputs/`
`data/runs/<run_id>/canonical/`
`data/runs/<run_id>/layers/`
`data/runs/<run_id>/reports/`

All artifacts in a run directory must be immutable after publish.

### 2.3 Canonical facility schema
Facilities are stored as point geometries with provenance and stable IDs.

| Field | Type | Required | Notes |
|---|---:|---:|---|
| facility_id | string | yes | Stable internal ID |
| org_id | string | yes | Stable internal organization ID |
| org_name | string | yes | Canonicalized organization name |
| source_facility_name | string | yes | NODE_NAME from source |
| lat | float | yes | WGS84 |
| lon | float | yes | WGS84 |
| h3_rN | string | yes | H3 index at configured resolutions N |
| city_label | string | no | CITY metadata |
| state_label | string | no | STATE metadata |
| country_label | string | no | COUNTRY metadata |
| source_name | string | yes | SOURCE |
| asof_date | date | yes | ASOF_DATE |
| ingest_timestamp | datetime | yes | Time ingested |
| record_hash | string | yes | Hash of raw record for idempotency |
| location_confidence | enum | yes | exact_point, campus_centroid, unknown |
| notes | string | no | Optional |

### 2.4 Outputs
The system produces three primary output classes.

A. Canonical datasets.
`canonical/facilities.parquet`
`canonical/organizations.parquet`

B. Derived layers.
`layers/<layer_name>/<layer_version>/` containing:
`layer_metadata.json`
`cells.parquet` (H3 cell sets and attributes)
`features.parquet` (optional vector features)
`tiles/` (optional pre-generated tiles)

C. Map-serving artifacts.
A tile server or API that can serve:
(1) facility points
(2) H3 cell polygons with attributes
(3) layer metadata and versioning
(4) time snapshots (optional)

### 2.5 API contracts (minimum)
The backend must expose these read-only endpoints.

| Endpoint | Method | Response | Purpose |
|---|---|---|---|
| /v1/runs/latest | GET | JSON | Discover latest published run |
| /v1/layers | GET | JSON | List layers and versions |
| /v1/layers/{layer}/metadata | GET | JSON | Layer metadata, params, provenance |
| /v1/facilities | GET | GeoJSON or JSON | Filtered facility points |
| /v1/tiles/{z}/{x}/{y}.mvt | GET | MVT | Vector tiles for map |
| /v1/health | GET | JSON | Liveness/readiness |

The API must be strictly versioned. Breaking changes require a new major path.

---

## 3. Spatial foundations and why H3

### 3.1 Coordinate system
All point coordinates are interpreted as WGS84 (EPSG:4326). If inputs provide other coordinate systems, the ingestion layer must convert to WGS84 and record provenance.

### 3.2 H3 rationale
H3 is used as the primary spatial index and as the canonical representation for grid-based derived layers.

H3 provides:
A. A global discrete index that maps each point to a cell.
B. Multi-resolution analysis by selecting cell resolution.
C. Efficient spatial joins and aggregation by cell key rather than polygon intersection.
D. Consistent distance semantics via grid distance, when appropriate.

H3 references:
Project: https://h3geo.org/
Documentation: https://h3geo.org/docs/
Core library: https://github.com/uber/h3

### 3.3 H3 usage in this system
A. Indexing points. Each facility gets H3 indices at one or more configured resolutions.
B. Derived layers. Metros and heatmaps are stored as H3 cell sets with attributes.
C. Visualization. Cells can be drawn as hex polygons at a chosen resolution.
D. Joins. Many operations reduce to key joins on h3 index strings.

### 3.4 Resolution policy
The system must define a fixed set of allowed resolutions and a mapping from UI zoom to resolution.

Resolution sets must be explicit in configuration. Example: resolutions = {4, 5, 6, 7, 8, 9}.
Zoom mapping must be stable and versioned. The UI must not silently change resolution selection logic.

### 3.5 Distance semantics
Two distinct distance semantics must be supported and must never be conflated.

A. H3 grid distance. “Y cells away” is defined as `grid_distance(h3_a, h3_b)` at a fixed resolution.
B. Geodesic distance. “Within D km” is computed using great-circle distance on WGS84 or projected approximations.

Each layer must declare which distance semantics it uses.

### 3.6 Country-level constraint via polygon-to-grid assignment
Countries are represented as H3 cell sets derived from an external polygon dataset.

This system supports approximation. It does not support exact conformity of hex edges to borders.
The membership rule must be declared and versioned, such as:
Rule C1: include cell if its centroid is inside the country polygon.
Rule C2: include cell if cell intersects polygon by any amount.
Rule C3: include cell if overlap fraction ≥ t.

All country layers must include:
A. polygon dataset source and version
B. inclusion rule
C. H3 resolution
D. timestamp and hashing for reproducibility

Disputed areas policy must be explicit. The default policy is “dataset-dependent” and “no geopolitical claims.”

---

## 4. System architecture

### 4.1 High-level components
Component A: Ingestion and normalization pipeline (agent-owned).
Component B: Layer computation pipeline (agent-owned).
Component C: Storage layer (database + object store).
Component D: Serving layer (API + tiles).
Component E: Web UI (interactive map).

### 4.2 Proposed reference stack (bootstrap-friendly)
A. Agent and pipelines: Python 3.11+.
B. H3 bindings: h3-py (or equivalent).
C. Geometry: shapely + pyproj; geopandas optional.
D. Storage (local): DuckDB + Parquet.
E. Storage (production): Postgres + PostGIS, plus object storage for run artifacts.
F. API server: FastAPI.
G. Vector tiles: served from PostGIS using a tile service (for example a lightweight tile server) or generated offline.
H. Web UI: MapLibre GL JS + a minimal frontend (Vite or Next.js).

This is a reference, not a constraint. Implementations may vary, but contracts and invariants must hold.

### 4.3 Data flow per run
Step 1. Fetch raw inputs for each source and store in `inputs/` with checksums.
Step 2. Validate raw schema and coordinate sanity.
Step 3. Normalize into canonical facility records.
Step 4. Compute H3 indices at configured resolutions.
Step 5. Compute derived layers defined in the layer registry.
Step 6. Run validation and invariant checks.
Step 7. Publish artifacts atomically and update “latest run” pointer.
Step 8. Notify observers and record metrics.

---

## 5. Long-running agent specification

### 5.1 Responsibilities
The agent is the only component that writes canonical datasets and derived layers.
It must:
A. Run scheduled ingestions and rebuilds.
B. Produce deterministic, versioned outputs.
C. Enforce schema contracts and invariants.
D. Publish run artifacts atomically.
E. Expose run status and logs.
F. Refuse to publish if critical tests fail.

### 5.2 Agent interface
The agent supports both scheduled execution and manual runs.

A. Scheduled run. Triggered by cron-like schedule.
B. Manual run. Triggered by CLI or API with explicit inputs and parameters.

Every run must have:
run_id: a stable identifier, for example `YYYYMMDD-HHMMSS-<git_sha>-<config_hash>`.
inputs_hash: hash of raw inputs.
config_hash: hash of the agent configuration, including parameters and layer registry.
code_hash: git commit hash.

### 5.3 Idempotency and atomic publish
Given the same inputs_hash and config_hash, the agent must produce identical artifacts.

Publish is atomic:
A. Write to a staging location.
B. Validate artifacts.
C. Flip a single pointer `data/published/latest` to the new run_id.
D. Never partially publish.

### 5.4 Parameter governance
All parameters must live in a versioned configuration file.
The agent must never auto-tune or mutate parameters without explicit operator action.

Parameters include:
A. H3 resolution set and zoom mapping.
B. Metro clustering parameters (X, Y, adjacency rules, seed selection).
C. Country polygon dataset version and membership rule.
D. Source trust rules and deduplication rules.

### 5.5 Observability
The agent must emit structured logs and metrics.

Minimum metrics:
A. run_success (boolean)
B. run_duration_seconds
C. facility_count_total
D. facility_count_by_source
E. invalid_record_count
F. layer_compute_duration_seconds by layer
G. publish_timestamp

Logs must include run_id and stage names.

### 5.6 Failure containment
A. Any schema mismatch or invalid coordinate beyond configured tolerances fails the run unless explicitly configured as “quarantine.”
B. Any invariant failure fails the run.
C. Any layer failure can either fail the run or mark the layer as failed based on layer criticality. Critical layers must fail the run.

The failure policy must be declared in config. The default is fail-closed.

### 5.7 Security and access
The agent must support read-only serving paths.
Write privileges are limited to the agent identity.
If facility coordinates are considered sensitive, access control and redaction must be implemented before any public exposure.

---

## 6. Layer framework and extension contracts

### 6.1 Layer registry
All derived layers are declared in a registry file, for example `configs/layers.yaml`.

A layer entry must define:
A. layer_name
B. layer_version
C. input dependencies (canonical datasets and other layers)
D. parameters (fully explicit)
E. semantics (distance metric, membership rule)
F. output schema
G. criticality (critical or optional)

### 6.2 Layer output contract
Every layer must produce:
A. `layer_metadata.json` with params, code_hash, inputs_hash, config_hash, and timestamps.
B. `cells.parquet` at minimum if the layer is grid-based.
C. Optional `features.parquet` if feature geometries are produced.

`cells.parquet` schema (minimum):
| Field | Type | Required |
|---|---:|---:|
| h3 | string | yes |
| resolution | int | yes |
| layer_value | float or string | yes |
| layer_id | string | yes |
| asof_date | date | yes |

### 6.3 Adding a new layer
A new layer must be implemented as a plugin with a stable interface.

Required plugin functions:
A. `spec()` returns layer metadata, parameters, and output schemas.
B. `compute(canonical_store, layer_store, params) -> artifacts` writes outputs to a provided staging directory.
C. `validate(artifacts) -> report` performs layer-specific validation.

The agent loads plugins via an explicit module list in configuration. Implicit discovery is not allowed for production mode.

### 6.4 Adding a new data source
A new source must implement a source adapter.

Required adapter functions:
A. `fetch(config) -> raw_files` downloads or reads source inputs into `inputs/`.
B. `parse(raw_files) -> records` yields typed records.
C. `normalize(records) -> canonical_facilities` maps into the canonical schema.
D. `source_provenance()` returns licensing, refresh cadence, and trust rules.

### 6.5 Schema evolution policy
Schemas are versioned. Fields may be added in a backward-compatible way.
Breaking changes require:
A. a schema version bump
B. dual-write period or migration tooling
C. updated golden tests and invariants

---

## 7. Metro definitions supported (initial)

### 7.1 Density-derived metro core (grid-based)
This is the “facility densest cell + neighborhood” concept.

Definition M1 (reference):
A. Choose H3 resolution r_metro for metro computation.
B. Compute facility counts per cell at r_metro.
C. Identify the densest cell c*.
D. Define candidate set S_Y as all cells with grid_distance(cell, c*) ≤ Y.
E. Define metro cell set M as cells in S_Y with facility_count ≥ X.
F. Optionally enforce contiguity by removing disconnected components not containing c*.

This produces a functional metro cluster. It is data-dependent and must be versioned by run.

M1 must declare:
A. r_metro
B. X threshold
C. Y radius in grid steps
D. contiguity rule
E. tie-breaking rule if multiple densest cells exist

### 7.2 Named hub metros (alias-based, geometry-driven)
This supports operational labels like “ORD”, “JFK”, “SFO”.

A named hub metro is defined as:
A. a hub label
B. one or more seed facilities or seed H3 cells
C. a growth rule (for example M1 anchored on the seed)

The label is a human alias. Geometry remains authoritative.

---

## 8. Validation and quality controls

### 8.1 Raw validation
A. Required columns present.
B. LATITUDE in [-90, 90] and LONGITUDE in [-180, 180].
C. Coordinate not null and not NaN.
D. Source and ASOF_DATE present.

### 8.2 Canonical validation
A. facility_id stable and unique within a run.
B. record_hash present for idempotency.
C. h3 indices computed for each configured resolution.
D. location_confidence populated.

### 8.3 Conflict handling and deduplication (initial policy)
This policy must be explicit and configurable.

Recommended initial policy:
A. No cross-source merging by default. Preserve separate records unless there is a strong key match.
B. Provide optional deduplication by normalized org_name + normalized node_name + proximity threshold (geodesic distance).
C. If merged, retain all provenance and choose geometry by highest trust rule.

All merges must be logged and reportable.

---

## 9. Serving and interactive web interface

### 9.1 Web UI requirements (minimum)
A. Interactive slippy map.
B. Layer toggles (facilities, metro cells, country masks).
C. Filters: organization, source, as-of date or run snapshot.
D. Hover tooltips: facility details and provenance.
E. Click drill-down: list facilities in selected cell or region.
F. Multi-resolution rendering: points at high zoom, aggregated cells at low zoom.
G. Shareable URLs encoding current state (layers, filters, snapshot).

### 9.2 Tiles and rendering policy
The UI must render based on:
A. Facility points for high zoom levels.
B. H3 cell polygons for lower zoom levels, using precomputed aggregated attributes.

A stable zoom-to-resolution mapping must be declared.
The UI must not compute heavy geospatial joins client-side. It should query tiles or API endpoints.

### 9.3 Backend serving policy
The backend must serve:
A. Vector tiles for map rendering.
B. Metadata and configuration for UI.
C. Facility query endpoints for details and filtering.

All responses include run_id and layer_version for traceability.

---

## 10. Tooling, repository layout, and how to run

### 10.1 Repository layout (reference)
`/configs/`
`/src/agent/`
`/src/ingest/`
`/src/normalize/`
`/src/layers/`
`/src/serve/`
`/frontend/`
`/tests/`
`/data/` (ignored by git; used for local runs)
`docker-compose.yml`
`README.md`

### 10.2 Local development run (reference)
The minimum supported workflow:
A. Place raw CSV in `data/manual_inputs/`.
B. Run agent in “local mode” to create a run directory.
C. Start backend server pointing at published run.
D. Start frontend against backend.

Commands must be codified in a single `Makefile` or `taskfile` with explicit targets, for example:
`make agent-run`
`make serve`
`make ui`

### 10.3 Containerized deployment
Provide Docker images for:
A. agent
B. api/tile server
C. frontend
D. database (Postgres + PostGIS) for production-like setups

Docker Compose must support a full demo deployment.

---

## 11. Tests for the agent (required)

The test strategy must prove correctness, stability, and safety of the long-running agent. Tests are mandatory gates for publish.

### 11.1 Unit tests
A. CSV parsing and schema validation.
B. Coordinate validation and normalization.
C. H3 indexing correctness at each configured resolution.
D. Grid distance function behavior and error handling.
E. Layer parameter parsing and hashing.

### 11.2 Property-based tests
These tests validate invariants over randomized but constrained inputs.
A. Point-to-H3 mapping is deterministic.
B. Repeated runs with identical inputs produce identical outputs.
C. Metro computation under M1 produces a subset of the candidate neighborhood set.
D. Contiguity enforcement produces connected components under declared adjacency.

### 11.3 Golden regression tests
Maintain small fixed fixtures and expected outputs.

Fixtures include:
A. A minimal facility CSV with known coordinates.
B. A known metro cluster outcome with fixed parameters.
C. A small country polygon fixture for membership rules.

Golden outputs include:
A. Expected canonical facilities parquet checksums.
B. Expected layer cell sets (exact H3 indices).
C. Expected metadata hashes.

Golden tests fail on any output drift.

### 11.4 Invariant tests (publish gates)
These are required for every run.

Facility invariants:
A. No facility with invalid lat/lon.
B. No missing H3 index at required resolutions.
C. facility_id uniqueness.

Layer invariants:
A. Every layer artifact has metadata with config_hash and inputs_hash.
B. For any H3 cell set layer, all cells have the declared resolution.
C. For contiguity-enforced metros, the metro set must be connected and must contain the seed cell.

Country invariants (if enabled):
A. A facility may map to at most one country under a chosen rule, unless explicitly configured for disputed/unassigned handling.
B. Country cell sets must not be empty for configured countries present in polygons.

System invariants:
A. Publish is atomic and leaves a valid “latest” pointer.
B. Run directory is immutable post-publish.

### 11.5 Integration tests
A. End-to-end pipeline on fixture data, including publish.
B. Backend serves layer metadata and tile endpoints for the published run.
C. Frontend can load map and render at least one layer from the backend.

### 11.6 Performance tests
A. H3 indexing throughput benchmark for N records.
B. Layer computation time bounds for expected dataset sizes.
C. Tile endpoint latency under concurrent load.

### 11.7 UI smoke tests
Automated headless checks:
A. Map loads.
B. Facility layer toggles on and shows at least one point.
C. Metro layer toggles on and shows at least one polygon.
D. Tooltip appears on hover for a known fixture feature.

### 11.8 Monitoring tests
A. Agent emits required metrics fields.
B. Backend health endpoint returns OK and includes run_id.
C. On deliberate failure, agent refuses to publish and surfaces a failure report.

---

## 12. Determinism, versioning, and reproducibility

Every published artifact must be traceable to:
A. exact code_hash
B. exact config_hash
C. exact inputs_hash
D. exact run timestamp

The agent must store:
A. the full configuration used for the run
B. dependency lockfiles
C. a run manifest JSON

The agent must support “rebuild run” for a past run_id if the inputs are present.

---

## 13. Milestones and acceptance criteria

Milestone 1: Canonical ingestion and indexing.
Acceptance:
A. Agent ingests example CSV, produces canonical facilities parquet, computes H3 indices, passes invariants.

Milestone 2: One derived layer (M1 metro cluster).
Acceptance:
A. Agent produces a metro layer cell set deterministically from fixture inputs and params, passes golden tests.

Milestone 3: Backend serving.
Acceptance:
A. API exposes /v1/runs/latest, /v1/layers, and /v1/facilities. Vector tiles serve at least one layer.

Milestone 4: Interactive web UI.
Acceptance:
A. UI loads, displays facilities, and displays metro cells with filters.

Milestone 5: Country polyfill layer.
Acceptance:
A. Country masks are generated from a declared polygon dataset and membership rule. Outputs are versioned and tested.

Milestone 6: Extension contract hardening.
Acceptance:
A. Adding a new layer requires only a plugin module and registry entry. Adding a new source requires only an adapter module and registry entry. Tests cover both.

---

## Appendix A: Example configuration (reference)

`configs/system.yaml` (illustrative)

run:
  mode: local
  publish_root: data/published
  staging_root: data/staging
  required_h3_resolutions: [5, 6, 7, 8, 9]
  zoom_to_h3:
    0-4: 5
    5-7: 6
    8-10: 7
    11-12: 8
    13-22: 9

sources:
  - name: peeringdb_csv
    path: data/manual_inputs/facilities.csv
    trust:
      geometry: high
      country_label: medium
      city_label: low

layers:
  - name: metro_density_core
    version: v1
    plugin: layers.metro_density_core:M1
    params:
      resolution: 6
      x_min_facilities: 2
      y_max_grid_distance: 3
      enforce_contiguity: true
    critical: true

country:
  enabled: true
  polygon_dataset:
    name: natural_earth_admin0
    version: <TBD>
    path: data/boundaries/ne_admin0.geojson
  h3_resolution: 4
  membership_rule: centroid_in_polygon

---

## Appendix B: Example metro semantics note

When the UI shows “ORD,” it is an operational metro alias mapped to a specific layer definition and parameters for a given run. It is not a claim about municipal boundaries. The UI must show the layer’s definition and parameters in metadata to prevent misinterpretation.