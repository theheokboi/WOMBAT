import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from inframap.agent.runner import run_pipeline
from inframap.config import load_layers_config, load_system_config
from inframap.serve.app import create_app

pytestmark = pytest.mark.skip(
    reason="Full pipeline run integration test disabled until polygon contract is finalized."
)


def _write_tw_input_fixture(tmp_path: Path) -> Path:
    fixture_path = tmp_path / "facilities_tw.csv"
    fixture_path.write_text(
        "\n".join(
            [
                "ORGANIZATION,NODE_NAME,LATITUDE,LONGITUDE,SOURCE,ASOF_DATE,COUNTRY",
                "ExampleNet,Taipei-1,25.0330,121.5654,fixture,2026-02-28,TW",
                "ExampleNet,Taipei-2,25.0478,121.5319,fixture,2026-02-28,TW",
                "ExampleNet,Kaohsiung-1,22.6273,120.3014,fixture,2026-02-28,TW",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return fixture_path


def _write_tw_only_polygon_dataset(tmp_path: Path) -> Path:
    source_path = Path("data/countries/TW.geojson")
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    features = []
    for feature in payload.get("features", []):
        properties = feature.get("properties", {})
        features.append(
            {
                "type": "Feature",
                "properties": {"iso_a2": "TW", "name": str(properties.get("COUNTRY", "TW"))},
                "geometry": feature["geometry"],
            }
        )
    payload["features"] = features
    out_path = tmp_path / "tw_only_admin0.geojson"
    out_path.write_text(json.dumps(payload), encoding="utf-8")
    return out_path


def _build_system_with_tmp_paths(tmp_path: Path, input_path: Path):
    system = load_system_config(Path("configs/system.yaml"))
    return system.__class__(
        config_version=system.config_version,
        allowed_h3_resolutions=system.allowed_h3_resolutions,
        canonical_h3_resolutions=system.canonical_h3_resolutions,
        country_mask_resolution=system.country_mask_resolution,
        zoom_to_h3_resolution=system.zoom_to_h3_resolution,
        ui=system.ui,
        inputs=[system.inputs[0].__class__(path=str(input_path), source_name="fixture")],
        paths=system.paths.__class__(
            runs_root=str(tmp_path / "runs"),
            staging_root=str(tmp_path / "staging"),
            published_root=str(tmp_path / "published"),
        ),
    )


def _build_layers_with_tw_scope(tw_polygon_path: Path):
    layers = load_layers_config(Path("configs/layers.yaml"))
    updated_layers = []
    for layer in layers.layers:
        if layer.name != "country_mask":
            updated_layers.append(layer)
            continue
        params = dict(layer.params)
        params["polygon_dataset"] = str(tw_polygon_path)
        params.pop("polygon_dataset_dir", None)
        params.pop("include_iso_a2", None)
        params["exclude_iso_a2"] = []
        updated_layers.append(layer.__class__(name=layer.name, plugin=layer.plugin, version=layer.version, params=params))
    return layers.__class__(layers_version=layers.layers_version, layers=updated_layers)


def test_api_endpoints_and_tiles(tmp_path: Path, monkeypatch) -> None:
    tw_fixture = _write_tw_input_fixture(tmp_path)
    tw_polygons = _write_tw_only_polygon_dataset(tmp_path)
    system = _build_system_with_tmp_paths(tmp_path, input_path=tw_fixture)
    layers = _build_layers_with_tw_scope(tw_polygon_path=tw_polygons)
    run_id = run_pipeline(system, layers)
    published_root = Path(system.paths.published_root)
    assert (published_root / "latest-dev").read_text(encoding="utf-8").strip() == run_id
    assert (published_root / "latest").read_text(encoding="utf-8").strip() == run_id

    adaptive_metadata_path = (
        Path(system.paths.runs_root)
        / run_id
        / "layers"
        / "facility_density_adaptive"
        / "v3"
        / "layer_metadata.json"
    )
    adaptive_metadata = json.loads(adaptive_metadata_path.read_text(encoding="utf-8"))
    adaptive_metadata["adaptive_counters"] = {
        "adjacency_checks": 12,
        "adjacency_violations": 2,
        "adjacency_violation_samples": [
            "872664c28ffffff@r7<->892664c28a3ffff@r9 (delta=2)",
        ],
    }
    adaptive_metadata_path.write_text(json.dumps(adaptive_metadata, sort_keys=True, indent=2), encoding="utf-8")

    app = create_app(
        runs_root=Path(system.paths.runs_root),
        published_root=Path(system.paths.published_root),
        system_config=system,
    )
    client = TestClient(app)
    monkeypatch.chdir(tmp_path)

    latest = client.get("/v1/runs/latest")
    assert latest.status_code == 200
    latest_body = latest.json()
    assert latest_body["run_id"] == run_id
    assert latest_body["pointer"] == "latest-dev"
    assert latest_body["lane"] == "dev"
    assert latest_body["inputs_hash"]
    assert latest_body["config_hash"]
    assert latest_body["code_hash"]

    latest_status = client.get("/v1/runs/latest/status")
    assert latest_status.status_code == 200
    latest_status_body = latest_status.json()
    assert latest_status_body["run_id"] == run_id
    assert latest_status_body["pointer"] == "latest-dev"
    assert latest_status_body["lane"] == "dev"
    assert "runtime_expectations" in latest_status_body
    assert latest_status_body["metrics"]["facility_count_total"] > 0
    assert latest_status_body["latest_progress_event"] is not None
    assert latest_status_body["latest_progress_event"]["status"] == "complete"
    assert latest_status_body["latest_progress_event"]["stage"] == "pipeline"
    assert latest_status_body["adaptive_policy"]["layer_version"] == "v3"
    assert latest_status_body["adaptive_policy"]["policy_name"] == "facility_hierarchical_partition_v3"
    assert latest_status_body["adaptive_policy"]["adjacency_health"]["status"] == "violations_detected"
    assert latest_status_body["adaptive_policy"]["adjacency_health"]["adjacency_checks"] == 12
    assert latest_status_body["adaptive_policy"]["adjacency_health"]["adjacency_violations"] == 2
    assert latest_status_body["adaptive_policy"]["adjacency_health"]["violation_rate"] == pytest.approx(2 / 12)
    assert latest_status_body["adaptive_policy"]["adjacency_health"]["sample"] == [
        "872664c28ffffff@r7<->892664c28a3ffff@r9 (delta=2)"
    ]

    active_status = client.get("/v1/runs/active/status")
    assert active_status.status_code == 200
    active_status_body = active_status.json()
    assert active_status_body["active"] is False
    assert "runtime_expectations" in active_status_body

    staging_root = Path(system.paths.staging_root)
    staging_progress_dir = staging_root / run_id / "reports"
    staging_progress_dir.mkdir(parents=True, exist_ok=True)
    (staging_progress_dir / "progress.jsonl").write_text(
        json.dumps(
            {
                "ts_utc": "2026-03-04T00:00:00Z",
                "run_id": run_id,
                "stage": "invariants",
                "status": "in_progress",
                "elapsed_s": 42.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (staging_root / "active_run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "in_progress",
                "stage": "invariants",
                "elapsed_s": 42.0,
                "ts_utc": "2026-03-04T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    active_status_live = client.get("/v1/runs/active/status")
    assert active_status_live.status_code == 200
    active_status_live_body = active_status_live.json()
    assert active_status_live_body["active"] is True
    assert active_status_live_body["active_status"]["run_id"] == run_id
    assert active_status_live_body["active_status"]["stage"] == "invariants"
    assert active_status_live_body["latest_progress_event"] is not None
    assert active_status_live_body["latest_progress_event"]["stage"] == "invariants"
    assert "not yet published" in active_status_live_body["published_note"]

    calibration_latest_missing = client.get("/v1/calibration/latest")
    assert calibration_latest_missing.status_code == 404
    calibration_tw_missing = client.get("/v1/calibration/estimates/gb")
    assert calibration_tw_missing.status_code == 404
    calibration_world_missing = client.get("/v1/calibration/estimates/world")
    assert calibration_world_missing.status_code == 404

    layers_resp = client.get("/v1/layers")
    assert layers_resp.status_code == 200
    names = {entry["layer_name"] for entry in layers_resp.json()["layers"]}
    assert {
        "metro_density_core",
        "country_mask",
        "facility_density_adaptive",
        "facility_density_r7_regions",
    }.issubset(names)

    meta = client.get("/v1/layers/metro_density_core/metadata")
    assert meta.status_code == 200
    assert meta.json()["layer_name"] == "metro_density_core"

    adaptive_meta = client.get("/v1/layers/facility_density_adaptive/metadata")
    assert adaptive_meta.status_code == 200
    adaptive_meta_json = adaptive_meta.json()
    assert adaptive_meta_json["layer_name"] == "facility_density_adaptive"
    assert adaptive_meta_json["layer_version"] == "v3"
    assert adaptive_meta_json["policy_name"] == "facility_hierarchical_partition_v3"
    assert adaptive_meta_json["coverage_domain"] == "country_mask_r2"
    assert adaptive_meta_json["params"]["base_resolution"] == 2
    assert adaptive_meta_json["params"]["empty_compact_min_resolution"] == 0
    assert adaptive_meta_json["params"]["facility_floor_resolution"] == 7
    assert adaptive_meta_json["params"]["facility_max_resolution"] == 7
    assert adaptive_meta_json["params"]["target_facilities_per_leaf"] == 1
    assert adaptive_meta_json["params"]["empty_interior_max_resolution"] == 2
    assert adaptive_meta_json["params"]["min_output_resolution"] == 2
    assert adaptive_meta_json["params"]["empty_refine_boundary_band_k"] == 1
    assert adaptive_meta_json["params"]["empty_refine_near_occupied_k"] == 1
    assert adaptive_meta_json["params"]["compact_empty_near_occupied"] is False
    assert adaptive_meta_json["params"]["max_neighbor_resolution_delta"] == 1

    r7_regions_meta = client.get("/v1/layers/facility_density_r7_regions/metadata")
    assert r7_regions_meta.status_code == 200
    r7_regions_meta_json = r7_regions_meta.json()
    assert r7_regions_meta_json["layer_name"] == "facility_density_r7_regions"
    assert r7_regions_meta_json["layer_version"] == "v1"
    assert r7_regions_meta_json["source_layer"] == "facility_density_adaptive"
    assert r7_regions_meta_json["params"]["target_resolution"] == 7

    metro_cells = client.get("/v1/layers/metro_density_core/cells")
    assert metro_cells.status_code == 200
    assert len(metro_cells.json()["features"]) > 0

    country_cells = client.get("/v1/layers/country_mask/cells")
    assert country_cells.status_code == 200
    country_features = country_cells.json()["features"]
    assert len(country_features) > 0
    assert "country_color" in country_features[0]["properties"]
    assert {feature["properties"]["layer_value"] for feature in country_features} == {"TW"}

    adaptive_cells_default = client.get("/v1/layers/facility_density_adaptive/cells")
    assert adaptive_cells_default.status_code == 200
    default_features = adaptive_cells_default.json()["features"]
    assert len(default_features) > 0
    default_resolutions = [int(feature["properties"]["resolution"]) for feature in default_features]
    assert min(default_resolutions) >= 2
    assert max(default_resolutions) <= 7
    assert "preview" not in adaptive_cells_default.json()

    adaptive_cells_fine = client.get("/v1/layers/facility_density_adaptive/cells?split_threshold=1")
    assert adaptive_cells_fine.status_code == 400
    assert "split_threshold preview is deprecated for facility_density_adaptive" in adaptive_cells_fine.json()["detail"]

    r7_region_cells = client.get("/v1/layers/facility_density_r7_regions/cells")
    assert r7_region_cells.status_code == 200
    r7_region_features = r7_region_cells.json()["features"]
    assert len(r7_region_features) > 0
    assert all(int(feature["properties"]["resolution"]) == 7 for feature in r7_region_features)
    assert all(feature["properties"]["cluster_id"].startswith("r7c:") for feature in r7_region_features)
    assert all("region_h3" in feature["properties"] for feature in r7_region_features)
    assert all("region_lat" in feature["properties"] for feature in r7_region_features)
    assert all("region_lon" in feature["properties"] for feature in r7_region_features)

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
    health_body = health.json()
    assert health_body["status"] == "ok"
    assert health_body["run_id"] == run_id
    assert health_body["pointer"] == "latest-dev"
    assert health_body["lane"] == "dev"

    ui_config = client.get("/v1/ui/config")
    assert ui_config.status_code == 200
    ui_payload = ui_config.json()
    assert isinstance(ui_payload["zoom_to_h3_resolution"], dict)
    assert ui_payload["zoom_to_h3_resolution"]
    assert ui_payload["drilldown_resolution"] in system.allowed_h3_resolutions

    root = client.get("/", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/ui/"
    tw = client.get("/tw", follow_redirects=False)
    assert tw.status_code == 307
    assert tw.headers["location"] == "/ui/?country=TW"
    tw_slash = client.get("/tw/", follow_redirects=False)
    assert tw_slash.status_code == 307
    assert tw_slash.headers["location"] == "/ui/?country=TW"
    demo = client.get("/demo", follow_redirects=False)
    assert demo.status_code == 307
    assert demo.headers["location"] == "/ui/?country=DEMO"
    demo_slash = client.get("/demo/", follow_redirects=False)
    assert demo_slash.status_code == 307
    assert demo_slash.headers["location"] == "/ui/?country=DEMO"

    calibration_dir = tmp_path / "artifacts" / "calibration"
    old_report_dir = calibration_dir / "20260228T010000Z"
    latest_report_dir = calibration_dir / "20260228T020000Z"
    old_report_dir.mkdir(parents=True, exist_ok=True)
    latest_report_dir.mkdir(parents=True, exist_ok=True)
    (old_report_dir / "report.json").write_text(
        json.dumps({"calibration_id": "old", "country": "TW", "runtime_seconds": 10.0, "facility_count_total": 10}),
        encoding="utf-8",
    )
    (latest_report_dir / "report.json").write_text(
        json.dumps({"country": "TW", "runtime_seconds": 60.0, "facility_count_total": 100}),
        encoding="utf-8",
    )

    calibration_latest = client.get("/v1/calibration/latest")
    assert calibration_latest.status_code == 200
    calibration_latest_body = calibration_latest.json()
    assert calibration_latest_body["country"] == "TW"
    assert calibration_latest_body["calibration_id"] == "20260228T020000Z"

    calibration_tw = client.get("/v1/calibration/estimates/gb")
    assert calibration_tw.status_code == 200
    calibration_tw_body = calibration_tw.json()
    assert calibration_tw_body["calibration_id"] == "20260228T020000Z"
    assert calibration_tw_body["country"] == "TW"
    assert calibration_tw_body["estimate_basis"] == "latest_calibration_report"
    assert "estimate" in calibration_tw_body

    calibration_world = client.get("/v1/calibration/estimates/world")
    assert calibration_world.status_code == 200
    calibration_world_body = calibration_world.json()
    assert calibration_world_body["calibration_id"] == "20260228T020000Z"
    assert calibration_world_body["country"] == "TW"
    assert calibration_world_body["deprecated"] is True
    assert calibration_world_body["deprecated_alias_for"] == "/v1/calibration/estimates/gb"
