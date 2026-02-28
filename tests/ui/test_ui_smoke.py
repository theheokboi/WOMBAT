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

    response = client.get("/ui/")
    assert response.status_code == 200
    assert "Infrastructure Layers" in response.text
    assert "toggle-facilities" in response.text
    assert "toggle-adaptive" in response.text
    assert "toggle-country" in response.text
    assert "toggle-metro" not in response.text
    assert "toggle-global-h3" not in response.text
    assert "adaptive-threshold" not in response.text
    assert "facility-style" not in response.text
