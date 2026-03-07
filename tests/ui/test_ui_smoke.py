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
    assert "Display scope: loading..." in response.text
    assert "display-scope" in response.text
    assert "run-selector" in response.text
    assert "basemap-selector" in response.text
    assert "Basemap" in response.text
    assert "CARTO Positron" in response.text
    assert "OSM Standard" in response.text
    assert "CARTO Dark" in response.text
    assert "country-selector" not in response.text
    assert "toggle-facilities" in response.text
    assert "toggle-adaptive" in response.text
    assert "toggle-country" in response.text
    assert "toggle-osm-transport" in response.text
    assert "OSM transport overlay" in response.text
    assert "osm-transport-source" in response.text
    assert "OSM transport source" in response.text
    assert "Shapefile" in response.text
    assert "Graph" in response.text
    assert "osm-graph-variant" in response.text
    assert "Graph variant" in response.text
    assert "Raw" in response.text
    assert "Collapsed" in response.text
    assert "Adaptive" in response.text
    assert "OSM railway (rail)" in response.text
    assert "OSM motorway" in response.text
    assert "OSM trunk" in response.text
    assert "OSM graph nodes (source=graph)" in response.text
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
    assert "Display scope: run=" in script_response.text
    assert "country-selector" not in script_response.text
    assert "run-selector" in script_response.text
    assert "BASEMAP_STYLES" in script_response.text
    assert "basemap-selector" in script_response.text
    assert "light_all" in script_response.text
    assert "dark_all" in script_response.text
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
    assert "OSM_TRANSPORT_STYLES" in script_response.text
    assert "toggle-osm-transport" in script_response.text
    assert "osm-transport-source" in script_response.text
    assert "/v1/osm/transport" in script_response.text
    assert "searchParams.set('source'" in script_response.text
    assert "include_nodes" in script_response.text
    assert "graph_variant" in script_response.text
    assert "searchParams.set('graph_variant'" in script_response.text
    assert "osm-graph-variant" in script_response.text
    assert "colorGraphEdgesByAdjacency" in script_response.text
    assert "/v1/calibration/estimates/world" not in script_response.text
