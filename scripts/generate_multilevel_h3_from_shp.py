from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import h3
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon as MplPolygon
import shapefile
from shapely.geometry import Point, Polygon, shape
from shapely.ops import unary_union


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate geometry-only multi-level H3 polygons from a shapefile.")
    parser.add_argument("--shp", required=True, help="Path to .shp file")
    parser.add_argument("--out-geojson", required=True, help="Output GeoJSON path")
    parser.add_argument("--out-png", required=True, help="Output PNG path")
    parser.add_argument("--country-code", default="UNK", help="Country code label for output properties")
    parser.add_argument("--base-resolution", type=int, default=4)
    parser.add_argument("--refine-1", type=int, default=5)
    parser.add_argument("--refine-2", type=int, default=6)
    parser.add_argument(
        "--overlap-threshold",
        type=float,
        default=0.15,
        help="Include child when overlap_ratio = area(cell ∩ geometry) / area(cell) is strictly greater than t",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Progress update interval for refinement loops.",
    )
    return parser.parse_args()


def load_country_geometry(shp_path: Path):
    reader = shapefile.Reader(str(shp_path))
    shapes = reader.shapes()
    if not shapes:
        raise ValueError(f"No shapes found in {shp_path}")
    geoms = [shape(s.__geo_interface__) for s in shapes]
    geom = unary_union(geoms)
    if geom.is_empty:
        raise ValueError(f"Input geometry is empty for {shp_path}")
    return geom


def boundary_cells(cells: set[str]) -> set[str]:
    out: set[str] = set()
    for cell in cells:
        for neighbor in h3.grid_disk(cell, 1):
            if neighbor == cell:
                continue
            if h3.get_resolution(neighbor) != h3.get_resolution(cell):
                continue
            if neighbor not in cells:
                out.add(cell)
                break
    return out


def cell_polygon(cell: str) -> Polygon:
    ring = []
    prev_lon = None
    for lat, lon in h3.cell_to_boundary(cell):
        adj_lon = float(lon)
        if prev_lon is not None:
            while adj_lon - prev_lon > 180:
                adj_lon -= 360
            while adj_lon - prev_lon < -180:
                adj_lon += 360
        ring.append((adj_lon, float(lat)))
        prev_lon = adj_lon
    ring.append(ring[0])
    return Polygon(ring)


def overlap_ratio(cell: str, geom) -> float:
    poly = cell_polygon(cell)
    if poly.is_empty or poly.area == 0:
        return 0.0
    inter_area = poly.intersection(geom).area
    return float(inter_area / poly.area)


def refine_with_threshold(
    leaves: set[str],
    cells_to_refine: set[str],
    next_resolution: int,
    geom,
    threshold: float,
    phase_name: str,
    progress_every: int,
) -> set[str]:
    next_leaves = set(leaves)
    ordered = sorted(cells_to_refine)
    total = len(ordered)
    started = time.perf_counter()
    for index, parent in enumerate(ordered, start=1):
        if parent not in next_leaves:
            continue
        next_leaves.remove(parent)
        kept_children: list[str] = []
        for child in sorted(h3.cell_to_children(parent, next_resolution)):
            child_str = str(child)
            ratio = overlap_ratio(child_str, geom)
            if ratio > threshold:
                kept_children.append(child_str)
        # Coverage-preserving fallback: if threshold drops all children, keep parent.
        if not kept_children:
            next_leaves.add(parent)
        else:
            next_leaves.update(kept_children)
        if index % progress_every == 0 or index == total:
            elapsed = time.perf_counter() - started
            rate = index / elapsed if elapsed > 0 else 0.0
            remaining = total - index
            eta = remaining / rate if rate > 0 else 0.0
            print(
                f"[progress] {phase_name}: {index}/{total} ({(index/total)*100:.1f}%) "
                f"elapsed={elapsed:.1f}s eta={eta:.1f}s"
            )
    return next_leaves


def leaf_covers_point(point_lon: float, point_lat: float, leaves_by_res: dict[int, set[str]]) -> bool:
    for resolution, cells in leaves_by_res.items():
        cell = h3.latlng_to_cell(point_lat, point_lon, resolution)
        if cell in cells:
            return True
    return False


def build_features(leaves: set[str], country_code: str) -> list[dict]:
    features: list[dict] = []
    for cell in sorted(leaves, key=lambda value: (h3.get_resolution(value), value)):
        ring = []
        prev_lon = None
        for lat, lon in h3.cell_to_boundary(cell):
            adj_lon = float(lon)
            if prev_lon is not None:
                while adj_lon - prev_lon > 180:
                    adj_lon -= 360
                while adj_lon - prev_lon < -180:
                    adj_lon += 360
            ring.append([adj_lon, float(lat)])
            prev_lon = adj_lon
        ring.append(ring[0])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {
                    "h3": cell,
                    "resolution": h3.get_resolution(cell),
                    "layer_value": country_code,
                    "method": "geometry_only_overlap_threshold_refine",
                },
            }
        )
    return features


def render_png(country_geom, features: list[dict], out_png: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 10), dpi=220)

    parts = list(country_geom.geoms) if hasattr(country_geom, "geoms") else [country_geom]
    for poly in parts:
        x, y = poly.exterior.xy
        ax.plot(x, y, color="black", linewidth=1.0, zorder=3)

    color_map = {4: "#93c5fd", 5: "#60a5fa", 6: "#1d4ed8", 7: "#1e3a8a", 8: "#1e40af", 9: "#1e429f"}
    patches: list[MplPolygon] = []
    facecolors: list[str] = []
    for feature in features:
        coords = feature["geometry"]["coordinates"][0]
        patches.append(MplPolygon(coords, closed=True))
        facecolors.append(color_map.get(int(feature["properties"]["resolution"]), "#3b82f6"))

    pc = PatchCollection(patches, facecolor=facecolors, edgecolor="white", linewidth=0.08, alpha=0.75, zorder=2)
    ax.add_collection(pc)

    minx, miny, maxx, maxy = country_geom.bounds
    padx = (maxx - minx) * 0.05
    pady = (maxy - miny) * 0.05
    ax.set_xlim(minx - padx, maxx + padx)
    ax.set_ylim(miny - pady, maxy + pady)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    legend_res = sorted({int(f["properties"]["resolution"]) for f in features})
    legend_items = [mpatches.Patch(color=color_map.get(r, "#3b82f6"), label=f"H3 r{r}") for r in legend_res]
    ax.legend(handles=legend_items, loc="lower left")
    plt.tight_layout()
    fig.savefig(out_png)


def main() -> None:
    total_started = time.perf_counter()
    args = parse_args()
    shp_path = Path(args.shp)
    out_geojson = Path(args.out_geojson)
    out_png = Path(args.out_png)
    out_geojson.parent.mkdir(parents=True, exist_ok=True)
    out_png.parent.mkdir(parents=True, exist_ok=True)

    print("[phase] load_geometry")
    country_geom = load_country_geometry(shp_path)

    print("[phase] build_base_cells")
    base_cells = set(h3.geo_to_cells(country_geom.__geo_interface__, args.base_resolution))
    leaves = set(base_cells)
    print(f"[info] base_cells={len(base_cells)}")

    print("[phase] refine_r4_boundary_to_r5")
    r4_boundary = boundary_cells(base_cells)
    leaves = refine_with_threshold(
        leaves=leaves,
        cells_to_refine=r4_boundary,
        next_resolution=args.refine_1,
        geom=country_geom,
        threshold=args.overlap_threshold,
        phase_name="r4->r5",
        progress_every=max(1, args.progress_every),
    )

    print("[phase] refine_r5_boundary_to_r6")
    r5_candidates = {cell for cell in leaves if h3.get_resolution(cell) == args.refine_1}
    r5_boundary = boundary_cells(r5_candidates)
    leaves = refine_with_threshold(
        leaves=leaves,
        cells_to_refine=r5_boundary,
        next_resolution=args.refine_2,
        geom=country_geom,
        threshold=args.overlap_threshold,
        phase_name="r5->r6",
        progress_every=max(1, args.progress_every),
    )

    print("[phase] build_features")
    features = build_features(leaves=leaves, country_code=args.country_code)
    counts_by_resolution = {
        str(resolution): sum(1 for feature in features if int(feature["properties"]["resolution"]) == resolution)
        for resolution in sorted({int(feature["properties"]["resolution"]) for feature in features})
    }

    leaves_by_resolution: dict[int, set[str]] = {}
    for feature in features:
        cell = str(feature["properties"]["h3"])
        resolution = int(feature["properties"]["resolution"])
        leaves_by_resolution.setdefault(resolution, set()).add(cell)

    print("[phase] qa_sampling")
    # Deterministic sample-based uncovered estimate for quick QA.
    import random

    random.seed(0)
    minx, miny, maxx, maxy = country_geom.bounds
    sample_target = 10000
    inside = 0
    uncovered = 0
    while inside < sample_target:
        lon = minx + (maxx - minx) * random.random()
        lat = miny + (maxy - miny) * random.random()
        point = Point(lon, lat)
        if not country_geom.covers(point):
            continue
        inside += 1
        if not leaf_covers_point(lon, lat, leaves_by_resolution):
            uncovered += 1

    print("[phase] write_outputs")
    payload = {
        "type": "FeatureCollection",
        "name": f"{args.country_code.lower()}_multilevel_h3",
        "metadata": {
            "source_shapefile": str(shp_path),
            "country": args.country_code,
            "base_resolution": args.base_resolution,
            "refined_resolutions": [args.refine_1, args.refine_2],
            "algorithm": "boundary_refine_with_overlap_threshold_and_parent_fallback",
            "overlap_threshold_t": args.overlap_threshold,
            "selection_rule": "keep child when overlap_ratio > t",
            "coverage_fallback": "keep_parent_if_no_children_selected",
            "cell_count_total": len(features),
            "counts_by_resolution": counts_by_resolution,
            "qa_uncovered_sample_ratio": uncovered / inside if inside else 0.0,
            "qa_sample_size": inside,
        },
        "features": features,
    }
    out_geojson.write_text(json.dumps(payload), encoding="utf-8")

    title = (
        f"{args.country_code} geometry + overlap-threshold multi-level H3 "
        f"(r{args.base_resolution}/r{args.refine_1}/r{args.refine_2}, t={args.overlap_threshold})"
    )
    render_png(country_geom=country_geom, features=features, out_png=out_png, title=title)

    print(f"geojson={out_geojson}")
    print(f"png={out_png}")
    print(f"total_cells={len(features)}")
    print(f"counts_by_resolution={counts_by_resolution}")
    print(f"qa_uncovered_sample_ratio={payload['metadata']['qa_uncovered_sample_ratio']}")
    print(f"elapsed_total_s={time.perf_counter() - total_started:.1f}")


if __name__ == "__main__":
    main()
