from pathlib import Path

import pytest

from inframap.agent.cli import _apply_country_selection, _env_truthy, _format_progress_line, _parse_country_codes
from inframap.config import load_layers_config


def test_parse_country_codes_normalizes_and_dedupes() -> None:
    assert _parse_country_codes("ar, JP,us,AR") == ["AR", "JP", "US"]


def test_parse_country_codes_rejects_invalid_token() -> None:
    with pytest.raises(ValueError, match="Invalid country code"):
        _parse_country_codes("ARG,US")


def test_apply_country_selection_updates_country_mask_params() -> None:
    layers = load_layers_config(Path("configs/layers.yaml"))
    updated = _apply_country_selection(layers, ["AR", "JP"])
    country_mask = next(layer for layer in updated.layers if layer.name == "country_mask")
    assert country_mask.params["polygon_dataset_dir"] == "data/countries"
    assert country_mask.params["include_iso_a2"] == ["AR", "JP"]
    assert "polygon_dataset" not in country_mask.params


def test_env_truthy_parsing() -> None:
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
        "note": "polygon 3/5 iso=US mode=quadtree_classify_split",
    }
    line = _format_progress_line(payload)
    assert line.startswith("[run-dev] in_progress layer:country_mask (country_mask)")
    assert "elapsed=12.3s" in line
    assert "note=polygon 3/5 iso=US mode=quadtree_classify_split" in line
