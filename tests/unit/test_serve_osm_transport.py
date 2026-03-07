from pathlib import Path
import json

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
    writer.record("secondary", "secondary-a")

    writer.line([[[121.45, 25.45], [121.55, 25.55]]])
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


def _prepare_run_root_with_graph_variant(tmp_path: Path, run_id: str, country: str = "TW") -> Path:
    run_graph_country = tmp_path / "runs" / run_id / "graph" / country
    run_graph_country.mkdir(parents=True, exist_ok=True)
    published = tmp_path / "published"
    published.mkdir(parents=True, exist_ok=True)
    (published / "latest-dev").write_text(run_id, encoding="utf-8")
    return run_graph_country


def _write_major_roads_edges_geojson(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[121.0, 25.0], [121.1, 25.1]],
                },
                "properties": {"road_class": "motorway"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[121.2, 25.2], [121.3, 25.3]],
                },
                "properties": {"road_class": "trunk_link"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[121.4, 25.4], [121.5, 25.5]],
                },
                "properties": {},
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_major_roads_nodes_geojson(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [121.05, 25.05]},
                "properties": {"node_id": 101, "lon": 121.05, "lat": 25.05},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [121.25, 25.25]},
                "properties": {"node_id": 102, "lon": 121.25, "lat": 25.25},
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_major_roads_edges_collapsed_geojson(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[121.0, 25.0], [121.3, 25.3]],
                },
                "properties": {"road_class": "motorway"},
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_major_roads_nodes_collapsed_geojson(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [121.0, 25.0]},
                "properties": {"node_id": 201, "lon": 121.0, "lat": 25.0},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [121.3, 25.3]},
                "properties": {"node_id": 202, "lon": 121.3, "lat": 25.3},
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_major_roads_edges_adaptive_geojson(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[121.8, 25.8], [121.9, 25.9]],
                },
                "properties": {"road_class": "motorway_link"},
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_major_roads_nodes_adaptive_geojson(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [121.8, 25.8]},
                "properties": {"node_id": 301, "lon": 121.8, "lat": 25.8},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [121.9, 25.9]},
                "properties": {"node_id": 302, "lon": 121.9, "lat": 25.9},
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_major_roads_edges_adaptive_portal_geojson(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[122.0, 24.8], [122.1, 24.9]],
                },
                "properties": {"road_class": "trunk"},
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_major_roads_nodes_adaptive_portal_geojson(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [122.0, 24.8]},
                "properties": {"node_id": 401, "lon": 122.0, "lat": 24.8},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [122.1, 24.9]},
                "properties": {"node_id": 402, "lon": 122.1, "lat": 24.9},
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_osm_transport_overlay_filters_mainline_classes_and_includes_railway(tmp_path: Path) -> None:
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
    assert payload["source"] == "shapefile"
    assert payload["available_countries"] == ["TW"]
    assert "run_id" not in payload

    observed_types = [feature["properties"]["transport_class"] for feature in payload["features"]]
    assert "motorway" in observed_types
    assert "trunk" in observed_types
    assert "secondary" in observed_types
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
    assert payload["source"] == "shapefile"
    assert payload["available_countries"] == ["TW", "US"]

    types_by_country: dict[str, set[str]] = {}
    for feature in payload["features"]:
        country = feature["properties"]["country_code"]
        infra_type = feature["properties"]["transport_class"]
        types_by_country.setdefault(country, set()).add(infra_type)

    assert types_by_country["TW"] == {"rail"}
    assert types_by_country["US"] == {"motorway", "trunk", "secondary"}


def test_osm_transport_overlay_source_graph_loads_major_roads_edges(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"
    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_major_roads_edges_geojson(tw / "major_roads_edges.geojson")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "graph"
    assert payload["available_countries"] == ["TW"]
    assert payload["classes"] == ["motorway", "trunk_link"]

    features = payload["features"]
    assert len(features) == 2
    assert all(feature["properties"]["country_code"] == "TW" for feature in features)
    assert {feature["properties"]["transport_class"] for feature in features} == {"motorway", "trunk_link"}


def test_osm_transport_overlay_source_graph_include_nodes_adds_point_features(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"
    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_major_roads_edges_geojson(tw / "major_roads_edges.geojson")
    _write_major_roads_nodes_geojson(tw / "major_roads_nodes.geojson")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph&include_nodes=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "graph"
    assert payload["classes"] == ["motorway", "trunk_link"]

    features = payload["features"]
    geometry_types = {feature["geometry"]["type"] for feature in features}
    assert geometry_types == {"LineString", "Point"}

    node_features = [
        feature
        for feature in features
        if feature["properties"].get("graph_feature_type") == "node"
    ]
    assert len(node_features) == 2
    assert {feature["properties"]["transport_class"] for feature in node_features} == {"graph_node"}


def test_osm_transport_overlay_source_graph_skips_missing_files_and_country_fallback(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"

    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_major_roads_edges_geojson(tw / "major_roads_edges.geojson")

    us = osm_root / "US"
    us.mkdir(parents=True)
    _write_roads_shapefile(us / "gis_osm_roads_free_1.shp")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "graph"
    assert payload["available_countries"] == ["TW"]

    missing_country = client.get("/v1/osm/transport?source=graph&country=US")
    assert missing_country.status_code == 404


def test_osm_transport_overlay_source_graph_variant_collapsed_loads_collapsed_files(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"
    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_major_roads_edges_geojson(tw / "major_roads_edges.geojson")
    _write_major_roads_edges_collapsed_geojson(tw / "major_roads_edges_collapsed.geojson")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph&graph_variant=collapsed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "graph"
    assert payload["available_countries"] == ["TW"]
    assert payload["classes"] == ["motorway"]
    assert len(payload["features"]) == 1
    assert payload["features"][0]["properties"]["transport_class"] == "motorway"


def test_osm_transport_overlay_source_graph_variant_collapsed_include_nodes_uses_collapsed_nodes(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"
    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_major_roads_edges_collapsed_geojson(tw / "major_roads_edges_collapsed.geojson")
    _write_major_roads_nodes_collapsed_geojson(tw / "major_roads_nodes_collapsed.geojson")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph&graph_variant=collapsed&include_nodes=true")

    assert response.status_code == 200
    payload = response.json()
    node_features = [feature for feature in payload["features"] if feature["properties"].get("graph_feature_type") == "node"]
    assert len(node_features) == 2
    assert {feature["properties"]["node_id"] for feature in node_features} == {201, 202}


def test_osm_transport_overlay_source_graph_variant_collapsed_country_listing_uses_collapsed_edges(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"

    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_major_roads_edges_geojson(tw / "major_roads_edges.geojson")

    us = osm_root / "US"
    us.mkdir(parents=True)
    _write_major_roads_edges_collapsed_geojson(us / "major_roads_edges_collapsed.geojson")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph&graph_variant=collapsed")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available_countries"] == ["US"]
    assert {feature["properties"]["country_code"] for feature in payload["features"]} == {"US"}


def test_osm_transport_overlay_source_graph_variant_adaptive_loads_adaptive_files(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"
    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_major_roads_edges_geojson(tw / "major_roads_edges.geojson")
    _write_major_roads_edges_adaptive_geojson(tw / "major_roads_edges_adaptive.geojson")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph&graph_variant=adaptive")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "graph"
    assert payload["available_countries"] == ["TW"]
    assert payload["classes"] == ["motorway_link"]
    assert len(payload["features"]) == 1
    assert payload["features"][0]["properties"]["transport_class"] == "motorway_link"


def test_osm_transport_overlay_source_graph_variant_adaptive_include_nodes_uses_adaptive_nodes(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"
    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_major_roads_edges_adaptive_geojson(tw / "major_roads_edges_adaptive.geojson")
    _write_major_roads_nodes_adaptive_geojson(tw / "major_roads_nodes_adaptive.geojson")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph&graph_variant=adaptive&include_nodes=true")

    assert response.status_code == 200
    payload = response.json()
    node_features = [feature for feature in payload["features"] if feature["properties"].get("graph_feature_type") == "node"]
    assert len(node_features) == 2
    assert {feature["properties"]["node_id"] for feature in node_features} == {301, 302}


def test_osm_transport_overlay_source_graph_variant_adaptive_country_listing_uses_adaptive_edges(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"

    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_major_roads_edges_geojson(tw / "major_roads_edges.geojson")

    us = osm_root / "US"
    us.mkdir(parents=True)
    _write_major_roads_edges_adaptive_geojson(us / "major_roads_edges_adaptive.geojson")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph&graph_variant=adaptive")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available_countries"] == ["US"]
    assert {feature["properties"]["country_code"] for feature in payload["features"]} == {"US"}


def test_osm_transport_overlay_source_graph_variant_adaptive_portal_loads_adaptive_portal_files(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"
    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_major_roads_edges_geojson(tw / "major_roads_edges.geojson")
    _write_major_roads_edges_adaptive_portal_geojson(tw / "major_roads_edges_adaptive_portal.geojson")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph&graph_variant=adaptive_portal")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "graph"
    assert payload["available_countries"] == ["TW"]
    assert payload["classes"] == ["trunk"]
    assert len(payload["features"]) == 1
    assert payload["features"][0]["properties"]["transport_class"] == "trunk"


def test_osm_transport_overlay_source_graph_variant_adaptive_portal_include_nodes_uses_adaptive_portal_nodes(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"
    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_major_roads_edges_adaptive_portal_geojson(tw / "major_roads_edges_adaptive_portal.geojson")
    _write_major_roads_nodes_adaptive_portal_geojson(tw / "major_roads_nodes_adaptive_portal.geojson")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph&graph_variant=adaptive_portal&include_nodes=true")

    assert response.status_code == 200
    payload = response.json()
    node_features = [feature for feature in payload["features"] if feature["properties"].get("graph_feature_type") == "node"]
    assert len(node_features) == 2
    assert {feature["properties"]["node_id"] for feature in node_features} == {401, 402}


def test_osm_transport_overlay_source_graph_variant_adaptive_portal_country_listing_uses_adaptive_portal_edges(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"

    tw = osm_root / "TW"
    tw.mkdir(parents=True)
    _write_major_roads_edges_geojson(tw / "major_roads_edges.geojson")

    us = osm_root / "US"
    us.mkdir(parents=True)
    _write_major_roads_edges_adaptive_portal_geojson(us / "major_roads_edges_adaptive_portal.geojson")

    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph&graph_variant=adaptive_portal")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available_countries"] == ["US"]
    assert {feature["properties"]["country_code"] for feature in payload["features"]} == {"US"}


def test_osm_transport_overlay_source_graph_variant_adaptive_portal_run_requires_run_id(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"
    osm_root.mkdir(parents=True)
    client = _build_client(tmp_path, osm_root)
    response = client.get("/v1/osm/transport?source=graph&graph_variant=adaptive_portal_run")
    assert response.status_code == 400
    assert "run_id is required" in response.json()["detail"]


def test_osm_transport_overlay_source_graph_variant_adaptive_portal_run_loads_run_scoped_files(tmp_path: Path) -> None:
    osm_root = tmp_path / "openstreetmap"
    run_graph = _prepare_run_root_with_graph_variant(tmp_path, run_id="run-123", country="TW")
    _write_major_roads_edges_adaptive_portal_geojson(run_graph / "major_roads_edges_adaptive_portal_run.geojson")
    _write_major_roads_nodes_adaptive_portal_geojson(run_graph / "major_roads_nodes_adaptive_portal_run.geojson")

    client = _build_client(tmp_path, osm_root)
    response = client.get(
        "/v1/osm/transport?source=graph&graph_variant=adaptive_portal_run&run_id=run-123&include_nodes=true"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "graph"
    assert payload["graph_variant"] == "adaptive_portal_run"
    assert payload["run_id"] == "run-123"
    assert payload["run_agnostic"] is False
    assert payload["available_countries"] == ["TW"]
    assert payload["classes"] == ["trunk"]
    node_features = [feature for feature in payload["features"] if feature["properties"].get("graph_feature_type") == "node"]
    assert len(node_features) == 2
    assert {feature["properties"]["node_id"] for feature in node_features} == {401, 402}
