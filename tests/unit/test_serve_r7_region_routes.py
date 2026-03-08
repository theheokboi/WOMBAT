from pathlib import Path
import json

from fastapi.testclient import TestClient

from inframap.config import load_system_config
from inframap.serve.app import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_client(tmp_path: Path) -> TestClient:
    system = load_system_config(REPO_ROOT / "configs" / "system.yaml")
    app = create_app(
        runs_root=tmp_path / "runs",
        published_root=tmp_path / "published",
        system_config=system,
        openstreetmap_root=tmp_path / "openstreetmap",
    )
    return TestClient(app)


def _write_route_artifact(path: Path, country_code: str) -> None:
    payload = {
        "country_code": country_code,
        "source_csv": f"2026-03-08-r7-regions-{country_code.lower()}.csv",
        "routes": [
            {
                "from_idx": 0,
                "to_idx": 0,
                "from_region_h3": "self-a",
                "to_region_h3": "self-a",
                "distance": 0.0,
                "duration": 0.0,
                "geometry": {"type": "LineString", "coordinates": [[121.0, 25.0]]},
            },
            {
                "from_idx": 0,
                "to_idx": 1,
                "from_region_h3": "a",
                "to_region_h3": "b",
                "distance": 12345.6,
                "duration": 789.0,
                "geometry": {"type": "LineString", "coordinates": [[121.0, 25.0], [121.1, 25.1]]},
            },
            {
                "from_idx": 1,
                "to_idx": 2,
                "from_region_h3": "b",
                "to_region_h3": "c",
                "distance": None,
                "duration": None,
                "geometry": None,
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_route_ui_artifact(path: Path, country_code: str) -> None:
    payload = {
        "type": "FeatureCollection",
        "country_code": country_code,
        "source_artifact": f"2026-03-08-r7-regions-{country_code.lower()}-routes.json",
        "route_count_total": 3,
        "self_route_count_excluded": 1,
        "null_geometry_count_excluded": 1,
        "feature_count": 1,
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[121.0, 25.0], [121.1, 25.1]]},
                "properties": {
                    "country_code": country_code,
                    "from_region_h3": "a",
                    "to_region_h3": "b",
                    "distance_m": 12345.6,
                    "duration_s": 789.0,
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_r7_region_routes_endpoint_returns_geojson_features(tmp_path: Path, monkeypatch) -> None:
    derived = tmp_path / "artifacts" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    _write_route_artifact(derived / "2026-03-08-r7-regions-tw-routes.json", "TW")
    _write_route_artifact(derived / "2026-03-08-r7-regions-ar-routes.json", "AR")
    monkeypatch.chdir(tmp_path)

    client = _build_client(tmp_path)
    response = client.get("/v1/r7-region-routes")

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["country"] is None
    assert payload["available_countries"] == ["AR", "TW"]
    assert payload["route_count_total"] == 6
    assert payload["self_route_count"] == 2
    assert payload["missing_geometry_count"] == 2
    assert payload["feature_count"] == 2
    assert sorted(payload["source_artifacts"]) == [
        "2026-03-08-r7-regions-ar-routes.json",
        "2026-03-08-r7-regions-tw-routes.json",
    ]
    assert {feature["properties"]["country_code"] for feature in payload["features"]} == {"AR", "TW"}
    assert all(feature["geometry"]["type"] == "LineString" for feature in payload["features"])


def test_r7_region_routes_endpoint_supports_country_filter_and_include_self(tmp_path: Path, monkeypatch) -> None:
    derived = tmp_path / "artifacts" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    _write_route_artifact(derived / "2026-03-08-r7-regions-tw-routes.json", "TW")
    monkeypatch.chdir(tmp_path)

    client = _build_client(tmp_path)
    response = client.get("/v1/r7-region-routes?country=TW&include_self=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["country"] == "TW"
    assert payload["available_countries"] == ["TW"]
    assert payload["route_count_total"] == 3
    assert payload["self_route_count"] == 1
    assert payload["missing_geometry_count"] == 1
    assert payload["feature_count"] == 2
    assert {feature["properties"]["from_idx"] for feature in payload["features"]} == {0}


def test_r7_region_routes_endpoint_rejects_unknown_country(tmp_path: Path, monkeypatch) -> None:
    derived = tmp_path / "artifacts" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    _write_route_artifact(derived / "2026-03-08-r7-regions-ar-routes.json", "AR")
    monkeypatch.chdir(tmp_path)

    client = _build_client(tmp_path)
    response = client.get("/v1/r7-region-routes?country=TW")

    assert response.status_code == 404
    assert "R7 region routes unavailable for country: TW" in response.json()["detail"]


def test_r7_region_routes_endpoint_prefers_ui_geojson_when_available(tmp_path: Path, monkeypatch) -> None:
    derived = tmp_path / "artifacts" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    _write_route_artifact(derived / "2026-03-08-r7-regions-ar-routes.json", "AR")
    _write_route_ui_artifact(derived / "2026-03-08-r7-regions-ar-routes-ui.geojson", "AR")
    monkeypatch.chdir(tmp_path)

    client = _build_client(tmp_path)
    response = client.get("/v1/r7-region-routes?country=AR")

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_kind"] == "ui_geojson"
    assert payload["route_count_total"] == 3
    assert payload["self_route_count"] == 1
    assert payload["missing_geometry_count"] == 1
    assert payload["feature_count"] == 1
    assert payload["source_artifacts"] == ["2026-03-08-r7-regions-ar-routes-ui.geojson"]
    assert payload["features"][0]["properties"]["source_artifact"] == "2026-03-08-r7-regions-ar-routes.json"


def test_r7_region_routes_endpoint_uses_raw_artifact_when_include_self_requested(tmp_path: Path, monkeypatch) -> None:
    derived = tmp_path / "artifacts" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    _write_route_artifact(derived / "2026-03-08-r7-regions-ar-routes.json", "AR")
    _write_route_ui_artifact(derived / "2026-03-08-r7-regions-ar-routes-ui.geojson", "AR")
    monkeypatch.chdir(tmp_path)

    client = _build_client(tmp_path)
    response = client.get("/v1/r7-region-routes?country=AR&include_self=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_kind"] == "raw_routes"
    assert payload["route_count_total"] == 3
    assert payload["self_route_count"] == 1
    assert payload["missing_geometry_count"] == 1
    assert payload["feature_count"] == 2
    assert payload["source_artifacts"] == ["2026-03-08-r7-regions-ar-routes.json"]
