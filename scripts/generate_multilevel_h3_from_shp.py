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
        "--refine-levels",
        default="",
        help="Comma-separated refinement resolutions (for example: 3,4,5). Overrides --refine-1/--refine-2 when set.",
    )
    parser.add_argument(
        "--overlap-threshold",
        type=float,
        default=0.15,
        help="Include child when overlap_ratio = area(cell ∩ geometry) / area(cell) is strictly greater than t",
    )
    parser.add_argument(
        "--selection-mode",
        choices=["overlap_threshold", "intersects", "classify_split"],
        default="overlap_threshold",
        help="Child inclusion rule for boundary refinement.",
    )
    parser.add_argument(
        "--base-contain",
        choices=["center", "full", "overlap", "bbox_overlap"],
        default="center",
        help=(
            "Containment mode for initial base-resolution cells. "
            "Uses h3shape_to_cells_experimental unless mode is center."
        ),
    )
    parser.add_argument(
        "--inside-epsilon",
        type=float,
        default=1e-6,
        help="For classify_split mode: ratio >= 1 - epsilon is considered fully inside.",
    )
    parser.add_argument(
        "--outside-epsilon",
        type=float,
        default=1e-9,
        help="For classify_split mode: ratio <= epsilon is considered fully outside.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Progress update interval for refinement loops.",
    )
    parser.add_argument(
        "--max-neighbor-delta",
        type=int,
        default=-1,
        help="Maximum allowed resolution jump across adjacent cells. Set <0 to disable smoothing.",
    )
    parser.add_argument(
        "--smoothing-progress-every",
        type=int,
        default=10,
        help="Progress update interval (iterations) for smoothing loop.",
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


def intersects_geom(cell: str, geom) -> bool:
    poly = cell_polygon(cell)
    if poly.is_empty:
        return False
    return bool(poly.intersects(geom))


def refine_with_threshold(
    leaves: set[str],
    cells_to_refine: set[str],
    next_resolution: int,
    geom,
    threshold: float,
    selection_mode: str,
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
            if selection_mode == "intersects":
                if intersects_geom(child_str, geom):
                    kept_children.append(child_str)
            else:
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


def classify_split_refine(
    *,
    base_cells: set[str],
    refine_levels: list[int],
    geom,
    inside_epsilon: float,
    outside_epsilon: float,
    progress_every: int,
) -> set[str]:
    leaves: set[str] = set()
    current_cells = sorted(base_cells)
    current_resolution = h3.get_resolution(current_cells[0]) if current_cells else None
    started = time.perf_counter()

    for next_resolution in refine_levels:
        if current_resolution is None:
            break
        total = len(current_cells)
        next_cells: list[str] = []
        for index, cell in enumerate(current_cells, start=1):
            ratio = overlap_ratio(cell, geom)
            if ratio >= (1.0 - inside_epsilon):
                leaves.add(cell)
            elif ratio <= outside_epsilon:
                pass
            else:
                for child in sorted(h3.cell_to_children(cell, next_resolution)):
                    next_cells.append(str(child))
            if index % progress_every == 0 or index == total:
                elapsed = time.perf_counter() - started
                rate = index / elapsed if elapsed > 0 else 0.0
                remaining = total - index
                eta = remaining / rate if rate > 0 else 0.0
                print(
                    f"[progress] classify r{current_resolution}->r{next_resolution}: "
                    f"{index}/{total} ({(index/total)*100:.1f}%) elapsed={elapsed:.1f}s eta={eta:.1f}s"
                )
        current_cells = next_cells
        current_resolution = next_resolution

    # Final frontier at max depth: keep cells that are not fully outside.
    if current_cells:
        total = len(current_cells)
        frontier_resolution = h3.get_resolution(current_cells[0])
        for index, cell in enumerate(current_cells, start=1):
            ratio = overlap_ratio(cell, geom)
            if ratio > outside_epsilon:
                leaves.add(cell)
            if index % progress_every == 0 or index == total:
                elapsed = time.perf_counter() - started
                rate = index / elapsed if elapsed > 0 else 0.0
                remaining = total - index
                eta = remaining / rate if rate > 0 else 0.0
                print(
                    f"[progress] classify frontier r{frontier_resolution}: "
                    f"{index}/{total} ({(index/total)*100:.1f}%) elapsed={elapsed:.1f}s eta={eta:.1f}s"
                )
    return leaves


def leaf_covers_point(point_lon: float, point_lat: float, leaves_by_res: dict[int, set[str]]) -> bool:
    for resolution, cells in leaves_by_res.items():
        cell = h3.latlng_to_cell(point_lat, point_lon, resolution)
        if cell in cells:
            return True
    return False


def expand_leaves_to_resolution(leaves: set[str], target_resolution: int) -> set[str]:
    out: set[str] = set()
    for cell in leaves:
        resolution = h3.get_resolution(cell)
        if resolution == target_resolution:
            out.add(cell)
        elif resolution < target_resolution:
            out.update(str(child) for child in h3.cell_to_children(cell, target_resolution))
        else:
            out.add(str(h3.cell_to_parent(cell, target_resolution)))
    return out


def _parent_cell(cell: str, resolution: int, cache: dict[tuple[str, int], str]) -> str:
    key = (cell, resolution)
    cached = cache.get(key)
    if cached is not None:
        return cached
    if h3.get_resolution(cell) == resolution:
        cache[key] = cell
    else:
        cache[key] = h3.cell_to_parent(cell, resolution)
    return cache[key]


def _leaf_sets_by_resolution(leaves: set[str]) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {resolution: set() for resolution in range(16)}
    for cell in leaves:
        out[h3.get_resolution(cell)].add(cell)
    return out


def _covering_leaf_for_neighbor(
    cell: str,
    resolution: int,
    by_resolution: dict[int, set[str]],
    parent_cache: dict[tuple[str, int], str],
) -> tuple[str, int] | None:
    for ancestor_resolution in range(resolution, -1, -1):
        ancestor = _parent_cell(cell, ancestor_resolution, parent_cache)
        if ancestor in by_resolution[ancestor_resolution]:
            return ancestor, ancestor_resolution
    return None


def count_neighbor_delta_violations(leaves: set[str], max_neighbor_delta: int) -> int:
    if max_neighbor_delta < 0 or not leaves:
        return 0
    by_resolution = _leaf_sets_by_resolution(leaves)
    parent_cache: dict[tuple[str, int], str] = {}
    resolution_by_leaf = {cell: h3.get_resolution(cell) for cell in leaves}
    violations = 0
    for cell in sorted(leaves, key=lambda value: (resolution_by_leaf[value], value)):
        resolution = resolution_by_leaf[cell]
        for neighbor in sorted(str(value) for value in h3.grid_disk(cell, 1)):
            if neighbor == cell:
                continue
            covered = _covering_leaf_for_neighbor(neighbor, resolution, by_resolution, parent_cache)
            if covered is None:
                continue
            _, neighbor_resolution = covered
            if abs(resolution - neighbor_resolution) > max_neighbor_delta:
                violations += 1
    return violations


def smooth_neighbor_deltas(
    leaves: set[str],
    max_neighbor_delta: int,
    max_resolution: int,
    progress_every: int,
) -> tuple[set[str], dict[str, int]]:
    if max_neighbor_delta < 0:
        return set(leaves), {"enabled": 0, "iterations": 0, "refined_cells": 0, "violations_after": 0}

    working = set(leaves)
    iterations = 0
    refined_cells = 0
    started = time.perf_counter()

    while True:
        by_resolution = _leaf_sets_by_resolution(working)
        parent_cache: dict[tuple[str, int], str] = {}
        resolution_by_leaf = {cell: h3.get_resolution(cell) for cell in working}
        coarse_candidates: dict[str, int] = {}

        for cell in sorted(working, key=lambda value: (resolution_by_leaf[value], value)):
            resolution = resolution_by_leaf[cell]
            for neighbor in sorted(str(value) for value in h3.grid_disk(cell, 1)):
                if neighbor == cell:
                    continue
                covered = _covering_leaf_for_neighbor(neighbor, resolution, by_resolution, parent_cache)
                if covered is None:
                    continue
                neighbor_leaf, neighbor_resolution = covered
                delta = abs(resolution - neighbor_resolution)
                if delta <= max_neighbor_delta:
                    continue
                if resolution < neighbor_resolution:
                    coarse = cell
                    finer_resolution = neighbor_resolution
                else:
                    coarse = neighbor_leaf
                    finer_resolution = resolution
                required_resolution = finer_resolution - max_neighbor_delta
                current = coarse_candidates.get(coarse)
                if current is None or required_resolution > current:
                    coarse_candidates[coarse] = required_resolution

        if not coarse_candidates:
            break

        iterations += 1
        refined = False
        for coarse in sorted(coarse_candidates, key=lambda value: (h3.get_resolution(value), value)):
            if coarse not in working:
                continue
            coarse_resolution = h3.get_resolution(coarse)
            target_resolution = coarse_candidates[coarse]
            if coarse_resolution >= target_resolution:
                continue
            if coarse_resolution >= max_resolution:
                continue
            working.remove(coarse)
            child_resolution = coarse_resolution + 1
            for child in sorted(h3.cell_to_children(coarse, child_resolution)):
                working.add(str(child))
            refined_cells += 1
            refined = True
            break

        if iterations % max(1, progress_every) == 0:
            elapsed = time.perf_counter() - started
            print(
                f"[progress] smoothing: iter={iterations} refined_cells={refined_cells} "
                f"candidate_count={len(coarse_candidates)} elapsed={elapsed:.1f}s"
            )

        if not refined:
            break

    violations_after = count_neighbor_delta_violations(working, max_neighbor_delta)
    return working, {
        "enabled": 1,
        "iterations": iterations,
        "refined_cells": refined_cells,
        "violations_after": int(violations_after),
    }


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

    if args.refine_levels.strip():
        refine_levels = [int(value.strip()) for value in args.refine_levels.split(",") if value.strip()]
    else:
        refine_levels = [int(args.refine_1), int(args.refine_2)]
    if not refine_levels:
        raise ValueError("At least one refinement resolution is required")
    if any(level <= int(args.base_resolution) for level in refine_levels):
        raise ValueError("All refine levels must be greater than base resolution")
    if refine_levels != sorted(refine_levels):
        raise ValueError("Refine levels must be sorted in ascending order")

    print("[phase] build_base_cells")
    if args.base_contain == "center":
        base_cells = set(h3.geo_to_cells(country_geom.__geo_interface__, args.base_resolution))
    else:
        h3shape = h3.geo_to_h3shape(country_geom.__geo_interface__)
        base_cells = set(
            h3.h3shape_to_cells_experimental(
                h3shape=h3shape,
                res=args.base_resolution,
                contain=args.base_contain,
            )
        )
    leaves = set(base_cells)
    print(f"[info] base_cells={len(base_cells)}")

    if args.selection_mode == "classify_split":
        print("[phase] classify_split_refine")
        leaves = classify_split_refine(
            base_cells=base_cells,
            refine_levels=refine_levels,
            geom=country_geom,
            inside_epsilon=float(args.inside_epsilon),
            outside_epsilon=float(args.outside_epsilon),
            progress_every=max(1, args.progress_every),
        )
    else:
        current_resolution = int(args.base_resolution)
        for next_resolution in refine_levels:
            print(f"[phase] refine_r{current_resolution}_boundary_to_r{next_resolution}")
            candidates = {cell for cell in leaves if h3.get_resolution(cell) == current_resolution}
            boundary = boundary_cells(candidates)
            leaves = refine_with_threshold(
                leaves=leaves,
                cells_to_refine=boundary,
                next_resolution=next_resolution,
                geom=country_geom,
                threshold=args.overlap_threshold,
                selection_mode=args.selection_mode,
                phase_name=f"r{current_resolution}->r{next_resolution}",
                progress_every=max(1, args.progress_every),
            )
            current_resolution = next_resolution

    max_refine_resolution = max(refine_levels)
    print("[phase] smooth_neighbor_deltas")
    leaves, smoothing = smooth_neighbor_deltas(
        leaves=leaves,
        max_neighbor_delta=int(args.max_neighbor_delta),
        max_resolution=max_refine_resolution,
        progress_every=max(1, int(args.smoothing_progress_every)),
    )
    print(
        f"[info] smoothing enabled={smoothing['enabled']} iterations={smoothing['iterations']} "
        f"refined_cells={smoothing['refined_cells']} violations_after={smoothing['violations_after']}"
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
    max_output_resolution = max(refine_levels)
    expanded_to_max = expand_leaves_to_resolution(leaves=leaves, target_resolution=max_output_resolution)

    print("[phase] qa_sampling")
    # Deterministic sample-based uncovered estimate for quick QA.
    import random

    random.seed(0)
    minx, miny, maxx, maxy = country_geom.bounds
    sample_target = 10000
    inside = 0
    uncovered_mixed_lookup = 0
    uncovered_maxres_lookup = 0
    while inside < sample_target:
        lon = minx + (maxx - minx) * random.random()
        lat = miny + (maxy - miny) * random.random()
        point = Point(lon, lat)
        if not country_geom.covers(point):
            continue
        inside += 1
        if not leaf_covers_point(lon, lat, leaves_by_resolution):
            uncovered_mixed_lookup += 1
        if h3.latlng_to_cell(lat, lon, max_output_resolution) not in expanded_to_max:
            uncovered_maxres_lookup += 1

    print("[phase] write_outputs")
    payload = {
        "type": "FeatureCollection",
        "name": f"{args.country_code.lower()}_multilevel_h3",
        "metadata": {
            "source_shapefile": str(shp_path),
            "country": args.country_code,
            "base_resolution": args.base_resolution,
            "base_contain_mode": args.base_contain,
            "refined_resolutions": refine_levels,
            "algorithm": "boundary_refine_with_overlap_threshold_and_parent_fallback",
            "overlap_threshold_t": args.overlap_threshold,
            "selection_mode": args.selection_mode,
            "selection_rule": (
                "split partial cells by overlap ratio; keep full-inside, drop full-outside"
                if args.selection_mode == "classify_split"
                else (
                    "keep child when child_polygon intersects country_polygon"
                    if args.selection_mode == "intersects"
                    else "keep child when overlap_ratio > t"
                )
            ),
            "inside_epsilon": float(args.inside_epsilon),
            "outside_epsilon": float(args.outside_epsilon),
            "max_neighbor_delta": int(args.max_neighbor_delta),
            "neighbor_smoothing": smoothing,
            "coverage_fallback": "keep_parent_if_no_children_selected",
            "cell_count_total": len(features),
            "counts_by_resolution": counts_by_resolution,
            "qa_uncovered_sample_ratio_mixed_lookup": uncovered_mixed_lookup / inside if inside else 0.0,
            "qa_uncovered_sample_ratio_maxres_lookup": uncovered_maxres_lookup / inside if inside else 0.0,
            "qa_max_lookup_resolution": int(max_output_resolution),
            "qa_sample_size": inside,
        },
        "features": features,
    }
    out_geojson.write_text(json.dumps(payload), encoding="utf-8")

    mode_label = (
        "classify-split"
        if args.selection_mode == "classify_split"
        else (
            "intersects"
            if args.selection_mode == "intersects"
            else f"overlap-threshold t={args.overlap_threshold}"
        )
    )
    levels_label = "/".join([f"r{args.base_resolution}"] + [f"r{level}" for level in refine_levels])
    title = (
        f"{args.country_code} geometry + {mode_label} multi-level H3 "
        f"({levels_label}, base={args.base_contain})"
    )
    render_png(country_geom=country_geom, features=features, out_png=out_png, title=title)

    print(f"geojson={out_geojson}")
    print(f"png={out_png}")
    print(f"total_cells={len(features)}")
    print(f"counts_by_resolution={counts_by_resolution}")
    print(f"qa_uncovered_sample_ratio_mixed={payload['metadata']['qa_uncovered_sample_ratio_mixed_lookup']}")
    print(f"qa_uncovered_sample_ratio_maxres={payload['metadata']['qa_uncovered_sample_ratio_maxres_lookup']}")
    print(f"elapsed_total_s={time.perf_counter() - total_started:.1f}")


if __name__ == "__main__":
    main()
