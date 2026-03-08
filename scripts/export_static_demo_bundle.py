#!/usr/bin/env python3
"""
Export the current UI state as static demo JSON/GeoJSON files.

The output is meant for static hosting of the frontend without the FastAPI backend.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from inframap.config import load_system_config
from inframap.serve.app import create_app


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "frontend" / "demo-data"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def get_json(client: TestClient, path: str) -> dict | None:
    response = client.get(path)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def export_bundle(run_id: str | None, output_dir: Path) -> None:
    os.chdir(REPO_ROOT)
    system = load_system_config(REPO_ROOT / "configs" / "system.yaml")
    app = create_app(
        runs_root=REPO_ROOT / system.paths.runs_root,
        published_root=REPO_ROOT / system.paths.published_root,
        system_config=system,
    )
    client = TestClient(app)

    latest = get_json(client, "/v1/runs/latest")
    effective_run_id = run_id or str((latest or {}).get("run_id") or "").strip()
    if not effective_run_id:
        raise RuntimeError("Unable to determine run_id for static demo export")

    ui_config = get_json(client, "/v1/ui/config")
    runs_catalog = get_json(client, "/v1/runs/catalog") or {"latest_run_id": effective_run_id, "runs": []}
    runs_catalog["latest_run_id"] = effective_run_id
    runs_catalog["runs"] = [
        run for run in (runs_catalog.get("runs") or [])
        if str(run.get("run_id") or "").strip() == effective_run_id
    ]
    if not runs_catalog["runs"]:
        runs_catalog["runs"] = [
            {
                "run_id": effective_run_id,
                "country_mask_mode": None,
                "country_mask_resolution": None,
            }
        ]

    write_json(output_dir / "ui-config.json", ui_config)
    write_json(output_dir / "runs-catalog.json", runs_catalog)

    static_exports = {
        "facilities.json": f"/v1/facilities?limit=50000&run_id={effective_run_id}",
        "country-mask-cells.json": f"/v1/layers/country_mask/cells?run_id={effective_run_id}",
        "facility-density-adaptive-cells.json": (
            f"/v1/layers/facility_density_adaptive/cells?limit=100000&run_id={effective_run_id}"
        ),
        "facility-density-r7-regions-cells.json": (
            f"/v1/layers/facility_density_r7_regions/cells?limit=200000&run_id={effective_run_id}"
        ),
        "facility-density-adaptive-metadata.json": (
            f"/v1/layers/facility_density_adaptive/metadata?run_id={effective_run_id}"
        ),
        "run-status.json": f"/v1/runs/{effective_run_id}/status",
        "active-status.json": "/v1/runs/active/status",
        "calibration-latest.json": "/v1/calibration/latest",
    }
    for filename, endpoint in static_exports.items():
        payload = get_json(client, endpoint)
        if payload is None:
            continue
        write_json(output_dir / filename, payload)

    route_countries: list[str] = []
    for country_code in ["AR", "TW"]:
        payload = get_json(client, f"/v1/r7-region-routes?country={country_code}")
        if payload is None:
            continue
        route_countries.append(country_code)
        write_json(output_dir / f"r7-region-routes-{country_code}.json", payload)

    manifest = {
        "mode": "static-demo",
        "run_id": effective_run_id,
        "route_countries": route_countries,
        "generated_from_latest": (latest or {}).get("run_id") == effective_run_id,
    }
    write_json(output_dir / "manifest.json", manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export static demo JSON/GeoJSON files for the current UI.")
    parser.add_argument("--run-id", default=None, help="Run id to export. Defaults to latest published run.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT), help="Output directory for static demo files.")
    args = parser.parse_args()
    export_bundle(run_id=args.run_id, output_dir=Path(args.output_dir))
    print(Path(args.output_dir))


if __name__ == "__main__":
    main()
