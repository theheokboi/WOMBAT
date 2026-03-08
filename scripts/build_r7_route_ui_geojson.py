#!/usr/bin/env python3
"""
Build lightweight UI GeoJSON artifacts from full r7 route JSON files.

Output goals:
- no self routes
- no null geometries
- one unordered edge per pair
- simplified and rounded coordinates
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterator


ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts" / "derived"


def _distance_sq(point: list[float], start: list[float], end: list[float]) -> float:
    x0, y0 = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return (x0 - x1) ** 2 + (y0 - y1) ** 2
    t = ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)
    if t <= 0:
        px, py = x1, y1
    elif t >= 1:
        px, py = x2, y2
    else:
        px = x1 + t * dx
        py = y1 + t * dy
    return (x0 - px) ** 2 + (y0 - py) ** 2


def simplify_linestring(points: list[list[float]], tolerance: float) -> list[list[float]]:
    if len(points) <= 2 or tolerance <= 0:
        return points
    keep = [False] * len(points)
    keep[0] = True
    keep[-1] = True
    threshold_sq = tolerance * tolerance
    stack = [(0, len(points) - 1)]
    while stack:
        start_idx, end_idx = stack.pop()
        max_dist_sq = -1.0
        split_idx = None
        start = points[start_idx]
        end = points[end_idx]
        for idx in range(start_idx + 1, end_idx):
            dist_sq = _distance_sq(points[idx], start, end)
            if dist_sq > max_dist_sq:
                max_dist_sq = dist_sq
                split_idx = idx
        if split_idx is not None and max_dist_sq > threshold_sq:
            keep[split_idx] = True
            stack.append((start_idx, split_idx))
            stack.append((split_idx, end_idx))
    return [point for point, should_keep in zip(points, keep) if should_keep]


def round_linestring(points: list[list[float]], precision: int) -> list[list[float]]:
    rounded: list[list[float]] = []
    previous: tuple[float, float] | None = None
    for lon, lat in points:
        current = (round(float(lon), precision), round(float(lat), precision))
        if current == previous:
            continue
        rounded.append([current[0], current[1]])
        previous = current
    if len(rounded) == 1 and points:
        lon, lat = points[-1]
        current = [round(float(lon), precision), round(float(lat), precision)]
        if rounded[0] != current:
            rounded.append(current)
    return rounded


def iter_routes(path: Path) -> Iterator[dict]:
    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8") as handle:
        buffer = ""
        in_routes = False
        eof = False
        while True:
            if not eof:
                chunk = handle.read(65536)
                if chunk:
                    buffer += chunk
                else:
                    eof = True
            if not in_routes:
                marker = '"routes": ['
                idx = buffer.find(marker)
                if idx == -1:
                    if eof:
                        return
                    if len(buffer) > len(marker):
                        buffer = buffer[-len(marker):]
                    continue
                buffer = buffer[idx + len(marker):]
                in_routes = True
            buffer = buffer.lstrip()
            if not buffer:
                if eof:
                    return
                continue
            if buffer[0] == "]":
                return
            if buffer[0] == ",":
                buffer = buffer[1:]
                continue
            try:
                route, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                if eof:
                    raise
                continue
            yield route
            buffer = buffer[end:]


def load_header_metadata(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8").split('"routes": [', 1)[0] + '"routes": []}')
    return {
        "country_code": payload.get("country_code"),
        "source_csv": payload.get("source_csv"),
        "osrm_base": payload.get("osrm_base"),
        "n_points": payload.get("n_points"),
    }


def build_ui_geojson(path: Path, precision: int, tolerance: float) -> Path:
    metadata = load_header_metadata(path)
    features = []
    route_count_total = 0
    route_count_with_geometry = 0
    self_route_count = 0
    null_geometry_count = 0
    reverse_duplicate_count = 0
    coordinate_input_count = 0
    coordinate_output_count = 0
    seen_pairs: dict[tuple[str, str], int] = {}

    for route in iter_routes(path):
        route_count_total += 1
        from_h3 = str(route.get("from_region_h3") or "")
        to_h3 = str(route.get("to_region_h3") or "")
        if from_h3 == to_h3:
            self_route_count += 1
            continue
        geometry = route.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
            null_geometry_count += 1
            continue
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            null_geometry_count += 1
            continue
        route_count_with_geometry += 1
        coordinate_input_count += len(coordinates)
        simplified = simplify_linestring(coordinates, tolerance)
        rounded = round_linestring(simplified, precision)
        if len(rounded) < 2:
            null_geometry_count += 1
            continue
        coordinate_output_count += len(rounded)
        pair = tuple(sorted((from_h3, to_h3)))
        feature = {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": rounded},
            "properties": {
                "country_code": metadata.get("country_code"),
                "from_region_h3": from_h3,
                "to_region_h3": to_h3,
                "distance_m": route.get("distance"),
                "duration_s": route.get("duration"),
            },
        }
        existing_index = seen_pairs.get(pair)
        if existing_index is None:
            seen_pairs[pair] = len(features)
            features.append(feature)
            continue
        reverse_duplicate_count += 1
        current_distance = feature["properties"].get("distance_m")
        existing_distance = features[existing_index]["properties"].get("distance_m")
        if existing_distance is None:
            features[existing_index] = feature
            continue
        if current_distance is not None and float(current_distance) < float(existing_distance):
            features[existing_index] = feature

    out_path = path.with_name(path.name.replace("-routes.json", "-routes-ui.geojson"))
    payload = {
        "type": "FeatureCollection",
        "country_code": metadata.get("country_code"),
        "source_artifact": path.name,
        "source_csv": metadata.get("source_csv"),
        "osrm_base": metadata.get("osrm_base"),
        "n_points": metadata.get("n_points"),
        "route_count_total": route_count_total,
        "route_count_with_geometry": route_count_with_geometry,
        "self_route_count_excluded": self_route_count,
        "null_geometry_count_excluded": null_geometry_count,
        "reverse_duplicate_count_excluded": reverse_duplicate_count,
        "coordinate_input_count": coordinate_input_count,
        "coordinate_output_count": coordinate_output_count,
        "coordinate_precision": precision,
        "simplify_tolerance": tolerance,
        "feature_count": len(features),
        "features": features,
    }
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build lightweight UI GeoJSON from full r7 route JSON artifacts.")
    parser.add_argument(
        "--inputs",
        nargs="*",
        default=[
            str(ARTIFACTS / "2026-03-08-r7-regions-tw-routes.json"),
            str(ARTIFACTS / "2026-03-08-r7-regions-ar-routes.json"),
        ],
        help="Input route JSON files",
    )
    parser.add_argument("--precision", type=int, default=5, help="Coordinate decimal precision")
    parser.add_argument(
        "--simplify-tolerance",
        type=float,
        default=0.01,
        help="Douglas-Peucker tolerance in lon/lat degrees",
    )
    args = parser.parse_args()

    for raw in args.inputs:
        path = Path(raw)
        if not path.exists():
            print(f"Skip {path}: not found")
            continue
        out_path = build_ui_geojson(path, precision=args.precision, tolerance=args.simplify_tolerance)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
