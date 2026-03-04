import json
from pathlib import Path

import pandas as pd
import h3
import pytest

from inframap.layers.country_mask import CountryMaskLayer


def _write_country_polygon_dataset(tmp_path: Path, iso_a2: str) -> Path:
    source = Path(f"data/countries/{iso_a2.upper()}.geojson")
    payload = json.loads(source.read_text(encoding="utf-8"))
    features = []
    for feature in payload.get("features", []):
        properties = feature.get("properties", {})
        features.append(
            {
                "type": "Feature",
                "properties": {"iso_a2": iso_a2.upper(), "name": str(properties.get("COUNTRY", iso_a2.upper()))},
                "geometry": feature["geometry"],
            }
        )
    out_path = tmp_path / f"{iso_a2.lower()}_country_mask_fixture.geojson"
    out_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    return out_path


def test_country_mask_centroid_assignment_rule() -> None:
    facilities = pd.DataFrame(
        [
            {"facility_id": "a", "asof_date": "2026-02-28"},
            {"facility_id": "b", "asof_date": "2026-02-28"},
        ]
    )
    layer = CountryMaskLayer(version="v1")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store={},
        params={
            "resolution": 4,
            "membership_rule": "centroid_in_polygon",
            "polygon_dataset_dir": "data/countries",
            "include_iso_a2": ["US"],
            "exclude_iso_a2": ["AQ"],
        },
    )

    assert metadata["layer_name"] == "country_mask"
    assert metadata["params"]["membership_rule"] == "centroid_in_polygon"
    assert len(cells) > 100
    assert cells["layer_value"].notnull().all()
    assert not cells["h3"].duplicated().any()
    assert "country_color" in cells.columns
    assert cells["country_color"].notnull().all()
    assert "country_color_palette" in metadata
    assert "AQ" not in set(cells["layer_value"].tolist())
    assert metadata["params"]["include_iso_a2"] == ["US"]
    assert metadata["polygon_dataset_files"] == ["data/countries/US.geojson"]
    assert metadata["polygon_dataset_source"] == "country_geojson_directory"

    country_color = (
        cells[["layer_value", "country_color"]]
        .drop_duplicates()
        .set_index("layer_value")["country_color"]
        .to_dict()
    )
    by_cell = cells.set_index("h3")["layer_value"].to_dict()
    for cell, iso in by_cell.items():
        for neighbor in h3.grid_disk(cell, 1):
            other_iso = by_cell.get(neighbor)
            if other_iso is None or other_iso == iso:
                continue
            assert country_color[iso] != country_color[other_iso]


def test_country_mask_warns_on_legacy_world_dataset_path(tmp_path: Path) -> None:
    facilities = pd.DataFrame([{"facility_id": "a", "asof_date": "2026-02-28"}])
    polygon_dataset = _write_country_polygon_dataset(tmp_path, "US")
    layer = CountryMaskLayer(version="v1", legacy_world_dataset_path=str(polygon_dataset))

    with pytest.warns(UserWarning, match="deprecated legacy world file"):
        metadata, _ = layer.compute(
            canonical_store={"facilities": facilities},
            layer_store={},
            params={
                "resolution": 4,
                "membership_rule": "centroid_in_polygon",
                "polygon_dataset": str(polygon_dataset),
                "exclude_iso_a2": ["AQ"],
            },
        )

    assert metadata["polygon_dataset_deprecated"] is True
    assert metadata["polygon_dataset_deprecation_notice"] == "legacy_world_dataset_deprecated_use_country_selection"


def test_country_mask_requires_include_iso_for_dataset_dir() -> None:
    facilities = pd.DataFrame([{"facility_id": "a", "asof_date": "2026-02-28"}])
    layer = CountryMaskLayer(version="v1")

    with pytest.raises(ValueError, match="requires non-empty include_iso_a2"):
        layer.compute(
            canonical_store={"facilities": facilities},
            layer_store={},
            params={
                "resolution": 4,
                "membership_rule": "centroid_in_polygon",
                "polygon_dataset_dir": "data/countries",
                "include_iso_a2": [],
            },
        )
