import json
from pathlib import Path

import pandas as pd
import h3
import pytest
from shapely.geometry import Polygon

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


def _has_ancestor_descendant_overlap(cells: pd.DataFrame) -> bool:
    cell_set = {str(value) for value in cells["h3"].astype(str).tolist()}
    for cell in sorted(cell_set, key=h3.get_resolution):
        resolution = h3.get_resolution(cell)
        for ancestor_resolution in range(resolution - 1, -1, -1):
            if h3.cell_to_parent(cell, ancestor_resolution) in cell_set:
                return True
    return False


def test_country_mask_fixed_overlap_ratio_assignment_rule() -> None:
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
            "membership_rule": "overlap_ratio",
            "polygon_dataset_dir": "data/countries",
            "include_iso_a2": ["TW"],
            "exclude_iso_a2": ["AQ"],
        },
    )

    assert metadata["layer_name"] == "country_mask"
    assert metadata["params"]["membership_rule"] == "overlap_ratio"
    assert metadata["distance_semantics"] == "fixed_resolution_overlap_ratio"
    assert len(cells) > 0
    assert cells["layer_value"].notnull().all()
    assert not cells["h3"].duplicated().any()
    assert "country_color" in cells.columns
    assert cells["country_color"].notnull().all()
    assert "country_color_palette" in metadata
    assert "AQ" not in set(cells["layer_value"].tolist())
    assert metadata["params"]["include_iso_a2"] == ["TW"]
    assert metadata["polygon_dataset_files"] == ["data/countries/TW.geojson"]
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


def test_country_mask_quadtree_classify_split_outputs_mixed_resolutions() -> None:
    facilities = pd.DataFrame([{"facility_id": "a", "asof_date": "2026-02-28"}])
    layer = CountryMaskLayer(version="v1")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store={},
        params={
            "mode": "quadtree_classify_split",
            "membership_rule": "centroid_in_polygon",
            "base_resolution": 2,
            "max_resolution": 6,
            "base_contain": "overlap",
            "inside_epsilon": 0.000001,
            "outside_epsilon": 0.000000001,
            "polygon_dataset_dir": "data/countries",
            "include_iso_a2": ["TW"],
            "exclude_iso_a2": [],
        },
    )

    assert metadata["params"]["mode"] == "quadtree_classify_split"
    assert metadata["distance_semantics"] == "quadtree_classify_split_overlap_ratio"
    resolutions = set(cells["resolution"].astype(int).tolist())
    assert min(resolutions) >= 2
    assert max(resolutions) == 6
    assert len(resolutions) > 1
    assert not _has_ancestor_descendant_overlap(cells)


def test_country_mask_warns_on_legacy_world_dataset_path(tmp_path: Path) -> None:
    facilities = pd.DataFrame([{"facility_id": "a", "asof_date": "2026-02-28"}])
    polygon_dataset = _write_country_polygon_dataset(tmp_path, "TW")
    layer = CountryMaskLayer(version="v1", legacy_world_dataset_path=str(polygon_dataset))

    with pytest.warns(UserWarning, match="deprecated legacy world file"):
        metadata, _ = layer.compute(
            canonical_store={"facilities": facilities},
            layer_store={},
            params={
                "resolution": 4,
                "membership_rule": "overlap_ratio",
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
                "membership_rule": "overlap_ratio",
                "polygon_dataset_dir": "data/countries",
                "include_iso_a2": [],
            },
        )


def test_country_mask_emits_polygon_progress_notes() -> None:
    facilities = pd.DataFrame([{"facility_id": "a", "asof_date": "2026-02-28"}])
    layer = CountryMaskLayer(version="v1")
    notes: list[str] = []

    def progress(note: str) -> None:
        notes.append(note)

    layer.compute(
        canonical_store={"facilities": facilities},
        layer_store={},
        params={
            "mode": "quadtree_classify_split",
            "membership_rule": "centroid_in_polygon",
            "base_resolution": 2,
            "max_resolution": 3,
            "base_contain": "overlap",
            "inside_epsilon": 0.000001,
            "outside_epsilon": 0.000000001,
            "polygon_dataset_dir": "data/countries",
            "include_iso_a2": ["TW"],
            "_progress_cb": progress,
        },
    )

    assert any(note.startswith("polygons loaded: ") for note in notes)
    assert any("polygon 1/" in note for note in notes)
    assert any(note.startswith("polygon processing complete: ") for note in notes)


def test_country_mask_fixed_overlap_ratio_selects_any_positive_overlap(tmp_path: Path) -> None:
    facilities = pd.DataFrame([{"facility_id": "a", "asof_date": "2026-02-28"}])
    polygon_dataset = tmp_path / "tiny_tw.geojson"
    polygon_dataset.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"iso_a2": "TW", "name": "TW"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [121.50, 25.00],
                                    [121.51, 25.00],
                                    [121.51, 25.01],
                                    [121.50, 25.01],
                                    [121.50, 25.00],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    layer = CountryMaskLayer(version="v1")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store={},
        params={
            "mode": "fixed_resolution",
            "resolution": 2,
            "membership_rule": "overlap_ratio",
            "polygon_dataset": str(polygon_dataset),
            "exclude_iso_a2": [],
        },
    )

    assert metadata["params"]["mode"] == "fixed_resolution"
    assert metadata["params"]["resolution"] == 2
    assert not cells.empty
    assert list(cells.columns) == [
        "h3",
        "resolution",
        "layer_value",
        "country_name",
        "country_color",
        "country_color_hex",
        "layer_id",
        "asof_date",
    ]

    counters = metadata["country_mask_counters"]
    fixed_counters = counters["fixed_resolution"]
    assert counters["polygon_count"] == 1
    assert counters["polygon_load_seconds"] >= 0.0
    assert fixed_counters["candidate_generation_seconds"] >= 0.0
    assert fixed_counters["overlap_filter_seconds"] >= 0.0
    assert fixed_counters["candidate_cell_count"] >= fixed_counters["accepted_cell_count"]
    assert fixed_counters["accepted_cell_count"] == len(cells)
    assert len(fixed_counters["per_polygon"]) == 1
    per_polygon = fixed_counters["per_polygon"][0]
    assert per_polygon["iso_a2"] == "TW"
    assert per_polygon["country_name"] == "TW"
    assert per_polygon["candidate_cell_count"] >= per_polygon["accepted_cell_count"] > 0
    assert per_polygon["candidate_generation_seconds"] >= 0.0
    assert per_polygon["overlap_filter_seconds"] >= 0.0
    assert fixed_counters["hottest_overlap_filter_polygon"]["iso_a2"] == "TW"


def test_country_mask_positive_overlap_predicate_rejects_touch_only_cells() -> None:
    layer = CountryMaskLayer(version="v1")
    cell = h3.latlng_to_cell(35.6764, 139.6500, 2)
    cell_polygon = layer._cell_polygon(cell)
    min_lon, min_lat, max_lon, max_lat = cell_polygon.bounds
    sliver = max(max_lon - min_lon, max_lat - min_lat) / 100.0

    touch_only_polygon = Polygon(
        [
            (max_lon, min_lat),
            (max_lon + sliver, min_lat),
            (max_lon + sliver, max_lat),
            (max_lon, max_lat),
            (max_lon, min_lat),
        ]
    )
    positive_overlap_polygon = Polygon(
        [
            (max_lon - sliver, min_lat),
            (max_lon + sliver, min_lat),
            (max_lon + sliver, max_lat),
            (max_lon - sliver, max_lat),
            (max_lon - sliver, min_lat),
        ]
    )

    assert layer._overlap_ratio(cell, touch_only_polygon) == 0.0
    assert layer._has_positive_area_overlap(cell, touch_only_polygon) is False
    assert layer._overlap_ratio(cell, positive_overlap_polygon) > 0.0
    assert layer._has_positive_area_overlap(cell, positive_overlap_polygon) is True
