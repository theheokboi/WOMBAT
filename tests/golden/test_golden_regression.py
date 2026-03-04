from hashlib import sha256
import json
from pathlib import Path

from inframap.ingest.pipeline import ingest_and_normalize
from inframap.layers.country_mask import CountryMaskLayer
from inframap.layers.facility_density_adaptive import FacilityDensityAdaptiveLayer
from inframap.layers.metro_density_core import MetroDensityCoreLayer
import h3


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


def _has_ancestor_descendant_overlap(cells: list[dict[str, object]]) -> bool:
    for i, row in enumerate(cells):
        cell = str(row["h3"])
        resolution = int(row["resolution"])
        for j, other in enumerate(cells):
            if i == j:
                continue
            other_cell = str(other["h3"])
            other_resolution = int(other["resolution"])
            if other_resolution <= resolution:
                continue
            if h3.cell_to_parent(other_cell, resolution) == cell:
                return True
    return False


def test_golden_canonical_facilities_hash() -> None:
    facilities, _, _ = ingest_and_normalize(
        [(Path("tests/fixtures/facilities_small.csv"), "fixture")],
        canonical_h3_resolutions=[4, 5, 7],
    )
    actual = sha256(facilities.sort_values("facility_id").to_csv(index=False).encode("utf-8")).hexdigest()
    expected = Path("tests/golden/canonical_facilities_hash.txt").read_text(encoding="utf-8").strip()
    assert actual == expected


def test_golden_metro_density_core_cells() -> None:
    facilities, _, _ = ingest_and_normalize(
        [(Path("tests/fixtures/facilities_small.csv"), "fixture")],
        canonical_h3_resolutions=[4, 5, 7],
    )
    layer = MetroDensityCoreLayer(version="m1")
    _, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store={},
        params={"resolution": 7, "min_facilities": 1, "core_radius": 2, "enforce_contiguity": True},
    )
    expected = json.loads(Path("tests/golden/metro_density_core_cells.json").read_text(encoding="utf-8"))
    assert sorted(cells["h3"].tolist()) == expected


def test_golden_country_mask_cells(tmp_path: Path) -> None:
    facilities, _, _ = ingest_and_normalize(
        [(Path("tests/fixtures/facilities_small.csv"), "fixture")],
        canonical_h3_resolutions=[4, 5, 7],
    )
    polygon_dataset = _write_country_polygon_dataset(tmp_path, "US")
    layer = CountryMaskLayer(version="v1")
    _, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store={},
        params={
            "resolution": 4,
            "membership_rule": "centroid_in_polygon",
            "polygon_dataset": str(polygon_dataset),
            "exclude_iso_a2": ["AQ"],
        },
    )
    subset = cells[["h3", "layer_value", "country_color"]].sort_values(
        ["h3", "layer_value", "country_color"]
    ).reset_index(drop=True)
    actual = sha256(subset.to_csv(index=False).encode("utf-8")).hexdigest()
    expected = Path("tests/golden/country_mask_cells_hash.txt").read_text(encoding="utf-8").strip()
    assert actual == expected


def test_golden_facility_density_adaptive_v3_fixture_is_deterministic_with_valid_partition() -> None:
    facilities, _, _ = ingest_and_normalize(
        [(Path("tests/fixtures/facilities_small.csv"), "fixture")],
        canonical_h3_resolutions=[4, 5, 7, 9, 13],
    )
    domain_r4 = sorted({str(cell) for cell in facilities["h3_r4"].astype(str).tolist()})
    country_cells = (
        facilities[["h3_r4"]]
        .drop_duplicates()
        .assign(
            h3=lambda frame: frame["h3_r4"].astype(str),
            resolution=4,
            layer_value="land",
            country_name="fixture",
        )[["h3", "resolution", "layer_value", "country_name"]]
        .sort_values("h3")
        .reset_index(drop=True)
    )
    assert len(domain_r4) == len(country_cells)

    adaptive = FacilityDensityAdaptiveLayer(version="v3")
    params = {
        "base_resolution": 4,
        "empty_compact_min_resolution": 0,
        "facility_floor_resolution": 9,
        "facility_max_resolution": 13,
        "target_facilities_per_leaf": 1,
        "empty_interior_max_resolution": 7,
        "empty_refine_boundary_band_k": 1,
        "empty_refine_near_occupied_k": 1,
        "max_neighbor_resolution_delta": 1,
    }
    metadata_a, cells_a = adaptive.compute(
        canonical_store={"facilities": facilities},
        layer_store={"country_mask": {"metadata": {"layer_name": "country_mask", "layer_version": "v1"}, "cells": country_cells}},
        params=params,
    )
    metadata_b, cells_b = adaptive.compute(
        canonical_store={"facilities": facilities},
        layer_store={"country_mask": {"metadata": {"layer_name": "country_mask", "layer_version": "v1"}, "cells": country_cells}},
        params=params,
    )

    assert metadata_a["layer_version"] == "v3"
    assert metadata_a["coverage_domain"] == "country_mask_r4"
    assert metadata_a == metadata_b
    subset_a = cells_a[["h3", "resolution", "layer_value"]].sort_values(["resolution", "h3"]).to_dict("records")
    subset_b = cells_b[["h3", "resolution", "layer_value"]].sort_values(["resolution", "h3"]).to_dict("records")
    assert subset_a == subset_b
    assert cells_a["h3"].is_unique
    assert int(cells_a["resolution"].min()) >= 0
    assert int(cells_a["resolution"].max()) <= 13
    occupied = cells_a[cells_a["layer_value"] > 0]
    assert not occupied.empty
    assert int(occupied["resolution"].min()) >= 9
    assert not _has_ancestor_descendant_overlap(subset_a)
