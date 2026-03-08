#!/usr/bin/env python3
"""
Fetch OSRM driving routes between all pairs of r7 region centroids.
Writes distance + geometry to JSON and a distance-only CSV matrix.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path

import requests

OSRM_BASE = os.environ.get("OSRM_BASE", "http://lisa.cs.northwestern.edu:8888")
ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts" / "derived"
PAIR_DELAY = float(os.environ.get("OSRM_DELAY", "0.5"))  # seconds between requests


def load_points(csv_path: Path) -> list[dict]:
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("region_lat"):
                continue
            rows.append(row)
    return rows


def route(session: requests.Session, lon1: float, lat1: float, lon2: float, lat2: float) -> dict | None:
    coords = f"{lon1},{lat1};{lon2},{lat2}"
    url = f"{OSRM_BASE}/route/v1/driving/{coords}"
    resp = session.get(url, params={"geometries": "geojson", "overview": "full"}, timeout=60)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        return None
    r = data["routes"][0]
    return {
        "distance": r["distance"],
        "duration": r["duration"],
        "geometry": r["geometry"],
    }


def run_one(csv_path: Path, out_base: Path) -> None:
    country = csv_path.stem.split("-")[-1].upper()
    points = load_points(csv_path)
    n = len(points)

    routes = []
    dist_rows = [["from_idx", "to_idx", "from_region_h3", "to_region_h3", "distance_m", "duration_s"]]
    session = requests.Session()
    session.headers["User-Agent"] = "h3-experiment-r7-routes/1.0"

    for i in range(n):
        lat_i = float(points[i]["region_lat"])
        lon_i = float(points[i]["region_lon"])
        h3_i = points[i]["region_h3"]

        for j in range(n):
            if i == j:
                routes.append({
                    "from_idx": i,
                    "to_idx": j,
                    "from_region_h3": h3_i,
                    "to_region_h3": h3_i,
                    "distance": 0.0,
                    "duration": 0.0,
                    "geometry": {"type": "LineString", "coordinates": [[lon_i, lat_i]]},
                })
                dist_rows.append([i, j, h3_i, h3_i, 0, 0])
                continue

            lat_j = float(points[j]["region_lat"])
            lon_j = float(points[j]["region_lon"])
            h3_j = points[j]["region_h3"]

            time.sleep(PAIR_DELAY)
            result = route(session, lon_i, lat_i, lon_j, lat_j)
            if result:
                routes.append({
                    "from_idx": i,
                    "to_idx": j,
                    "from_region_h3": h3_i,
                    "to_region_h3": h3_j,
                    "distance": result["distance"],
                    "duration": result["duration"],
                    "geometry": result["geometry"],
                })
                dist_rows.append([i, j, h3_i, h3_j, round(result["distance"], 2), round(result["duration"], 2)])
            else:
                routes.append({
                    "from_idx": i,
                    "to_idx": j,
                    "from_region_h3": h3_i,
                    "to_region_h3": h3_j,
                    "distance": None,
                    "duration": None,
                    "geometry": None,
                })
                dist_rows.append([i, j, h3_i, h3_j, "", ""])
            sys.stderr.write(f"{country} {i}-{j} / {n * n}\n")

    payload = {
        "country_code": country,
        "source_csv": csv_path.name,
        "osrm_base": OSRM_BASE,
        "n_points": n,
        "routes": routes,
    }
    json_path = out_base / f"2026-03-08-r7-regions-{country.lower()}-routes.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    csv_path_out = out_base / f"2026-03-08-r7-regions-{country.lower()}-distances.csv"
    with csv_path_out.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(dist_rows)

    print(f"Wrote {json_path} ({len(routes)} routes)")
    print(f"Wrote {csv_path_out}")


def main() -> None:
    for stub in ["tw", "ar"]:
        csv_path = ARTIFACTS / f"2026-03-08-r7-regions-{stub}.csv"
        if not csv_path.exists():
            print(f"Skip {csv_path}: not found", file=sys.stderr)
            continue
        run_one(csv_path, ARTIFACTS)


if __name__ == "__main__":
    main()
