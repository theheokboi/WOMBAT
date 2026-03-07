from __future__ import annotations

import h3

from inframap.ingest.major_road_graph import (
    _adaptive_portal_anchor_node_ids,
    _adaptive_mask_cell_for_point,
    _adaptive_mask_cells_by_resolution,
    _build_portal_node_id,
    _filter_cross_cell_edges,
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


def test_filter_mainline_edges_fixed_resolution_applies_coarse_and_fine_class_sets() -> None:
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

    assert [edge["edge_id"] for edge in coarse_filtered] == ["m", "t"]
    assert [edge["edge_id"] for edge in fine_filtered] == ["m", "t", "p", "s", "tt", "u", "r"]


def test_filter_mainline_edges_adaptive_mask_uses_cell_resolution() -> None:
    coarse_cell = str(h3.latlng_to_cell(37.70, -122.45, 5))
    coarse_neighbor = sorted(set(h3.grid_disk(coarse_cell, 2)) - {coarse_cell})[0]
    fine_cell = sorted(h3.cell_to_children(coarse_neighbor, 6))[0]
    fine_neighbor = sorted(set(h3.grid_disk(fine_cell, 1)) - {fine_cell})[0]
    adaptive_mask_cells = {coarse_cell, fine_cell, fine_neighbor}
    occupied_cells = {fine_cell}

    coarse_lat, coarse_lon = h3.cell_to_latlng(coarse_cell)
    fine_lat, fine_lon = h3.cell_to_latlng(fine_cell)
    fine_neighbor_lat, fine_neighbor_lon = h3.cell_to_latlng(fine_neighbor)
    edges = [
        _edge("coarse_secondary", 1, 2, [[coarse_lon - 0.01, coarse_lat], [coarse_lon + 0.01, coarse_lat]], road_class="secondary"),
        _edge("coarse_trunk", 3, 4, [[coarse_lon - 0.01, coarse_lat + 0.01], [coarse_lon + 0.01, coarse_lat + 0.01]], road_class="trunk"),
        _edge("fine_secondary", 5, 6, [[fine_lon - 0.001, fine_lat], [fine_lon + 0.001, fine_lat]], road_class="secondary"),
        _edge("fine_tertiary", 7, 8, [[fine_lon - 0.001, fine_lat + 0.001], [fine_lon + 0.001, fine_lat + 0.001]], road_class="tertiary"),
        _edge("fine_unclassified", 11, 12, [[fine_lon - 0.001, fine_lat + 0.002], [fine_lon + 0.001, fine_lat + 0.002]], road_class="unclassified"),
        _edge("fine_residential", 13, 14, [[fine_lon - 0.001, fine_lat + 0.003], [fine_lon + 0.001, fine_lat + 0.003]], road_class="residential"),
        _edge(
            "fine_unoccupied_secondary",
            9,
            10,
            [[fine_neighbor_lon - 0.001, fine_neighbor_lat], [fine_neighbor_lon + 0.001, fine_neighbor_lat]],
            road_class="secondary",
        ),
    ]

    filtered = _filter_mainline_edges_for_adaptive_mask(
        edges,
        adaptive_mask_cells=adaptive_mask_cells,
        occupied_cells=occupied_cells,
    )

    assert [edge["edge_id"] for edge in filtered] == [
        "coarse_trunk",
        "fine_secondary",
        "fine_tertiary",
        "fine_unclassified",
        "fine_residential",
    ]


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
    for edge in contracted:
        coords = edge["geometry"]["coordinates"]
        mid_lon = (float(coords[0][0]) + float(coords[-1][0])) / 2.0
        mid_lat = (float(coords[0][1]) + float(coords[-1][1])) / 2.0
        assert _adaptive_mask_cell_for_point([mid_lon, mid_lat], mask_lookup) is not None


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
