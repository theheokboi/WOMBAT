# Physical Network Infrastructure Map

Dev-first, geometry-first infrastructure mapping with H3.

## Current Mode: Dev Only

This repository is intentionally optimized for fast visual iteration.
Strict reproducibility/promotion guardrails are deferred and tracked as future hardening work.

## Decision Guide

- **I'm exploring**: use the dev loop (`run-dev`, `serve-dev`, `ui-dev`, `verify-dev`).
- **I'm promoting**: not supported in current mode; promotion/repro lane is deferred to engineering hardening.

## Commands

```bash
COUNTRIES=TW make run-dev
make serve-dev
make ui-dev
make verify-dev
```

Compatibility aliases are preserved:

- `make run` -> `make run-dev`
- `make serve` -> `make serve-dev`
- `make ui` -> `make ui-dev`

## Fast Loop (Visual Iteration)

```bash
# 1) Run a scoped dev pipeline
COUNTRIES=TW make run-dev

# 2) Serve dev data
make serve-dev

# 3) Open UI
make ui-dev

# 4) Validate quickly
make verify-dev
```

Country selection for each run is controlled by `COUNTRIES` (comma-separated ISO-2 codes).  
Example: `COUNTRIES=TW make run-dev` uses `data/countries/TW.geojson` via the `country_mask` layer.
When multiple runs exist, UI run selector (`Run / r-level`) can switch between published runs (and their effective r-level) without rerunning.
For each selected run, the UI now renders all countries included in that run scope (no per-country selector).

Canonical ingest now supports a landing-points TSV schema (`city_name`, `state_province`, `country`, `latitude`, `longitude`, `asof_date`, ...). Landing points are normalized into canonical facilities using `latitude/longitude` (not `standard_latitude/standard_longitude`), so they participate in adaptive H3 partitioning the same way as facilities.
In the UI, landing points are rendered with a distinct point color from regular facility points.

Default country-mask policy in `configs/layers.yaml` is:

- `mode: fixed_resolution`
- `membership_rule: overlap_ratio`
- `resolution: 2`
- fixed inclusion criterion: include cell when `overlap_ratio > 0`

Adaptive facility partitioning derives its effective base resolution from country-mask metadata when fixed mode is active, so `coverage_domain` follows the active mask resolution (for example, `country_mask_r2`).
Adaptive output bounds are config-driven: set `facility_density_adaptive.params.min_output_resolution` (and `facility_max_resolution`) in `configs/layers.yaml`; UI filtering reads these bounds from published adaptive metadata.

`make run-dev` now prints live stage progress while the pipeline runs.  
Set `RUN_DEV_PROGRESS=0` to disable stream output for a quiet run.

Screenshot path convention:

- `artifacts/screenshots/<YYYY-MM-DD>-<short-name>.png`

## Data and Pointer Behavior (Dev)

- Active pointer: `data/published/latest-dev`
- Compatibility alias: `data/published/latest` mirrors `latest-dev`
- Serve and API paths read `latest-dev` first and fall back to `latest` only for backward compatibility when `latest-dev` is absent.
- Dev exploration must not rely on strict/prod pointer semantics.

## Dev Verification Contract

`make verify-dev` is the minimum required check set:

- input/schema sanity (targeted ingest/unit checks)
- layer compute no-crash (integration run path)
- API payload non-empty for selected scope
- UI smoke

## API Notes

Read endpoints remain under `/v1`.
Run-oriented responses now include pointer/lane context for dev visibility.
OSM transport overlay data is available from the run-agnostic endpoint `/v1/osm/transport` (no `run_id` coupling).
`/v1/osm/transport` supports `source=shapefile` (default) and `source=graph`; graph mode supports `graph_variant=raw|collapsed|adaptive` (default `raw`).
`graph_variant=raw` reads `major_roads_edges.geojson` (and optional `major_roads_nodes.geojson` when `include_nodes=true`).
`graph_variant=collapsed` reads `major_roads_edges_collapsed.geojson` (and optional `major_roads_nodes_collapsed.geojson` when `include_nodes=true`).
`graph_variant=adaptive` reads `major_roads_edges_adaptive.geojson` (and optional `major_roads_nodes_adaptive.geojson` when `include_nodes=true`), where adaptive means fixed-resolution H3 boundary-aware protected-node contraction.
Frontend exposes an `OSM transport overlay` toggle and legend entries for `rail`, `motorway`, and `trunk`.

Major-road graph GeoJSON artifacts can be generated from country OSM PBF files with:

```bash
python scripts/build_major_roads_graph.py --country TW
```

By default this writes both raw and collapsed graph variants. Use `--graph-variant raw|collapsed|both` to control outputs.
The command now prints stage-level progress with a progress bar and ETA while building graph artifacts.

Adaptive-aware contraction output can be generated as an additive graph variant:

```bash
python scripts/build_major_roads_graph.py --country TW --graph-variant adaptive --adaptive-resolution 6
```

`adaptive` here is a static country-level graph artifact generated with fixed H3 resolution boundary protection. It is not yet a run-scoped overlay derived from published `facility_density_adaptive` output.

To compare `raw` vs `collapsed` as cable-corridor proxy graphs (connectivity/path-length drift, shortcut and detour signals), run:

```bash
python scripts/evaluate_major_roads_graph.py --country TW --out artifacts/eval/TW-major-roads-eval.json
```

This evaluation reads static OSM graph artifacts and writes a static analysis report; it does not create run-scoped published layer outputs.

## Deferred Hardening (For Engineering)

Not active in current mode:

- strict determinism rerun enforcement
- strict promotion lane and explicit promote command
- strict-only pointer lifecycle (`latest-strict`)
- full blocking gate publish policy

## Archived Docs

Historical handover/planning/log summaries were moved to:

- `archive/docs/HANDOVER.md`
- `archive/docs/HIERARCHICAL_ADAPTIVE_PLAN.md`
- `archive/docs/LOGS.md`
- `archive/docs/NEXT_STEPS.md`

## References

- `docs/PROJECT.md` (authoritative contracts)
- `docs/ADAPTIVE_CELL_ROUTING.md` (design discussion on graph density, adaptive cells, and routing)
- `AGENTS.md`
