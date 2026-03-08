from __future__ import annotations

import h3

from inframap.ingest.major_road_graph import (
    _cell_metric_proxy_edges,
    _cell_metric_feeder_proxy_edges,
    _cell_metric_proxy_tree_edges,
    _adaptive_portal_anchor_node_ids,
    _adaptive_mask_cell_for_point,
    _adaptive_mask_cells_by_resolution,
    _build_portal_node_id,
    _build_portal_node_id_for_mask,
    _connected_node_ids,
    _filter_cross_cell_edges,
    _filter_adaptive_portal_edges_post_contract,
    _filter_mainline_edges_by_cell_priority,
    _filter_mainline_edges_for_adaptive_mask,
    _filter_mainline_edges_for_fixed_resolution,
    contract_edges_within_adaptive_mask_preserving_portals,
    contract_edges_within_cells_preserving_portals,
    _node_cells_at_resolution,
    _protected_nodes_from_cross_cell_edges,
    contract_degree2_undirected_edges,
    split_edges_with_adaptive_mask_portals,
    split_edges_with_adaptive_portals,
)


def _edge(
    edge_id: str,
    u: int,
    v: int,
    coords: list[list[float]],
    *,
    road_class: str = "motorway",
    oneway: str | None = None,
    name: str | None = "m1",
    ref: str | None = None,
) -> dict[str, object]:
    return {
        "edge_id": edge_id,
        "u": u,
        "v": v,
        "road_class": road_class,
        "oneway": oneway,
        "name": name,
        "ref": ref,
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def test_contract_degree2_undirected_edges_collapses_interior_chain_node() -> None:
    edges = [
        _edge("e1", 1, 2, [[0.0, 0.0], [1.0, 0.0]]),
        _edge("e2", 2, 3, [[1.0, 0.0], [2.0, 0.0]]),
        _edge("e3", 3, 4, [[2.0, 0.0], [3.0, 0.0]]),
        _edge("e4", 3, 5, [[2.0, 0.0], [2.0, 1.0]], road_class="trunk", name="t1"),
    ]

    contracted = contract_degree2_undirected_edges(edges)

    assert len(contracted) == 3
    merged = next(edge for edge in contracted if {edge["u"], edge["v"]} == {1, 3})
    assert merged["road_class"] == "motorway"
    assert merged["geometry"]["coordinates"] == [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]

    branch = next(edge for edge in contracted if {edge["u"], edge["v"]} == {3, 5})
    assert branch["road_class"] == "trunk"


def test_contract_degree2_undirected_edges_is_deterministic_across_input_order() -> None:
    ordered = [
        _edge("a", 10, 11, [[0.0, 0.0], [1.0, 0.0]]),
        _edge("b", 11, 12, [[1.0, 0.0], [2.0, 0.0]]),
        _edge("c", 12, 13, [[2.0, 0.0], [3.0, 0.0]]),
    ]
    reversed_input = list(reversed(ordered))

    first = contract_degree2_undirected_edges(ordered)
    second = contract_degree2_undirected_edges(reversed_input)

    assert len(first) == 1
    assert len(second) == 1
    assert first[0]["u"] == 10
    assert first[0]["v"] == 13
    assert second[0]["u"] == 10
    assert second[0]["v"] == 13
    assert first[0]["edge_id"] == second[0]["edge_id"]
    assert first[0]["geometry"]["coordinates"] == second[0]["geometry"]["coordinates"]


def test_contract_degree2_undirected_edges_respects_protected_nodes() -> None:
    edges = [
        _edge("e1", 1, 2, [[0.0, 0.0], [1.0, 0.0]]),
        _edge("e2", 2, 3, [[1.0, 0.0], [2.0, 0.0]]),
    ]

    contracted = contract_degree2_undirected_edges(edges, protected_nodes={2})

    assert len(contracted) == 2
    assert sorted((int(edge["u"]), int(edge["v"])) for edge in contracted) == [(1, 2), (2, 3)]


def test_contract_degree2_undirected_edges_with_protected_nodes_is_deterministic() -> None:
    ordered = [
        _edge("a", 1, 2, [[0.0, 0.0], [1.0, 0.0]]),
        _edge("b", 2, 3, [[1.0, 0.0], [2.0, 0.0]]),
        _edge("c", 3, 4, [[2.0, 0.0], [3.0, 0.0]]),
    ]
    reversed_input = list(reversed(ordered))

    first = contract_degree2_undirected_edges(ordered, protected_nodes={2})
    second = contract_degree2_undirected_edges(reversed_input, protected_nodes={2})

    assert len(first) == 2
    assert len(second) == 2
    assert sorted((int(edge["u"]), int(edge["v"])) for edge in first) == [(1, 2), (2, 4)]
    assert sorted((int(edge["u"]), int(edge["v"])) for edge in second) == [(1, 2), (2, 4)]
    assert [edge["edge_id"] for edge in first] == [edge["edge_id"] for edge in second]


def test_contract_degree2_undirected_edges_can_ignore_metadata_differences() -> None:
    edges = [
        _edge("a", 1, 2, [[0.0, 0.0], [1.0, 0.0]], road_class="motorway", name="a1"),
        _edge("b", 2, 3, [[1.0, 0.0], [2.0, 0.0]], road_class="trunk", name="b2"),
    ]

    strict = contract_degree2_undirected_edges(edges)
    topology_only = contract_degree2_undirected_edges(edges, merge_by_topology_only=True)

    assert len(strict) == 2
    assert len(topology_only) == 1
    assert {int(topology_only[0]["u"]), int(topology_only[0]["v"])} == {1, 3}


def test_protected_nodes_from_cross_cell_edges_marks_only_cross_cell_endpoints() -> None:
    nodes = {
        1: (121.0, 25.0),
        2: (121.02, 25.01),
        3: (130.0, 35.0),
    }
    node_cells = _node_cells_at_resolution(nodes, resolution=2)
    edges = [
        _edge("e1", 1, 2, [[121.0, 25.0], [121.02, 25.01]]),
        _edge("e2", 2, 3, [[121.02, 25.01], [130.0, 35.0]]),
    ]

    protected = _protected_nodes_from_cross_cell_edges(edges, node_cells)

    assert node_cells[1] == node_cells[2]
    assert node_cells[2] != node_cells[3]
    assert protected == {2, 3}


def test_split_edges_with_adaptive_portals_splits_cross_cell_segments() -> None:
    resolution = 5
    nodes = {
        1: (-122.55, 37.70),
        2: (-122.30, 37.70),
    }
    edges = [
        _edge("cross", 1, 2, [[-122.55, 37.70], [-122.30, 37.70]]),
    ]

    split_edges, split_nodes, portal_nodes = split_edges_with_adaptive_portals(edges, nodes, resolution=resolution)

    assert _node_cells_at_resolution(nodes, resolution=resolution)[1] != _node_cells_at_resolution(nodes, resolution=resolution)[2]
    assert len(portal_nodes) >= 1
    assert len(split_edges) >= 2
    assert all(int(edge["u"]) in split_nodes for edge in split_edges)
    assert all(int(edge["v"]) in split_nodes for edge in split_edges)
    # Split output should not keep any segment crossing multiple H3 cells in its interior.
    for edge in split_edges:
        coords = edge["geometry"]["coordinates"]
        mid_lon = (float(coords[0][0]) + float(coords[-1][0])) / 2.0
        mid_lat = (float(coords[0][1]) + float(coords[-1][1])) / 2.0
        mid_cell = str(h3.latlng_to_cell(mid_lat, mid_lon, resolution))
        quarter_lon = float(coords[0][0]) * 0.75 + float(coords[-1][0]) * 0.25
        quarter_lat = float(coords[0][1]) * 0.75 + float(coords[-1][1]) * 0.25
        three_quarter_lon = float(coords[0][0]) * 0.25 + float(coords[-1][0]) * 0.75
        three_quarter_lat = float(coords[0][1]) * 0.25 + float(coords[-1][1]) * 0.75
        assert str(h3.latlng_to_cell(quarter_lat, quarter_lon, resolution)) == mid_cell
        assert str(h3.latlng_to_cell(three_quarter_lat, three_quarter_lon, resolution)) == mid_cell


def test_split_edges_with_adaptive_portals_handles_multiple_crossings_per_segment() -> None:
    resolution = 5
    nodes = {
        1: (-123.50, 37.70),
        2: (-121.00, 37.70),
    }
    edges = [
        _edge("long_cross", 1, 2, [[-123.50, 37.70], [-121.00, 37.70]]),
    ]

    split_edges, _split_nodes, portal_nodes = split_edges_with_adaptive_portals(edges, nodes, resolution=resolution)

    assert len(portal_nodes) >= 2
    assert len(split_edges) >= 3


def test_build_portal_node_id_stays_within_javascript_safe_integer_range() -> None:
    first = _build_portal_node_id(-122.450000001, 37.700000001, 5)
    second = _build_portal_node_id(-122.450000009, 37.700000009, 5)

    assert abs(first) < 2**53
    assert abs(second) < 2**53
    assert first != second


def test_build_portal_node_id_for_mask_is_direction_invariant() -> None:
    first = _build_portal_node_id_for_mask(-122.45, 37.70, "8428347ffffffff", "8528347bfffffff")
    second = _build_portal_node_id_for_mask(-122.45, 37.70, "8528347bfffffff", "8428347ffffffff")

    assert first == second
    assert abs(first) < 2**53


def test_adaptive_portal_split_and_contract_is_deterministic() -> None:
    resolution = 5
    nodes = {
        1: (-122.55, 37.70),
        2: (-122.45, 37.70),
        3: (-122.35, 37.70),
        4: (-122.25, 37.70),
    }
    ordered_edges = [
        _edge("e1", 1, 2, [[-122.55, 37.70], [-122.45, 37.70]]),
        _edge("e2", 2, 3, [[-122.45, 37.70], [-122.35, 37.70]]),
        _edge("e3", 3, 4, [[-122.35, 37.70], [-122.25, 37.70]]),
    ]
    reversed_edges = list(reversed(ordered_edges))

    first_split_edges, first_split_nodes, first_portals = split_edges_with_adaptive_portals(
        ordered_edges,
        nodes,
        resolution=resolution,
    )
    second_split_edges, second_split_nodes, second_portals = split_edges_with_adaptive_portals(
        reversed_edges,
        nodes,
        resolution=resolution,
    )

    assert [edge["edge_id"] for edge in first_split_edges] == [edge["edge_id"] for edge in second_split_edges]
    assert first_portals == second_portals
    assert first_split_nodes == second_split_nodes

    first_contracted = contract_edges_within_cells_preserving_portals(
        split_edges=first_split_edges,
        portal_node_ids=first_portals,
        resolution=resolution,
    )
    second_contracted = contract_edges_within_cells_preserving_portals(
        split_edges=second_split_edges,
        portal_node_ids=second_portals,
        resolution=resolution,
    )

    assert [edge["edge_id"] for edge in first_contracted] == [edge["edge_id"] for edge in second_contracted]
    assert [(int(edge["u"]), int(edge["v"])) for edge in first_contracted] == [
        (int(edge["u"]), int(edge["v"])) for edge in second_contracted
    ]


def test_contract_edges_within_cells_preserving_portals_can_prune_non_anchor_leaf_chains() -> None:
    edges = [
        _edge("a", 2, 1, [[121.00, 25.00], [121.01, 25.00]]),
        _edge("b", 2, 3, [[121.00, 25.00], [121.00, 25.01]]),
        _edge("c", 2, 99, [[121.00, 25.00], [121.01, 25.01]]),
    ]

    kept = contract_edges_within_cells_preserving_portals(
        split_edges=edges,
        portal_node_ids={99},
        resolution=5,
        prune_non_anchor_leaves=False,
    )
    pruned = contract_edges_within_cells_preserving_portals(
        split_edges=edges,
        portal_node_ids={99},
        resolution=5,
        prune_non_anchor_leaves=True,
    )

    assert len(kept) == 3
    assert len(pruned) == 1
    assert {int(pruned[0]["u"]), int(pruned[0]["v"])} == {2, 99}


def test_contract_edges_within_cells_preserving_portals_can_prune_all_leaf_nodes() -> None:
    edges = [
        _edge("a", 2, 1, [[121.00, 25.00], [121.01, 25.00]]),
        _edge("b", 2, 3, [[121.00, 25.00], [121.00, 25.01]]),
        _edge("c", 2, 99, [[121.00, 25.00], [121.01, 25.01]]),
    ]
    pruned = contract_edges_within_cells_preserving_portals(
        split_edges=edges,
        portal_node_ids={99},
        resolution=5,
        prune_all_leaves=True,
    )

    assert pruned == []


def test_filter_cross_cell_edges_drops_intra_cell_edges() -> None:
    nodes = {
        1: (121.00, 25.00),
        2: (121.02, 25.01),
        3: (130.00, 35.00),
    }
    node_cells = _node_cells_at_resolution(nodes, resolution=2)
    edges = [
        _edge("intra", 1, 2, [[121.00, 25.00], [121.02, 25.01]]),
        _edge("cross", 2, 3, [[121.02, 25.01], [130.00, 35.00]]),
    ]

    filtered = _filter_cross_cell_edges(edges, node_cells)

    assert node_cells[1] == node_cells[2]
    assert node_cells[2] != node_cells[3]
    assert len(filtered) == 1
    assert filtered[0]["edge_id"] == "cross"


def test_adaptive_portal_anchor_node_ids_keeps_portals_and_junctions_only() -> None:
    edges = [
        _edge("a", 1, 2, [[0.0, 0.0], [1.0, 0.0]]),
        _edge("b", 2, 3, [[1.0, 0.0], [2.0, 0.0]]),
        _edge("c", 2, 4, [[1.0, 0.0], [1.0, 1.0]]),
    ]
    anchors = _adaptive_portal_anchor_node_ids(edges, portal_node_ids={4})

    # 2 is a junction (deg=3), 4 is explicit portal.
    assert anchors == {2, 4}


def test_filter_mainline_edges_fixed_resolution_keeps_only_motorway_trunk_primary_secondary() -> None:
    edges = [
        _edge("m", 1, 2, [[0.0, 0.0], [1.0, 0.0]], road_class="motorway"),
        _edge("t", 2, 3, [[1.0, 0.0], [2.0, 0.0]], road_class="trunk"),
        _edge("p", 3, 4, [[2.0, 0.0], [3.0, 0.0]], road_class="primary"),
        _edge("s", 3, 4, [[2.0, 0.0], [3.0, 0.0]], road_class="secondary"),
        _edge("tt", 4, 5, [[3.0, 0.0], [4.0, 0.0]], road_class="tertiary"),
        _edge("u", 5, 6, [[4.0, 0.0], [5.0, 0.0]], road_class="unclassified"),
        _edge("r", 6, 7, [[5.0, 0.0], [6.0, 0.0]], road_class="residential"),
        _edge("ml", 3, 4, [[2.0, 0.0], [3.0, 0.0]], road_class="motorway_link"),
        _edge("tl", 4, 5, [[3.0, 0.0], [4.0, 0.0]], road_class="trunk_link"),
        _edge("sl", 5, 6, [[4.0, 0.0], [5.0, 0.0]], road_class="secondary_link"),
    ]

    coarse_filtered = _filter_mainline_edges_for_fixed_resolution(edges, resolution=5)
    fine_filtered = _filter_mainline_edges_for_fixed_resolution(edges, resolution=6)

    assert [edge["edge_id"] for edge in coarse_filtered] == ["m", "t", "p", "s"]
    assert [edge["edge_id"] for edge in fine_filtered] == ["m", "t", "p", "s"]


def test_filter_mainline_edges_adaptive_mask_uses_cell_resolution() -> None:
    cell_r2 = str(h3.latlng_to_cell(0.0, 0.0, 2))
    cell_r3 = str(h3.latlng_to_cell(20.0, 20.0, 3))
    cell_r4 = str(h3.latlng_to_cell(10.0, 60.0, 4))
    cell_r5 = str(h3.latlng_to_cell(40.0, -100.0, 5))
    cell_r6 = str(h3.latlng_to_cell(-20.0, 120.0, 6))
    cell_r7 = str(h3.latlng_to_cell(-35.0, 30.0, 7))
    cell_r8 = str(h3.latlng_to_cell(-10.0, -40.0, 8))
    cell_r9 = str(h3.latlng_to_cell(5.0, -20.0, 9))
    adaptive_mask_cells = {cell_r2, cell_r3, cell_r4, cell_r5, cell_r6, cell_r7, cell_r8, cell_r9}
    occupied_cells = {cell_r9}

    lat_r2, lon_r2 = h3.cell_to_latlng(cell_r2)
    lat_r3, lon_r3 = h3.cell_to_latlng(cell_r3)
    lat_r4, lon_r4 = h3.cell_to_latlng(cell_r4)
    lat_r5, lon_r5 = h3.cell_to_latlng(cell_r5)
    lat_r6, lon_r6 = h3.cell_to_latlng(cell_r6)
    lat_r7, lon_r7 = h3.cell_to_latlng(cell_r7)
    lat_r8, lon_r8 = h3.cell_to_latlng(cell_r8)
    lat_r9, lon_r9 = h3.cell_to_latlng(cell_r9)
    edges = [
        _edge("r2_motorway", 1, 2, [[lon_r2 - 0.01, lat_r2], [lon_r2 + 0.01, lat_r2]], road_class="motorway"),
        _edge("r2_trunk", 3, 4, [[lon_r2 - 0.01, lat_r2 + 0.01], [lon_r2 + 0.01, lat_r2 + 0.01]], road_class="trunk"),
        _edge("r2_motorway_link", 5, 6, [[lon_r2 - 0.01, lat_r2 + 0.02], [lon_r2 + 0.01, lat_r2 + 0.02]], road_class="motorway_link"),
        _edge("r3_trunk", 7, 8, [[lon_r3 - 0.005, lat_r3], [lon_r3 + 0.005, lat_r3]], road_class="trunk"),
        _edge("r3_primary", 9, 10, [[lon_r3 - 0.005, lat_r3 + 0.005], [lon_r3 + 0.005, lat_r3 + 0.005]], road_class="primary"),
        _edge("r3_trunk_link", 11, 12, [[lon_r3 - 0.005, lat_r3 + 0.01], [lon_r3 + 0.005, lat_r3 + 0.01]], road_class="trunk_link"),
        _edge("r4_trunk", 25, 26, [[lon_r4 - 0.003, lat_r4], [lon_r4 + 0.003, lat_r4]], road_class="trunk"),
        _edge("r4_primary", 27, 28, [[lon_r4 - 0.003, lat_r4 + 0.003], [lon_r4 + 0.003, lat_r4 + 0.003]], road_class="primary"),
        _edge("r5_primary", 13, 14, [[lon_r5 - 0.002, lat_r5], [lon_r5 + 0.002, lat_r5]], road_class="primary"),
        _edge("r5_secondary", 15, 16, [[lon_r5 - 0.002, lat_r5 + 0.002], [lon_r5 + 0.002, lat_r5 + 0.002]], road_class="secondary"),
        _edge("r6_primary", 17, 18, [[lon_r6 - 0.001, lat_r6], [lon_r6 + 0.001, lat_r6]], road_class="primary"),
        _edge("r6_secondary", 21, 22, [[lon_r6 - 0.001, lat_r6 + 0.002], [lon_r6 + 0.001, lat_r6 + 0.002]], road_class="secondary"),
        _edge("r7_primary", 29, 30, [[lon_r7 - 0.0005, lat_r7], [lon_r7 + 0.0005, lat_r7]], road_class="primary"),
        _edge("r7_secondary", 31, 32, [[lon_r7 - 0.0005, lat_r7 + 0.0005], [lon_r7 + 0.0005, lat_r7 + 0.0005]], road_class="secondary"),
        _edge("r8_primary", 33, 34, [[lon_r8 - 0.0003, lat_r8], [lon_r8 + 0.0003, lat_r8]], road_class="primary"),
        _edge("r8_secondary", 35, 36, [[lon_r8 - 0.0003, lat_r8 + 0.0003], [lon_r8 + 0.0003, lat_r8 + 0.0003]], road_class="secondary"),
        _edge("r9_secondary", 37, 38, [[lon_r9 - 0.0002, lat_r9], [lon_r9 + 0.0002, lat_r9]], road_class="secondary"),
        _edge("outside_motorway", 21, 22, [[0.0, 0.0], [0.01, 0.0]], road_class="motorway"),
        _edge("outside_trunk", 23, 24, [[0.0, 0.01], [0.01, 0.01]], road_class="trunk"),
    ]

    filtered = _filter_mainline_edges_for_adaptive_mask(edges, adaptive_mask_cells=adaptive_mask_cells, occupied_cells=occupied_cells)

    assert [edge["edge_id"] for edge in filtered] == [
        "r2_motorway",
        "r2_motorway_link",
        "r4_trunk",
        "r7_primary",
        "r8_primary",
        "r9_secondary",
        "outside_motorway",
    ]


def test_filter_mainline_edges_adaptive_mask_uncovered_uses_coarsest_neighbor_resolution() -> None:
    lat = 10.0
    lon = 10.0
    center_r3 = str(h3.latlng_to_cell(lat, lon, 3))
    center_r4 = str(h3.latlng_to_cell(lat, lon, 4))
    neighbor_r3 = sorted(str(cell) for cell in set(h3.grid_disk(center_r3, 1)) - {center_r3})[0]
    neighbor_r4 = sorted(str(cell) for cell in set(h3.grid_disk(center_r4, 1)) - {center_r4})[0]
    adaptive_mask_cells = {neighbor_r3, neighbor_r4}

    edges = [
        _edge("outside_motorway", 1, 2, [[lon - 0.01, lat], [lon + 0.01, lat]], road_class="motorway"),
        _edge("outside_trunk", 3, 4, [[lon - 0.01, lat + 0.01], [lon + 0.01, lat + 0.01]], road_class="trunk"),
        _edge("outside_primary", 5, 6, [[lon - 0.01, lat + 0.02], [lon + 0.01, lat + 0.02]], road_class="primary"),
    ]

    filtered = _filter_mainline_edges_for_adaptive_mask(edges, adaptive_mask_cells=adaptive_mask_cells, occupied_cells=set())

    assert [edge["edge_id"] for edge in filtered] == ["outside_motorway"]


def test_filter_mainline_edges_by_cell_priority_keeps_highest_class_per_cell() -> None:
    resolution = 5
    cell_a = str(h3.latlng_to_cell(37.70, -122.45, resolution))
    cell_b = sorted(set(h3.grid_disk(cell_a, 2)) - {cell_a})[0]
    cell_c = sorted(set(h3.grid_disk(cell_b, 2)) - {cell_a, cell_b})[0]

    lat_a, lon_a = h3.cell_to_latlng(cell_a)
    lat_b, lon_b = h3.cell_to_latlng(cell_b)
    lat_c, lon_c = h3.cell_to_latlng(cell_c)
    edges = [
        _edge("a_trunk", 1, 2, [[lon_a - 0.005, lat_a], [lon_a + 0.005, lat_a]], road_class="trunk"),
        _edge("a_motorway", 3, 4, [[lon_a - 0.005, lat_a + 0.002], [lon_a + 0.005, lat_a + 0.002]], road_class="motorway"),
        _edge("b_primary", 5, 6, [[lon_b - 0.005, lat_b], [lon_b + 0.005, lat_b]], road_class="primary"),
        _edge("b_trunk", 7, 8, [[lon_b - 0.005, lat_b + 0.002], [lon_b + 0.005, lat_b + 0.002]], road_class="trunk"),
        _edge("c_secondary", 9, 10, [[lon_c - 0.005, lat_c], [lon_c + 0.005, lat_c]], road_class="secondary"),
    ]

    filtered = _filter_mainline_edges_by_cell_priority(edges, resolution=resolution)

    assert [edge["edge_id"] for edge in filtered] == ["a_motorway", "b_trunk", "c_secondary"]


def test_filter_mainline_edges_by_cell_priority_escalates_bridge_cells_for_connectivity() -> None:
    resolution = 5
    cell_a = str(h3.latlng_to_cell(37.70, -122.45, resolution))
    cell_b = sorted(set(h3.grid_disk(cell_a, 1)) - {cell_a})[0]
    cell_c = sorted(set(h3.grid_disk(cell_b, 1)) - {cell_a, cell_b})[0]

    lat_a, lon_a = h3.cell_to_latlng(cell_a)
    lat_b, lon_b = h3.cell_to_latlng(cell_b)
    lat_c, lon_c = h3.cell_to_latlng(cell_c)
    edges = [
        _edge("ab_motorway", 1, 2, [[lon_a, lat_a], [lon_b, lat_b]], road_class="motorway"),
        _edge("b_motorway_local", 3, 4, [[lon_b - 0.001, lat_b], [lon_b + 0.001, lat_b]], road_class="motorway"),
        _edge("c_motorway_local", 5, 6, [[lon_c - 0.001, lat_c], [lon_c + 0.001, lat_c]], road_class="motorway"),
        _edge("bc_trunk_bridge", 7, 8, [[lon_b, lat_b], [lon_c, lat_c]], road_class="trunk"),
    ]

    filtered = _filter_mainline_edges_by_cell_priority(edges, resolution=resolution)
    filtered_ids = [str(edge["edge_id"]) for edge in filtered]

    assert "ab_motorway" in filtered_ids
    assert "bc_trunk_bridge" in filtered_ids


def test_filter_mainline_edges_by_cell_priority_allows_link_classes() -> None:
    resolution = 5
    cell = str(h3.latlng_to_cell(37.70, -122.45, resolution))
    lat, lon = h3.cell_to_latlng(cell)
    edges = [
        _edge("pl", 1, 2, [[lon - 0.002, lat], [lon + 0.002, lat]], road_class="primary_link"),
    ]

    filtered = _filter_mainline_edges_by_cell_priority(edges, resolution=resolution)

    assert [edge["edge_id"] for edge in filtered] == ["pl"]


def test_filter_adaptive_portal_edges_post_contract_keeps_link_classes() -> None:
    edges = [
        _edge("m", 1, 2, [[0.0, 0.0], [1.0, 0.0]], road_class="motorway"),
        _edge("ml", 2, 3, [[1.0, 0.0], [2.0, 0.0]], road_class="motorway_link"),
        _edge("tl", 3, 4, [[2.0, 0.0], [3.0, 0.0]], road_class="trunk_link"),
        _edge("pl", 4, 5, [[3.0, 0.0], [4.0, 0.0]], road_class="primary_link"),
        _edge("sl", 5, 6, [[4.0, 0.0], [5.0, 0.0]], road_class="secondary_link"),
        _edge("tt", 6, 7, [[5.0, 0.0], [6.0, 0.0]], road_class="tertiary"),
    ]

    filtered = _filter_adaptive_portal_edges_post_contract(edges)

    assert [edge["edge_id"] for edge in filtered] == ["m", "ml", "tl", "pl", "sl"]


def test_connected_node_ids_contains_only_edge_endpoints() -> None:
    edges = [
        _edge("a", 1, 2, [[0.0, 0.0], [1.0, 0.0]]),
        _edge("b", 2, 3, [[1.0, 0.0], [2.0, 0.0]]),
    ]

    assert _connected_node_ids(edges) == {1, 2, 3}


def test_cell_metric_proxy_edges_collapses_boundary_chain() -> None:
    edges = [
        _edge("a", 1, 2, [[121.0, 25.0], [121.01, 25.0]], road_class="primary"),
        _edge("b", 2, 3, [[121.01, 25.0], [121.02, 25.0]], road_class="primary"),
    ]
    proxy = _cell_metric_proxy_edges(edges, terminal_nodes={1, 3})

    assert len(proxy) == 1
    assert {int(proxy[0]["u"]), int(proxy[0]["v"])} == {1, 3}
    assert proxy[0]["geometry"]["coordinates"] == [[121.0, 25.0], [121.01, 25.0], [121.02, 25.0]]


def test_cell_metric_proxy_edges_prefers_larger_roads_with_bias() -> None:
    edges = [
        _edge("secondary_direct", 1, 2, [[121.0000, 25.0000], [121.0100, 25.0000]], road_class="secondary"),
        _edge("motorway_leg_1", 1, 4, [[121.0000, 25.0000], [121.0050, 25.0010]], road_class="motorway"),
        _edge("motorway_leg_2", 4, 2, [[121.0050, 25.0010], [121.0100, 25.0000]], road_class="motorway"),
    ]
    proxy = _cell_metric_proxy_edges(edges, terminal_nodes={1, 2})

    assert len(proxy) == 1
    assert proxy[0]["road_class"] == "motorway"
    assert [tuple(coord) for coord in proxy[0]["geometry"]["coordinates"]] == [
        (121.0000, 25.0000),
        (121.0050, 25.0010),
        (121.0100, 25.0000),
    ]


def test_cell_metric_proxy_tree_edges_keeps_minimum_terminal_backbone() -> None:
    edges = [
        _edge("a", 1, 2, [[121.0000, 25.0000], [121.0100, 25.0000]], road_class="primary"),
        _edge("b", 2, 3, [[121.0100, 25.0000], [121.0200, 25.0000]], road_class="primary"),
    ]

    proxy = _cell_metric_proxy_tree_edges(edges, terminal_nodes={1, 2, 3})

    assert len(proxy) == 2
    assert sorted((int(edge["u"]), int(edge["v"])) for edge in proxy) == [(1, 2), (2, 3)]
    assert all({int(edge["u"]), int(edge["v"])} != {1, 3} for edge in proxy)


def test_cell_metric_proxy_tree_edges_prefers_lower_total_cost_tree() -> None:
    edges = [
        _edge("motorway_12", 1, 4, [[121.0000, 25.0000], [121.0030, 25.0000]], road_class="motorway"),
        _edge("motorway_12b", 4, 2, [[121.0030, 25.0000], [121.0060, 25.0000]], road_class="motorway"),
        _edge("motorway_23", 2, 5, [[121.0060, 25.0000], [121.0090, 25.0000]], road_class="motorway"),
        _edge("motorway_23b", 5, 3, [[121.0090, 25.0000], [121.0120, 25.0000]], road_class="motorway"),
        _edge("secondary_13", 1, 3, [[121.0000, 25.0000], [121.0120, 25.0000]], road_class="secondary"),
    ]

    proxy = _cell_metric_proxy_tree_edges(edges, terminal_nodes={1, 2, 3})

    assert len(proxy) == 2
    assert sorted((int(edge["u"]), int(edge["v"])) for edge in proxy) == [(1, 2), (2, 3)]


def test_cell_metric_feeder_proxy_edges_keeps_large_road_backbone_and_feeds_smaller_portals() -> None:
    edges = [
        _edge("motorway_12", 1, 4, [[121.0000, 25.0000], [121.0050, 25.0000]], road_class="motorway"),
        _edge("motorway_12b", 4, 2, [[121.0050, 25.0000], [121.0100, 25.0000]], road_class="motorway"),
        _edge("secondary_23", 2, 5, [[121.0100, 25.0000], [121.0120, 24.9985]], road_class="secondary"),
        _edge("secondary_23b", 5, 3, [[121.0120, 24.9985], [121.0140, 24.9970]], road_class="secondary"),
    ]

    proxy = _cell_metric_feeder_proxy_edges(edges, terminal_nodes={1, 2, 3})

    assert len(proxy) == 2
    assert sorted((int(edge["u"]), int(edge["v"])) for edge in proxy) == [(1, 2), (2, 3)]
    motorway_edge = next(edge for edge in proxy if {int(edge["u"]), int(edge["v"])} == {1, 2})
    feeder_edge = next(edge for edge in proxy if {int(edge["u"]), int(edge["v"])} == {2, 3})
    assert motorway_edge["road_class"] == "motorway"
    assert feeder_edge["road_class"] == "secondary"


def test_split_edges_with_adaptive_mask_portals_and_contract_keeps_mask_membership() -> None:
    coarse_cell = str(h3.latlng_to_cell(37.70, -122.45, 4))
    coarse_neighbor = sorted(set(h3.grid_disk(coarse_cell, 1)) - {coarse_cell})[0]
    fine_cell = sorted(h3.cell_to_children(coarse_neighbor, 5))[0]
    adaptive_mask_cells = {coarse_cell, fine_cell}

    coarse_lat, coarse_lon = h3.cell_to_latlng(coarse_cell)
    fine_lat, fine_lon = h3.cell_to_latlng(fine_cell)
    nodes = {
        1: (coarse_lon, coarse_lat),
        2: (fine_lon, fine_lat),
    }
    edges = [
        _edge("mask_cross", 1, 2, [[coarse_lon, coarse_lat], [fine_lon, fine_lat]]),
    ]

    split_edges, split_nodes, portal_nodes = split_edges_with_adaptive_mask_portals(edges, nodes, adaptive_mask_cells)

    assert len(portal_nodes) >= 1
    assert len(split_edges) >= 2
    assert all(int(edge["u"]) in split_nodes for edge in split_edges)
    assert all(int(edge["v"]) in split_nodes for edge in split_edges)

    contracted = contract_edges_within_adaptive_mask_preserving_portals(
        split_edges=split_edges,
        portal_node_ids=portal_nodes,
        adaptive_mask_cells=adaptive_mask_cells,
    )
    assert contracted

    mask_lookup = _adaptive_mask_cells_by_resolution(adaptive_mask_cells)
    covered_edges = 0
    for edge in contracted:
        coords = edge["geometry"]["coordinates"]
        mid_lon = (float(coords[0][0]) + float(coords[-1][0])) / 2.0
        mid_lat = (float(coords[0][1]) + float(coords[-1][1])) / 2.0
        if _adaptive_mask_cell_for_point([mid_lon, mid_lat], mask_lookup) is not None:
            covered_edges += 1
    assert covered_edges >= 1


def test_contract_edges_within_adaptive_mask_preserving_portals_keeps_uncovered_segments() -> None:
    adaptive_mask_cells = {str(h3.latlng_to_cell(37.70, -122.45, 4))}
    edges = [
        _edge("inside", 1, 2, [[-122.45, 37.70], [-122.44, 37.70]], road_class="motorway"),
        _edge("outside", 3, 4, [[0.0, 0.0], [0.01, 0.0]], road_class="motorway"),
    ]

    contracted = contract_edges_within_adaptive_mask_preserving_portals(
        split_edges=edges,
        portal_node_ids=set(),
        adaptive_mask_cells=adaptive_mask_cells,
    )

    assert sorted(str(edge["edge_id"]) for edge in contracted) == ["inside", "outside"]


def test_contract_edges_within_adaptive_mask_preserving_portals_uses_boundary_proxy_for_multi_portal_cell() -> None:
    adaptive_cell = str(h3.latlng_to_cell(25.0, 121.0, 5))
    edges = [
        _edge("a", 1, 2, [[121.0000, 25.0000], [121.0100, 25.0000]], road_class="secondary"),
        _edge("b", 2, 4, [[121.0100, 25.0000], [121.0200, 25.0000]], road_class="secondary"),
        _edge("branch", 2, 3, [[121.0100, 25.0000], [121.0100, 25.0100]], road_class="secondary"),
    ]

    contracted = contract_edges_within_adaptive_mask_preserving_portals(
        split_edges=edges,
        portal_node_ids={1, 4},
        adaptive_mask_cells={adaptive_cell},
    )

    assert len(contracted) == 1
    assert {int(contracted[0]["u"]), int(contracted[0]["v"])} == {1, 4}


def test_contract_edges_within_adaptive_mask_preserving_portals_uses_tree_for_three_portals() -> None:
    adaptive_cell = str(h3.latlng_to_cell(25.0, 121.0, 5))
    edges = [
        _edge("a", 1, 2, [[121.0000, 25.0000], [121.0100, 25.0000]], road_class="primary"),
        _edge("b", 2, 3, [[121.0100, 25.0000], [121.0200, 25.0000]], road_class="primary"),
    ]

    contracted = contract_edges_within_adaptive_mask_preserving_portals(
        split_edges=edges,
        portal_node_ids={1, 2, 3},
        adaptive_mask_cells={adaptive_cell},
    )

    assert len(contracted) == 2
    assert sorted((int(edge["u"]), int(edge["v"])) for edge in contracted) == [(1, 2), (2, 3)]


def test_contract_edges_within_adaptive_mask_preserving_portals_prefers_large_backbone_then_feeders() -> None:
    adaptive_cell = str(h3.latlng_to_cell(25.0, 121.0, 5))
    edges = [
        _edge("motorway_12", 1, 4, [[121.0000, 25.0000], [121.0050, 25.0000]], road_class="motorway"),
        _edge("motorway_12b", 4, 2, [[121.0050, 25.0000], [121.0100, 25.0000]], road_class="motorway"),
        _edge("secondary_23", 2, 5, [[121.0100, 25.0000], [121.0120, 24.9985]], road_class="secondary"),
        _edge("secondary_23b", 5, 3, [[121.0120, 24.9985], [121.0140, 24.9970]], road_class="secondary"),
    ]

    contracted = contract_edges_within_adaptive_mask_preserving_portals(
        split_edges=edges,
        portal_node_ids={1, 2, 3},
        adaptive_mask_cells={adaptive_cell},
    )

    assert len(contracted) == 2
    assert sorted((int(edge["u"]), int(edge["v"])) for edge in contracted) == [(1, 2), (2, 3)]
    assert next(edge for edge in contracted if {int(edge["u"]), int(edge["v"])} == {1, 2})["road_class"] == "motorway"


def test_adaptive_mask_portal_split_and_contract_is_deterministic() -> None:
    coarse_cell = str(h3.latlng_to_cell(37.70, -122.45, 4))
    coarse_neighbor = sorted(set(h3.grid_disk(coarse_cell, 1)) - {coarse_cell})[0]
    fine_cell = sorted(h3.cell_to_children(coarse_neighbor, 5))[0]
    adaptive_mask_cells = {coarse_cell, fine_cell}

    coarse_lat, coarse_lon = h3.cell_to_latlng(coarse_cell)
    fine_lat, fine_lon = h3.cell_to_latlng(fine_cell)
    mid_lon = (coarse_lon + fine_lon) / 2.0
    mid_lat = (coarse_lat + fine_lat) / 2.0
    nodes = {
        1: (coarse_lon, coarse_lat),
        2: (mid_lon, mid_lat),
        3: (fine_lon, fine_lat),
    }
    ordered_edges = [
        _edge("a", 1, 2, [[coarse_lon, coarse_lat], [mid_lon, mid_lat]]),
        _edge("b", 2, 3, [[mid_lon, mid_lat], [fine_lon, fine_lat]]),
    ]
    reversed_edges = list(reversed(ordered_edges))

    first_split_edges, first_split_nodes, first_portals = split_edges_with_adaptive_mask_portals(
        ordered_edges,
        nodes,
        adaptive_mask_cells,
    )
    second_split_edges, second_split_nodes, second_portals = split_edges_with_adaptive_mask_portals(
        reversed_edges,
        nodes,
        adaptive_mask_cells,
    )

    assert [edge["edge_id"] for edge in first_split_edges] == [edge["edge_id"] for edge in second_split_edges]
    assert first_portals == second_portals
    assert first_split_nodes == second_split_nodes

    first_contracted = contract_edges_within_adaptive_mask_preserving_portals(
        split_edges=first_split_edges,
        portal_node_ids=first_portals,
        adaptive_mask_cells=adaptive_mask_cells,
    )
    second_contracted = contract_edges_within_adaptive_mask_preserving_portals(
        split_edges=second_split_edges,
        portal_node_ids=second_portals,
        adaptive_mask_cells=adaptive_mask_cells,
    )

    assert [edge["edge_id"] for edge in first_contracted] == [edge["edge_id"] for edge in second_contracted]
    assert [(int(edge["u"]), int(edge["v"])) for edge in first_contracted] == [
        (int(edge["u"]), int(edge["v"])) for edge in second_contracted
    ]
