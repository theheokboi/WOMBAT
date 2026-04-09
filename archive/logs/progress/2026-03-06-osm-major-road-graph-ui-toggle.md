# OSM Major-Road Graph UI Toggle

Checklist
- [x] Confirm requirement reference and existing contracts
- [x] Add/update tests for changed behavior
- [x] Implement minimal code for graph build + API/UI toggle
- [x] Run local verification for impacted paths
- [x] Update docs/config examples if interfaces changed
- [x] Update README.md and AGENTS.md for workflow/contract/tooling changes
- [x] Mistake replay check

## 2026-03-06T21:03:00Z
- Status: in progress
- Checklist item: Confirm requirement reference and existing contracts
- Update: Scoped task to integrate a new undirected major-road graph source from `data/openstreetmap/TW/taiwan-260305.osm.pbf` into existing `/v1/osm/transport` UI overlay with source toggle. `docs/PROJECT.md` is not present; proceeding using current API/UI contracts and explicit user requirements. BLOCKED: authoritative requirement file missing in repository.
- Evidence: `src/inframap/serve/app.py`; `frontend/main.js`; `tests/unit/test_serve_osm_transport.py`; `docs/IMPLEMENTATION_PLAN.md`
- Next: Install optimized parser dependency and split implementation across worker agents (backend graph builder/API, frontend toggle/tests).

## 2026-03-06T21:05:52Z
- Status: in progress
- Checklist item: Implement minimal code for graph build + API/UI toggle
- Update: Installed `osmium`, added OSM PBF major-road graph builder + country script, extended `/v1/osm/transport` with `source=shapefile|graph` (default shapefile), added UI source selector with reload, and expanded transport styles for link classes. Generated TW graph artifacts from `taiwan-260305.osm.pbf`.
- Evidence: `src/inframap/ingest/major_road_graph.py`; `scripts/build_major_roads_graph.py`; `src/inframap/serve/app.py`; `frontend/index.html`; `frontend/main.js`; `data/openstreetmap/TW/major_roads_edges.geojson`; `data/openstreetmap/TW/major_roads_nodes.geojson`
- Next: Run impacted verification, UI visual protocol, docs/mistake replay checks, and finalize handoff.

## 2026-03-06T21:05:52Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: Completed impacted verification and visual protocol: unit/UI tests pass, `make verify-dev` pass, `make run-dev COUNTRIES=TW` pass, API payload for `source=graph` verified non-empty on local server, and UI screenshot captured with graph source selected.
- Evidence: `pytest -q tests/unit/test_serve_osm_transport.py tests/ui/test_ui_smoke.py` -> `5 passed`; `make verify-dev` -> `7 passed, 1 skipped` + `1 passed`; `make run-dev COUNTRIES=TW` -> complete run id `run-b5e322b987e3-67c008612de6-fc2dfd1d688f`; `curl http://127.0.0.1:8001/v1/osm/transport?country=TW&source=graph&limit=10` -> `feature_count=10`; `artifacts/screenshots/2026-03-06-ui-osm-transport-graph-toggle.png`
- Next: Complete docs freshness and mistake replay confirmation, then handoff.

## 2026-03-06T21:05:52Z
- Status: complete
- Checklist item: Mistake replay check
- Update: Docs/config review complete. README and AGENTS were updated for the new graph source behavior and build script. Mistake replay check completed against ledger before handoff.
- Evidence: `README.md`; `AGENTS.md`; `tail -n 40 logs/mistakes.md`
- Next: None.

## 2026-03-06T21:11:50Z
- Status: in progress
- Checklist item: Implement minimal code for graph build + API/UI toggle
- Update: Follow-up enhancement requested: render graph nodes together with edges and color adjacent graph edges differently. Implemented API option `include_nodes=true` for `source=graph`, preserved edge metadata for adjacency coloring (`u`, `v`, `edge_id`), and updated UI graph mode to request nodes and apply greedy adjacency-based edge palette assignment.
- Evidence: `src/inframap/serve/app.py`; `frontend/main.js`; `tests/unit/test_serve_osm_transport.py`; `tests/ui/test_ui_smoke.py`
- Next: Re-run impacted tests and visual verification screenshot.

## 2026-03-06T21:11:50Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: Passed focused test suite and verified live API/UI behavior on local server with graph nodes enabled. Captured updated screenshot showing graph-source rendering with node markers and multicolor edges.
- Evidence: `pytest -q tests/unit/test_serve_osm_transport.py tests/ui/test_ui_smoke.py` -> `6 passed`; `curl http://127.0.0.1:8001/v1/osm/transport?country=TW&source=graph&include_nodes=true&limit=40` -> `source=graph`; `artifacts/screenshots/2026-03-06-ui-osm-transport-graph-nodes-colors.png`
- Next: Refresh docs notes and complete mistake replay check.

## 2026-03-06T21:11:50Z
- Status: complete
- Checklist item: Mistake replay check
- Update: Updated README and AGENTS docs for `include_nodes=true` graph behavior and completed mistake replay check with corrective ledger append for a command parsing error encountered during payload validation.
- Evidence: `README.md`; `AGENTS.md`; `logs/mistakes.md`
- Next: None.
