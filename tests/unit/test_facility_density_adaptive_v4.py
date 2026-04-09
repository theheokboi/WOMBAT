from typing import Any

import h3
import pandas as pd

from inframap.layers.facility_density_adaptive import FacilityDensityAdaptiveLayer


def _v4_params() -> dict[str, int | bool]:
    return {
        "base_resolution": 4,
        "min_output_resolution": 5,
        "empty_compact_min_resolution": 0,
        "facility_floor_resolution": 6,
        "facility_floor_offset": 1,
        "facility_max_resolution": 8,
        "target_facilities_per_leaf": 2,
        "empty_interior_max_resolution": 5,
        "empty_refine_boundary_band_k": 1,
        "empty_refine_near_occupied_k": 1,
        "compact_empty_near_occupied": True,
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
        [{"h3": cell, "resolution": base_resolution, "layer_value": "land", "country_name": "TW"} for cell in sorted(cells_set)]
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
        rows.append({"facility_id": f"f{i}", "lat": lat, "lon": lon, "asof_date": asof_date})
    return pd.DataFrame(rows)


def _assert_adaptive_counters_present(metadata: dict[str, Any]) -> None:
    counters = metadata["adaptive_counters"]
    assert isinstance(counters, dict)
    required = {
        "initial_recursion_seconds",
        "neighbor_smoothing_seconds",
        "post_compaction_seconds",
        "country_intersection_filter_seconds",
        "covering_leaf_lookup_count",
        "parent_cell_lookup_count",
        "smoothing_candidate_count",
        "smoothing_refinement_count",
        "compaction_candidate_count",
        "compaction_accept_count",
        "leaf_count_total",
        "adjacency_checks",
        "violating_neighbor_pairs",
        "max_neighbor_delta_observed",
        "smoothing_iterations",
    }
    assert required.issubset(counters.keys())


def test_adaptive_v4_singleton_occupied_region_stops_before_v3_floor() -> None:
    base = h3.latlng_to_cell(41.8781, -87.6298, 4)
    occupied_r7 = str(sorted(h3.cell_to_children(base, 7))[0])
    facilities = _facilities_from_cells([occupied_r7])
    params = _v4_params()
    params["facility_floor_resolution"] = 7
    params["facility_max_resolution"] = 8
    params["empty_interior_max_resolution"] = 6

    layer = FacilityDensityAdaptiveLayer(version="v4")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"]), radius=1),
        params=params,
    )

    occupied = cells[cells["layer_value"] > 0]
    assert metadata["layer_version"] == "v4"
    assert metadata["policy_name"] == "facility_hierarchical_partition_v4"
    assert len(occupied) == 1
    assert int(occupied.iloc[0]["resolution"]) == int(params["facility_floor_resolution"]) - int(
        params["facility_floor_offset"]
    )
    assert metadata["stopping_rules"]["facility_branch"]["rule"] == "sparse_until_floor_minus_offset_then_density"
    assert (
        metadata["stopping_rules"]["facility_branch"]["sparse_min_resolution"]
        == int(params["facility_floor_resolution"]) - int(params["facility_floor_offset"])
    )
    assert metadata["stopping_rules"]["facility_branch"]["facility_floor_offset"] == int(params["facility_floor_offset"])
    assert (
        metadata["stopping_rules"]["facility_branch"]["sparse_max_facility_count_inclusive"]
        == int(params["target_facilities_per_leaf"])
    )
    assert metadata["stopping_rules"]["post_compaction"]["occupied_singleton_compaction_enabled"] is False
    _assert_adaptive_counters_present(metadata)


def test_adaptive_v4_recursively_refines_dense_clusters_beyond_floor() -> None:
    base = h3.latlng_to_cell(41.8781, -87.6298, 4)
    r6_children = [str(child) for child in sorted(h3.cell_to_children(base, 6))]
    singleton_r6 = r6_children[0]
    dense_r8 = str(sorted(h3.cell_to_children(r6_children[1], 8))[0])
    facilities = _facilities_from_cells([singleton_r6, dense_r8, dense_r8, dense_r8])
    params = _v4_params()

    layer = FacilityDensityAdaptiveLayer(version="v4")
    _, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"])),
        params=params,
    )

    occupied = cells[cells["layer_value"] > 0].sort_values(["resolution", "h3"]).reset_index(drop=True)
    assert len(occupied) == 2
    singleton = occupied[occupied["layer_value"] == 1]
    dense = occupied[occupied["layer_value"] == 3]
    assert len(singleton) == 1
    assert len(dense) == 1
    assert int(singleton.iloc[0]["resolution"]) >= int(params["facility_floor_resolution"]) - int(
        params["facility_floor_offset"]
    )
    assert int(singleton.iloc[0]["resolution"]) < int(dense.iloc[0]["resolution"])
    assert int(dense.iloc[0]["resolution"]) == int(params["facility_max_resolution"])


def test_adaptive_v4_floor_offset_zero_allows_sparse_branch_to_stop_at_floor() -> None:
    base = h3.latlng_to_cell(41.8781, -87.6298, 4)
    occupied_r7 = str(sorted(h3.cell_to_children(base, 7))[0])
    facilities = _facilities_from_cells([occupied_r7])
    params = _v4_params()
    params["facility_floor_resolution"] = 7
    params["facility_floor_offset"] = 0
    params["facility_max_resolution"] = 8
    params["empty_interior_max_resolution"] = 7

    layer = FacilityDensityAdaptiveLayer(version="v4")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"]), radius=1),
        params=params,
    )

    occupied = cells[cells["layer_value"] > 0]
    assert len(occupied) == 1
    assert int(occupied.iloc[0]["resolution"]) == int(params["facility_floor_resolution"])
    assert metadata["stopping_rules"]["facility_branch"]["sparse_min_resolution"] == int(params["facility_floor_resolution"])
    assert metadata["stopping_rules"]["empty_branch"]["boundary_or_near_occupied_max_resolution"] == int(
        params["facility_floor_resolution"]
    )


def test_adaptive_v4_accepts_country_edge_alias_param() -> None:
    base = h3.latlng_to_cell(41.8781, -87.6298, 4)
    occupied_r7 = str(sorted(h3.cell_to_children(base, 7))[0])
    facilities = _facilities_from_cells([occupied_r7])
    params = _v4_params()
    params["empty_refine_country_edge_k"] = int(params.pop("empty_refine_boundary_band_k"))

    layer = FacilityDensityAdaptiveLayer(version="v4")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"]), radius=1),
        params=params,
    )

    assert not cells.empty
    assert metadata["params"]["empty_refine_country_edge_k"] == 1
    assert metadata["params"]["empty_refine_boundary_band_k"] == 1
    assert metadata["stopping_rules"]["empty_branch"]["country_edge_k"] == 1
    assert metadata["stopping_rules"]["empty_branch"]["boundary_band_k"] == 1


def test_adaptive_v4_does_not_compact_singleton_occupied_sibling_group() -> None:
    layer = FacilityDensityAdaptiveLayer(version="v4")
    parent = str(h3.latlng_to_cell(41.8781, -87.6298, 5))
    children_list = [str(child) for child in sorted(h3.cell_to_children(parent, 6))]
    children = {child: 0 for child in children_list}
    children[children_list[0]] = 1

    compacted = layer._compact_sparse_sibling_leaves(
        leaves=children,
        min_output_resolution=5,
        base_resolution=4,
        empty_interior_max_resolution=7,
        facility_floor_resolution=9,
        facility_max_resolution=9,
        max_neighbor_resolution_delta=1,
        intersects_domain=lambda cell, resolution: True,
        is_boundary_band=lambda cell, resolution: False,
        is_near_occupied=lambda cell, resolution: False,
        compact_empty_near_occupied=True,
        adaptive_counters={},
    )

    assert compacted == children
