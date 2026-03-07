# Backend Major-Road Graph Support

Checklist
- [x] Confirm requirement reference and existing contracts
- [x] Add/update tests for changed behavior
- [x] Implement minimal code for graph ingest module and country script
- [x] Integrate `/v1/osm/transport` source toggle with backward-compatible default path
- [x] Run local verification for impacted paths
- [x] Update docs/config examples when behavior/interfaces change
- [x] Update `README.md` and `AGENTS.md` for workflow/contract/tooling changes
- [x] Mistake replay check

## 2026-03-06T20:58:37Z
- Status: in progress
- Checklist item: Confirm requirement reference and existing contracts
- Update: Reviewed current transport overlay endpoint and unit tests. Confirmed existing default behavior is shapefile-backed motorway/trunk plus rail features. `docs/PROJECT.md` is not present in this repository snapshot, so implementation contract is mapped to the explicit user requirements and current code/tests. BLOCKED: authoritative `docs/PROJECT.md` file missing.
- Evidence: `src/inframap/serve/app.py`; `tests/unit/test_serve_osm_transport.py`; `ls docs`
- Next: Implement graph ingester + script and then extend endpoint source toggle with focused tests.

## 2026-03-06T21:01:11Z
- Status: in progress
- Checklist item: Implement minimal code for graph ingest module and country script
- Update: Added deterministic osmium-backed graph build module and script entrypoint. Graph build performs a split-node first pass (shared-node detection), then segments selected ways (`motorway`, `trunk`, `motorway_link`, `trunk_link`) into undirected graph edges between split points while preserving full coordinate sequence. Also integrated `/v1/osm/transport` `source` query toggle with graph feature loading from `major_roads_edges.geojson` and source-aware country availability.
- Evidence: `src/inframap/ingest/major_road_graph.py`; `scripts/build_major_roads_graph.py`; `src/inframap/serve/app.py`; `pyproject.toml`
- Next: Finalize and run focused unit tests for source toggle and graph fallback, then do docs/mistake replay checks.

## 2026-03-06T21:02:01Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: Added focused unit tests for shapefile default source behavior, graph source loading, and graph missing-file fallback. Verified impacted backend paths only.
- Evidence: `pytest -q tests/unit/test_serve_osm_transport.py` -> `4 passed`; `python -m py_compile src/inframap/ingest/major_road_graph.py scripts/build_major_roads_graph.py src/inframap/serve/app.py tests/unit/test_serve_osm_transport.py`
- Next: Finalize docs and perform mistake replay check before handoff.

## 2026-03-06T21:02:01Z
- Status: complete
- Checklist item: Mistake replay check
- Update: Updated README and AGENTS for new OSM transport source contract and graph generation script. Mistake replay check completed against current ledger; no new mistakes discovered during this task.
- Evidence: `README.md`; `AGENTS.md`; `tail -n 40 logs/mistakes.md`
- Next: Handoff touched file list and concise rationale.
