from hashlib import sha256
import json
from pathlib import Path

from inframap.ingest.pipeline import ingest_and_normalize
from inframap.layers.country_mask import CountryMaskLayer
from inframap.layers.metro_density_core import MetroDensityCoreLayer


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


def test_golden_country_mask_cells() -> None:
    facilities, _, _ = ingest_and_normalize(
        [(Path("tests/fixtures/facilities_small.csv"), "fixture")],
        canonical_h3_resolutions=[4, 5, 7],
    )
    layer = CountryMaskLayer(version="v1")
    _, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store={},
        params={
            "resolution": 4,
            "membership_rule": "centroid_in_polygon",
            "polygon_dataset": "data/reference/natural_earth_admin0_subset.geojson",
            "exclude_iso_a2": ["AQ"],
        },
    )
    subset = cells[["h3", "layer_value", "country_color"]].sort_values(
        ["h3", "layer_value", "country_color"]
    ).reset_index(drop=True)
    actual = sha256(subset.to_csv(index=False).encode("utf-8")).hexdigest()
    expected = Path("tests/golden/country_mask_cells_hash.txt").read_text(encoding="utf-8").strip()
    assert actual == expected
