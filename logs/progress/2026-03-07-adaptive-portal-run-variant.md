# Task: adaptive_portal_run variant support

Checklist:
- [~] Confirm requirement in 
- [ ] Add/update tests for changed behavior
- [ ] Implement minimal code in ingest + build script
- [ ] Run focused local verification for impacted paths
- [ ] Docs/config check (, , )
- [ ] Mistake replay check logged

## 2026-03-07T08:32:00Z
- Status: in progress
- Checklist item: Confirm requirement in 
- Update: Started task and scoped required files for ingest, build script, and unit tests.
- Evidence: docs/PROJECT.md:70:- `graph_variant=adaptive_portal` uses `major_roads_edges_adaptive_portal.geojson` and `major_roads_nodes_adaptive_portal.geojson`, produced by fixed-resolution boundary splitting with explicit portal/interface nodes and per-cell topology contraction; adaptive-portal output is mainline-only (`motorway`/`trunk`) and nodes are anchor-only (portal + junction nodes).
scripts/build_major_roads_graph.py:7:from inframap.ingest.major_road_graph import build_major_road_graph_variants
scripts/build_major_roads_graph.py:16:    "write_adaptive_portal": "Write adaptive portal graph files",
scripts/build_major_roads_graph.py:102:        choices=("raw", "collapsed", "adaptive", "adaptive_portal", "both"),
scripts/build_major_roads_graph.py:138:    if "adaptive" in variants or "adaptive_portal" in variants:
scripts/build_major_roads_graph.py:140:    outputs = build_major_road_graph_variants(**build_kwargs)
scripts/build_major_roads_graph.py:156:    if "adaptive_portal" in outputs:
scripts/build_major_roads_graph.py:157:        adaptive_portal_edges_path, adaptive_portal_nodes_path = outputs["adaptive_portal"]
scripts/build_major_roads_graph.py:158:        print(f"edges_geojson_adaptive_portal={adaptive_portal_edges_path}")
scripts/build_major_roads_graph.py:159:        print(f"nodes_geojson_adaptive_portal={adaptive_portal_nodes_path}")
tests/unit/test_major_road_graph_contraction.py:6:    _adaptive_portal_anchor_node_ids,
tests/unit/test_major_road_graph_contraction.py:14:    split_edges_with_adaptive_portals,
tests/unit/test_major_road_graph_contraction.py:144:def test_split_edges_with_adaptive_portals_splits_cross_cell_segments() -> None:
tests/unit/test_major_road_graph_contraction.py:154:    split_edges, split_nodes, portal_nodes = split_edges_with_adaptive_portals(edges, nodes, resolution=resolution)
tests/unit/test_major_road_graph_contraction.py:175:def test_split_edges_with_adaptive_portals_handles_multiple_crossings_per_segment() -> None:
tests/unit/test_major_road_graph_contraction.py:185:    split_edges, _split_nodes, portal_nodes = split_edges_with_adaptive_portals(edges, nodes, resolution=resolution)
tests/unit/test_major_road_graph_contraction.py:200:def test_adaptive_portal_split_and_contract_is_deterministic() -> None:
tests/unit/test_major_road_graph_contraction.py:215:    first_split_edges, first_split_nodes, first_portals = split_edges_with_adaptive_portals(
tests/unit/test_major_road_graph_contraction.py:220:    second_split_edges, second_split_nodes, second_portals = split_edges_with_adaptive_portals(
tests/unit/test_major_road_graph_contraction.py:308:def test_adaptive_portal_anchor_node_ids_keeps_portals_and_junctions_only() -> None:
tests/unit/test_major_road_graph_contraction.py:314:    anchors = _adaptive_portal_anchor_node_ids(edges, portal_node_ids={4})
src/inframap/serve/app.py:250:    graph_variant: Literal["raw", "collapsed", "adaptive", "adaptive_portal", "adaptive_portal_run"]
src/inframap/serve/app.py:256:    if graph_variant == "adaptive_portal":
src/inframap/serve/app.py:257:        return "major_roads_edges_adaptive_portal.geojson", "major_roads_nodes_adaptive_portal.geojson"
src/inframap/serve/app.py:258:    if graph_variant == "adaptive_portal_run":
src/inframap/serve/app.py:259:        return "major_roads_edges_adaptive_portal_run.geojson", "major_roads_nodes_adaptive_portal_run.geojson"
src/inframap/serve/app.py:265:    graph_variant: Literal["raw", "collapsed", "adaptive", "adaptive_portal", "adaptive_portal_run"],
src/inframap/serve/app.py:347:    graph_variant: Literal["raw", "collapsed", "adaptive", "adaptive_portal", "adaptive_portal_run"],
src/inframap/serve/app.py:764:        graph_variant: Literal["raw", "collapsed", "adaptive", "adaptive_portal", "adaptive_portal_run"] = Query(
src/inframap/serve/app.py:772:            if graph_variant == "adaptive_portal_run":
src/inframap/serve/app.py:774:                    raise HTTPException(status_code=400, detail="run_id is required for graph_variant=adaptive_portal_run")
src/inframap/serve/app.py:821:            "run_agnostic": not (source == "graph" and graph_variant == "adaptive_portal_run"),
src/inframap/serve/app.py:822:            "run_id": used_run_id if graph_variant == "adaptive_portal_run" else None,
tests/unit/test_major_road_graph_progress.py:23:def test_build_major_road_graph_variants_emits_progress_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
tests/unit/test_major_road_graph_progress.py:50:    outputs = major_road_graph.build_major_road_graph_variants(
tests/unit/test_major_road_graph_progress.py:53:        variants=("raw", "adaptive", "adaptive_portal"),
tests/unit/test_major_road_graph_progress.py:58:    assert set(outputs) == {"raw", "adaptive", "adaptive_portal"}
tests/unit/test_major_road_graph_progress.py:68:        ("phase_start", "write_adaptive_portal"),
tests/unit/test_major_road_graph_progress.py:69:        ("phase_end", "write_adaptive_portal"),
tests/unit/test_major_road_graph_progress.py:78:def test_build_major_road_graph_variants_validates_adaptive_resolution_before_write(tmp_path: Path) -> None:
tests/unit/test_major_road_graph_progress.py:81:        major_road_graph.build_major_road_graph_variants(
tests/unit/test_major_road_graph_progress.py:84:            variants=("raw", "adaptive_portal"),
tests/unit/test_serve_osm_transport.py:174:def _write_major_roads_edges_adaptive_portal_geojson(path: Path) -> None:
tests/unit/test_serve_osm_transport.py:191:def _write_major_roads_nodes_adaptive_portal_geojson(path: Path) -> None:
tests/unit/test_serve_osm_transport.py:449:def test_osm_transport_overlay_source_graph_variant_adaptive_portal_loads_adaptive_portal_files(tmp_path: Path) -> None:
tests/unit/test_serve_osm_transport.py:454:    _write_major_roads_edges_adaptive_portal_geojson(tw / "major_roads_edges_adaptive_portal.geojson")
tests/unit/test_serve_osm_transport.py:457:    response = client.get("/v1/osm/transport?source=graph&graph_variant=adaptive_portal")
tests/unit/test_serve_osm_transport.py:468:def test_osm_transport_overlay_source_graph_variant_adaptive_portal_include_nodes_uses_adaptive_portal_nodes(tmp_path: Path) -> None:
tests/unit/test_serve_osm_transport.py:472:    _write_major_roads_edges_adaptive_portal_geojson(tw / "major_roads_edges_adaptive_portal.geojson")
tests/unit/test_serve_osm_transport.py:473:    _write_major_roads_nodes_adaptive_portal_geojson(tw / "major_roads_nodes_adaptive_portal.geojson")
tests/unit/test_serve_osm_transport.py:476:    response = client.get("/v1/osm/transport?source=graph&graph_variant=adaptive_portal&include_nodes=true")
tests/unit/test_serve_osm_transport.py:485:def test_osm_transport_overlay_source_graph_variant_adaptive_portal_country_listing_uses_adaptive_portal_edges(tmp_path: Path) -> None:
tests/unit/test_serve_osm_transport.py:494:    _write_major_roads_edges_adaptive_portal_geojson(us / "major_roads_edges_adaptive_portal.geojson")
tests/unit/test_serve_osm_transport.py:497:    response = client.get("/v1/osm/transport?source=graph&graph_variant=adaptive_portal")
tests/ui/test_ui_smoke.py:96:    assert "adaptive_portal" in script_response.text
src/inframap/ingest/major_road_graph.py:21:ADAPTIVE_PORTAL_EDGE_FILENAME = "major_roads_edges_adaptive_portal.geojson"
src/inframap/ingest/major_road_graph.py:22:ADAPTIVE_PORTAL_NODE_FILENAME = "major_roads_nodes_adaptive_portal.geojson"
src/inframap/ingest/major_road_graph.py:23:GraphVariant = Literal["raw", "collapsed", "adaptive", "adaptive_portal"]
src/inframap/ingest/major_road_graph.py:467:def split_edges_with_adaptive_portals(
src/inframap/ingest/major_road_graph.py:669:def _adaptive_portal_anchor_node_ids(edges: list[dict[str, object]], portal_node_ids: set[int]) -> set[int]:
src/inframap/ingest/major_road_graph.py:680:    if variant == "adaptive_portal":
src/inframap/ingest/major_road_graph.py:689:def build_major_road_graph_variants(
src/inframap/ingest/major_road_graph.py:708:    if ("adaptive" in requested or "adaptive_portal" in requested) and adaptive_resolution is None:
src/inframap/ingest/major_road_graph.py:709:        raise ValueError("adaptive_resolution is required when adaptive or adaptive_portal graph variant is requested")
src/inframap/ingest/major_road_graph.py:772:    if "adaptive_portal" in requested:
src/inframap/ingest/major_road_graph.py:773:        def write_adaptive_portal() -> None:
src/inframap/ingest/major_road_graph.py:774:            split_edges, split_nodes, portal_nodes = split_edges_with_adaptive_portals(
src/inframap/ingest/major_road_graph.py:779:            adaptive_portal_edges = contract_edges_within_cells_preserving_portals(
src/inframap/ingest/major_road_graph.py:784:            adaptive_portal_edges = _filter_mainline_edges(adaptive_portal_edges)
src/inframap/ingest/major_road_graph.py:785:            adaptive_portal_node_ids = sorted(_adaptive_portal_anchor_node_ids(adaptive_portal_edges, portal_nodes))
src/inframap/ingest/major_road_graph.py:786:            adaptive_portal_node_items = [
src/inframap/ingest/major_road_graph.py:787:                (node_id, split_nodes[node_id]) for node_id in adaptive_portal_node_ids if node_id in split_nodes
src/inframap/ingest/major_road_graph.py:789:            adaptive_portal_edge_features = _to_edge_features(adaptive_portal_edges)
src/inframap/ingest/major_road_graph.py:790:            adaptive_portal_node_features = _to_node_features(adaptive_portal_node_items)
src/inframap/ingest/major_road_graph.py:791:            adaptive_portal_edges_name, adaptive_portal_nodes_name = _variant_filenames("adaptive_portal")
src/inframap/ingest/major_road_graph.py:792:            adaptive_portal_edges_path = output_dir / adaptive_portal_edges_name
src/inframap/ingest/major_road_graph.py:793:            adaptive_portal_nodes_path = output_dir / adaptive_portal_nodes_name
src/inframap/ingest/major_road_graph.py:794:            _write_geojson(adaptive_portal_edges_path, adaptive_portal_edge_features)
src/inframap/ingest/major_road_graph.py:795:            _write_geojson(adaptive_portal_nodes_path, adaptive_portal_node_features)
src/inframap/ingest/major_road_graph.py:796:            outputs["adaptive_portal"] = (adaptive_portal_edges_path, adaptive_portal_nodes_path)
src/inframap/ingest/major_road_graph.py:798:        run_stage("write_adaptive_portal", write_adaptive_portal)
src/inframap/ingest/major_road_graph.py:805:    outputs = build_major_road_graph_variants(pbf_path=pbf_path, output_dir=output_dir, variants=("raw",))
- Next: Confirm contract details in  and implement additive variant path.

## 2026-03-07T08:32:14Z
- Status: in progress
- Checklist item: Confirm requirement in 
- Update: Confirmed existing contract for  behavior and that serve path already supports  filenames; proceeding with ingest/build implementation.
- Evidence: ,  graph variant filename mapping includes .
- Next: Implement additive  ingest path using run-scoped adaptive mask cells.

Checklist status:
- [x] Confirm requirement in 
- [ ] Add/update tests for changed behavior
- [ ] Implement minimal code in ingest + build script
- [ ] Run focused local verification for impacted paths
- [ ] Docs/config check (, , )
- [ ] Mistake replay check logged

## 2026-03-07T08:36:31Z
- Status: in progress
- Checklist item: Add/update tests for changed behavior
- Update: Added progress validation coverage for write_adaptive_portal_run stage and adaptive_mask_cells validation; added contraction tests for adaptive mask split/contract correctness and determinism.
- Evidence: tests/unit/test_major_road_graph_progress.py and tests/unit/test_major_road_graph_contraction.py updated.
- Next: Implement and verify ingest/build script behavior with focused tests.

Checklist status:
- [x] Confirm requirement in docs/PROJECT.md
- [~] Add/update tests for changed behavior
- [~] Implement minimal code in ingest + build script
- [ ] Run focused local verification for impacted paths
- [ ] Docs/config check (docs/PROJECT.md, README.md, AGENTS.md)
- [ ] Mistake replay check logged

## 2026-03-07T08:36:31Z
- Status: in progress
- Checklist item: Run focused local verification for impacted paths
- Update: Ran focused tests for touched graph ingest/progress/contraction paths; all passed.
- Evidence: pytest -q tests/unit/test_major_road_graph_progress.py tests/unit/test_major_road_graph_contraction.py -> 20 passed
- Next: Complete docs check and mistake replay confirmation before handoff.

Checklist status:
- [x] Confirm requirement in docs/PROJECT.md
- [x] Add/update tests for changed behavior
- [x] Implement minimal code in ingest + build script
- [x] Run focused local verification for impacted paths
- [~] Docs/config check (docs/PROJECT.md, README.md, AGENTS.md)
- [ ] Mistake replay check logged

## 2026-03-07T08:38:40Z
- Status: in progress
- Checklist item: Docs/config check (docs/PROJECT.md, README.md, AGENTS.md)
- Update: Updated transport graph contract docs to include adaptive_portal_run run-scoped artifact paths and behavior.
- Evidence: docs/PROJECT.md, README.md, and AGENTS.md edited.
- Next: Run mistake replay check and complete task handoff.

Checklist status:
- [x] Confirm requirement in docs/PROJECT.md
- [x] Add/update tests for changed behavior
- [x] Implement minimal code in ingest + build script
- [x] Run focused local verification for impacted paths
- [x] Docs/config check (docs/PROJECT.md, README.md, AGENTS.md)
- [~] Mistake replay check logged

## 2026-03-07T08:38:40Z
- Status: complete
- Checklist item: Mistake replay check logged
- Update: Reviewed logs/mistakes.md, appended current-session mistake and prevention rule, and confirmed replay completion before handoff.
- Evidence: logs/mistakes.md includes 2026-03-07T08:37:55Z entry.
- Next: Handoff with changed files and focused test results.

Checklist status:
- [x] Confirm requirement in docs/PROJECT.md
- [x] Add/update tests for changed behavior
- [x] Implement minimal code in ingest + build script
- [x] Run focused local verification for impacted paths
- [x] Docs/config check (docs/PROJECT.md, README.md, AGENTS.md)
- [x] Mistake replay check logged
