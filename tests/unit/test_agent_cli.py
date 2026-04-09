from threading import Event
from pathlib import Path

import pytest

import inframap.agent.cli as cli_module
from inframap.agent.cli import (
    _apply_country_selection,
    _env_truthy,
    _format_progress_line,
    main,
    _parse_country_codes,
    _resolve_country_selection,
)
from inframap.config import load_layers_config


def test_parse_country_codes_normalizes_and_dedupes() -> None:
    assert _parse_country_codes("tw, TW,tw") == ["TW"]


def test_parse_country_codes_rejects_invalid_token() -> None:
    with pytest.raises(ValueError, match="Invalid country code"):
        _parse_country_codes("ARG,TW")


def test_resolve_country_selection_prefers_countries_over_country() -> None:
    countries, source_env_var, raw_value = _resolve_country_selection("TW,JP", "AR")
    assert countries == ["TW", "JP"]
    assert source_env_var == "COUNTRIES"
    assert raw_value == "TW,JP"


def test_resolve_country_selection_falls_back_to_country() -> None:
    countries, source_env_var, raw_value = _resolve_country_selection(None, "AR")
    assert countries == ["AR"]
    assert source_env_var == "COUNTRY"
    assert raw_value == "AR"


def test_apply_country_selection_updates_country_mask_params() -> None:
    layers = load_layers_config(Path("configs/layers.yaml"))
    updated = _apply_country_selection(layers, ["TW"])
    country_mask = next(layer for layer in updated.layers if layer.name == "country_mask")
    assert country_mask.params["polygon_dataset_dir"] == "data/countries"
    assert country_mask.params["include_iso_a2"] == ["TW"]
    assert "polygon_dataset" not in country_mask.params


def test_env_truthy_parsing() -> None:
    assert _env_truthy(None, default=True) is True
    assert _env_truthy(None, default=False) is False
    assert _env_truthy("1", default=False) is True
    assert _env_truthy("true", default=False) is True
    assert _env_truthy("0", default=True) is False
    assert _env_truthy("off", default=True) is False
    assert _env_truthy("unexpected", default=True) is True


def test_format_progress_line_includes_stage_status_and_elapsed() -> None:
    payload = {
        "status": "in_progress",
        "stage": "layer:country_mask",
        "elapsed_s": 12.34,
        "layer_name": "country_mask",
        "note": "polygon 1/1 iso=TW mode=quadtree_classify_split",
    }
    line = _format_progress_line(payload)
    assert line.startswith("[run-dev] in_progress layer:country_mask (country_mask)")
    assert "elapsed=12.3s" in line
    assert "note=polygon 1/1 iso=TW mode=quadtree_classify_split" in line


@pytest.mark.parametrize(("raw_value", "expected_enabled"), [("off", False), ("on", True)])
def test_main_records_adaptive_cache_runtime_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
    expected_enabled: bool,
) -> None:
    system = cli_module.load_system_config(Path("configs/system.yaml"))
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
    layers = load_layers_config(Path("configs/layers.v4.yaml"))
    captured: dict[str, object] = {}

    monkeypatch.delenv("COUNTRIES", raising=False)
    monkeypatch.delenv("COUNTRY", raising=False)
    monkeypatch.setenv("RUN_DEV_PROGRESS", "0")
    monkeypatch.setenv("ADAPTIVE_CACHE", raw_value)
    monkeypatch.setattr(cli_module, "load_system_config", lambda path: system)
    monkeypatch.setattr(cli_module, "load_layers_config", lambda path: layers)
    monkeypatch.setattr(cli_module, "_start_progress_monitor", lambda staging_root, enabled: (Event(), None))

    def fake_build_effective_config_report(
        system_arg,
        layers_arg,
        *,
        system_config_path,
        layers_config_path,
        runtime_overrides,
    ):
        captured["runtime_overrides"] = runtime_overrides
        return {"runtime_overrides": runtime_overrides}

    def fake_run_pipeline(
        system_arg,
        layers_arg,
        *,
        effective_config,
        latest_pointer,
        compatibility_alias,
        enforce_blocking_checks,
        run_invariants_check,
    ) -> str:
        captured["effective_config"] = effective_config
        return "run-test-adaptive-cache"

    monkeypatch.setattr(cli_module, "build_effective_config_report", fake_build_effective_config_report)
    monkeypatch.setattr(cli_module, "run_pipeline", fake_run_pipeline)

    main()

    assert captured["runtime_overrides"] == {
        "adaptive_cache": {
            "source_env_var": "ADAPTIVE_CACHE",
            "raw_value": raw_value,
            "enabled": expected_enabled,
            "applied_to_layer": "facility_density_adaptive",
        }
    }
    assert captured["effective_config"] == {"runtime_overrides": captured["runtime_overrides"]}
