from __future__ import annotations

import json
from pathlib import Path

import h3
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon as MplPolygon
import pandas as pd
import shapefile
from shapely.geometry import Point, shape
from shapely.ops import unary_union

from inframap.config import load_layers_config
from inframap.layers.facility_density_adaptive import FacilityDensityAdaptiveLayer


def _cell_ring(cell: str) -> list[list[float]]:
    ring: list[list[float]] = []
    prev_lon: float | None = None
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
    return ring


def main() -> None:
    repo = Path("/Users/hyes92121/Desktop/h3-experiment")
    shp_path = repo / "archive/data/gadm41_ARG_shp-20260304T181253Z/gadm41_ARG_0.shp"
    input_tsv = repo / "data/facilities/peeringdb_facility.tsv"
    out_geojson = repo / "artifacts/derived/2026-03-04-arg-facility-density-adaptive.geojson"
    out_png = repo / "artifacts/screenshots/2026-03-04-arg-facility-density-adaptive.png"
    out_geojson.parent.mkdir(parents=True, exist_ok=True)
    out_png.parent.mkdir(parents=True, exist_ok=True)

    country_geom = unary_union([shape(s.__geo_interface__) for s in shapefile.Reader(str(shp_path)).shapes()])

    raw = pd.read_csv(input_tsv, sep="\t")
    valid = raw[raw["latitude"].notna() & raw["longitude"].notna()].copy()
    inside_mask = valid.apply(
        lambda row: country_geom.covers(Point(float(row["longitude"]), float(row["latitude"]))),
        axis=1,
    )
    facilities_arg = valid[inside_mask].copy()
    facilities_arg = facilities_arg.rename(columns={"latitude": "lat", "longitude": "lon"})
    facilities_arg["asof_date"] = "2026-03-04"
    facilities_arg = facilities_arg[["lat", "lon", "asof_date"]].reset_index(drop=True)

    # r4 country domain derived from AR polygon overlap to avoid border under-coverage.
    h3shape = h3.geo_to_h3shape(country_geom.__geo_interface__)
    domain_r4 = sorted(
        str(cell)
        for cell in h3.h3shape_to_cells_experimental(
            h3shape=h3shape,
            res=4,
            contain="overlap",
        )
    )
    country_cells = (
        pd.DataFrame({"h3": domain_r4})
        .assign(resolution=4, layer_value="AR", country_name="Argentina")
        .sort_values("h3")
        .reset_index(drop=True)
    )

    layers_cfg = load_layers_config(repo / "configs/layers.yaml")
    adaptive_cfg = next(layer for layer in layers_cfg.layers if layer.name == "facility_density_adaptive")
    adaptive = FacilityDensityAdaptiveLayer(version=adaptive_cfg.version)
    metadata, cells = adaptive.compute(
        canonical_store={"facilities": facilities_arg},
        layer_store={"country_mask": {"metadata": {"layer_name": "country_mask", "layer_version": "v1"}, "cells": country_cells}},
        params=dict(adaptive_cfg.params),
    )
    adaptive.validate({"metadata": metadata, "cells": cells})

    features = []
    for _, row in cells.sort_values(["resolution", "h3"]).iterrows():
        cell = str(row["h3"])
        resolution = int(row["resolution"])
        value = int(row["layer_value"])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [_cell_ring(cell)]},
                "properties": {"h3": cell, "resolution": resolution, "layer_value": value, "layer_name": "facility_density_adaptive"},
            }
        )

    payload = {
        "type": "FeatureCollection",
        "name": "arg_facility_density_adaptive",
        "metadata": {
            "source_shapefile": str(shp_path),
            "input_rows_total": int(len(raw)),
            "arg_facility_points": int(len(facilities_arg)),
            "adaptive_metadata": metadata,
            "cell_count_total": int(len(features)),
            "counts_by_resolution": {
                str(int(r)): int(c)
                for r, c in cells["resolution"].value_counts(sort=False).sort_index().to_dict().items()
            },
        },
        "features": features,
    }
    out_geojson.write_text(json.dumps(payload), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(10, 10), dpi=220)
    parts = list(country_geom.geoms) if hasattr(country_geom, "geoms") else [country_geom]
    for poly in parts:
        x, y = poly.exterior.xy
        ax.plot(x, y, color="black", linewidth=1.0, zorder=3)

    color_map = {4: "#93c5fd", 5: "#60a5fa", 6: "#3b82f6", 7: "#2563eb", 8: "#1d4ed8", 9: "#1e3a8a"}
    patches: list[MplPolygon] = []
    facecolors: list[str] = []
    for feature in features:
        resolution = int(feature["properties"]["resolution"])
        patches.append(MplPolygon(feature["geometry"]["coordinates"][0], closed=True))
        facecolors.append(color_map.get(resolution, "#1e40af"))
    pc = PatchCollection(patches, facecolor=facecolors, edgecolor="white", linewidth=0.07, alpha=0.75, zorder=2)
    ax.add_collection(pc)

    # facility points
    if not facilities_arg.empty:
        ax.scatter(
            facilities_arg["lon"].astype(float).tolist(),
            facilities_arg["lat"].astype(float).tolist(),
            s=8,
            c="#111827",
            alpha=0.9,
            label="Facilities",
            zorder=4,
        )

    minx, miny, maxx, maxy = country_geom.bounds
    padx = (maxx - minx) * 0.05
    pady = (maxy - miny) * 0.05
    ax.set_xlim(minx - padx, maxx + padx)
    ax.set_ylim(miny - pady, maxy + pady)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title("ARG facility_density_adaptive (AR-scoped)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    plt.tight_layout()
    fig.savefig(out_png)

    print(f"geojson={out_geojson}")
    print(f"png={out_png}")
    print(f"arg_facility_points={len(facilities_arg)}")
    print(f"adaptive_cells={len(features)}")


if __name__ == "__main__":
    main()
