## 2026-03-07T08:27:07Z
- Status: in progress
- Checklist item: Inspect ingest graph builder logic and mask handling
- Update: Started reviewing major road graph adaptive portal code to understand H3 boundary splitting and contraction steps.
- Evidence: src/inframap/ingest/major_road_graph.py lines ~350-520
- Next: Map existing boundary split pipeline to general polygon mask flow.
## 2026-03-07T08:27:23Z
- Status: in progress
- Checklist item: Identify minimal code path for adaptive polygon boundary splitting
- Update: Mapped `_boundary_crossing_point`, `_segment_crossings`, and `contract_edges_within_cells_preserving_portals` to the H3-driven workflow; noted they all rely on resolution-based cell membership checks tied to `_point_cell`.
- Evidence: src/inframap/ingest/major_road_graph.py lines 412-540
- Next: Sketch deterministic mask membership predicate and split/portal function signatures that can replace the H3 resolution dependency.
