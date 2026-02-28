from pathlib import Path

import pandas as pd

from inframap.config import load_layers_config
from inframap.layers.registry import build_layer_registry


def test_layer_registry_loads_explicit_plugins() -> None:
    layers = load_layers_config(Path("configs/layers.yaml"))
    registry = build_layer_registry(layers)
    assert set(registry.keys()) == {"metro_density_core", "country_mask"}


def test_metro_density_core_outputs_seed_and_cells() -> None:
    facilities = pd.DataFrame(
        [
            {"facility_id": "a", "h3_r7": "872830828ffffff", "asof_date": "2026-02-28"},
            {"facility_id": "b", "h3_r7": "872830828ffffff", "asof_date": "2026-02-28"},
            {"facility_id": "c", "h3_r7": "87283082effffff", "asof_date": "2026-02-28"},
        ]
    )
    layers = load_layers_config(Path("configs/layers.yaml"))
    registry = build_layer_registry(layers)
    metro = registry["metro_density_core"]
    metadata, cells = metro.compute(
        canonical_store={"facilities": facilities},
        layer_store={},
        params={"resolution": 7, "min_facilities": 1, "core_radius": 1, "enforce_contiguity": True},
    )

    assert metadata["layer_name"] == "metro_density_core"
    assert metadata["layer_version"] == "m1"
    assert metadata["seed_cell"] in set(cells["h3"])
    assert (cells["resolution"] == 7).all()
