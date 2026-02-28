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


def test_api_endpoints_and_tiles(tmp_path: Path) -> None:
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

    layers_resp = client.get("/v1/layers")
    assert layers_resp.status_code == 200
    names = {entry["layer_name"] for entry in layers_resp.json()["layers"]}
    assert {"metro_density_core", "country_mask", "facility_density_adaptive"}.issubset(names)

    meta = client.get("/v1/layers/metro_density_core/metadata")
    assert meta.status_code == 200
    assert meta.json()["layer_name"] == "metro_density_core"

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

    adaptive_cells_fine = client.get("/v1/layers/facility_density_adaptive/cells?split_threshold=1")
    assert adaptive_cells_fine.status_code == 200
    fine_features = adaptive_cells_fine.json()["features"]
    assert len(fine_features) >= len(default_features)

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
