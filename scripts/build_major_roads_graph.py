from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter

import pandas as pd

from inframap.ingest.major_road_graph import build_major_road_graph_variants


_STAGE_LABELS = {
    "collect_shared_nodes": "Collect shared road nodes",
    "build_raw_graph": "Build raw road graph",
    "write_raw": "Write raw graph files",
    "write_collapsed": "Write collapsed graph files",
    "write_adaptive": "Write adaptive graph files",
    "write_adaptive_portal": "Write adaptive portal graph files",
    "write_adaptive_portal_run": "Write adaptive portal run graph files",
}


def _stage_order(variants: tuple[str, ...]) -> list[str]:
    order = ["collect_shared_nodes", "build_raw_graph"]
    for variant in variants:
        order.append(f"write_{variant}")
    return order


def _format_seconds(value: float) -> str:
    total = max(0, int(round(value)))
    minutes, seconds = divmod(total, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _progress_bar(fraction: float, width: int = 28) -> str:
    clamped = min(max(float(fraction), 0.0), 1.0)
    filled = int(round(clamped * width))
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


class ProgressReporter:
    def __init__(self, variants: tuple[str, ...]) -> None:
        self._stages = _stage_order(variants)
        count = len(self._stages)
        if count <= 2:
            self._weights = {stage: 1.0 / count for stage in self._stages}
        else:
            base_weight = 0.8 / 2
            write_weight = 0.2 / (count - 2)
            self._weights = {}
            for stage in self._stages:
                if stage in {"collect_shared_nodes", "build_raw_graph"}:
                    self._weights[stage] = base_weight
                else:
                    self._weights[stage] = write_weight
        self._elapsed = 0.0
        self._completed_weight = 0.0
        self._started = perf_counter()

    def callback(self, event: str, stage: str, payload: dict[str, object]) -> None:
        label = _STAGE_LABELS.get(stage, stage.replace("_", " ").title())
        if event == "phase_start":
            index = self._stages.index(stage) + 1 if stage in self._stages else 0
            print(f"[{index}/{len(self._stages)}] {label}...")
            return
        if event == "phase_end":
            elapsed_stage = float(payload.get("elapsed_seconds", 0.0) or 0.0)
            self._elapsed += max(0.0, elapsed_stage)
            self._completed_weight += self._weights.get(stage, 0.0)
            progress = min(self._completed_weight, 1.0)
            eta = 0.0
            if progress > 0:
                eta = max(0.0, (self._elapsed / progress) - self._elapsed)
            print(
                f"    {_progress_bar(progress)} {progress * 100:5.1f}% | "
                f"elapsed {_format_seconds(self._elapsed)} | eta {_format_seconds(eta)}"
            )
            return
        if event == "done":
            total_elapsed = perf_counter() - self._started
            print(f"    {_progress_bar(1.0)} 100.0% | elapsed {_format_seconds(total_elapsed)} | eta 00:00")


def _default_pbf_path(country_code: str, openstreetmap_root: Path) -> Path:
    country_dir = openstreetmap_root / country_code
    candidates = sorted(country_dir.glob("*.osm.pbf"))
    if not candidates:
        raise FileNotFoundError(f"No .osm.pbf file found under {country_dir}")
    return candidates[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build major-road graph GeoJSON files from an OSM PBF.")
    parser.add_argument("--country", required=True, help="ISO A2 country code (for default input/output paths)")
    parser.add_argument(
        "--openstreetmap-root",
        default="data/openstreetmap",
        help="Root folder containing per-country OSM directories",
    )
    parser.add_argument("--pbf", default=None, help="Path to input .osm.pbf (default: first in country directory)")
    parser.add_argument("--out-dir", default=None, help="Output directory (default: country directory)")
    parser.add_argument(
        "--graph-variant",
        choices=("raw", "collapsed", "adaptive", "adaptive_portal", "adaptive_portal_run", "both"),
        default="both",
        help="Graph output variant to write",
    )
    parser.add_argument(
        "--adaptive-resolution",
        type=int,
        default=6,
        help="Adaptive H3 resolution used when graph_variant includes adaptive",
    )
    parser.add_argument("--run-id", default=None, help="Run ID used for graph_variant=adaptive_portal_run")
    parser.add_argument("--runs-root", default="data/runs", help="Runs root used for run-scoped graph outputs")
    return parser.parse_args()


def _latest_adaptive_mask_cells(run_root: Path) -> tuple[set[str], set[str]]:
    layer_root = run_root / "layers" / "facility_density_adaptive"
    layer_dirs = sorted(path for path in layer_root.glob("*") if path.is_dir())
    if not layer_dirs:
        raise FileNotFoundError(f"No facility_density_adaptive layer directory found under {layer_root}")
    cells_path = layer_dirs[-1] / "cells.parquet"
    if not cells_path.exists():
        raise FileNotFoundError(f"Adaptive mask cells parquet not found: {cells_path}")
    cells = pd.read_parquet(cells_path)
    if "h3" not in cells.columns:
        raise ValueError(f"Adaptive mask cells parquet missing h3 column: {cells_path}")
    mask_cells = {str(cell) for cell in cells["h3"].astype(str).tolist()}
    occupied_cells: set[str] = set()
    if "layer_value" in cells.columns:
        occupied = cells[cells["layer_value"] > 0]
        occupied_cells = {str(cell) for cell in occupied["h3"].astype(str).tolist()}
    return mask_cells, occupied_cells


def main() -> None:
    args = parse_args()
    country_code = str(args.country).strip().upper()
    if len(country_code) != 2 or not country_code.isalpha():
        raise ValueError(f"Invalid country code: {country_code}")

    osm_root = Path(args.openstreetmap_root)
    country_dir = osm_root / country_code
    runs_root = Path(args.runs_root)
    run_id = str(args.run_id).strip() if isinstance(args.run_id, str) and str(args.run_id).strip() else None
    pbf_path = Path(args.pbf) if args.pbf else _default_pbf_path(country_code, osm_root)

    variant_arg = str(args.graph_variant).strip().lower()
    if variant_arg == "both":
        variants = ("raw", "collapsed")
    else:
        variants = (variant_arg,)
    if variant_arg == "adaptive_portal_run" and run_id is None:
        raise ValueError("--run-id is required when --graph-variant=adaptive_portal_run")

    if args.out_dir:
        out_dir = Path(args.out_dir)
    elif variant_arg == "adaptive_portal_run":
        out_dir = runs_root / str(run_id) / "graph" / country_code
    else:
        out_dir = country_dir

    progress = ProgressReporter(variants=variants)
    build_kwargs = {
        "pbf_path": pbf_path,
        "output_dir": out_dir,
        "variants": variants,
        "progress_callback": progress.callback,
    }
    if "adaptive" in variants or "adaptive_portal" in variants:
        build_kwargs["adaptive_resolution"] = int(args.adaptive_resolution)
    if "adaptive_portal_run" in variants:
        adaptive_mask_cells, adaptive_occupied_cells = _latest_adaptive_mask_cells(runs_root / str(run_id))
        build_kwargs["adaptive_mask_cells"] = adaptive_mask_cells
        build_kwargs["adaptive_occupied_cells"] = adaptive_occupied_cells
    outputs = build_major_road_graph_variants(**build_kwargs)
    print(f"country={country_code}")
    print(f"input_pbf={pbf_path}")
    print(f"graph_variant={variant_arg}")
    if "raw" in outputs:
        raw_edges_path, raw_nodes_path = outputs["raw"]
        print(f"edges_geojson={raw_edges_path}")
        print(f"nodes_geojson={raw_nodes_path}")
    if "collapsed" in outputs:
        collapsed_edges_path, collapsed_nodes_path = outputs["collapsed"]
        print(f"edges_geojson_collapsed={collapsed_edges_path}")
        print(f"nodes_geojson_collapsed={collapsed_nodes_path}")
    if "adaptive" in outputs:
        adaptive_edges_path, adaptive_nodes_path = outputs["adaptive"]
        print(f"edges_geojson_adaptive={adaptive_edges_path}")
        print(f"nodes_geojson_adaptive={adaptive_nodes_path}")
    if "adaptive_portal" in outputs:
        adaptive_portal_edges_path, adaptive_portal_nodes_path = outputs["adaptive_portal"]
        print(f"edges_geojson_adaptive_portal={adaptive_portal_edges_path}")
        print(f"nodes_geojson_adaptive_portal={adaptive_portal_nodes_path}")
    if "adaptive_portal_run" in outputs:
        adaptive_portal_run_edges_path, adaptive_portal_run_nodes_path = outputs["adaptive_portal_run"]
        print(f"edges_geojson_adaptive_portal_run={adaptive_portal_run_edges_path}")
        print(f"nodes_geojson_adaptive_portal_run={adaptive_portal_run_nodes_path}")


if __name__ == "__main__":
    main()
