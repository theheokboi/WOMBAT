from pathlib import Path

import shapefile
from fastapi.testclient import TestClient

from inframap.config import load_system_config
from inframap.serve.app import create_app


def _write_roads_shapefile(path: Path) -> None:
    writer = shapefile.Writer(str(path), shapeType=shapefile.POLYLINE)
    writer.field("fclass", "C")
    writer.field("name", "C")

    writer.line([[[121.0, 25.0], [121.1, 25.1]]])
    writer.record("motorway", "motorway-a")

    writer.line([[[121.2, 25.2], [121.3, 25.3]]])
    writer.record("trunk", "trunk-a")

    writer.line([[[121.4, 25.4], [121.5, 25.5]]])
    writer.record("residential", "residential-a")

    writer.close()


def _write_railways_shapefile(path: Path) -> None:
    writer = shapefile.Writer(str(path), shapeType=shapefile.POLYLINE)
    writer.field("fclass", "C")
    writer.field("name", "C")

    writer.line([[[121.6, 25.6], [121.7, 25.7]]])
    writer.record("rail", "rail-a")

    writer.close()


def _build_client(tmp_path: Path, osm_root: Path) -> TestClient:
    system = load_system_config(Path("configs/system.yaml"))
    app = create_app(
        runs_root=tmp_path / "runs",
        published_root=tmp_path / "published",
        system_config=system,
        openstreetmap_root=osm_root,
    )
    return TestClient(app)


def test_osm_transport_overlay_filters_motorway_and_trunk_and_includes_railway(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"
    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_roads_shapefile(tw / "gis_osm_roads_free_1.shp")
    _write_railways_shapefile(tw / "gis_osm_railways_free_1.shp")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport")

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["available_countries"] == ["TW"]
    assert "run_id" not in payload

    observed_types = [feature["properties"]["transport_class"] for feature in payload["features"]]
    assert "motorway" in observed_types
    assert "trunk" in observed_types
    assert "rail" in observed_types
    assert "residential" not in observed_types

    countries = {feature["properties"]["country_code"] for feature in payload["features"]}
    assert countries == {"TW"}


def test_osm_transport_overlay_skips_missing_files_and_lists_available_countries(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"

    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_railways_shapefile(tw / "gis_osm_railways_free_1.shp")

    us = osm_root / "US"
    us.mkdir(parents=True)
    _write_roads_shapefile(us / "gis_osm_roads_free_1.shp")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport")

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["available_countries"] == ["TW", "US"]

    types_by_country: dict[str, set[str]] = {}
    for feature in payload["features"]:
        country = feature["properties"]["country_code"]
        infra_type = feature["properties"]["transport_class"]
        types_by_country.setdefault(country, set()).add(infra_type)

    assert types_by_country["TW"] == {"rail"}
    assert types_by_country["US"] == {"motorway", "trunk"}
