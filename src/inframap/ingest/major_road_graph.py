from __future__ import annotations

import json
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Literal

import h3
import osmium


MAJOR_HIGHWAY_CLASSES = {"motorway", "trunk", "motorway_link", "trunk_link"}
RAW_EDGE_FILENAME = "major_roads_edges.geojson"
RAW_NODE_FILENAME = "major_roads_nodes.geojson"
COLLAPSED_EDGE_FILENAME = "major_roads_edges_collapsed.geojson"
COLLAPSED_NODE_FILENAME = "major_roads_nodes_collapsed.geojson"
ADAPTIVE_EDGE_FILENAME = "major_roads_edges_adaptive.geojson"
ADAPTIVE_NODE_FILENAME = "major_roads_nodes_adaptive.geojson"
GraphVariant = Literal["raw", "collapsed", "adaptive"]
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


def contract_degree2_undirected_edges(
    edges: list[dict[str, object]],
    protected_nodes: set[int] | None = None,
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
            if _edge_merge_key(first) != _edge_merge_key(second):
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


def _variant_filenames(variant: GraphVariant) -> tuple[str, str]:
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

    requested = tuple(dict.fromkeys(variants))
    if "adaptive" in requested and adaptive_resolution is None:
        raise ValueError("adaptive_resolution is required when adaptive graph variant is requested")

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

    notify("done", "complete", {"output_count": len(outputs)})
    return outputs


def build_major_road_graph(pbf_path: Path, output_dir: Path) -> tuple[Path, Path]:
    outputs = build_major_road_graph_variants(pbf_path=pbf_path, output_dir=output_dir, variants=("raw",))
    return outputs["raw"]
