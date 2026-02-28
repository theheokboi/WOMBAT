import h3
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from inframap.layers.metro_density_core import MetroDensityCoreLayer


@settings(max_examples=20)
@given(st.sampled_from(["872830828ffffff", "87283082effffff", "87283082affffff"]))
def test_contiguous_component_contains_seed(seed: str) -> None:
    neighbors = list(h3.grid_disk(seed, 1))
    rows = []
    for i, cell in enumerate(neighbors[:4]):
        rows.append({"facility_id": f"f{i}", "h3_r7": cell, "asof_date": "2026-02-28"})
        rows.append({"facility_id": f"ff{i}", "h3_r7": cell, "asof_date": "2026-02-28"})

    facilities = pd.DataFrame(rows)
    layer = MetroDensityCoreLayer(version="m1")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store={},
        params={"resolution": 7, "min_facilities": 1, "core_radius": 1, "enforce_contiguity": True},
    )
    assert metadata["seed_cell"] in set(cells["h3"])
