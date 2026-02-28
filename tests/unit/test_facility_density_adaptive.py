import h3
import pandas as pd

from inframap.layers.facility_density_adaptive import FacilityDensityAdaptiveLayer


def test_adaptive_layer_splits_dense_cells_until_threshold() -> None:
    parent = h3.latlng_to_cell(0.0, 0.0, 1)
    children = sorted(h3.cell_to_children(parent, 2))
    lat_a, lon_a = h3.cell_to_latlng(children[0])
    lat_b, lon_b = h3.cell_to_latlng(children[1])

    facilities = pd.DataFrame(
        [
            {"facility_id": "a", "lat": lat_a, "lon": lon_a, "asof_date": "2026-02-28"},
            {"facility_id": "b", "lat": lat_b, "lon": lon_b, "asof_date": "2026-02-28"},
        ]
    )

    layer = FacilityDensityAdaptiveLayer(version="v1")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store={},
        params={"min_resolution": 1, "max_resolution": 2, "split_threshold": 1},
    )

    assert metadata["layer_name"] == "facility_density_adaptive"
    assert metadata["params"]["split_threshold"] == 1
    assert len(cells) == 2
    assert set(cells["resolution"].tolist()) == {2}
    assert set(cells["layer_value"].tolist()) == {1}

