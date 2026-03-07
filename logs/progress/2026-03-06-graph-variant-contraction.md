# Task Checklist
- [~] Confirm requirement in docs/PROJECT contract and existing code paths
- [ ] Add/update tests for contraction utility and transport graph_variant behavior
- [ ] Implement minimal ingest contraction utility and variant output paths
- [ ] Implement build script graph variant mode (raw|collapsed|both)
- [ ] Implement serve graph_variant query param for source=graph
- [ ] Run impacted backend tests and record results
- [ ] Update README.md and AGENTS.md docs
- [ ] Run mistake replay check and record confirmation

## 2026-03-06T22:14:56Z
- Status: in progress
- Checklist item: Confirm requirement in docs/PROJECT contract and existing code paths
- Update: Started task and created execution checklist; located major road graph ingest/build/serve/test files and identified existing raw filenames and graph endpoint behavior.
- Evidence: src/inframap/ingest/major_road_graph.py, scripts/build_major_roads_graph.py, src/inframap/serve/app.py, tests/unit/test_serve_osm_transport.py
- Next: Locate project contract file and confirm transport/graph constraints before edits.

## 2026-03-06T22:16:09Z
- Status: blocked
- Checklist item: Confirm requirement in docs/PROJECT contract and existing code paths
- Update: BLOCKED: `docs/PROJECT.md` is absent in repository, so direct contract confirmation from the referenced authoritative doc is not possible.
- Evidence: docs/ contains only docs/IMPLEMENTATION_PLAN.md
- Next: Use existing AGENTS.md API contract and current implementation behavior as the working contract for this task.

## 2026-03-06T22:16:15Z
- Status: in progress
- Checklist item: Confirm requirement in docs/PROJECT contract and existing code paths
- Update: Proceeding with implementation using AGENTS.md transport contract and current raw graph file behavior as baseline constraints.
- Evidence: AGENTS.md API and transport rules section; existing raw graph files in src/inframap/ingest/major_road_graph.py
- Next: Implement contraction utility and variant outputs with deterministic edge IDs.

## 2026-03-06T22:19:34Z
- Status: in progress
- Checklist item: Implement minimal ingest contraction utility and variant output paths
- Update: Added pure-Python `contract_degree2_undirected_edges` utility, deterministic contracted edge-id generation, and variant output support for raw/collapsed graph edge+node GeoJSON files while preserving raw defaults via `build_major_road_graph`.
- Evidence: src/inframap/ingest/major_road_graph.py
- Next: Add build-script and API graph_variant handling plus unit tests.

## 2026-03-06T22:19:35Z
- Status: in progress
- Checklist item: Implement build script graph variant mode (raw|collapsed|both)
- Update: Added `--graph-variant {raw,collapsed,both}` with default `both`; raw output keys remain unchanged for compatibility.
- Evidence: scripts/build_major_roads_graph.py
- Next: Extend `/v1/osm/transport` graph source with variant selection and update tests.

## 2026-03-06T22:19:36Z
- Status: in progress
- Checklist item: Add/update tests for contraction utility and transport graph_variant behavior
- Update: Added contraction utility unit tests and extended OSM transport graph tests for collapsed variant edge/node loading and country availability behavior.
- Evidence: tests/unit/test_major_road_graph_contraction.py, tests/unit/test_serve_osm_transport.py
- Next: Run impacted backend tests and update docs.

## 2026-03-06T22:19:37Z
- Status: in progress
- Checklist item: Run impacted backend tests and record results
- Update: Ran targeted backend unit tests for contraction and serve transport variant behavior.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py tests/unit/test_serve_osm_transport.py` => `10 passed in 0.88s`
- Next: Update README/AGENTS docs and perform mistake replay check.

## 2026-03-06T22:19:38Z
- Status: in progress
- Checklist item: Update README.md and AGENTS.md docs
- Update: Documented `graph_variant` API option and raw/collapsed artifact file mapping; documented build script variant mode default behavior.
- Evidence: README.md, AGENTS.md
- Next: Run mistake replay check and finalize checklist completion.

## 2026-03-06T22:19:39Z
- Status: complete
- Checklist item: Run mistake replay check and record confirmation
- Update: Reviewed `logs/mistakes.md` prevention rules before handoff and confirmed this task followed applicable rules (deterministic/minimal change focus; safe markdown append patterns).
- Evidence: logs/mistakes.md
- Next: Handoff with completed checklist snapshot.

## 2026-03-06T22:19:40Z
- Status: complete
- Checklist item: Final checklist snapshot
- Update: Checklist status snapshot.
- Evidence: task tracking
- Next: none

### Checklist Snapshot (Final)
- [x] Confirm requirement in docs/PROJECT contract and existing code paths (blocked on missing file; proceeded with AGENTS.md contract)
- [x] Add/update tests for contraction utility and transport graph_variant behavior
- [x] Implement minimal ingest contraction utility and variant output paths
- [x] Implement build script graph variant mode (raw|collapsed|both)
- [x] Implement serve graph_variant query param for source=graph
- [x] Run impacted backend tests and record results
- [x] Update README.md and AGENTS.md docs
- [x] Run mistake replay check and record confirmation

## 2026-03-06T22:20:35Z
- Status: complete
- Checklist item: at least once before handoff
- Update: Final validation pass completed with targeted unit tests and Python syntax compile checks for changed backend files.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py tests/unit/test_serve_osm_transport.py` and `python -m py_compile src/inframap/ingest/major_road_graph.py scripts/build_major_roads_graph.py src/inframap/serve/app.py tests/unit/test_serve_osm_transport.py tests/unit/test_major_road_graph_contraction.py`
- Next: handoff
