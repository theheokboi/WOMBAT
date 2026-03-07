# Adaptive Cell Routing Notes

## Objective

Capture the current design discussion about using adaptive cells to reduce the search space of the major-road graph while preserving realistic routing behavior.

## Problem

The project has two relevant spatial structures:

- A major-road graph derived from OpenStreetMap `motorway`, `trunk`, `motorway_link`, and `trunk_link`.
- An adaptive H3 cell partition that becomes finer near infrastructure and coarser elsewhere.

The practical problem is that the raw road graph is too dense for the intended use case, but aggressive simplification can remove routing realism. The discussion goal is to determine how the road graph and adaptive cells should interact without rebuilding graphs per query or doing expensive geometry work during routing.

## Current Repo State

- The major-road graph is built from OSM PBF input by `src/inframap/ingest/major_road_graph.py` and exposed through `scripts/build_major_roads_graph.py`.
- The builder emits `raw` and `collapsed` graph variants as GeoJSON edge and node files under `data/openstreetmap/<country>/`.
- The graph artifacts are currently treated as run-agnostic overlay data and served by `/v1/osm/transport` in `src/inframap/serve/app.py`.
- The adaptive H3 partition is produced by `src/inframap/layers/facility_density_adaptive.py` as a run-scoped published layer with metadata-backed resolution bounds and smoothing guarantees.
- Contract details should be read alongside `docs/PROJECT.md`; this note focuses on the design discussion around graph density and routing.

## Findings

- The high-level proposal is correct in one important respect: the road graph should remain the authority, and cells should act as a spatial abstraction or pruning layer.
- The current `collapsed` graph is not a safe routing backbone. The contraction routine is explicitly undirected and merges degree-2 chains for simplification, which is suitable for display and coarse analysis but not for direction-sensitive routing.
- The adaptive cell layer already guarantees useful structural properties for a pruning/index layer, including published resolution bounds, deterministic output ordering, no ancestor/descendant overlap, bounded neighbor resolution deltas, and optional country-polygon clipping.
- The graph and adaptive layers currently live in different lifecycle domains: graph artifacts are run-agnostic, country-scoped static files, while adaptive cells are run-scoped published outputs influenced by the facility distribution of a specific run.
- That lifecycle split matters. Any artifact that depends on adaptive cells should be stored with the published run, not mixed into the static OSM graph directory.

## Risks In The Full Cell-Pruned Routing Proposal

- Recording only "which edges touch which cells" is not enough for routing. If an edge crosses multiple cells and is not split at the boundaries, cell membership remains ambiguous during traversal.
- A cell sequence alone may over-prune the search space. Realistic routes may briefly leave the obvious corridor to follow the road network topology, especially around sparse interchanges or coastal geometry.
- Reusing the current collapsed graph for routing would risk invalid paths because the current simplification does not preserve directed traversal semantics.
- Building a full portal or interface-node layer adds preprocessing cost, artifact design complexity, and a new consistency surface between static graph data and run-specific adaptive outputs.

## Recommended Direction

Use a two-layer model, but implement it in stages.

1. Keep a directed raw road graph as the routing authority.
2. Treat adaptive cells as a pruning/index layer, not as a replacement network.
3. If cells are used for routing, split edges at adaptive-cell boundaries and materialize portal/interface nodes.
4. Store any cell-derived routing overlay as a run-scoped published artifact because it depends on adaptive layer output.
5. Keep the current `collapsed` graph as a display-oriented simplification unless a new directed contraction path is introduced.

## Adaptive-Aware Contraction

Before building a full cell-portal routing layer, a simpler intermediate step is "adaptive-aware contraction."

Adaptive-aware contraction means simplifying the road graph while treating the adaptive partition as a set of protection rules:

- Always keep branch and intersection nodes.
- Keep nodes on or near adaptive cell boundaries.
- Keep nodes inside fine-resolution cells.
- Keep nodes near facilities or landing stations.
- Keep nodes required to preserve one-way or attribute changes.
- Contract degree-2 chains only in coarse, low-interest areas where the adaptive partition says detail is less important.

This approach keeps one routing graph, reduces density where the map is intentionally coarse, and avoids the full complexity of cell-boundary splitting and portal-graph routing in the first iteration.

## Suggested Implementation Path

1. Introduce a routing-oriented graph artifact separate from the current display-oriented `collapsed` variant.
2. Prototype adaptive-aware contraction on top of the raw graph.
3. Measure graph-size reduction and route-quality impact near fine-cell regions and sparse coarse-cell regions.
4. If adaptive-aware contraction is insufficient, add edge splitting at adaptive-cell boundaries and build a portal/interface overlay.
5. Route on the raw directed graph restricted to a conservative corridor induced by the portal overlay, with fallback widening if the corridor is too narrow.

## Important Constraints

- Do not use free text or approximate labels to infer spatial membership. Geometry must remain authoritative.
- Preserve reproducibility boundaries. Any adaptive-cell-derived artifact should carry run metadata and be published with the run.
- Keep `/v1` API compatibility and avoid breaking the current run-agnostic `/v1/osm/transport` overlay contract unless a new endpoint is introduced for routing-oriented artifacts.
- Keep the distinction between visualization artifacts and routing artifacts explicit. A graph that is acceptable for map display may not be valid for routing.

## Open Questions

- Should the routing graph remain country-level static data, or should the project accept run-scoped routing overlays as first-class published outputs?
- Is the next step intended to optimize visualization density, routing performance, or both?
- How much route-quality error is acceptable in exchange for graph reduction in coarse cells?
