from __future__ import annotations

import argparse
import json
from pathlib import Path

from inframap.ingest.major_road_graph_eval import evaluate_graph_variant_pair


def _default_edges_paths(country_code: str, openstreetmap_root: Path) -> tuple[Path, Path]:
    country_dir = openstreetmap_root / country_code
    raw_edges = country_dir / "major_roads_edges.geojson"
    collapsed_edges = country_dir / "major_roads_edges_collapsed.geojson"
    return raw_edges, collapsed_edges


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate raw vs collapsed major-road graph variants for corridor-proxy plausibility."
    )
    parser.add_argument("--country", required=True, help="ISO A2 country code")
    parser.add_argument(
        "--openstreetmap-root",
        default="data/openstreetmap",
        help="Root folder containing per-country OSM graph directories",
    )
    parser.add_argument("--raw-edges", default=None, help="Path to raw edge GeoJSON")
    parser.add_argument("--collapsed-edges", default=None, help="Path to collapsed edge GeoJSON")
    parser.add_argument("--max-pairs", type=int, default=128, help="Maximum sampled node pairs for path comparison")
    parser.add_argument(
        "--ratio-tolerance",
        type=float,
        default=0.02,
        help="Allowed path-length ratio drift before counting shortcut/detour",
    )
    parser.add_argument("--out", default=None, help="Optional output JSON report path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    country_code = str(args.country).strip().upper()
    if len(country_code) != 2 or not country_code.isalpha():
        raise ValueError(f"Invalid country code: {country_code}")

    osm_root = Path(args.openstreetmap_root)
    raw_default, collapsed_default = _default_edges_paths(country_code, osm_root)
    raw_edges_path = Path(args.raw_edges) if args.raw_edges else raw_default
    collapsed_edges_path = Path(args.collapsed_edges) if args.collapsed_edges else collapsed_default

    if not raw_edges_path.exists():
        raise FileNotFoundError(f"Raw edges file not found: {raw_edges_path}")
    if not collapsed_edges_path.exists():
        raise FileNotFoundError(f"Collapsed edges file not found: {collapsed_edges_path}")
    if args.max_pairs < 1:
        raise ValueError("--max-pairs must be >= 1")
    if args.ratio_tolerance < 0:
        raise ValueError("--ratio-tolerance must be >= 0")

    report = evaluate_graph_variant_pair(
        raw_edges_path=raw_edges_path,
        collapsed_edges_path=collapsed_edges_path,
        max_pairs=int(args.max_pairs),
        ratio_tolerance=float(args.ratio_tolerance),
    )
    report["country"] = country_code

    print(f"country={country_code}")
    print(f"raw_edges={raw_edges_path}")
    print(f"collapsed_edges={collapsed_edges_path}")
    print(f"sample_pairs_evaluated={report['comparison']['sample_pairs_evaluated']}")
    print(f"shortcut_pairs={report['comparison']['shortcut_pairs']}")
    print(f"detour_pairs={report['comparison']['detour_pairs']}")

    report_json = json.dumps(report, ensure_ascii=True, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_json + "\n", encoding="utf-8")
        print(f"report_json={out_path}")
    else:
        print(report_json)


if __name__ == "__main__":
    main()
