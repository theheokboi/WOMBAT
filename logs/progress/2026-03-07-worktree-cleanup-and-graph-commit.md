# Task: Worktree Cleanup And Graph Commit

Checklist
- [x] Inspect remaining tracked and untracked files
- [~] Separate feature code from local artifacts/data
- [ ] Add ignore rules for local generated artifacts and datasets
- [ ] Verify the OSM graph feature changes
- [ ] Commit the remaining coherent feature/log changes

## 2026-03-07T06:33:30Z
- Status: in progress
- Checklist item: Separate feature code from local artifacts/data
- Update: Grouped the remaining dirty worktree into one coherent OSM graph feature set plus local generated artifacts/data (screenshots and `data/openstreetmap/TW/*`). Preparing to ignore local artifacts, verify the code changes, and commit only the feature files and related logs.
- Evidence: `git status --short`; `git diff --name-status HEAD`; targeted reads of frontend, backend, ingest, script, and test files.
- Next: Add ignore rules for local artifacts/data, run targeted verification, and stage the feature scope.

## 2026-03-07T06:28:09Z
- Status: in progress
- Checklist item: Verify the OSM graph feature changes
- Update: Added ignore rules for local screenshots and per-country OSM graph input/output files, then ran targeted verification for the graph endpoint, contraction logic, and UI smoke path. All targeted checks passed.
- Evidence: `.gitignore`; `pytest -q tests/unit/test_serve_osm_transport.py tests/unit/test_major_road_graph_contraction.py tests/ui/test_ui_smoke.py`; `python -m py_compile src/inframap/serve/app.py src/inframap/ingest/major_road_graph.py scripts/build_major_roads_graph.py tests/unit/test_serve_osm_transport.py tests/unit/test_major_road_graph_contraction.py`
- Next: Stage the coherent feature files and related logs, then commit them without including local datasets or screenshots.
