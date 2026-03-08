from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from inframap.config import load_system_config
from inframap.serve.app import create_app


@pytest.mark.ui_smoke
def test_ui_static_smoke() -> None:
    system = load_system_config(Path("configs/system.yaml"))
    app = create_app(
        runs_root=Path(system.paths.runs_root),
        published_root=Path(system.paths.published_root),
        system_config=system,
    )
    client = TestClient(app)

    response = client.get("/ui/index.html")
    assert response.status_code == 200
    assert "Infrastructure Layers" in response.text
    assert "./styles.css" in response.text
    assert "./main.js" in response.text
    assert "Display scope: loading..." in response.text
    assert "display-scope" in response.text
    assert "run-selector" in response.text
    assert "basemap-selector" in response.text
    assert "Basemap" in response.text
    assert "CARTO Positron" in response.text
    assert "CARTO Dark" in response.text
    assert "country-selector" not in response.text
    assert "toggle-facilities" in response.text
    assert "Facility / landing points" in response.text
    assert "toggle-adaptive" in response.text
    assert "Adaptive Facility H3" in response.text
    assert "toggle-r7-regions" in response.text
    assert "R7 Network Regions" in response.text
    assert "toggle-r7-routes" in response.text
    assert "R7 Region Routes" in response.text
    assert "toggle-country" in response.text
    assert "Country H3" in response.text
    assert '<input type="checkbox" id="toggle-facilities" checked />' in response.text
    assert '<input type="checkbox" id="toggle-country" />' in response.text
    assert '<input type="checkbox" id="toggle-adaptive" />' in response.text
    assert '<input type="checkbox" id="toggle-r7-regions" checked />' in response.text
    assert '<input type="checkbox" id="toggle-r7-routes" checked />' in response.text
    assert "toggle-places" not in response.text
    assert "Populated places" not in response.text
    assert "toggle-osm-transport" not in response.text
    assert "OSM transport overlay" not in response.text
    assert "osm-transport-source" not in response.text
    assert "OSM transport source" not in response.text
    assert "osm-graph-variant" not in response.text
    assert "Graph variant" not in response.text
    assert "OSM railway (rail)" not in response.text
    assert "OSM motorway" not in response.text
    assert "OSM trunk" not in response.text
    assert "OSM primary" not in response.text
    assert "OSM secondary" not in response.text
    assert "Published Run & Adaptive Version" in response.text
    assert "latest-adaptive-version" in response.text
    assert "adaptive-policy" in response.text
    assert "runtime-expectation" in response.text
    assert "calibration-basis" in response.text
    assert "calibration-world-estimate" not in response.text
    assert "TW-calibrated world runtime estimate" not in response.text
    assert "toggle-metro" not in response.text
    assert "toggle-global-h3" not in response.text
    assert "adaptive-threshold" not in response.text
    assert "facility-style" not in response.text

    script_response = client.get("/ui/main.js")
    assert script_response.status_code == 200
    assert "Leaf facility count" in script_response.text
    assert "mode=all-countries" in script_response.text
    assert "buildAvailableCountries" in script_response.text
    assert "new URLSearchParams(window.location.search)" in script_response.text
    assert "demo-data/manifest.json" in script_response.text
    assert "source=${dataSource.mode}" in script_response.text
    assert "detectDataSource" in script_response.text
    assert "Display scope: run=" in script_response.text
    assert "country-selector" not in script_response.text
    assert "run-selector" in script_response.text
    assert "BASEMAP_STYLES" in script_response.text
    assert "basemap-selector" in script_response.text
    assert "light_all" in script_response.text
    assert "dark_all" in script_response.text
    assert "tile.openstreetmap.org" not in script_response.text
    assert "/v1/layers/facility_density_adaptive/metadata" in script_response.text
    assert "/v1/runs/catalog" in script_response.text
    assert "/v1/runs/latest/status" in script_response.text
    assert "/v1/runs/active/status" in script_response.text
    assert "/v1/calibration/latest" in script_response.text
    assert "buildAdaptiveResolutionBounds" in script_response.text
    assert "min_output_resolution" in script_response.text
    assert "facility_max_resolution" in script_response.text
    assert "isAdaptiveResolutionAllowed" in script_response.text
    assert "isLandingPointFeature" in script_response.text
    assert "LANDING_POINT_COLOR" in script_response.text
    assert "toggle-facilities" in script_response.text
    assert "toggle-country" in script_response.text
    assert "toggle-adaptive" in script_response.text
    assert "toggle-r7-regions" in script_response.text
    assert "/v1/layers/facility_density_r7_regions/cells" in script_response.text
    assert "facility_density_r7_regions" in script_response.text
    assert "Region H3:" in script_response.text
    assert "Region coordinates:" in script_response.text
    assert "region_lat" in script_response.text
    assert "region_lon" in script_response.text
    assert "buildUniqueR7RegionMarkers" in script_response.text
    assert "circleMarker" in script_response.text
    assert "region point" in script_response.text
    assert "toggle-r7-routes" in script_response.text
    assert "/v1/r7-region-routes?country=${country}" in script_response.text
    assert "r7-region-routes-${country}.json" in script_response.text
    assert "Layer: r7_region_routes" in script_response.text
    assert "toggle-places" not in script_response.text
    assert "/v1/populated-places" not in script_response.text
    assert "POPULATED_PLACE_COLOR" not in script_response.text
    assert "getPopulatedPlaceRadius" not in script_response.text
    assert "toggle-osm-transport" not in script_response.text
    assert "osm-transport-source" not in script_response.text
    assert "/v1/osm/transport" not in script_response.text
    assert "graph_variant" not in script_response.text
    assert "adaptive_portal" not in script_response.text
    assert "/v1/calibration/estimates/world" not in script_response.text
