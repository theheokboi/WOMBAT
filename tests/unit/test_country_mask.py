import pandas as pd
import h3

from inframap.layers.country_mask import CountryMaskLayer


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
            "polygon_dataset": "data/reference/natural_earth_admin0_subset.geojson",
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
