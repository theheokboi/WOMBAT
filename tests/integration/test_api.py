import json
from pathlib import Path

from fastapi.testclient import TestClient

from inframap.agent.runner import run_pipeline
from inframap.config import load_layers_config, load_system_config
from inframap.serve.app import create_app


def _build_system_with_tmp_paths(tmp_path: Path):
    system = load_system_config(Path("configs/system.yaml"))
    return system.__class__(
        config_version=system.config_version,
        allowed_h3_resolutions=system.allowed_h3_resolutions,
        canonical_h3_resolutions=system.canonical_h3_resolutions,
        country_mask_resolution=system.country_mask_resolution,
        zoom_to_h3_resolution=system.zoom_to_h3_resolution,
        ui=system.ui,
        inputs=list(system.inputs),
        paths=system.paths.__class__(
            runs_root=str(tmp_path / "runs"),
            staging_root=str(tmp_path / "staging"),
            published_root=str(tmp_path / "published"),
        ),
    )


def test_api_endpoints_and_tiles(tmp_path: Path, monkeypatch) -> None:
    system = _build_system_with_tmp_paths(tmp_path)
    layers = load_layers_config(Path("configs/layers.yaml"))
    run_id = run_pipeline(system, layers)

    app = create_app(
        runs_root=Path(system.paths.runs_root),
        published_root=Path(system.paths.published_root),
        system_config=system,
    )
    client = TestClient(app)

    latest = client.get("/v1/runs/latest")
    assert latest.status_code == 200
    assert latest.json()["run_id"] == run_id

    latest_status = client.get("/v1/runs/latest/status")
    assert latest_status.status_code == 200
    latest_status_body = latest_status.json()
    assert latest_status_body["run_id"] == run_id
    assert "runtime_expectations" in latest_status_body
    assert latest_status_body["adaptive_policy"]["layer_version"] == "v3"
    assert latest_status_body["adaptive_policy"]["policy_name"] == "facility_hierarchical_partition_v3"

    active_status = client.get("/v1/runs/active/status")
    assert active_status.status_code == 200
    assert active_status.json()["active"] is False

    calibration_latest_missing = client.get("/v1/calibration/latest")
    assert calibration_latest_missing.status_code == 404
    calibration_world_missing = client.get("/v1/calibration/estimates/world")
    assert calibration_world_missing.status_code == 404

    layers_resp = client.get("/v1/layers")
    assert layers_resp.status_code == 200
    names = {entry["layer_name"] for entry in layers_resp.json()["layers"]}
    assert {"metro_density_core", "country_mask", "facility_density_adaptive"}.issubset(names)

    meta = client.get("/v1/layers/metro_density_core/metadata")
    assert meta.status_code == 200
    assert meta.json()["layer_name"] == "metro_density_core"

    adaptive_meta = client.get("/v1/layers/facility_density_adaptive/metadata")
    assert adaptive_meta.status_code == 200
    adaptive_meta_json = adaptive_meta.json()
    assert adaptive_meta_json["layer_name"] == "facility_density_adaptive"
    assert adaptive_meta_json["layer_version"] == "v3"
    assert adaptive_meta_json["policy_name"] == "facility_hierarchical_partition_v3"
    assert adaptive_meta_json["coverage_domain"] == "country_mask_r4"
    assert adaptive_meta_json["params"]["base_resolution"] == 4
    assert adaptive_meta_json["params"]["empty_compact_min_resolution"] == 0
    assert adaptive_meta_json["params"]["facility_floor_resolution"] == 9
    assert adaptive_meta_json["params"]["facility_max_resolution"] == 13
    assert adaptive_meta_json["params"]["target_facilities_per_leaf"] == 1
    assert adaptive_meta_json["params"]["empty_interior_max_resolution"] == 5
    assert adaptive_meta_json["params"]["empty_refine_boundary_band_k"] == 1
    assert adaptive_meta_json["params"]["empty_refine_near_occupied_k"] == 1
    assert adaptive_meta_json["params"]["max_neighbor_resolution_delta"] == 1

    metro_cells = client.get("/v1/layers/metro_density_core/cells")
    assert metro_cells.status_code == 200
    assert len(metro_cells.json()["features"]) > 0

    country_cells = client.get("/v1/layers/country_mask/cells")
    assert country_cells.status_code == 200
    country_features = country_cells.json()["features"]
    assert len(country_features) > 0
    assert "country_color" in country_features[0]["properties"]

    adaptive_cells_default = client.get("/v1/layers/facility_density_adaptive/cells")
    assert adaptive_cells_default.status_code == 200
    default_features = adaptive_cells_default.json()["features"]
    assert len(default_features) > 0
    assert "preview" not in adaptive_cells_default.json()

    adaptive_cells_fine = client.get("/v1/layers/facility_density_adaptive/cells?split_threshold=1")
    assert adaptive_cells_fine.status_code == 400
    assert "split_threshold preview is deprecated for facility_density_adaptive" in adaptive_cells_fine.json()["detail"]

    facilities = client.get("/v1/facilities")
    assert facilities.status_code == 200
    body = facilities.json()
    assert body["run_id"] == run_id
    assert len(body["features"]) > 0

    tile = client.get("/v1/tiles/2/1/1.mvt")
    assert tile.status_code == 200
    assert len(tile.content) > 0

    health = client.get("/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ui_config = client.get("/v1/ui/config")
    assert ui_config.status_code == 200
    ui_payload = ui_config.json()
    assert isinstance(ui_payload["zoom_to_h3_resolution"], dict)
    assert ui_payload["zoom_to_h3_resolution"]
    assert ui_payload["drilldown_resolution"] in system.allowed_h3_resolutions

    root = client.get("/", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/ui/"

    calibration_dir = tmp_path / "artifacts" / "calibration"
    old_report_dir = calibration_dir / "20260228T010000Z"
    latest_report_dir = calibration_dir / "20260228T020000Z"
    old_report_dir.mkdir(parents=True, exist_ok=True)
    latest_report_dir.mkdir(parents=True, exist_ok=True)
    (old_report_dir / "report.json").write_text(
        json.dumps({"calibration_id": "old", "country": "GB", "runtime_seconds": 10.0, "facility_count_total": 10}),
        encoding="utf-8",
    )
    (latest_report_dir / "report.json").write_text(
        json.dumps({"country": "US", "runtime_seconds": 60.0, "facility_count_total": 100}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    calibration_latest = client.get("/v1/calibration/latest")
    assert calibration_latest.status_code == 200
    calibration_latest_body = calibration_latest.json()
    assert calibration_latest_body["country"] == "US"
    assert calibration_latest_body["calibration_id"] == "20260228T020000Z"

    calibration_world = client.get("/v1/calibration/estimates/world")
    assert calibration_world.status_code == 200
    calibration_world_body = calibration_world.json()
    assert calibration_world_body["calibration_id"] == "20260228T020000Z"
    assert "world_snapshot" in calibration_world_body
    assert "estimate" in calibration_world_body
