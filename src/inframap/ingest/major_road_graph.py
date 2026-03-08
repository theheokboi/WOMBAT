from __future__ import annotations

import json
import math
import heapq
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Literal

import h3
import osmium


MAINLINE_ALLOWED_CLASSES = frozenset({"motorway", "trunk", "primary", "secondary"})
MAINLINE_CLASS_PRIORITY: tuple[str, ...] = ("motorway", "trunk", "primary", "secondary")
MAINLINE_CLASS_PRIORITY_RANK = {road_class: index for index, road_class in enumerate(MAINLINE_CLASS_PRIORITY)}
ADAPTIVE_PORTAL_ALLOWED_CLASSES = frozenset(
    {
        "motorway",
        "motorway_link",
        "trunk",
        "trunk_link",
        "primary",
        "primary_link",
        "secondary",
        "secondary_link",
    }
)
ADAPTIVE_PORTAL_CLASS_PRIORITY: tuple[str, ...] = (
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
)
ADAPTIVE_PORTAL_CLASS_PRIORITY_RANK = {
    road_class: index for index, road_class in enumerate(ADAPTIVE_PORTAL_CLASS_PRIORITY)
}
MAJOR_HIGHWAY_CLASSES = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
}
RAW_EDGE_FILENAME = "major_roads_edges.geojson"
RAW_NODE_FILENAME = "major_roads_nodes.geojson"
COLLAPSED_EDGE_FILENAME = "major_roads_edges_collapsed.geojson"
COLLAPSED_NODE_FILENAME = "major_roads_nodes_collapsed.geojson"
ADAPTIVE_EDGE_FILENAME = "major_roads_edges_adaptive.geojson"
ADAPTIVE_NODE_FILENAME = "major_roads_nodes_adaptive.geojson"
ADAPTIVE_PORTAL_EDGE_FILENAME = "major_roads_edges_adaptive_portal.geojson"
ADAPTIVE_PORTAL_NODE_FILENAME = "major_roads_nodes_adaptive_portal.geojson"
ADAPTIVE_PORTAL_RUN_EDGE_FILENAME = "major_roads_edges_adaptive_portal_run.geojson"
ADAPTIVE_PORTAL_RUN_NODE_FILENAME = "major_roads_nodes_adaptive_portal_run.geojson"
GraphVariant = Literal["raw", "collapsed", "adaptive", "adaptive_portal", "adaptive_portal_run"]
ProgressCallback = Callable[[str, str, dict[str, Any]], None]


def _way_road_class(way: osmium.osm.Way) -> str | None:
    value = str(way.tags.get("highway", "")).strip().lower()
    if value in MAJOR_HIGHWAY_CLASSES:
        return value
    return None


def _build_edge_id(way_id: int, segment_index: int, u: int, v: int, road_class: str, coordinates: list[list[float]]) -> str:
    coords_key = ";".join(f"{lon:.7f},{lat:.7f}" for lon, lat in coordinates)
    raw = f"{way_id}|{segment_index}|{u}|{v}|{road_class}|{coords_key}"
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def _build_contracted_edge_id(
    component_edge_ids: list[str],
    u: int,
    v: int,
    road_class: str,
    oneway: str | None,
    name: str | None,
    ref: str | None,
    coordinates: list[list[float]],
) -> str:
    components_key = ",".join(sorted(component_edge_ids))
    coords_key = ";".join(f"{lon:.7f},{lat:.7f}" for lon, lat in coordinates)
    raw = f"{components_key}|{u}|{v}|{road_class}|{oneway}|{name}|{ref}|{coords_key}"
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def _edge_merge_key(edge: dict[str, object]) -> tuple[str, str | None, str | None, str | None]:
    return (
        str(edge.get("road_class", "")),
        edge.get("oneway") if isinstance(edge.get("oneway"), str) or edge.get("oneway") is None else None,
        edge.get("name") if isinstance(edge.get("name"), str) or edge.get("name") is None else None,
        edge.get("ref") if isinstance(edge.get("ref"), str) or edge.get("ref") is None else None,
    )


def _reverse_coordinates(coordinates: list[list[float]]) -> list[list[float]]:
    return [list(coord) for coord in reversed(coordinates)]


def _edge_coordinates(edge: dict[str, object]) -> list[list[float]]:
    geometry = edge.get("geometry")
    if not isinstance(geometry, dict):
        return []
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list):
        return []
    normalized: list[list[float]] = []
    for coord in coordinates:
        if not (isinstance(coord, list) and len(coord) >= 2):
            continue
        normalized.append([float(coord[0]), float(coord[1])])
    return normalized


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return r * c


def _edge_length_m(edge: dict[str, object]) -> float:
    coords = _edge_coordinates(edge)
    if len(coords) < 2:
        return 0.0
    total = 0.0
    for start, end in zip(coords, coords[1:]):
        total += _haversine_m(float(start[0]), float(start[1]), float(end[0]), float(end[1]))
    return total


def _road_class_penalty(road_class: str) -> float:
    normalized = str(road_class).strip().lower()
    if normalized in {"motorway", "motorway_link"}:
        return 1.0
    if normalized in {"trunk", "trunk_link"}:
        return 1.1
    if normalized in {"primary", "primary_link"}:
        return 1.25
    if normalized in {"secondary", "secondary_link"}:
        return 1.5
    return 2.0


def _road_class_tier_rank(road_class: str) -> int:
    normalized = str(road_class).strip().lower()
    if normalized in {"motorway", "motorway_link"}:
        return 0
    if normalized in {"trunk", "trunk_link"}:
        return 1
    if normalized in {"primary", "primary_link"}:
        return 2
    if normalized in {"secondary", "secondary_link"}:
        return 3
    return 4


def _oriented_coords_for_edge(edge: dict[str, object], from_node: int, to_node: int) -> list[list[float]]:
    coords = _edge_coordinates(edge)
    if len(coords) < 2:
        return []
    if int(edge["u"]) == from_node and int(edge["v"]) == to_node:
        return coords
    if int(edge["u"]) == to_node and int(edge["v"]) == from_node:
        return _reverse_coordinates(coords)
    return []


def _cell_metric_proxy_edges(
    edges: list[dict[str, object]],
    terminal_nodes: set[int],
) -> list[dict[str, object]]:
    terminals = sorted({int(node_id) for node_id in terminal_nodes})
    if len(terminals) < 2:
        return []

    adjacency: dict[int, list[tuple[int, dict[str, object], float]]] = defaultdict(list)
    for edge in edges:
        u = int(edge["u"])
        v = int(edge["v"])
        if u == v:
            continue
        length_m = _edge_length_m(edge)
        if length_m <= 0:
            continue
        cost = length_m * _road_class_penalty(str(edge.get("road_class", "")))
        adjacency[u].append((v, edge, cost))
        adjacency[v].append((u, edge, cost))

    proxy_edges: list[dict[str, object]] = []
    for source_idx, source in enumerate(terminals):
        distances: dict[int, float] = {source: 0.0}
        previous: dict[int, tuple[int, dict[str, object]]] = {}
        heap: list[tuple[float, int]] = [(0.0, source)]

        while heap:
            current_dist, node = heapq.heappop(heap)
            if current_dist > distances.get(node, float("inf")):
                continue
            for neighbor, edge, step_cost in adjacency.get(node, []):
                next_dist = current_dist + step_cost
                if next_dist >= distances.get(neighbor, float("inf")):
                    continue
                distances[neighbor] = next_dist
                previous[neighbor] = (node, edge)
                heapq.heappush(heap, (next_dist, neighbor))

        for target in terminals[source_idx + 1 :]:
            if target not in previous:
                continue
            path_edges: list[dict[str, object]] = []
            path_coords_rev: list[list[list[float]]] = []
            path_road_classes: list[str] = []
            cursor = target
            while cursor != source:
                step = previous.get(cursor)
                if step is None:
                    path_edges = []
                    path_coords_rev = []
                    break
                parent, edge = step
                oriented = _oriented_coords_for_edge(edge, parent, cursor)
                if len(oriented) < 2:
                    path_edges = []
                    path_coords_rev = []
                    break
                path_edges.append(edge)
                path_coords_rev.append(oriented)
                path_road_classes.append(str(edge.get("road_class", "")))
                cursor = parent
            if not path_edges or not path_coords_rev:
                continue

            path_coords = list(path_coords_rev[-1])
            for segment in reversed(path_coords_rev[:-1]):
                path_coords.extend(segment[1:])
            component_edge_ids = sorted({str(edge.get("edge_id", "")) for edge in path_edges if edge.get("edge_id")})
            if not component_edge_ids:
                continue
            path_class = min(
                path_road_classes,
                key=lambda value: (_road_class_penalty(value), str(value).strip().lower()),
            )

            proxy_u = source
            proxy_v = target
            proxy_coords = path_coords
            if proxy_u > proxy_v:
                proxy_u, proxy_v = proxy_v, proxy_u
                proxy_coords = _reverse_coordinates(proxy_coords)
            proxy_edges.append(
                {
                    "edge_id": _build_contracted_edge_id(
                        component_edge_ids=component_edge_ids,
                        u=proxy_u,
                        v=proxy_v,
                        road_class=path_class,
                        oneway=None,
                        name=None,
                        ref=None,
                        coordinates=proxy_coords,
                    ),
                    "u": proxy_u,
                    "v": proxy_v,
                    "road_class": path_class,
                    "oneway": None,
                    "name": None,
                    "ref": None,
                    "geometry": {"type": "LineString", "coordinates": proxy_coords},
                }
            )

    deduped: dict[tuple[int, int], dict[str, object]] = {}
    for edge in sorted(proxy_edges, key=lambda item: str(item.get("edge_id", ""))):
        key = (int(edge["u"]), int(edge["v"]))
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = edge
            continue
        if _edge_length_m(edge) < _edge_length_m(existing):
            deduped[key] = edge
    return sorted(deduped.values(), key=lambda item: str(item["edge_id"]))


def _cell_metric_proxy_tree_edges(
    edges: list[dict[str, object]],
    terminal_nodes: set[int],
) -> list[dict[str, object]]:
    terminals = sorted({int(node_id) for node_id in terminal_nodes})
    if len(terminals) < 2:
        return []

    adjacency: dict[int, list[tuple[int, dict[str, object], float]]] = defaultdict(list)
    for edge in edges:
        u = int(edge["u"])
        v = int(edge["v"])
        if u == v:
            continue
        length_m = _edge_length_m(edge)
        if length_m <= 0:
            continue
        cost = length_m * _road_class_penalty(str(edge.get("road_class", "")))
        adjacency[u].append((v, edge, cost))
        adjacency[v].append((u, edge, cost))

    path_lookup: dict[tuple[int, int], tuple[float, dict[int, tuple[int, dict[str, object]]]]] = {}
    pair_candidates: list[tuple[float, int, int]] = []
    for source_idx, source in enumerate(terminals):
        distances: dict[int, float] = {source: 0.0}
        previous: dict[int, tuple[int, dict[str, object]]] = {}
        heap: list[tuple[float, int]] = [(0.0, source)]

        while heap:
            current_dist, node = heapq.heappop(heap)
            if current_dist > distances.get(node, float("inf")):
                continue
            for neighbor, edge, step_cost in adjacency.get(node, []):
                next_dist = current_dist + step_cost
                if next_dist >= distances.get(neighbor, float("inf")):
                    continue
                distances[neighbor] = next_dist
                previous[neighbor] = (node, edge)
                heapq.heappush(heap, (next_dist, neighbor))

        for target in terminals[source_idx + 1 :]:
            distance = distances.get(target)
            if distance is None:
                continue
            key = (source, target)
            path_lookup[key] = (distance, previous)
            pair_candidates.append((distance, source, target))

    if not pair_candidates:
        return []

    parent = {terminal: terminal for terminal in terminals}

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> bool:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return False
        if left_root < right_root:
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root
        return True

    mst_pairs: list[tuple[int, int]] = []
    for _distance, source, target in sorted(pair_candidates, key=lambda item: (item[0], item[1], item[2])):
        if not union(source, target):
            continue
        mst_pairs.append((source, target))
        if len(mst_pairs) == len(terminals) - 1:
            break

    proxy_edges: list[dict[str, object]] = []
    for source, target in mst_pairs:
        lookup = path_lookup.get((source, target))
        if lookup is None:
            continue
        _distance, previous = lookup
        path_edges: list[dict[str, object]] = []
        path_coords_rev: list[list[list[float]]] = []
        path_road_classes: list[str] = []
        cursor = target
        while cursor != source:
            step = previous.get(cursor)
            if step is None:
                path_edges = []
                path_coords_rev = []
                break
            parent_node, edge = step
            oriented = _oriented_coords_for_edge(edge, parent_node, cursor)
            if len(oriented) < 2:
                path_edges = []
                path_coords_rev = []
                break
            path_edges.append(edge)
            path_coords_rev.append(oriented)
            path_road_classes.append(str(edge.get("road_class", "")))
            cursor = parent_node
        if not path_edges or not path_coords_rev:
            continue

        path_coords = list(path_coords_rev[-1])
        for segment in reversed(path_coords_rev[:-1]):
            path_coords.extend(segment[1:])
        component_edge_ids = sorted({str(edge.get("edge_id", "")) for edge in path_edges if edge.get("edge_id")})
        if not component_edge_ids:
            continue
        path_class = min(
            path_road_classes,
            key=lambda value: (_road_class_penalty(value), str(value).strip().lower()),
        )

        proxy_u = source
        proxy_v = target
        proxy_coords = path_coords
        if proxy_u > proxy_v:
            proxy_u, proxy_v = proxy_v, proxy_u
            proxy_coords = _reverse_coordinates(proxy_coords)
        proxy_edges.append(
            {
                "edge_id": _build_contracted_edge_id(
                    component_edge_ids=component_edge_ids,
                    u=proxy_u,
                    v=proxy_v,
                    road_class=path_class,
                    oneway=None,
                    name=None,
                    ref=None,
                    coordinates=proxy_coords,
                ),
                "u": proxy_u,
                "v": proxy_v,
                "road_class": path_class,
                "oneway": None,
                "name": None,
                "ref": None,
                "geometry": {"type": "LineString", "coordinates": proxy_coords},
            }
        )

    return sorted(proxy_edges, key=lambda item: str(item["edge_id"]))


def _build_proxy_edge_from_previous(
    source: int,
    target: int,
    previous: dict[int, tuple[int, dict[str, object]]],
) -> dict[str, object] | None:
    path_edges: list[dict[str, object]] = []
    path_coords_rev: list[list[list[float]]] = []
    path_road_classes: list[str] = []
    cursor = target
    while cursor != source:
        step = previous.get(cursor)
        if step is None:
            return None
        parent_node, edge = step
        oriented = _oriented_coords_for_edge(edge, parent_node, cursor)
        if len(oriented) < 2:
            return None
        path_edges.append(edge)
        path_coords_rev.append(oriented)
        path_road_classes.append(str(edge.get("road_class", "")))
        cursor = parent_node

    if not path_edges or not path_coords_rev:
        return None

    path_coords = list(path_coords_rev[-1])
    for segment in reversed(path_coords_rev[:-1]):
        path_coords.extend(segment[1:])
    component_edge_ids = sorted({str(edge.get("edge_id", "")) for edge in path_edges if edge.get("edge_id")})
    if not component_edge_ids:
        return None
    path_class = min(
        path_road_classes,
        key=lambda value: (_road_class_penalty(value), str(value).strip().lower()),
    )

    proxy_u = source
    proxy_v = target
    proxy_coords = path_coords
    if proxy_u > proxy_v:
        proxy_u, proxy_v = proxy_v, proxy_u
        proxy_coords = _reverse_coordinates(proxy_coords)
    return {
        "edge_id": _build_contracted_edge_id(
            component_edge_ids=component_edge_ids,
            u=proxy_u,
            v=proxy_v,
            road_class=path_class,
            oneway=None,
            name=None,
            ref=None,
            coordinates=proxy_coords,
        ),
        "u": proxy_u,
        "v": proxy_v,
        "road_class": path_class,
        "oneway": None,
        "name": None,
        "ref": None,
        "geometry": {"type": "LineString", "coordinates": proxy_coords},
    }


def _nearest_target_proxy_edge(
    edges: list[dict[str, object]],
    source: int,
    targets: set[int],
    max_tier_rank: int,
) -> dict[str, object] | None:
    if not targets or source in targets:
        return None

    adjacency: dict[int, list[tuple[int, dict[str, object], float]]] = defaultdict(list)
    for edge in edges:
        if _road_class_tier_rank(str(edge.get("road_class", ""))) > max_tier_rank:
            continue
        u = int(edge["u"])
        v = int(edge["v"])
        if u == v:
            continue
        length_m = _edge_length_m(edge)
        if length_m <= 0:
            continue
        cost = length_m * _road_class_penalty(str(edge.get("road_class", "")))
        adjacency[u].append((v, edge, cost))
        adjacency[v].append((u, edge, cost))

    distances: dict[int, float] = {source: 0.0}
    previous: dict[int, tuple[int, dict[str, object]]] = {}
    heap: list[tuple[float, int]] = [(0.0, source)]
    remaining_targets = set(int(node_id) for node_id in targets if int(node_id) != source)

    while heap:
        current_dist, node = heapq.heappop(heap)
        if current_dist > distances.get(node, float("inf")):
            continue
        if node in remaining_targets:
            return _build_proxy_edge_from_previous(source, node, previous)
        for neighbor, edge, step_cost in adjacency.get(node, []):
            next_dist = current_dist + step_cost
            if next_dist >= distances.get(neighbor, float("inf")):
                continue
            distances[neighbor] = next_dist
            previous[neighbor] = (node, edge)
            heapq.heappush(heap, (next_dist, neighbor))
    return None


def _dedupe_proxy_edges(edges: list[dict[str, object]]) -> list[dict[str, object]]:
    deduped: dict[tuple[int, int], dict[str, object]] = {}
    for edge in sorted(edges, key=lambda item: str(item.get("edge_id", ""))):
        key = (int(edge["u"]), int(edge["v"]))
        existing = deduped.get(key)
        if existing is None or _edge_length_m(edge) < _edge_length_m(existing):
            deduped[key] = edge
    return sorted(deduped.values(), key=lambda item: str(item["edge_id"]))


def _cell_metric_feeder_proxy_edges(
    edges: list[dict[str, object]],
    terminal_nodes: set[int],
) -> list[dict[str, object]]:
    terminals = sorted({int(node_id) for node_id in terminal_nodes})
    if len(terminals) < 2:
        return []

    portal_tier_rank: dict[int, int] = {}
    for terminal in terminals:
        incident_ranks = sorted(
            {
                _road_class_tier_rank(str(edge.get("road_class", "")))
                for edge in edges
                if int(edge["u"]) == terminal or int(edge["v"]) == terminal
            }
        )
        if incident_ranks:
            portal_tier_rank[terminal] = incident_ranks[0]

    if len(portal_tier_rank) < 2:
        return []

    connected_portals: set[int] = set()
    proxy_edges: list[dict[str, object]] = []
    for rank in sorted(set(portal_tier_rank.values())):
        rank_portals = sorted(node_id for node_id, node_rank in portal_tier_rank.items() if node_rank == rank)
        if not rank_portals:
            continue

        if not connected_portals:
            initial_edges = _cell_metric_proxy_tree_edges(
                [edge for edge in edges if _road_class_tier_rank(str(edge.get("road_class", ""))) <= rank],
                terminal_nodes=set(rank_portals),
            )
            proxy_edges.extend(initial_edges)
            connected_portals.update(rank_portals)
            continue

        for portal in rank_portals:
            feeder_edge = _nearest_target_proxy_edge(
                edges,
                source=portal,
                targets=connected_portals,
                max_tier_rank=rank,
            )
            if feeder_edge is None:
                connected_portals.add(portal)
                continue
            proxy_edges.append(feeder_edge)
            connected_portals.add(portal)

    return _dedupe_proxy_edges(proxy_edges)


def contract_degree2_undirected_edges(
    edges: list[dict[str, object]],
    protected_nodes: set[int] | None = None,
    merge_by_topology_only: bool = False,
) -> list[dict[str, object]]:
    """Collapse interior degree-2 nodes in an undirected edge list."""
    active_edges: dict[str, dict[str, object]] = {}
    node_to_edges: dict[int, set[str]] = defaultdict(set)
    protected = {int(node_id) for node_id in protected_nodes or set()}

    for edge in edges:
        edge_id = str(edge.get("edge_id", ""))
        if not edge_id:
            continue
        u = int(edge["u"])
        v = int(edge["v"])
        if u == v:
            continue
        coords = _edge_coordinates(edge)
        if len(coords) < 2:
            continue
        if [float(coords[0][0]), float(coords[0][1])] == [float(coords[-1][0]), float(coords[-1][1])]:
            continue
        copied = {
            "edge_id": edge_id,
            "u": u,
            "v": v,
            "road_class": str(edge.get("road_class", "")),
            "oneway": edge.get("oneway") if isinstance(edge.get("oneway"), str) or edge.get("oneway") is None else None,
            "name": edge.get("name") if isinstance(edge.get("name"), str) or edge.get("name") is None else None,
            "ref": edge.get("ref") if isinstance(edge.get("ref"), str) or edge.get("ref") is None else None,
            "geometry": {"type": "LineString", "coordinates": coords},
            "_component_edge_ids": [edge_id],
        }
        active_edges[edge_id] = copied
        node_to_edges[u].add(edge_id)
        node_to_edges[v].add(edge_id)

    while True:
        candidate_nodes = sorted(
            node for node, incident in node_to_edges.items() if len(incident) == 2 and node not in protected
        )
        merged = False
        for node in candidate_nodes:
            incident_ids = sorted(node_to_edges.get(node, set()))
            if len(incident_ids) != 2:
                continue
            first = active_edges.get(incident_ids[0])
            second = active_edges.get(incident_ids[1])
            if first is None or second is None:
                continue
            if (not merge_by_topology_only) and _edge_merge_key(first) != _edge_merge_key(second):
                continue
            if int(first["u"]) == int(first["v"]) or int(second["u"]) == int(second["v"]):
                continue

            first_u = int(first["u"])
            first_v = int(first["v"])
            second_u = int(second["u"])
            second_v = int(second["v"])
            if node not in {first_u, first_v} or node not in {second_u, second_v}:
                continue
            other_a = first_v if first_u == node else first_u
            other_b = second_v if second_u == node else second_u
            if other_a == other_b:
                continue

            first_coords = _edge_coordinates(first)
            second_coords = _edge_coordinates(second)
            if len(first_coords) < 2 or len(second_coords) < 2:
                continue

            first_oriented = first_coords if first_v == node else _reverse_coordinates(first_coords)
            second_oriented = second_coords if second_u == node else _reverse_coordinates(second_coords)
            merged_coords = first_oriented + second_oriented[1:]
            merged_u = other_a
            merged_v = other_b
            if merged_u > merged_v:
                merged_coords = _reverse_coordinates(merged_coords)
                merged_u, merged_v = merged_v, merged_u

            component_edge_ids = sorted(
                {
                    *[str(value) for value in first.get("_component_edge_ids", [])],
                    *[str(value) for value in second.get("_component_edge_ids", [])],
                }
            )
            merged_road_class, merged_oneway, merged_name, merged_ref = _edge_merge_key(first)
            merged_edge_id = _build_contracted_edge_id(
                component_edge_ids=component_edge_ids,
                u=merged_u,
                v=merged_v,
                road_class=merged_road_class,
                oneway=merged_oneway,
                name=merged_name,
                ref=merged_ref,
                coordinates=merged_coords,
            )

            merged_edge = {
                "edge_id": merged_edge_id,
                "u": merged_u,
                "v": merged_v,
                "road_class": merged_road_class,
                "oneway": merged_oneway,
                "name": merged_name,
                "ref": merged_ref,
                "geometry": {"type": "LineString", "coordinates": merged_coords},
                "_component_edge_ids": component_edge_ids,
            }

            for edge_id in incident_ids:
                removed = active_edges.pop(edge_id, None)
                if removed is None:
                    continue
                node_to_edges[int(removed["u"])].discard(edge_id)
                node_to_edges[int(removed["v"])].discard(edge_id)

            active_edges[merged_edge_id] = merged_edge
            node_to_edges[merged_u].add(merged_edge_id)
            node_to_edges[merged_v].add(merged_edge_id)
            merged = True
            break
        if not merged:
            break

    contracted_edges = []
    for edge_id in sorted(active_edges):
        edge = active_edges[edge_id]
        contracted_edges.append(
            {
                "edge_id": edge["edge_id"],
                "u": edge["u"],
                "v": edge["v"],
                "road_class": edge["road_class"],
                "oneway": edge["oneway"],
                "name": edge["name"],
                "ref": edge["ref"],
                "geometry": edge["geometry"],
            }
        )
    return contracted_edges


class _SplitNodeCollector(osmium.SimpleHandler):
    def __init__(self) -> None:
        super().__init__()
        self._ref_counts: dict[int, int] = defaultdict(int)

    def way(self, way: osmium.osm.Way) -> None:
        road_class = _way_road_class(way)
        if road_class is None:
            return
        refs = [int(node.ref) for node in way.nodes]
        if len(refs) < 2:
            return
        for ref in set(refs):
            self._ref_counts[ref] += 1

    @property
    def shared_node_refs(self) -> set[int]:
        return {node_id for node_id, count in self._ref_counts.items() if count > 1}


class _MajorRoadGraphBuilder(osmium.SimpleHandler):
    def __init__(self, shared_node_refs: set[int]) -> None:
        super().__init__()
        self._shared_node_refs = shared_node_refs
        self.nodes: dict[int, tuple[float, float]] = {}
        self.edges: list[dict[str, object]] = []

    def way(self, way: osmium.osm.Way) -> None:
        road_class = _way_road_class(way)
        if road_class is None:
            return
        if len(way.nodes) < 2:
            return

        split_indices = {0, len(way.nodes) - 1}
        for index, node in enumerate(way.nodes):
            if int(node.ref) in self._shared_node_refs:
                split_indices.add(index)
        ordered_splits = sorted(split_indices)
        if len(ordered_splits) < 2:
            return

        for split_index in ordered_splits:
            split_node = way.nodes[split_index]
            if not split_node.location.valid():
                continue
            self.nodes[int(split_node.ref)] = (float(split_node.location.lon), float(split_node.location.lat))

        oneway_raw = way.tags.get("oneway")
        name = way.tags.get("name")
        ref = way.tags.get("ref")

        for segment_index, (start_index, end_index) in enumerate(zip(ordered_splits, ordered_splits[1:])):
            coordinates: list[list[float]] = []
            missing_location = False
            for node_index in range(start_index, end_index + 1):
                node = way.nodes[node_index]
                if not node.location.valid():
                    missing_location = True
                    break
                coordinates.append([float(node.location.lon), float(node.location.lat)])
            if missing_location or len(coordinates) < 2:
                continue

            u = int(way.nodes[start_index].ref)
            v = int(way.nodes[end_index].ref)
            self.edges.append(
                {
                    "edge_id": _build_edge_id(
                        way_id=int(way.id),
                        segment_index=segment_index,
                        u=u,
                        v=v,
                        road_class=road_class,
                        coordinates=coordinates,
                    ),
                    "u": u,
                    "v": v,
                    "road_class": road_class,
                    "oneway": str(oneway_raw) if oneway_raw is not None else None,
                    "name": str(name) if name is not None else None,
                    "ref": str(ref) if ref is not None else None,
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                }
            )


def _write_geojson(path: Path, features: list[dict[str, object]]) -> None:
    payload = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


def _to_node_features(node_items: list[tuple[int, tuple[float, float]]]) -> list[dict[str, object]]:
    return [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "node_id": node_id,
                "lon": lon,
                "lat": lat,
            },
        }
        for node_id, (lon, lat) in node_items
    ]


def _to_edge_features(edges: list[dict[str, object]]) -> list[dict[str, object]]:
    edge_features = []
    for edge in sorted(edges, key=lambda item: str(item["edge_id"])):
        edge_features.append(
            {
                "type": "Feature",
                "geometry": edge["geometry"],
                "properties": {
                    "edge_id": edge["edge_id"],
                    "u": edge["u"],
                    "v": edge["v"],
                    "road_class": edge["road_class"],
                    "oneway": edge["oneway"],
                    "name": edge["name"],
                    "ref": edge["ref"],
                },
            }
        )
    return edge_features


def _node_cells_at_resolution(nodes: dict[int, tuple[float, float]], resolution: int) -> dict[int, str]:
    return {
        int(node_id): str(h3.latlng_to_cell(float(lat), float(lon), resolution))
        for node_id, (lon, lat) in nodes.items()
    }


def _protected_nodes_from_cross_cell_edges(
    edges: list[dict[str, object]],
    node_cells: dict[int, str],
) -> set[int]:
    protected_nodes: set[int] = set()
    for edge in edges:
        u = int(edge["u"])
        v = int(edge["v"])
        u_cell = node_cells.get(u)
        v_cell = node_cells.get(v)
        if u_cell is None or v_cell is None:
            continue
        if u_cell != v_cell:
            protected_nodes.add(u)
            protected_nodes.add(v)
    return protected_nodes


def _filter_cross_cell_edges(
    edges: list[dict[str, object]],
    node_cells: dict[int, str],
) -> list[dict[str, object]]:
    filtered: list[dict[str, object]] = []
    for edge in edges:
        u = int(edge["u"])
        v = int(edge["v"])
        u_cell = node_cells.get(u)
        v_cell = node_cells.get(v)
        if u_cell is None or v_cell is None:
            continue
        if u_cell == v_cell:
            continue
        filtered.append(edge)
    return filtered


def _mainline_classes_for_resolution(resolution: int) -> frozenset[str]:
    return MAINLINE_ALLOWED_CLASSES


def _filter_mainline_edges_for_fixed_resolution(edges: list[dict[str, object]], resolution: int) -> list[dict[str, object]]:
    allowed = _mainline_classes_for_resolution(resolution)
    filtered: list[dict[str, object]] = []
    for edge in edges:
        road_class = str(edge.get("road_class", "")).strip().lower()
        if road_class in allowed:
            filtered.append(edge)
    return filtered


def _filter_mainline_edges_by_cell_priority(edges: list[dict[str, object]], resolution: int) -> list[dict[str, object]]:
    _ = resolution
    allowed = ADAPTIVE_PORTAL_ALLOWED_CLASSES
    best_rank_by_cell: dict[str, int] = {}
    max_rank_by_cell: dict[str, int] = {}
    edge_records: list[tuple[dict[str, object], str, int, str, str]] = []
    fallback_rank = len(ADAPTIVE_PORTAL_CLASS_PRIORITY_RANK)
    cross_cells: set[str] = set()

    for edge in edges:
        road_class = str(edge.get("road_class", "")).strip().lower()
        if road_class not in allowed:
            continue
        coords = _edge_coordinates(edge)
        if len(coords) < 2:
            continue
        mid_lon = (float(coords[0][0]) + float(coords[-1][0])) / 2.0
        mid_lat = (float(coords[0][1]) + float(coords[-1][1])) / 2.0
        cell = str(h3.latlng_to_cell(mid_lat, mid_lon, resolution))
        start_cell = str(h3.latlng_to_cell(float(coords[0][1]), float(coords[0][0]), resolution))
        end_cell = str(h3.latlng_to_cell(float(coords[-1][1]), float(coords[-1][0]), resolution))
        rank = ADAPTIVE_PORTAL_CLASS_PRIORITY_RANK.get(road_class, fallback_rank)
        edge_records.append((edge, cell, rank, start_cell, end_cell))
        current_best = best_rank_by_cell.get(cell)
        if current_best is None or rank < current_best:
            best_rank_by_cell[cell] = rank
        current_max = max_rank_by_cell.get(cell)
        if current_max is None or rank > current_max:
            max_rank_by_cell[cell] = rank
        if start_cell != end_cell:
            cross_cells.add(start_cell)
            cross_cells.add(end_cell)

    if not edge_records:
        return []

    selected_rank_by_cell = dict(best_rank_by_cell)
    if len(cross_cells) > 1:
        # Start from strict per-cell highest-priority classes, then relax only where
        # needed to bridge disconnected cross-cell components.
        for _ in range(len(ADAPTIVE_PORTAL_CLASS_PRIORITY)):
            parent: dict[str, str] = {cell: cell for cell in cross_cells}
            size: dict[str, int] = {cell: 1 for cell in cross_cells}

            def find(cell: str) -> str:
                root = cell
                while parent[root] != root:
                    root = parent[root]
                while parent[cell] != cell:
                    next_cell = parent[cell]
                    parent[cell] = root
                    cell = next_cell
                return root

            def union(a: str, b: str) -> None:
                root_a = find(a)
                root_b = find(b)
                if root_a == root_b:
                    return
                if size[root_a] < size[root_b]:
                    root_a, root_b = root_b, root_a
                parent[root_b] = root_a
                size[root_a] += size[root_b]

            for _edge, owner_cell, rank, start_cell, end_cell in edge_records:
                if start_cell == end_cell:
                    continue
                if rank <= selected_rank_by_cell.get(owner_cell, fallback_rank):
                    union(start_cell, end_cell)

            roots = {find(cell) for cell in cross_cells}
            if len(roots) <= 1:
                break

            cells_to_escalate: set[str] = set()
            for _edge, owner_cell, rank, start_cell, end_cell in edge_records:
                if start_cell == end_cell:
                    continue
                if find(start_cell) == find(end_cell):
                    continue
                current = selected_rank_by_cell.get(owner_cell)
                max_rank = max_rank_by_cell.get(owner_cell)
                if current is None or max_rank is None:
                    continue
                if rank > current and current < max_rank:
                    cells_to_escalate.add(owner_cell)

            if not cells_to_escalate:
                break
            for cell in sorted(cells_to_escalate):
                selected_rank_by_cell[cell] = min(
                    selected_rank_by_cell[cell] + 1,
                    max_rank_by_cell.get(cell, selected_rank_by_cell[cell]),
                )

    filtered: list[dict[str, object]] = []
    for edge, cell, rank, _start_cell, _end_cell in edge_records:
        if rank <= selected_rank_by_cell.get(cell, fallback_rank):
            filtered.append(edge)
    return filtered


def _filter_mainline_edges_for_adaptive_mask(
    edges: list[dict[str, object]],
    adaptive_mask_cells: set[str],
    occupied_cells: set[str] | None = None,
) -> list[dict[str, object]]:
    mask_cells_by_resolution = _adaptive_mask_cells_by_resolution(adaptive_mask_cells)
    __ = occupied_cells

    def allowed_classes_for_resolution(resolution: int) -> set[str]:
        if int(resolution) <= 3:
            return {"motorway", "motorway_link"}
        if int(resolution) <= 6:
            return {"motorway", "motorway_link", "trunk", "trunk_link"}
        if int(resolution) <= 8:
            return {"motorway", "motorway_link", "trunk", "trunk_link", "primary"}
        return {
            "motorway",
            "motorway_link",
            "trunk",
            "trunk_link",
            "primary",
            "secondary",
        }

    def neighboring_resolution_for_uncovered_point(lon: float, lat: float) -> int | None:
        neighbor_resolutions: list[int] = []
        for resolution, cells in mask_cells_by_resolution.items():
            center_cell = str(h3.latlng_to_cell(lat, lon, resolution))
            neighbor_cells = {str(cell) for cell in h3.grid_disk(center_cell, 1)}
            if neighbor_cells & cells:
                neighbor_resolutions.append(int(resolution))
        if not neighbor_resolutions:
            return None
        # Larger H3 cells have smaller resolution numbers.
        return min(neighbor_resolutions)

    filtered: list[dict[str, object]] = []
    for edge in edges:
        road_class = str(edge.get("road_class", "")).strip().lower()
        coords = _edge_coordinates(edge)
        if len(coords) < 2:
            continue
        mid_lon = (float(coords[0][0]) + float(coords[-1][0])) / 2.0
        mid_lat = (float(coords[0][1]) + float(coords[-1][1])) / 2.0
        mid_cell = _adaptive_mask_cell_for_point([mid_lon, mid_lat], mask_cells_by_resolution)
        if mid_cell is None:
            neighbor_resolution = neighboring_resolution_for_uncovered_point(mid_lon, mid_lat)
            if neighbor_resolution is None:
                # No nearby mask context; keep strictest policy.
                allowed_classes = allowed_classes_for_resolution(0)
            else:
                allowed_classes = allowed_classes_for_resolution(neighbor_resolution)
        else:
            allowed_classes = allowed_classes_for_resolution(h3.get_resolution(mid_cell))
        if road_class in allowed_classes:
            filtered.append(edge)
    return filtered


def _filter_adaptive_portal_edges_post_contract(edges: list[dict[str, object]]) -> list[dict[str, object]]:
    filtered: list[dict[str, object]] = []
    for edge in edges:
        road_class = str(edge.get("road_class", "")).strip().lower()
        if road_class in ADAPTIVE_PORTAL_ALLOWED_CLASSES:
            filtered.append(edge)
    return filtered


def _connected_node_ids(edges: list[dict[str, object]]) -> set[int]:
    connected: set[int] = set()
    for edge in edges:
        connected.add(int(edge["u"]))
        connected.add(int(edge["v"]))
    return connected


def _interpolate_point(start: list[float], end: list[float], fraction: float) -> list[float]:
    return [
        float(start[0]) + (float(end[0]) - float(start[0])) * fraction,
        float(start[1]) + (float(end[1]) - float(start[1])) * fraction,
    ]


def _point_cell(point: list[float], resolution: int) -> str:
    return str(h3.latlng_to_cell(float(point[1]), float(point[0]), resolution))


def _build_portal_node_id(lon: float, lat: float, resolution: int) -> int:
    raw = f"{resolution}|{lon:.9f}|{lat:.9f}"
    # Keep IDs within JavaScript safe integer range to avoid client-side collisions.
    return -int(sha256(raw.encode("utf-8")).hexdigest()[:13], 16)


def _build_portal_node_id_for_mask(lon: float, lat: float, from_cell: str | None, to_cell: str | None) -> int:
    normalized_from, normalized_to = sorted((str(from_cell or ""), str(to_cell or "")))
    raw = f"{normalized_from}|{normalized_to}|{lon:.9f}|{lat:.9f}"
    # Keep IDs within JavaScript safe integer range to avoid client-side collisions.
    return -int(sha256(raw.encode("utf-8")).hexdigest()[:13], 16)


def _build_split_edge_id(base_edge_id: str, segment_index: int, u: int, v: int, coordinates: list[list[float]]) -> str:
    coords_key = ";".join(f"{lon:.7f},{lat:.7f}" for lon, lat in coordinates)
    raw = f"{base_edge_id}|{segment_index}|{u}|{v}|{coords_key}"
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def _boundary_crossing_point(start: list[float], end: list[float], resolution: int) -> list[float] | None:
    start_cell = _point_cell(start, resolution)
    end_cell = _point_cell(end, resolution)
    if start_cell == end_cell:
        return None
    lo = 0.0
    hi = 1.0
    for _ in range(48):
        mid = (lo + hi) / 2.0
        mid_point = _interpolate_point(start, end, mid)
        if _point_cell(mid_point, resolution) == start_cell:
            lo = mid
        else:
            hi = mid
    crossing = _interpolate_point(start, end, hi)
    if crossing == start or crossing == end:
        return None
    return crossing


def _adaptive_mask_cells_by_resolution(adaptive_mask_cells: set[str]) -> dict[int, set[str]]:
    by_resolution: dict[int, set[str]] = defaultdict(set)
    for cell in sorted({str(cell) for cell in adaptive_mask_cells}):
        by_resolution[h3.get_resolution(cell)].add(cell)
    return dict(by_resolution)


def _adaptive_mask_cell_for_point(point: list[float], mask_cells_by_resolution: dict[int, set[str]]) -> str | None:
    if not mask_cells_by_resolution:
        return None
    lon = float(point[0])
    lat = float(point[1])
    for resolution in sorted(mask_cells_by_resolution, reverse=True):
        cell = str(h3.latlng_to_cell(lat, lon, resolution))
        if cell in mask_cells_by_resolution[resolution]:
            return cell
    return None


def _boundary_crossing_point_by_mask(
    start: list[float],
    end: list[float],
    mask_cells_by_resolution: dict[int, set[str]],
) -> tuple[list[float], str | None, str | None] | None:
    start_cell = _adaptive_mask_cell_for_point(start, mask_cells_by_resolution)
    end_cell = _adaptive_mask_cell_for_point(end, mask_cells_by_resolution)
    if start_cell == end_cell:
        return None
    lo = 0.0
    hi = 1.0
    for _ in range(48):
        mid = (lo + hi) / 2.0
        mid_point = _interpolate_point(start, end, mid)
        if _adaptive_mask_cell_for_point(mid_point, mask_cells_by_resolution) == start_cell:
            lo = mid
        else:
            hi = mid
    crossing = _interpolate_point(start, end, hi)
    if crossing == start or crossing == end:
        return None
    crossing_from = _adaptive_mask_cell_for_point(_interpolate_point(start, crossing, 0.999999999), mask_cells_by_resolution)
    crossing_to = _adaptive_mask_cell_for_point(_interpolate_point(crossing, end, 0.000000001), mask_cells_by_resolution)
    return crossing, crossing_from, crossing_to


def _segment_crossings_by_mask(
    start: list[float],
    end: list[float],
    mask_cells_by_resolution: dict[int, set[str]],
) -> list[tuple[list[float], str | None, str | None]]:
    crossings: list[tuple[list[float], str | None, str | None]] = []
    current_start = list(start)
    for _ in range(64):
        crossing = _boundary_crossing_point_by_mask(current_start, end, mask_cells_by_resolution)
        if crossing is None:
            break
        crossings.append(crossing)
        # Nudge toward the segment end so subsequent iterations can detect later boundaries.
        current_start = _interpolate_point(crossing[0], end, 1e-9)
        if current_start == crossing[0]:
            break
    return crossings


def _segment_crossings(start: list[float], end: list[float], resolution: int) -> list[list[float]]:
    crossings: list[list[float]] = []
    current_start = list(start)
    for _ in range(64):
        crossing = _boundary_crossing_point(current_start, end, resolution)
        if crossing is None:
            break
        crossings.append(crossing)
        # Nudge toward the segment end so subsequent iterations can detect later boundaries.
        current_start = _interpolate_point(crossing, end, 1e-9)
        if current_start == crossing:
            break
    return crossings


def split_edges_with_adaptive_portals(
    edges: list[dict[str, object]],
    nodes: dict[int, tuple[float, float]],
    resolution: int,
) -> tuple[list[dict[str, object]], dict[int, tuple[float, float]], set[int]]:
    split_edges: list[dict[str, object]] = []
    split_nodes: dict[int, tuple[float, float]] = {int(node_id): (float(lon), float(lat)) for node_id, (lon, lat) in nodes.items()}
    portal_node_ids: set[int] = set()

    for edge in sorted(edges, key=lambda item: str(item.get("edge_id", ""))):
        edge_id = str(edge.get("edge_id", ""))
        if not edge_id:
            continue
        coords = _edge_coordinates(edge)
        if len(coords) < 2:
            continue
        u = int(edge["u"])
        v = int(edge["v"])
        current_u = u
        current_coords: list[list[float]] = [list(coords[0])]
        split_segment_index = 0

        for start, end in zip(coords, coords[1:]):
            crossings = _segment_crossings(start, end, resolution)
            if not crossings:
                current_coords.append(list(end))
                continue

            for crossing in crossings:
                portal_lon = float(crossing[0])
                portal_lat = float(crossing[1])
                portal_node_id = _build_portal_node_id(portal_lon, portal_lat, resolution)
                portal_node_ids.add(portal_node_id)
                split_nodes[portal_node_id] = (portal_lon, portal_lat)

                current_coords.append([portal_lon, portal_lat])
                if len(current_coords) >= 2:
                    split_edges.append(
                        {
                            "edge_id": _build_split_edge_id(
                                edge_id,
                                split_segment_index,
                                current_u,
                                portal_node_id,
                                current_coords,
                            ),
                            "u": current_u,
                            "v": portal_node_id,
                            "road_class": str(edge.get("road_class", "")),
                            "oneway": edge.get("oneway")
                            if isinstance(edge.get("oneway"), str) or edge.get("oneway") is None
                            else None,
                            "name": edge.get("name")
                            if isinstance(edge.get("name"), str) or edge.get("name") is None
                            else None,
                            "ref": edge.get("ref") if isinstance(edge.get("ref"), str) or edge.get("ref") is None else None,
                            "geometry": {"type": "LineString", "coordinates": current_coords},
                        }
                    )
                    split_segment_index += 1
                current_u = portal_node_id
                current_coords = [[portal_lon, portal_lat]]

            current_coords.append(list(end))

        if len(current_coords) >= 2:
            split_edges.append(
                {
                    "edge_id": _build_split_edge_id(edge_id, split_segment_index, current_u, v, current_coords),
                    "u": current_u,
                    "v": v,
                    "road_class": str(edge.get("road_class", "")),
                    "oneway": edge.get("oneway") if isinstance(edge.get("oneway"), str) or edge.get("oneway") is None else None,
                    "name": edge.get("name") if isinstance(edge.get("name"), str) or edge.get("name") is None else None,
                    "ref": edge.get("ref") if isinstance(edge.get("ref"), str) or edge.get("ref") is None else None,
                    "geometry": {"type": "LineString", "coordinates": current_coords},
                }
            )

    return split_edges, split_nodes, portal_node_ids


def split_edges_with_adaptive_mask_portals(
    edges: list[dict[str, object]],
    nodes: dict[int, tuple[float, float]],
    adaptive_mask_cells: set[str],
) -> tuple[list[dict[str, object]], dict[int, tuple[float, float]], set[int]]:
    split_edges: list[dict[str, object]] = []
    split_nodes: dict[int, tuple[float, float]] = {int(node_id): (float(lon), float(lat)) for node_id, (lon, lat) in nodes.items()}
    portal_node_ids: set[int] = set()
    mask_cells_by_resolution = _adaptive_mask_cells_by_resolution(adaptive_mask_cells)

    for edge in sorted(edges, key=lambda item: str(item.get("edge_id", ""))):
        edge_id = str(edge.get("edge_id", ""))
        if not edge_id:
            continue
        coords = _edge_coordinates(edge)
        if len(coords) < 2:
            continue
        u = int(edge["u"])
        v = int(edge["v"])
        current_u = u
        current_coords: list[list[float]] = [list(coords[0])]
        split_segment_index = 0

        for start, end in zip(coords, coords[1:]):
            crossings = _segment_crossings_by_mask(start, end, mask_cells_by_resolution)
            if not crossings:
                current_coords.append(list(end))
                continue

            for crossing, crossing_from, crossing_to in crossings:
                portal_lon = float(crossing[0])
                portal_lat = float(crossing[1])
                portal_node_id = _build_portal_node_id_for_mask(portal_lon, portal_lat, crossing_from, crossing_to)
                portal_node_ids.add(portal_node_id)
                split_nodes[portal_node_id] = (portal_lon, portal_lat)

                current_coords.append([portal_lon, portal_lat])
                if len(current_coords) >= 2:
                    split_edges.append(
                        {
                            "edge_id": _build_split_edge_id(
                                edge_id,
                                split_segment_index,
                                current_u,
                                portal_node_id,
                                current_coords,
                            ),
                            "u": current_u,
                            "v": portal_node_id,
                            "road_class": str(edge.get("road_class", "")),
                            "oneway": edge.get("oneway")
                            if isinstance(edge.get("oneway"), str) or edge.get("oneway") is None
                            else None,
                            "name": edge.get("name")
                            if isinstance(edge.get("name"), str) or edge.get("name") is None
                            else None,
                            "ref": edge.get("ref") if isinstance(edge.get("ref"), str) or edge.get("ref") is None else None,
                            "geometry": {"type": "LineString", "coordinates": current_coords},
                        }
                    )
                    split_segment_index += 1
                current_u = portal_node_id
                current_coords = [[portal_lon, portal_lat]]

            current_coords.append(list(end))

        if len(current_coords) >= 2:
            split_edges.append(
                {
                    "edge_id": _build_split_edge_id(edge_id, split_segment_index, current_u, v, current_coords),
                    "u": current_u,
                    "v": v,
                    "road_class": str(edge.get("road_class", "")),
                    "oneway": edge.get("oneway") if isinstance(edge.get("oneway"), str) or edge.get("oneway") is None else None,
                    "name": edge.get("name") if isinstance(edge.get("name"), str) or edge.get("name") is None else None,
                    "ref": edge.get("ref") if isinstance(edge.get("ref"), str) or edge.get("ref") is None else None,
                    "geometry": {"type": "LineString", "coordinates": current_coords},
                }
            )

    return split_edges, split_nodes, portal_node_ids


def contract_edges_within_cells_preserving_portals(
    split_edges: list[dict[str, object]],
    portal_node_ids: set[int],
    resolution: int,
    merge_by_topology_only: bool = True,
    prune_non_anchor_leaves: bool = False,
    prune_all_leaves: bool = False,
) -> list[dict[str, object]]:
    degree: dict[int, int] = defaultdict(int)
    for edge in split_edges:
        degree[int(edge["u"])] += 1
        degree[int(edge["v"])] += 1
    junction_nodes = {node_id for node_id, value in degree.items() if value >= 3}
    protected_nodes = set(portal_node_ids) | junction_nodes

    cell_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for edge in split_edges:
        coords = _edge_coordinates(edge)
        if len(coords) < 2:
            continue
        mid_lon = (float(coords[0][0]) + float(coords[-1][0])) / 2.0
        mid_lat = (float(coords[0][1]) + float(coords[-1][1])) / 2.0
        cell = str(h3.latlng_to_cell(mid_lat, mid_lon, resolution))
        cell_groups[cell].append(edge)

    contracted: list[dict[str, object]] = []
    for cell in sorted(cell_groups):
        grouped_edges = sorted(cell_groups[cell], key=lambda item: str(item["edge_id"]))
        group_nodes = {int(edge["u"]) for edge in grouped_edges} | {int(edge["v"]) for edge in grouped_edges}
        group_portal_nodes = group_nodes & set(portal_node_ids)
        if len(group_portal_nodes) >= 2:
            contracted.extend(_cell_metric_proxy_edges(grouped_edges, terminal_nodes=group_portal_nodes))
        else:
            contracted.extend(
                contract_degree2_undirected_edges(
                    grouped_edges,
                    protected_nodes=protected_nodes,
                    merge_by_topology_only=merge_by_topology_only,
                )
            )
    if prune_all_leaves:
        contracted = _prune_all_leaf_edges(contracted)
        contracted = contract_degree2_undirected_edges(
            contracted,
            protected_nodes=protected_nodes,
            merge_by_topology_only=merge_by_topology_only,
        )
    elif prune_non_anchor_leaves:
        contracted = _prune_non_anchor_leaf_edges(contracted, anchor_nodes=protected_nodes)
        contracted = contract_degree2_undirected_edges(
            contracted,
            protected_nodes=protected_nodes,
            merge_by_topology_only=merge_by_topology_only,
        )
    return sorted(contracted, key=lambda item: str(item["edge_id"]))


def contract_edges_within_adaptive_mask_preserving_portals(
    split_edges: list[dict[str, object]],
    portal_node_ids: set[int],
    adaptive_mask_cells: set[str],
    merge_by_topology_only: bool = True,
    prune_non_anchor_leaves: bool = False,
    prune_all_leaves: bool = False,
    cell_progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, object]]:
    degree: dict[int, int] = defaultdict(int)
    for edge in split_edges:
        degree[int(edge["u"])] += 1
        degree[int(edge["v"])] += 1
    junction_nodes = {node_id for node_id, value in degree.items() if value >= 3}
    protected_nodes = set(portal_node_ids) | junction_nodes
    mask_cells_by_resolution = _adaptive_mask_cells_by_resolution(adaptive_mask_cells)

    cell_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    uncovered_edges: list[dict[str, object]] = []
    for edge in split_edges:
        coords = _edge_coordinates(edge)
        if len(coords) < 2:
            continue
        mid_lon = (float(coords[0][0]) + float(coords[-1][0])) / 2.0
        mid_lat = (float(coords[0][1]) + float(coords[-1][1])) / 2.0
        cell = _adaptive_mask_cell_for_point([mid_lon, mid_lat], mask_cells_by_resolution)
        if cell is None:
            uncovered_edges.append(edge)
            continue
        cell_groups[cell].append(edge)

    contracted: list[dict[str, object]] = []
    total_cells = len(cell_groups)
    for index, cell in enumerate(sorted(cell_groups), start=1):
        grouped_edges = sorted(cell_groups[cell], key=lambda item: str(item["edge_id"]))
        group_nodes = {int(edge["u"]) for edge in grouped_edges} | {int(edge["v"]) for edge in grouped_edges}
        group_portal_nodes = group_nodes & set(portal_node_ids)
        if len(group_portal_nodes) >= 2:
            contracted.extend(_cell_metric_feeder_proxy_edges(grouped_edges, terminal_nodes=group_portal_nodes))
        else:
            contracted.extend(
                contract_degree2_undirected_edges(
                    grouped_edges,
                    protected_nodes=protected_nodes,
                    merge_by_topology_only=merge_by_topology_only,
                )
            )
        if cell_progress_callback is not None:
            cell_progress_callback(index, total_cells)
    if uncovered_edges:
        contracted.extend(sorted(uncovered_edges, key=lambda item: str(item["edge_id"])))
    if prune_all_leaves:
        contracted = _prune_all_leaf_edges(contracted)
        contracted = contract_degree2_undirected_edges(
            contracted,
            protected_nodes=protected_nodes,
            merge_by_topology_only=merge_by_topology_only,
        )
    elif prune_non_anchor_leaves:
        contracted = _prune_non_anchor_leaf_edges(contracted, anchor_nodes=protected_nodes)
        contracted = contract_degree2_undirected_edges(
            contracted,
            protected_nodes=protected_nodes,
            merge_by_topology_only=merge_by_topology_only,
        )
    return sorted(contracted, key=lambda item: str(item["edge_id"]))


def _prune_non_anchor_leaf_edges(
    edges: list[dict[str, object]],
    anchor_nodes: set[int],
) -> list[dict[str, object]]:
    active_edges: dict[str, dict[str, object]] = {str(edge.get("edge_id", "")): dict(edge) for edge in edges if edge.get("edge_id")}
    node_to_edges: dict[int, set[str]] = defaultdict(set)
    for edge_id, edge in active_edges.items():
        u = int(edge["u"])
        v = int(edge["v"])
        node_to_edges[u].add(edge_id)
        node_to_edges[v].add(edge_id)

    while True:
        removable_leaves = sorted(node for node, incident in node_to_edges.items() if len(incident) == 1 and node not in anchor_nodes)
        if not removable_leaves:
            break
        changed = False
        for node in removable_leaves:
            incident_ids = sorted(node_to_edges.get(node, set()))
            if len(incident_ids) != 1:
                continue
            edge_id = incident_ids[0]
            edge = active_edges.pop(edge_id, None)
            if edge is None:
                continue
            u = int(edge["u"])
            v = int(edge["v"])
            node_to_edges[u].discard(edge_id)
            node_to_edges[v].discard(edge_id)
            changed = True
        if not changed:
            break

    return sorted(active_edges.values(), key=lambda item: str(item["edge_id"]))


def _prune_all_leaf_edges(edges: list[dict[str, object]]) -> list[dict[str, object]]:
    active_edges: dict[str, dict[str, object]] = {str(edge.get("edge_id", "")): dict(edge) for edge in edges if edge.get("edge_id")}
    node_to_edges: dict[int, set[str]] = defaultdict(set)
    for edge_id, edge in active_edges.items():
        u = int(edge["u"])
        v = int(edge["v"])
        node_to_edges[u].add(edge_id)
        node_to_edges[v].add(edge_id)

    while True:
        leaves = sorted(node for node, incident in node_to_edges.items() if len(incident) == 1)
        if not leaves:
            break
        changed = False
        for node in leaves:
            incident_ids = sorted(node_to_edges.get(node, set()))
            if len(incident_ids) != 1:
                continue
            edge_id = incident_ids[0]
            edge = active_edges.pop(edge_id, None)
            if edge is None:
                continue
            u = int(edge["u"])
            v = int(edge["v"])
            node_to_edges[u].discard(edge_id)
            node_to_edges[v].discard(edge_id)
            changed = True
        if not changed:
            break

    return sorted(active_edges.values(), key=lambda item: str(item["edge_id"]))


def _adaptive_portal_anchor_node_ids(edges: list[dict[str, object]], portal_node_ids: set[int]) -> set[int]:
    degree: dict[int, int] = defaultdict(int)
    for edge in edges:
        degree[int(edge["u"])] += 1
        degree[int(edge["v"])] += 1
    anchors = {int(node_id) for node_id in portal_node_ids}
    anchors.update(node_id for node_id, value in degree.items() if value >= 3)
    return anchors


def _variant_filenames(variant: GraphVariant) -> tuple[str, str]:
    if variant == "adaptive_portal_run":
        return ADAPTIVE_PORTAL_RUN_EDGE_FILENAME, ADAPTIVE_PORTAL_RUN_NODE_FILENAME
    if variant == "adaptive_portal":
        return ADAPTIVE_PORTAL_EDGE_FILENAME, ADAPTIVE_PORTAL_NODE_FILENAME
    if variant == "adaptive":
        return ADAPTIVE_EDGE_FILENAME, ADAPTIVE_NODE_FILENAME
    if variant == "collapsed":
        return COLLAPSED_EDGE_FILENAME, COLLAPSED_NODE_FILENAME
    return RAW_EDGE_FILENAME, RAW_NODE_FILENAME


def build_major_road_graph_variants(
    pbf_path: Path,
    output_dir: Path,
    variants: tuple[GraphVariant, ...] = ("raw",),
    adaptive_resolution: int | None = None,
    adaptive_mask_cells: set[str] | None = None,
    adaptive_occupied_cells: set[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[GraphVariant, tuple[Path, Path]]:
    def notify(event: str, stage: str, payload: dict[str, Any] | None = None) -> None:
        if progress_callback is None:
            return
        progress_callback(event, stage, payload or {})

    def run_stage(stage: str, fn: Callable[[], None]) -> None:
        notify("phase_start", stage)
        started = perf_counter()
        fn()
        notify("phase_end", stage, {"elapsed_seconds": perf_counter() - started})

    def run_substep(stage: str, step: str, fn: Callable[[], Any]) -> Any:
        started = perf_counter()
        result = fn()
        notify(
            "phase_update",
            stage,
            {
                "step": step,
                "elapsed_seconds": perf_counter() - started,
            },
        )
        return result

    requested = tuple(dict.fromkeys(variants))
    if ("adaptive" in requested or "adaptive_portal" in requested) and adaptive_resolution is None:
        raise ValueError("adaptive_resolution is required when adaptive or adaptive_portal graph variant is requested")
    if "adaptive_portal_run" in requested and not adaptive_mask_cells:
        raise ValueError("adaptive_mask_cells is required when adaptive_portal_run graph variant is requested")

    collector = _SplitNodeCollector()
    run_stage("collect_shared_nodes", lambda: collector.apply_file(str(pbf_path), locations=False))

    builder = _MajorRoadGraphBuilder(shared_node_refs=collector.shared_node_refs)
    run_stage("build_raw_graph", lambda: builder.apply_file(str(pbf_path), locations=True, idx="flex_mem"))

    outputs: dict[GraphVariant, tuple[Path, Path]] = {}
    output_dir.mkdir(parents=True, exist_ok=True)
    if "raw" in requested:
        def write_raw() -> None:
            raw_edge_features = _to_edge_features(builder.edges)
            raw_node_features = _to_node_features(sorted(builder.nodes.items()))
            raw_edges_name, raw_nodes_name = _variant_filenames("raw")
            raw_edges_path = output_dir / raw_edges_name
            raw_nodes_path = output_dir / raw_nodes_name
            _write_geojson(raw_edges_path, raw_edge_features)
            _write_geojson(raw_nodes_path, raw_node_features)
            outputs["raw"] = (raw_edges_path, raw_nodes_path)

        run_stage("write_raw", write_raw)

    if "collapsed" in requested:
        def write_collapsed() -> None:
            collapsed_edges = contract_degree2_undirected_edges(builder.edges)
            collapsed_node_ids = sorted(
                {int(edge["u"]) for edge in collapsed_edges} | {int(edge["v"]) for edge in collapsed_edges}
            )
            collapsed_node_items = [
                (node_id, builder.nodes[node_id]) for node_id in collapsed_node_ids if node_id in builder.nodes
            ]
            collapsed_edge_features = _to_edge_features(collapsed_edges)
            collapsed_node_features = _to_node_features(collapsed_node_items)
            collapsed_edges_name, collapsed_nodes_name = _variant_filenames("collapsed")
            collapsed_edges_path = output_dir / collapsed_edges_name
            collapsed_nodes_path = output_dir / collapsed_nodes_name
            _write_geojson(collapsed_edges_path, collapsed_edge_features)
            _write_geojson(collapsed_nodes_path, collapsed_node_features)
            outputs["collapsed"] = (collapsed_edges_path, collapsed_nodes_path)

        run_stage("write_collapsed", write_collapsed)

    if "adaptive" in requested:
        def write_adaptive() -> None:
            node_cells = _node_cells_at_resolution(builder.nodes, adaptive_resolution)
            protected_nodes = _protected_nodes_from_cross_cell_edges(builder.edges, node_cells)
            adaptive_edges = contract_degree2_undirected_edges(builder.edges, protected_nodes=protected_nodes)
            adaptive_node_ids = sorted({int(edge["u"]) for edge in adaptive_edges} | {int(edge["v"]) for edge in adaptive_edges})
            adaptive_node_items = [
                (node_id, builder.nodes[node_id]) for node_id in adaptive_node_ids if node_id in builder.nodes
            ]
            adaptive_edge_features = _to_edge_features(adaptive_edges)
            adaptive_node_features = _to_node_features(adaptive_node_items)
            adaptive_edges_name, adaptive_nodes_name = _variant_filenames("adaptive")
            adaptive_edges_path = output_dir / adaptive_edges_name
            adaptive_nodes_path = output_dir / adaptive_nodes_name
            _write_geojson(adaptive_edges_path, adaptive_edge_features)
            _write_geojson(adaptive_nodes_path, adaptive_node_features)
            outputs["adaptive"] = (adaptive_edges_path, adaptive_nodes_path)

        run_stage("write_adaptive", write_adaptive)

    if "adaptive_portal" in requested:
        def write_adaptive_portal() -> None:
            split_edges, split_nodes, portal_nodes = run_substep(
                "write_adaptive_portal",
                "split_edges_with_portals",
                lambda: split_edges_with_adaptive_portals(
                    builder.edges,
                    builder.nodes,
                    adaptive_resolution,
                ),
            )
            notify(
                "phase_update",
                "write_adaptive_portal",
                {
                    "step": "split_edges_with_portals_counts",
                    "split_edges": len(split_edges),
                    "portal_nodes": len(portal_nodes),
                },
            )
            adaptive_portal_edges = split_edges
            adaptive_portal_connected_nodes = _connected_node_ids(adaptive_portal_edges)
            adaptive_portal_node_ids = sorted(adaptive_portal_connected_nodes)
            adaptive_portal_node_items = [
                (node_id, split_nodes[node_id]) for node_id in adaptive_portal_node_ids if node_id in split_nodes
            ]
            adaptive_portal_edge_features = _to_edge_features(adaptive_portal_edges)
            adaptive_portal_node_features = _to_node_features(adaptive_portal_node_items)
            for feature in adaptive_portal_edge_features:
                props = feature.get("properties")
                if isinstance(props, dict):
                    props["adaptive_resolution"] = int(adaptive_resolution)
            for feature in adaptive_portal_node_features:
                props = feature.get("properties")
                if isinstance(props, dict):
                    props["adaptive_resolution"] = int(adaptive_resolution)
            adaptive_portal_edges_name, adaptive_portal_nodes_name = _variant_filenames("adaptive_portal")
            adaptive_portal_edges_path = output_dir / adaptive_portal_edges_name
            adaptive_portal_nodes_path = output_dir / adaptive_portal_nodes_name
            _write_geojson(adaptive_portal_edges_path, adaptive_portal_edge_features)
            _write_geojson(adaptive_portal_nodes_path, adaptive_portal_node_features)
            outputs["adaptive_portal"] = (adaptive_portal_edges_path, adaptive_portal_nodes_path)

        run_stage("write_adaptive_portal", write_adaptive_portal)

    if "adaptive_portal_run" in requested:
        def write_adaptive_portal_run() -> None:
            split_edges, split_nodes, portal_nodes = run_substep(
                "write_adaptive_portal_run",
                "split_edges_with_adaptive_mask_portals",
                lambda: split_edges_with_adaptive_mask_portals(
                    builder.edges,
                    builder.nodes,
                    adaptive_mask_cells or set(),
                ),
            )
            notify(
                "phase_update",
                "write_adaptive_portal_run",
                {
                    "step": "split_edges_with_adaptive_mask_portals_counts",
                    "split_edges": len(split_edges),
                    "portal_nodes": len(portal_nodes),
                },
            )
            adaptive_portal_run_edges = run_substep(
                "write_adaptive_portal_run",
                "contract_within_adaptive_mask_preserving_portals",
                lambda: contract_edges_within_adaptive_mask_preserving_portals(
                    split_edges=split_edges,
                    portal_node_ids=portal_nodes,
                    adaptive_mask_cells=adaptive_mask_cells or set(),
                    cell_progress_callback=lambda processed, total: notify(
                        "phase_update",
                        "write_adaptive_portal_run",
                        {
                            "step": "contract_cells_progress",
                            "processed_cells": int(processed),
                            "total_cells": int(total),
                        },
                    ),
                ),
            )
            adaptive_portal_run_edges = run_substep(
                "write_adaptive_portal_run",
                "post_contract_mainline_filter",
                lambda: _filter_mainline_edges_for_adaptive_mask(
                    adaptive_portal_run_edges,
                    adaptive_mask_cells=adaptive_mask_cells or set(),
                    occupied_cells=adaptive_occupied_cells or set(),
                ),
            )
            adaptive_portal_run_connected_nodes = _connected_node_ids(adaptive_portal_run_edges)
            adaptive_portal_run_node_ids = sorted(
                _adaptive_portal_anchor_node_ids(adaptive_portal_run_edges, portal_nodes)
                & adaptive_portal_run_connected_nodes
            )
            adaptive_portal_run_node_items = [
                (node_id, split_nodes[node_id]) for node_id in adaptive_portal_run_node_ids if node_id in split_nodes
            ]
            adaptive_portal_run_edge_features = _to_edge_features(adaptive_portal_run_edges)
            adaptive_portal_run_node_features = _to_node_features(adaptive_portal_run_node_items)
            adaptive_portal_run_edges_name, adaptive_portal_run_nodes_name = _variant_filenames("adaptive_portal_run")
            adaptive_portal_run_edges_path = output_dir / adaptive_portal_run_edges_name
            adaptive_portal_run_nodes_path = output_dir / adaptive_portal_run_nodes_name
            _write_geojson(adaptive_portal_run_edges_path, adaptive_portal_run_edge_features)
            _write_geojson(adaptive_portal_run_nodes_path, adaptive_portal_run_node_features)
            outputs["adaptive_portal_run"] = (adaptive_portal_run_edges_path, adaptive_portal_run_nodes_path)

        run_stage("write_adaptive_portal_run", write_adaptive_portal_run)

    notify("done", "complete", {"output_count": len(outputs)})
    return outputs


def build_major_road_graph(pbf_path: Path, output_dir: Path) -> tuple[Path, Path]:
    outputs = build_major_road_graph_variants(pbf_path=pbf_path, output_dir=output_dir, variants=("raw",))
    return outputs["raw"]
