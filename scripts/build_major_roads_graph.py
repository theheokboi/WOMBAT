from __future__ import annotations

import argparse
from pathlib import Path

from inframap.ingest.major_road_graph import build_major_road_graph_variants


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
        choices=("raw", "collapsed", "both"),
        default="both",
        help="Graph output variant to write",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    country_code = str(args.country).strip().upper()
    if len(country_code) != 2 or not country_code.isalpha():
        raise ValueError(f"Invalid country code: {country_code}")

    osm_root = Path(args.openstreetmap_root)
    country_dir = osm_root / country_code
    pbf_path = Path(args.pbf) if args.pbf else _default_pbf_path(country_code, osm_root)
    out_dir = Path(args.out_dir) if args.out_dir else country_dir

    variant_arg = str(args.graph_variant).strip().lower()
    if variant_arg == "both":
        variants = ("raw", "collapsed")
    else:
        variants = (variant_arg,)
    outputs = build_major_road_graph_variants(pbf_path=pbf_path, output_dir=out_dir, variants=variants)
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


if __name__ == "__main__":
    main()
