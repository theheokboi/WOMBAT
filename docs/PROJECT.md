# Project Contracts

## Mission

Deliver fast, country-scoped, visual iteration for infrastructure mapping while preserving a minimal reproducibility backbone.

## Operating Mode

The repository currently runs in dev-only mode.

- Exploration speed is prioritized.
- Strict promotion and hard blocking gates are deferred to a future hardening phase.
- Day-to-day commands and docs must not assume strict or production-only workflows.
- The pipeline defaults to dev semantics.
- Strict blocking enforcement is disabled in the active path.
- The invariant gate is skipped by default in dev runs.

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

`COUNTRIES` accepts one ISO A2 code or a comma-separated list of ISO A2 codes.

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
- `facility_density_adaptive` is a published run-scoped layer and must derive its effective base resolution from fixed-resolution `country_mask` metadata when present.
- Published adaptive layer output must preserve metadata-backed resolution bounds and neighbor smoothing guarantees.

## Transport Graph Contract

- `/v1/osm/transport` remains under the `/v1` prefix.
- Default behavior is `source=shapefile`.
- `source=graph` loads per-country major-road graph artifacts from `data/openstreetmap/<country>/`.
- `graph_variant=raw` uses `major_roads_edges.geojson` and `major_roads_nodes.geojson`.
- `graph_variant=collapsed` uses `major_roads_edges_collapsed.geojson` and `major_roads_nodes_collapsed.geojson`.
- `graph_variant=adaptive` uses `major_roads_edges_adaptive.geojson` and `major_roads_nodes_adaptive.geojson`, produced by protected-node contraction at fixed H3 resolution (cross-cell endpoints are preserved).
- `include_nodes=true` loads the node file that matches the selected graph variant when present.
- Current graph artifacts are run-agnostic overlay data.
- `scripts/evaluate_major_roads_graph.py` compares `raw` vs `collapsed` edge artifacts using connectivity and path-length-ratio metrics for cable-corridor plausibility checks; its report is a static OSM graph analysis artifact (not a run-scoped published layer artifact).

## Graph And Layer Roles

- The major-road graph is the base network artifact.
- The adaptive H3 layer is a run-scoped published spatial abstraction layer.
- Artifacts derived from adaptive-cell output must be treated as run-scoped published data unless the project explicitly redefines them as static country-level assets.
- Visualization artifacts and routing artifacts must be documented separately when they diverge in semantics.

## Verification Contract

`make verify-dev` must cover:

- input and schema sanity
- layer compute no-crash
- API payload non-empty for selected scope
- UI smoke

Non-blocking reporting remains required for performance or monitoring checks.

## API Response Expectations

- Keep the `/v1` versioned path prefix.
- Include `run_id` in run-backed responses.
- Include pointer and lane context in run and health status payloads for dev visibility.
- Preserve backward compatibility for additive updates.

## Documentation Policy

- `docs/PROJECT.md` is the authoritative contract document.
- `README.md` is the operator and contributor quick-start guide.
- `AGENTS.md` defines contributor and coding-agent workflow rules.
- Workflow, contract, tooling, or command changes must update all affected docs in the same change.

## Log Retention

- `logs/mistakes.md` remains a live append-only ledger.
- `logs/progress/` is for active and recent task logs.
- Completed progress logs older than 7 days should be moved to `archive/logs/progress/` instead of being deleted.
- Historical logs should be archived before any deletion policy is considered.
