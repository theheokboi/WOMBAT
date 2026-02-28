from pathlib import Path

import json
import pytest

from inframap.agent.runner import run_pipeline
from inframap.config import load_layers_config, load_system_config


@pytest.mark.perf_monitoring
def test_metrics_emitted_with_required_keys(tmp_path: Path) -> None:
    system = load_system_config(Path("configs/system.yaml"))
    layers = load_layers_config(Path("configs/layers.yaml"))
    system = system.__class__(
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

    run_id = run_pipeline(system, layers)
    metrics_path = tmp_path / "runs" / run_id / "reports" / "metrics.json"
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))

    required = {
        "run_success",
        "run_duration_seconds",
        "facility_count_total",
        "facility_count_by_source",
        "invalid_record_count",
        "layer_compute_duration_seconds",
        "publish_timestamp",
    }
    assert required.issubset(payload.keys())
    assert payload["run_duration_seconds"] >= 0
