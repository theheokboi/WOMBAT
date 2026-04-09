# Project Contracts

## Mission

Deliver fast, country-scoped, visual iteration for infrastructure mapping while preserving a minimal reproducibility backbone.

## Operating Mode

The repository currently runs in dev-only mode.

- Exploration speed is prioritized.
- Strict promotion and hard blocking gates are deferred.
- Day-to-day commands and docs must not assume strict or production-only workflows.

## Command Surface

Primary development commands:

- `make run-dev COUNTRIES=<code[,code...]>`
- `make serve-dev`
- `make ui-dev`
- `make verify-dev`

Compatibility aliases:

- `make run` -> `make run-dev`
- `make serve` -> `make serve-dev`
- `make ui` -> `make ui-dev`
- `make verify-dev` -> `make verify-fast`

Advanced workflows remain supported but are not part of the default inner loop:

- `PYTHONPATH=src python scripts/export_static_demo_bundle.py --run-id <run-id>`
- `PYTHONPATH=src python scripts/export_facilities_sqlite.py --output <sqlite-path>`

## Reproducibility Backbone

Every run must persist:

- `run_id`
- `inputs_hash`
- `config_hash`
- `code_hash`

Published run directories are immutable after pointer update.

## Pointer And Publish Contract

- Active dev pointer: `data/published/latest-dev`
- Compatibility alias: `data/published/latest`
- The compatibility alias is expected to mirror `latest-dev`.
- Serve and API paths read `latest-dev` first and fall back to `latest` only for backward compatibility when `latest-dev` is absent.
- Dev workflows must not rely on strict or production pointer semantics.
- Publish operations must update pointers atomically.

## Data Contracts

- Geometry is authoritative. Do not infer spatial membership from free text.
- `country_mask` is the coverage authority for country-scoped runs.
- Canonical facility ingest accepts explicit geocoded point sources, including `data/facilities/peeringdb_facility.tsv`, `data/landing_points/std_landing_points.tsv`, and `data/datacenters/datacenters_geocoded.tsv`.
- External sharing may export normalized rows to one SQLite `facilities` table with source provenance preserved in-row.
- `facility_density_adaptive` is a published run-scoped layer and must derive its effective base resolution from fixed-resolution `country_mask` metadata when present.
- `facility_density_r7_regions` is an additive published run-scoped layer derived from `facility_density_adaptive`; it emits only `resolution == 7` cells from the published adaptive output and includes deterministic `cluster_id` values plus a representative region coordinate.
- Published adaptive layer output must preserve metadata-backed resolution bounds and neighbor smoothing guarantees.
- Adaptive layer metadata may expose additive `adaptive_counters` without changing existing top-level report keys.
- Empty near-occupied sibling groups may compact above the normal empty-interior cap when `facility_density_adaptive.params.compact_empty_near_occupied=true`; boundary-band empties remain non-compactable.
- Fully covered singleton occupied sibling groups may compact back to their parent when the merged parent remains outside the boundary band and still satisfies neighbor-delta validation.

## Transport Graph Contract

- `/v1/osm/transport` remains under the `/v1` prefix.
- `/v1/osm/transport` serves shapefile-backed road and railway overlays only.

## API Response Expectations

- Keep the `/v1` versioned path prefix.
- Include `run_id` in run-backed responses.
- Include pointer and lane context in run and health payloads for dev visibility.
- Preserve backward compatibility for additive updates.
- The main frontend remains available under `/ui/`.
- The k-rings experiment page is exposed at `/k-rings` via redirect to `/ui/k-rings.html` and must honor the same `run` and `data=static|api` query semantics as the main frontend.
- `/v1/populated-places` is a static, run-agnostic Natural Earth overlay with optional `country` and `limit` filters.
- `/v1/r7-region-routes` serves saved derived route artifacts as GeoJSON `LineString` features with optional `country` and `include_self` filters.
- When no live backend is available, the frontend may load equivalent browser-ready static snapshots from `frontend/demo-data/`.

## Verification Contract

`make verify-fast` must cover:

- input and schema sanity
- publish or run-state sanity for the affected path
- API payload non-empty for a selected scope
- UI smoke

`make verify-dev` is a compatibility alias to `make verify-fast`.

Non-blocking reporting remains required for performance or monitoring checks.

## Documentation Policy

- `docs/PROJECT.md` is the authoritative contract document.
- `README.md` is the quick-start guide.
- `AGENTS.md` defines contributor and coding-agent workflow rules.
- Workflow, contract, tooling, or command changes must update the owning docs in the same change.

## Log Retention

- `logs/mistakes.md` remains a live append-only ledger.
- `logs/progress/` is for committed milestone, contract, or handoff logs.
- Routine local task notes may remain untracked.
- Completed committed progress logs older than 7 days should be moved to `archive/logs/progress/`.
