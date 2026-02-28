import h3
import pandas as pd
import pytest

from inframap.layers.facility_density_adaptive import FacilityDensityAdaptiveLayer
from inframap.validation.invariants import run_invariants


def _adaptive_v3_params() -> dict[str, int]:
    return {
        "base_resolution": 4,
        "min_output_resolution": 5,
        "empty_compact_min_resolution": 0,
        "facility_floor_resolution": 9,
        "facility_max_resolution": 9,
        "target_facilities_per_leaf": 1,
        "empty_interior_max_resolution": 7,
        "empty_refine_boundary_band_k": 1,
        "empty_refine_near_occupied_k": 1,
        "max_neighbor_resolution_delta": 1,
    }


def _country_mask_store(
    base_resolution: int = 4, radius: int = 0
) -> dict[str, dict[str, pd.DataFrame | dict[str, str]]]:
    base_cell = str(h3.latlng_to_cell(41.8781, -87.6298, base_resolution))
    cells_set = {base_cell}
    if radius > 0:
        cells_set = {str(cell) for cell in h3.grid_disk(base_cell, radius)}
    cells = pd.DataFrame(
        [{"h3": cell, "resolution": base_resolution, "layer_value": "land", "country_name": "US"} for cell in sorted(cells_set)]
    )
    return {
        "country_mask": {
            "metadata": {"layer_name": "country_mask", "layer_version": "v1"},
            "cells": cells,
        }
    }


def _facilities_from_cells(cells: list[str], asof_date: str = "2026-02-28") -> pd.DataFrame:
    rows = []
    for i, cell in enumerate(cells):
        lat, lon = h3.cell_to_latlng(cell)
        rows.append({"facility_id": f"f{i}", "lat": lat, "lon": lon, "h3_r5": "852664c7fffffff", "asof_date": asof_date})
    return pd.DataFrame(rows)


def test_invariants_pass_for_valid_data() -> None:
    facilities = pd.DataFrame(
        [
            {"facility_id": "f1", "lat": 41.0, "lon": -87.0, "h3_r5": "852664c7fffffff"},
            {"facility_id": "f2", "lat": 40.0, "lon": -88.0, "h3_r5": "85266437fffffff"},
        ]
    )
    layer_artifacts = {
        "metro_density_core": {
            "metadata": {"layer_name": "metro_density_core", "layer_version": "m1", "seed_cell": "852664c7fffffff"},
            "cells": pd.DataFrame(
                [{"h3": "852664c7fffffff", "resolution": 5, "layer_value": 2, "layer_id": "metro_density_core:m1"}]
            ),
        }
    }
    run_invariants(facilities, layer_artifacts, required_h3_resolutions=[5])


def test_invariants_fail_on_duplicate_facility_id() -> None:
    facilities = pd.DataFrame(
        [
            {"facility_id": "f1", "lat": 41.0, "lon": -87.0, "h3_r5": "852664c7fffffff"},
            {"facility_id": "f1", "lat": 40.0, "lon": -88.0, "h3_r5": "85266437fffffff"},
        ]
    )
    with pytest.raises(ValueError, match="facility_id"):
        run_invariants(facilities, {}, required_h3_resolutions=[5])


def test_invariants_pass_for_adaptive_mixed_resolution_partition_without_overlap() -> None:
    base = h3.latlng_to_cell(41.0, -87.0, 8)
    child = sorted(h3.cell_to_children(base, 9))[0]
    sibling = sorted(h3.cell_to_children(base, 9))[1]

    facilities = pd.DataFrame(
        [
            {"facility_id": "f1", "lat": 41.0, "lon": -87.0, "h3_r5": "852664c7fffffff"},
            {"facility_id": "f2", "lat": 42.0, "lon": -88.0, "h3_r5": "85266437fffffff"},
        ]
    )
    layer_artifacts = {
        "facility_density_adaptive": {
            "metadata": {
                "layer_name": "facility_density_adaptive",
                "layer_version": "v3",
                "policy_name": "facility_hierarchical_partition_v3",
                "coverage_domain": "country_mask_r4",
            },
            "cells": pd.DataFrame(
                [
                    {
                        "h3": child,
                        "resolution": 9,
                        "layer_value": 1,
                        "layer_id": "facility_density_adaptive:v3",
                    },
                    {
                        "h3": sibling,
                        "resolution": 9,
                        "layer_value": 1,
                        "layer_id": "facility_density_adaptive:v3",
                    },
                ]
            ),
        }
    }
    run_invariants(facilities, layer_artifacts, required_h3_resolutions=[5])


def test_invariants_fail_on_adaptive_ancestor_descendant_overlap() -> None:
    parent = h3.latlng_to_cell(41.0, -87.0, 9)
    child = sorted(h3.cell_to_children(parent, 10))[0]

    facilities = pd.DataFrame(
        [
            {"facility_id": "f1", "lat": 41.0, "lon": -87.0, "h3_r5": "852664c7fffffff"},
            {"facility_id": "f2", "lat": 42.0, "lon": -88.0, "h3_r5": "85266437fffffff"},
        ]
    )
    layer_artifacts = {
        "facility_density_adaptive": {
            "metadata": {
                "layer_name": "facility_density_adaptive",
                "layer_version": "v3",
                "policy_name": "facility_hierarchical_partition_v3",
                "coverage_domain": "country_mask_r4",
            },
            "cells": pd.DataFrame(
                [
                    {
                        "h3": parent,
                        "resolution": 9,
                        "layer_value": 1,
                        "layer_id": "facility_density_adaptive:v3",
                    },
                    {
                        "h3": child,
                        "resolution": 10,
                        "layer_value": 1,
                        "layer_id": "facility_density_adaptive:v3",
                    },
                ]
            ),
        }
    }
    with pytest.raises(ValueError, match="ancestor|descendant|overlap|partition"):
        run_invariants(facilities, layer_artifacts, required_h3_resolutions=[5])


def test_invariants_pass_when_adaptive_neighbor_smoothing_delta_within_limit() -> None:
    coarse = str(h3.latlng_to_cell(41.0, -87.0, 8))
    adjacent_coarse = sorted(str(cell) for cell in h3.grid_disk(coarse, 1) if str(cell) != coarse)[0]
    fine = None
    for child in sorted(str(cell) for cell in h3.cell_to_children(adjacent_coarse, 9)):
        if any(h3.cell_to_parent(str(neighbor), 8) == coarse for neighbor in h3.grid_disk(child, 1)):
            fine = child
            break
    assert fine is not None
    facilities = pd.DataFrame(
        [
            {"facility_id": "f1", "lat": 41.0, "lon": -87.0, "h3_r5": "852664c7fffffff"},
            {"facility_id": "f2", "lat": 42.0, "lon": -88.0, "h3_r5": "85266437fffffff"},
        ]
    )
    layer_artifacts = {
        "facility_density_adaptive": {
            "metadata": {
                "layer_name": "facility_density_adaptive",
                "layer_version": "v3",
                "policy_name": "facility_hierarchical_partition_v3",
                "coverage_domain": "country_mask_r4",
                "params": {"max_neighbor_resolution_delta": 1},
            },
            "cells": pd.DataFrame(
                [
                    {"h3": coarse, "resolution": 8, "layer_value": 0, "layer_id": "facility_density_adaptive:v3"},
                    {"h3": fine, "resolution": 9, "layer_value": 1, "layer_id": "facility_density_adaptive:v3"},
                ]
            ),
        }
    }
    run_invariants(facilities, layer_artifacts, required_h3_resolutions=[5])


def test_invariants_fail_when_adaptive_neighbor_smoothing_delta_exceeds_limit() -> None:
    coarse = str(h3.latlng_to_cell(41.0, -87.0, 7))
    adjacent_coarse = sorted(str(cell) for cell in h3.grid_disk(coarse, 1) if str(cell) != coarse)[0]
    fine = None
    for child in sorted(str(cell) for cell in h3.cell_to_children(adjacent_coarse, 9)):
        if any(h3.cell_to_parent(str(neighbor), 7) == coarse for neighbor in h3.grid_disk(child, 1)):
            fine = child
            break
    assert fine is not None
    facilities = pd.DataFrame(
        [
            {"facility_id": "f1", "lat": 41.0, "lon": -87.0, "h3_r5": "852664c7fffffff"},
            {"facility_id": "f2", "lat": 42.0, "lon": -88.0, "h3_r5": "85266437fffffff"},
        ]
    )
    layer_artifacts = {
        "facility_density_adaptive": {
            "metadata": {
                "layer_name": "facility_density_adaptive",
                "layer_version": "v3",
                "policy_name": "facility_hierarchical_partition_v3",
                "coverage_domain": "country_mask_r4",
                "params": {"max_neighbor_resolution_delta": 1},
            },
            "cells": pd.DataFrame(
                [
                    {"h3": coarse, "resolution": 7, "layer_value": 0, "layer_id": "facility_density_adaptive:v3"},
                    {"h3": fine, "resolution": 9, "layer_value": 1, "layer_id": "facility_density_adaptive:v3"},
                ]
            ),
        }
    }
    with pytest.raises(ValueError, match="smoothing adjacency delta"):
        run_invariants(facilities, layer_artifacts, required_h3_resolutions=[5])


def test_invariants_pass_for_real_adaptive_output_with_dense_local_neighbors() -> None:
    params = _adaptive_v3_params()
    facilities = _facilities_from_cells(["8d2664c2abaa53f", "8d2664c2aba343f"])
    layer = FacilityDensityAdaptiveLayer(version="v3")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities[["facility_id", "lat", "lon", "asof_date"]]},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"]), radius=2),
        params=params,
    )
    layer_artifacts = {"facility_density_adaptive": {"metadata": metadata, "cells": cells}}
    run_invariants(facilities, layer_artifacts, required_h3_resolutions=[5])
