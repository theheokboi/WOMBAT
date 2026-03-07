from __future__ import annotations

import json
import heapq
import math
from collections import defaultdict, deque
from hashlib import sha256
from pathlib import Path
from typing import Any


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _haversine_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    return 2.0 * radius * math.asin(math.sqrt(a))


def _linestring_length_meters(coordinates: list[list[float]]) -> float:
    if len(coordinates) < 2:
        return 0.0
    length = 0.0
    for start, end in zip(coordinates, coordinates[1:]):
        lon1, lat1 = float(start[0]), float(start[1])
        lon2, lat2 = float(end[0]), float(end[1])
        length += _haversine_meters(lon1, lat1, lon2, lat2)
    return float(length)


def _iter_edge_features(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    if not isinstance(features, list):
        return
    for feature in features:
        if isinstance(feature, dict):
            yield feature


def _edge_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for feature in _iter_edge_features(path):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            continue
        if str(geometry.get("type", "")).strip() != "LineString":
            continue
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list):
            continue
        normalized: list[list[float]] = []
        for coord in coordinates:
            if not (isinstance(coord, list) and len(coord) >= 2):
                continue
            normalized.append([float(coord[0]), float(coord[1])])
        if len(normalized) < 2:
            continue
        u = properties.get("u")
        v = properties.get("v")
        if u is None or v is None:
            continue
        u_int = int(u)
        v_int = int(v)
        if u_int == v_int:
            continue
        records.append(
            {
                "u": u_int,
                "v": v_int,
                "length_m": _linestring_length_meters(normalized),
            }
        )
    return records


def _build_weighted_adjacency(edges: list[dict[str, Any]]) -> dict[int, dict[int, float]]:
    adjacency: dict[int, dict[int, float]] = defaultdict(dict)
    for edge in edges:
        u = int(edge["u"])
        v = int(edge["v"])
        length_m = float(edge["length_m"])
        existing = adjacency[u].get(v)
        if existing is None or length_m < existing:
            adjacency[u][v] = length_m
            adjacency[v][u] = length_m
    return dict(adjacency)


def _connected_component_sizes(adjacency: dict[int, dict[int, float]]) -> list[int]:
    unvisited = set(adjacency)
    sizes: list[int] = []
    while unvisited:
        root = min(unvisited)
        queue: deque[int] = deque([root])
        unvisited.remove(root)
        size = 0
        while queue:
            node = queue.popleft()
            size += 1
            for neighbor in adjacency.get(node, {}):
                if neighbor not in unvisited:
                    continue
                unvisited.remove(neighbor)
                queue.append(neighbor)
        sizes.append(size)
    return sorted(sizes, reverse=True)


def _dijkstra_distance(adjacency: dict[int, dict[int, float]], source: int, target: int) -> float | None:
    if source == target:
        return 0.0
    if source not in adjacency or target not in adjacency:
        return None

    frontier: list[tuple[float, int]] = [(0.0, source)]
    best: dict[int, float] = {source: 0.0}
    while frontier:
        distance, node = heapq.heappop(frontier)
        if node == target:
            return distance
        if distance > best.get(node, float("inf")):
            continue
        for neighbor, weight in adjacency.get(node, {}).items():
            candidate = distance + float(weight)
            if candidate >= best.get(neighbor, float("inf")):
                continue
            best[neighbor] = candidate
            heapq.heappush(frontier, (candidate, neighbor))
    return None


def _deterministic_node_pairs(nodes: list[int], max_pairs: int) -> list[tuple[int, int]]:
    if max_pairs <= 0 or len(nodes) < 2:
        return []
    ordered = sorted(set(nodes))
    pairs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    left = 0
    right = len(ordered) - 1
    while left < right and len(pairs) < max_pairs:
        pair = (ordered[left], ordered[right])
        if pair not in seen:
            pairs.append(pair)
            seen.add(pair)
        left += 1
        right -= 1

    index = 0
    while len(pairs) < max_pairs and index + 1 < len(ordered):
        pair = (ordered[index], ordered[index + 1])
        if pair not in seen:
            pairs.append(pair)
            seen.add(pair)
        index += 1

    return pairs


def _graph_summary(edges: list[dict[str, Any]]) -> dict[str, Any]:
    adjacency = _build_weighted_adjacency(edges)
    component_sizes = _connected_component_sizes(adjacency)
    node_count = len(adjacency)
    degree_counts = [len(neighbors) for neighbors in adjacency.values()]
    degree2_nodes = sum(1 for degree in degree_counts if degree == 2)
    branch_nodes = sum(1 for degree in degree_counts if degree >= 3)
    return {
        "edge_count": len(edges),
        "node_count": node_count,
        "total_length_m": float(sum(float(edge["length_m"]) for edge in edges)),
        "component_count": len(component_sizes),
        "largest_component_node_count": int(component_sizes[0]) if component_sizes else 0,
        "largest_component_node_share": float(component_sizes[0] / node_count) if component_sizes and node_count else 0.0,
        "degree2_node_share": float(degree2_nodes / node_count) if node_count else 0.0,
        "branch_node_share": float(branch_nodes / node_count) if node_count else 0.0,
    }


def evaluate_graph_variant_pair(
    raw_edges_path: Path,
    collapsed_edges_path: Path,
    *,
    max_pairs: int = 128,
    ratio_tolerance: float = 0.02,
) -> dict[str, Any]:
    raw_edges = _edge_records(raw_edges_path)
    collapsed_edges = _edge_records(collapsed_edges_path)
    raw_adjacency = _build_weighted_adjacency(raw_edges)
    collapsed_adjacency = _build_weighted_adjacency(collapsed_edges)

    shared_nodes = sorted(set(raw_adjacency) & set(collapsed_adjacency))
    candidate_pairs = _deterministic_node_pairs(shared_nodes, max_pairs=max_pairs)

    ratios: list[float] = []
    shortcut_pairs = 0
    detour_pairs = 0
    raw_reachable_pairs = 0
    collapsed_reachable_pairs = 0
    for source, target in candidate_pairs:
        raw_distance = _dijkstra_distance(raw_adjacency, source, target)
        if raw_distance is None or raw_distance <= 0:
            continue
        raw_reachable_pairs += 1
        collapsed_distance = _dijkstra_distance(collapsed_adjacency, source, target)
        if collapsed_distance is None:
            continue
        collapsed_reachable_pairs += 1
        ratio = float(collapsed_distance / raw_distance)
        ratios.append(ratio)
        if ratio < 1.0 - ratio_tolerance:
            shortcut_pairs += 1
        elif ratio > 1.0 + ratio_tolerance:
            detour_pairs += 1

    reachability_preserved = raw_reachable_pairs == collapsed_reachable_pairs
    path_ratio_min = min(ratios) if ratios else None
    path_ratio_max = max(ratios) if ratios else None
    path_ratio_avg = (sum(ratios) / len(ratios)) if ratios else None

    raw_summary = _graph_summary(raw_edges)
    collapsed_summary = _graph_summary(collapsed_edges)
    raw_edge_count = raw_summary["edge_count"]
    raw_node_count = raw_summary["node_count"]
    edge_reduction_ratio = None
    if raw_edge_count:
        edge_reduction_ratio = float((raw_edge_count - collapsed_summary["edge_count"]) / raw_edge_count)
    node_reduction_ratio = None
    if raw_node_count:
        node_reduction_ratio = float((raw_node_count - collapsed_summary["node_count"]) / raw_node_count)

    return {
        "artifact_scope": "static_osm_country_graph",
        "raw": raw_summary,
        "collapsed": collapsed_summary,
        "comparison": {
            "edge_reduction_ratio": edge_reduction_ratio,
            "node_reduction_ratio": node_reduction_ratio,
            "shared_node_count": len(shared_nodes),
            "sample_pairs_requested": len(candidate_pairs),
            "sample_pairs_evaluated": len(ratios),
            "raw_reachable_sample_pairs": raw_reachable_pairs,
            "collapsed_reachable_sample_pairs": collapsed_reachable_pairs,
            "reachability_preserved_for_sample_pairs": reachability_preserved,
            "shortcut_pairs": shortcut_pairs,
            "detour_pairs": detour_pairs,
            "path_length_ratio_min": path_ratio_min,
            "path_length_ratio_max": path_ratio_max,
            "path_length_ratio_avg": path_ratio_avg,
            "ratio_tolerance": float(ratio_tolerance),
        },
        "inputs": {
            "raw_edges_path": str(raw_edges_path),
            "raw_edges_sha256": _file_sha256(raw_edges_path),
            "collapsed_edges_path": str(collapsed_edges_path),
            "collapsed_edges_sha256": _file_sha256(collapsed_edges_path),
        },
    }
