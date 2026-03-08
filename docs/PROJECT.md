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

Static demo export command:

- `PYTHONPATH=src python scripts/export_static_demo_bundle.py --run-id <run-id>`

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
- `facility_density_r7_regions` is an additive published run-scoped layer derived from `facility_density_adaptive`; it emits only `resolution == 7` cells from the published adaptive output, assigns deterministic connected-component `cluster_id` values over H3 adjacency, and includes a representative region coordinate chosen as the member-cell center nearest to the cluster centroid.
- Published adaptive layer output must preserve metadata-backed resolution bounds and neighbor smoothing guarantees.
- Empty near-occupied sibling groups may compact back to their parent above the normal empty-interior cap when `facility_density_adaptive.params.compact_empty_near_occupied=true`; boundary-band empties remain non-compactable.

## Transport Graph Contract

- `/v1/osm/transport` remains under the `/v1` prefix.
- Default behavior is `source=shapefile`.
- `source=graph` loads per-country major-road graph artifacts from `data/openstreetmap/<country>/`.
- `graph_variant=raw` uses `major_roads_edges.geojson` and `major_roads_nodes.geojson`.
- `graph_variant=collapsed` uses `major_roads_edges_collapsed.geojson` and `major_roads_nodes_collapsed.geojson`.
- `graph_variant=adaptive` uses `major_roads_edges_adaptive.geojson` and `major_roads_nodes_adaptive.geojson`, produced by protected-node contraction at fixed H3 resolution (cross-cell endpoints are preserved).
- `graph_variant=adaptive_portal` uses `major_roads_edges_adaptive_portal.geojson` and `major_roads_nodes_adaptive_portal.geojson`, produced by fixed-resolution boundary splitting with explicit portal/interface nodes and per-cell topology contraction; class filtering keeps `motorway`/`trunk`/`primary`/`secondary` plus `motorway_link`/`trunk_link`/`primary_link`/`secondary_link`, starts with early per-cell priority (motorway mainline first, then link, then trunk mainline/link, primary mainline/link, secondary mainline/link) before portal splitting, then escalates classes only on cells needed to bridge disconnected cross-cell components, and nodes are anchor-only (portal + junction nodes) after pruning nodes not connected to any retained edge.
- `graph_variant=adaptive_portal_run` uses run-scoped files under `data/runs/<run_id>/graph/<country>/`: `major_roads_edges_adaptive_portal_run.geojson` and `major_roads_nodes_adaptive_portal_run.geojson`; this variant uses `facility_density_adaptive` run cells as a variable-resolution mask, applies `motorway`/`trunk`/`primary`/`secondary` filtering, and contracts covered cell interiors to a per-cell hierarchical portal backbone where higher-class portals stay on higher-class roads and lower-class portals attach upward as feeders before connected-anchor node pruning.
- `include_nodes=true` loads the node file that matches the selected graph variant when present.
- Graph artifacts are run-agnostic except `adaptive_portal_run`, which is run-scoped.
- `scripts/evaluate_major_roads_graph.py` compares `raw` vs `collapsed` edge artifacts using connectivity and path-length-ratio metrics for cable-corridor plausibility checks; its report is a static OSM graph analysis artifact (not a run-scoped published layer artifact).

## Graph And Layer Roles

- The major-road graph is the base network artifact.
- The adaptive H3 layer is a run-scoped published spatial abstraction layer.
- The `facility_density_r7_regions` layer is a run-scoped derived visualization layer for network-region envelopes at fixed `r7`.
- Artifacts derived from adaptive-cell output must be treated as run-scoped published data unless the project explicitly redefines them as static country-level assets.
- Visualization artifacts and routing artifacts must be documented separately when they diverge in semantics.
- Saved `r7` region route artifacts may be exposed as static derived overlays when they are generated outside the publish pipeline; those overlays must preserve source artifact provenance and country scoping.
- Visualization-oriented route overlays should prefer separate compact GeoJSON artifacts (for example `*-routes-ui.geojson`) with simplified lines, rounded coordinates, no self-routes, no null geometries, and optional reverse-pair deduplication.
- Static demo bundles are frontend-only snapshots derived from the current published run and should contain browser-ready JSON/GeoJSON rather than internal parquet-backed data products.

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
- `/v1/populated-places` is a static, run-agnostic Natural Earth reference overlay backed by `data/populated_places/ne_10m_populated_places.shp`; it returns GeoJSON point features and supports optional `country` and `limit` query parameters.
- `/v1/r7-region-routes` serves saved derived route artifacts as GeoJSON `LineString` features with optional `country` and `include_self` query parameters; when `include_self=false`, it should prefer compact visualization artifacts from `artifacts/derived/*-r7-regions-*-routes-ui.geojson` and fall back to full `*-routes.json` artifacts otherwise. Feature properties must retain country code, source artifact name, source/destination region identifiers, and route distance/duration metrics.
- When no live backend is available, the frontend may load equivalent browser-ready static snapshots from `frontend/demo-data/`.

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
