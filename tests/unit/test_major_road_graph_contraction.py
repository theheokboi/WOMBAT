from __future__ import annotations

from inframap.ingest.major_road_graph import (
    _node_cells_at_resolution,
    _protected_nodes_from_cross_cell_edges,
    contract_degree2_undirected_edges,
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
