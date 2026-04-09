import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from inframap.config import load_system_config
from inframap.serve.app import create_app


def _write_smoke_run(tmp_path: Path) -> tuple[Path, Path, str]:
    run_id = "20260409T000000Z-smoke"
    runs_root = tmp_path / "runs"
    published_root = tmp_path / "published"
    run_root = runs_root / run_id
    facilities_root = run_root / "canonical"
    layer_root = run_root / "layers" / "country_mask" / "v1"
    reports_root = run_root / "reports"

    facilities_root.mkdir(parents=True, exist_ok=True)
    layer_root.mkdir(parents=True, exist_ok=True)
    reports_root.mkdir(parents=True, exist_ok=True)
    published_root.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "facility_id": "facility-1",
                "org_name": "ExampleNet",
                "source_name": "fixture",
                "lat": 25.033,
                "lon": 121.5654,
                "h3_r7": "87754e64dffffff",
            }
        ]
    ).to_parquet(facilities_root / "facilities.parquet", index=False)

    pd.DataFrame(
        [
            {
                "h3": "82754ffffffffff",
                "layer_value": "1",
                "resolution": 2,
            }
        ]
    ).to_parquet(layer_root / "cells.parquet", index=False)

    (layer_root / "layer_metadata.json").write_text(
        json.dumps(
            {
                "layer_name": "country_mask",
                "layer_version": "v1",
                "params": {"mode": "fixed_resolution", "resolution": 2},
            }
        ),
        encoding="utf-8",
    )
    (reports_root / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "inputs_hash": "inputs",
                "config_hash": "config",
                "code_hash": "code",
            }
        ),
        encoding="utf-8",
    )
    (reports_root / "metrics.json").write_text(
        json.dumps({"facility_count_total": 1, "layer_compute_duration_seconds": {"country_mask": 0.1}}),
        encoding="utf-8",
    )
    (reports_root / "progress.jsonl").write_text(
        json.dumps(
            {
                "ts_utc": "2026-04-09T00:00:00Z",
                "run_id": run_id,
                "stage": "pipeline",
                "status": "complete",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (published_root / "latest-dev").write_text(run_id, encoding="utf-8")
    (published_root / "latest").write_text(run_id, encoding="utf-8")

    return runs_root, published_root, run_id


def test_api_smoke_payloads_are_non_empty(tmp_path: Path) -> None:
    runs_root, published_root, run_id = _write_smoke_run(tmp_path)
    system = load_system_config(Path("configs/system.yaml"))
    system = system.__class__(
        config_version=system.config_version,
        allowed_h3_resolutions=system.allowed_h3_resolutions,
        canonical_h3_resolutions=system.canonical_h3_resolutions,
        country_mask_resolution=system.country_mask_resolution,
        zoom_to_h3_resolution=system.zoom_to_h3_resolution,
        ui=system.ui,
        inputs=list(system.inputs),
        paths=system.paths.__class__(
            runs_root=str(runs_root),
            staging_root=str(tmp_path / "staging"),
            published_root=str(published_root),
        ),
    )
    app = create_app(
        runs_root=runs_root,
        published_root=published_root,
        system_config=system,
    )
    client = TestClient(app)

    latest = client.get("/v1/runs/latest")
    assert latest.status_code == 200
    assert latest.json()["run_id"] == run_id

    status = client.get("/v1/runs/latest/status")
    assert status.status_code == 200
    assert status.json()["metrics"]["facility_count_total"] == 1

    layers = client.get("/v1/layers")
    assert layers.status_code == 200
    assert layers.json()["layers"]

    facilities = client.get("/v1/facilities")
    assert facilities.status_code == 200
    assert facilities.json()["features"]

    cells = client.get("/v1/layers/country_mask/cells")
    assert cells.status_code == 200
    assert cells.json()["features"]
