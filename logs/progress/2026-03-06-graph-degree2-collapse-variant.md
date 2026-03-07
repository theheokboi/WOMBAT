# Graph Degree-2 Collapse Variant

Checklist
- [x] Confirm requirement reference and compatibility constraints
- [x] Add/update tests for changed behavior
- [x] Implement minimal code for collapse variant (backend + UI selector)
- [x] Run local verification for impacted paths
- [x] Update docs/config examples when behavior/interfaces change
- [x] Update README.md and AGENTS.md for workflow/contract/tooling changes
- [x] Mistake replay check

## 2026-03-06T21:20:30Z
- Status: in progress
- Checklist item: Confirm requirement reference and compatibility constraints
- Update: Reviewed current graph artifact/API/UI coupling and decided to implement degree-2 contraction as an opt-in graph variant (`raw` default, `collapsed` opt-in) to avoid breaking existing `source=graph` behavior. `docs/PROJECT.md` remains absent, so requirement mapping uses user request and existing contracts.
- Evidence: `src/inframap/ingest/major_road_graph.py`; `src/inframap/serve/app.py`; `frontend/main.js`; explorer-agent findings
- Next: Merge worker implementations for backend and frontend, then run focused and dev verification.

## 2026-03-06T21:25:47Z
- Status: in progress
- Checklist item: Implement minimal code for collapse variant (backend + UI selector)
- Update: Merged worker changes implementing `graph_variant=raw|collapsed` end-to-end: ingest contraction utility + variant artifacts, script variant flag, API variant loading, and UI selector to request raw/collapsed graph mode while preserving default raw behavior.
- Evidence: `src/inframap/ingest/major_road_graph.py`; `scripts/build_major_roads_graph.py`; `src/inframap/serve/app.py`; `frontend/index.html`; `frontend/main.js`; `frontend/styles.css`
- Next: Run focused tests, regenerate TW graph variants, then run dev verification and visual protocol checks.

## 2026-03-06T21:25:47Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: Verification complete. Focused tests pass, `make verify-dev` passes, TW raw+collapsed artifacts regenerated, collapsed API payload verified non-empty, and updated UI screenshot captured with graph variant set to collapsed.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py tests/unit/test_serve_osm_transport.py tests/ui/test_ui_smoke.py` -> `11 passed`; `make verify-dev` -> unit/integration `7 passed, 1 skipped` + ui smoke `1 passed`; `python scripts/build_major_roads_graph.py --country TW --graph-variant both`; API check `/v1/osm/transport?country=TW&source=graph&graph_variant=collapsed&include_nodes=true`; screenshot `artifacts/screenshots/2026-03-06-ui-graph-collapsed-variant.png`
- Next: Final docs/mistake replay checks and handoff.

## 2026-03-06T21:25:47Z
- Status: complete
- Checklist item: Mistake replay check
- Update: Docs and contract notes updated for graph variant behavior in README and AGENTS. Mistake replay check completed against current ledger before handoff.
- Evidence: `README.md`; `AGENTS.md`; `tail -n 20 logs/mistakes.md`
- Next: None.
