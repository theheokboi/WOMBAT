from pathlib import Path

import shapefile
from fastapi.testclient import TestClient

from inframap.config import load_system_config
from inframap.serve.app import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_populated_places_shapefile(path: Path) -> None:
    writer = shapefile.Writer(str(path), shapeType=shapefile.POINT)
    writer.field("NAME", "C")
    writer.field("NAMEASCII", "C")
    writer.field("ADM0NAME", "C")
    writer.field("ISO_A2", "C")
    writer.field("FEATURECLA", "C")
    writer.field("POP_MAX", "N", decimal=0)
    writer.field("MIN_ZOOM", "F", decimal=1)

    writer.point(121.5654, 25.0330)
    writer.record("Taipei", "Taipei", "Taiwan", "TW", "Admin-0 capital", 7000000, 3.0)

    writer.point(120.3014, 22.6273)
    writer.record("Kaohsiung", "Kaohsiung", "Taiwan", "TW", "Admin-1 capital", 1500000, 5.0)

    writer.point(-58.3816, -34.6037)
    writer.record("Buenos Aires", "Buenos Aires", "Argentina", "AR", "Admin-0 capital", 15000000, 2.0)

    writer.close()


def _build_client(tmp_path: Path) -> TestClient:
    system = load_system_config(REPO_ROOT / "configs" / "system.yaml")
    app = create_app(
        runs_root=tmp_path / "runs",
        published_root=tmp_path / "published",
        system_config=system,
        openstreetmap_root=tmp_path / "openstreetmap",
    )
    return TestClient(app)


def test_populated_places_endpoint_returns_feature_collection(tmp_path: Path, monkeypatch) -> None:
    places_dir = tmp_path / "data" / "populated_places"
    places_dir.mkdir(parents=True, exist_ok=True)
    _write_populated_places_shapefile(places_dir / "ne_10m_populated_places.shp")
    monkeypatch.chdir(tmp_path)

    client = _build_client(tmp_path)
    response = client.get("/v1/populated-places")

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["run_agnostic"] is True
    assert payload["country"] is None
    assert payload["available_countries"] == ["AR", "TW"]
    assert payload["feature_count"] == 3

    first = payload["features"][0]
    assert first["geometry"]["type"] == "Point"
    assert {
        "name",
        "name_ascii",
        "country_name",
        "country_code",
        "feature_class",
        "population_max",
        "min_zoom",
    }.issubset(first["properties"])


def test_populated_places_endpoint_supports_country_filter_and_limit(tmp_path: Path, monkeypatch) -> None:
    places_dir = tmp_path / "data" / "populated_places"
    places_dir.mkdir(parents=True, exist_ok=True)
    _write_populated_places_shapefile(places_dir / "ne_10m_populated_places.shp")
    monkeypatch.chdir(tmp_path)

    client = _build_client(tmp_path)
    response = client.get("/v1/populated-places?country=TW&limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["country"] == "TW"
    assert payload["feature_count"] == 1
    assert len(payload["features"]) == 1
    assert payload["features"][0]["properties"]["country_code"] == "TW"


def test_populated_places_endpoint_rejects_unknown_country(tmp_path: Path, monkeypatch) -> None:
    places_dir = tmp_path / "data" / "populated_places"
    places_dir.mkdir(parents=True, exist_ok=True)
    _write_populated_places_shapefile(places_dir / "ne_10m_populated_places.shp")
    monkeypatch.chdir(tmp_path)

    client = _build_client(tmp_path)
    response = client.get("/v1/populated-places?country=US")

    assert response.status_code == 404
    assert "Populated places unavailable for country: US" in response.json()["detail"]
