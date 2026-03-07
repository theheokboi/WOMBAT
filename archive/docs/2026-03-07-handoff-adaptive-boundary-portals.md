# Handoff: Adaptive Boundary/Portal Graph Next Step

Date: 2026-03-07 (UTC)

## Current State

- `graph_variant=adaptive` is implemented and exposed in API/UI.
- Current adaptive variant is **fixed-resolution H3 boundary-aware protected-node contraction**:
  - protects existing endpoints of cross-cell edges
  - does not split edges at cell boundaries
  - does not materialize portal/interface nodes
- This is why graph density can still remain high and boundary-node behavior is not yet visible.

## What To Build Next

Implement a new prototype variant that is boundary-node explicit.

Proposed variant name:

- `graph_variant=adaptive_portal` (additive, do not replace current `adaptive` yet)

Core algorithm:

1. Assign each edge geometry to H3 cells at fixed resolution `R`.
2. Detect each edge/cell boundary crossing.
3. Split edge geometry at crossing points.
4. Create portal/interface nodes at split points and cell boundary intersections.
5. Build per-cell subgraph segments between preserved nodes.
6. Contract degree-2 chains within each cell while preserving:
   - portal/interface nodes
   - branch-critical nodes
   - required attribute/topology breakpoints

## Acceptance Criteria

- Boundary nodes are materialized where edges cross cell boundaries.
- Node count per cell is significantly reduced versus `raw`/current `adaptive`.
- Corridor reachability is preserved for sampled source-target node pairs.
- No unrealistic path shortcuts are introduced beyond agreed tolerance.
- Output remains deterministic for identical input/config.

## Reproducibility/Contract Boundaries

- Keep this variant in static OSM graph artifacts initially (same lifecycle as existing graph variants).
- Do not mix with run-scoped `facility_density_adaptive` artifacts yet.
- Preserve `/v1/osm/transport` backward compatibility and additive variant semantics.

## Suggested Implementation Order

1. Geometry split + portal node generation utility in ingest path.
2. New variant writer and filenames in graph builder.
3. API support for new variant in `/v1/osm/transport`.
4. UI selector support for new variant.
5. Tests:
   - boundary split correctness
   - deterministic output
   - API variant loading
   - UI smoke selector coverage
6. Evaluate against current `raw`, `collapsed`, `adaptive` metrics.

## Useful Commands

Build current adaptive:

```bash
python scripts/build_major_roads_graph.py --country TW --graph-variant adaptive --adaptive-resolution 5
```

Evaluate raw vs collapsed:

```bash
python scripts/evaluate_major_roads_graph.py --country TW --out artifacts/eval/TW-major-roads-eval.json
```

Run focused tests:

```bash
pytest -q tests/unit/test_major_road_graph_contraction.py tests/unit/test_serve_osm_transport.py tests/unit/test_major_road_graph_eval.py tests/unit/test_major_road_graph_progress.py tests/ui/test_ui_smoke.py
```
