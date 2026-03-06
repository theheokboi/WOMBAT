from __future__ import annotations

import json
from pathlib import Path

import pytest

from inframap.agent.calibrate import run_calibration
from inframap.config import load_layers_config, load_system_config


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


@pytest.mark.parametrize("latest_preexists", [False, True])
def test_calibration_produces_report_without_publish_mutation(tmp_path: Path, latest_preexists: bool) -> None:
    system = _build_system_with_tmp_paths(tmp_path)
    layers = load_layers_config(Path("configs/layers.yaml"))

    latest_path = Path(system.paths.published_root) / "latest"
    if latest_preexists:
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        latest_path.write_text("sentinel-run-id\n", encoding="utf-8")
        before_state = ("exists", latest_path.read_text(encoding="utf-8"))
    else:
        before_state = ("missing", "")

    calibration_root = Path("artifacts") / "calibration"
    before_reports = set(calibration_root.glob("*/report.json")) if calibration_root.exists() else set()

    report_path = run_calibration(system=system, layers=layers, country_code="TW")
    try:
        assert report_path.exists()
        assert report_path.parent.parent == calibration_root
        after_reports = set(calibration_root.glob("*/report.json"))
        assert report_path in after_reports - before_reports

        report = json.loads(report_path.read_text(encoding="utf-8"))
        required = {
            "country_code",
            "run_timestamp_utc",
            "facility_count",
            "domain_r4_cell_count",
            "layer_durations_seconds",
            "stage_durations_seconds",
            "invariant_stage_duration_seconds",
        }
        assert required.issubset(report.keys())
        assert report["country_code"] == "TW"
        assert isinstance(report["facility_count"], int)
        assert isinstance(report["domain_r4_cell_count"], int)
        assert isinstance(report["layer_durations_seconds"], dict)
        assert isinstance(report["stage_durations_seconds"], dict)
        assert report["invariant_stage_duration_seconds"] >= 0.0

        if before_state[0] == "exists":
            assert latest_path.exists()
            assert latest_path.read_text(encoding="utf-8") == before_state[1]
        else:
            assert not latest_path.exists()
    finally:
        if report_path.exists():
            report_path.unlink()
        if report_path.parent.exists():
            report_path.parent.rmdir()
