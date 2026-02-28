from pathlib import Path
from time import perf_counter

import pytest

from inframap.config import load_layers_config, load_system_config
from inframap.ingest.pipeline import ingest_and_normalize
from inframap.layers.country_mask import CountryMaskLayer
from inframap.layers.facility_density_adaptive import FacilityDensityAdaptiveLayer
from inframap.validation.invariants import run_invariants


@pytest.mark.perf_monitoring
def test_adaptive_compute_runtime_budget_fixture() -> None:
    facilities, _, _ = ingest_and_normalize(
        [(Path("tests/fixtures/facilities_small.csv"), "fixture")],
        canonical_h3_resolutions=[4, 5, 7, 9, 13],
    )
    country_layer = CountryMaskLayer(version="v1")
    _, country_cells = country_layer.compute(
        canonical_store={"facilities": facilities},
        layer_store={},
        params={
            "resolution": 4,
            "membership_rule": "centroid_in_polygon",
            "polygon_dataset": "data/reference/natural_earth_admin0_subset.geojson",
            "exclude_iso_a2": ["AQ"],
        },
    )
    adaptive = FacilityDensityAdaptiveLayer(version="v3")
    params = load_layers_config(Path("configs/layers.yaml")).layers[-1].params

    started = perf_counter()
    _, cells = adaptive.compute(
        canonical_store={"facilities": facilities},
        layer_store={"country_mask": {"metadata": {"layer_name": "country_mask", "layer_version": "v1"}, "cells": country_cells}},
        params=params,
    )
    elapsed = perf_counter() - started
    assert len(cells) > 0
    assert elapsed < 20.0


@pytest.mark.perf_monitoring
def test_adaptive_invariant_runtime_budget_fixture() -> None:
    system = load_system_config(Path("configs/system.yaml"))
    facilities, organizations, _ = ingest_and_normalize(
        [(Path("tests/fixtures/facilities_small.csv"), "fixture")],
        canonical_h3_resolutions=sorted(set(system.canonical_h3_resolutions + [system.country_mask_resolution])),
    )
    country_layer = CountryMaskLayer(version="v1")
    _, country_cells = country_layer.compute(
        canonical_store={"facilities": facilities},
        layer_store={},
        params={
            "resolution": 4,
            "membership_rule": "centroid_in_polygon",
            "polygon_dataset": "data/reference/natural_earth_admin0_subset.geojson",
            "exclude_iso_a2": ["AQ"],
        },
    )
    adaptive = FacilityDensityAdaptiveLayer(version="v3")
    params = load_layers_config(Path("configs/layers.yaml")).layers[-1].params
    metadata, cells = adaptive.compute(
        canonical_store={"facilities": facilities, "organizations": organizations},
        layer_store={"country_mask": {"metadata": {"layer_name": "country_mask", "layer_version": "v1"}, "cells": country_cells}},
        params=params,
    )
    layer_artifacts = {
        "facility_density_adaptive": {"metadata": metadata, "cells": cells},
        "country_mask": {"metadata": {"layer_name": "country_mask", "layer_version": "v1"}, "cells": country_cells},
    }

    started = perf_counter()
    run_invariants(
        facilities=facilities,
        layer_artifacts=layer_artifacts,
        required_h3_resolutions=system.canonical_h3_resolutions,
    )
    elapsed = perf_counter() - started
    assert elapsed < 15.0
