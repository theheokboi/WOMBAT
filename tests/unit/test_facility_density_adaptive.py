import h3
import pandas as pd

from inframap.layers.facility_density_adaptive import FacilityDensityAdaptiveLayer


def _v2_params() -> dict[str, int | bool]:
    return {
        "base_resolution": 4,
        "empty_compact_min_resolution": 0,
        "facility_floor_resolution": 9,
        "facility_max_resolution": 13,
        "target_facilities_per_leaf": 1,
        "allow_domain_expansion": True,
        "allow_cross_border_compaction": True,
    }


def _country_mask_store(base_resolution: int = 4) -> dict[str, dict[str, pd.DataFrame | dict[str, str]]]:
    base_cell = h3.latlng_to_cell(41.8781, -87.6298, base_resolution)
    cells = pd.DataFrame(
        [{"h3": base_cell, "resolution": base_resolution, "layer_value": "land", "country_name": "US"}]
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


def _has_ancestor_descendant_overlap(cells: pd.DataFrame) -> bool:
    h3_cells = [str(value) for value in cells["h3"].tolist()]
    resolutions = [int(value) for value in cells["resolution"].tolist()]
    for idx, cell in enumerate(h3_cells):
        resolution = resolutions[idx]
        for jdx, other in enumerate(h3_cells):
            if idx == jdx:
                continue
            other_resolution = resolutions[jdx]
            if other_resolution <= resolution:
                continue
            if h3.cell_to_parent(other, resolution) == cell:
                return True
    return False


def test_adaptive_v2_empty_domain_compacts_to_coarse_levels() -> None:
    facilities = pd.DataFrame(columns=["facility_id", "lat", "lon", "asof_date"])
    params = _v2_params()

    layer = FacilityDensityAdaptiveLayer(version="v2")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"])),
        params=params,
    )

    assert metadata["layer_name"] == "facility_density_adaptive"
    assert metadata["layer_version"] == "v2"
    assert metadata["policy_name"] == "facility_hierarchical_partition_v2"
    assert metadata["coverage_domain"] == "country_mask_r4"
    assert int(cells["resolution"].min()) == int(params["empty_compact_min_resolution"])


def test_adaptive_v2_enforces_facility_floor_r9() -> None:
    base = h3.latlng_to_cell(41.8781, -87.6298, 4)
    child = sorted(h3.cell_to_children(base, 9))[0]
    facilities = _facilities_from_cells([child])
    params = _v2_params()

    layer = FacilityDensityAdaptiveLayer(version="v2")
    _, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"])),
        params=params,
    )

    occupied = cells[cells["layer_value"] > 0]
    assert not occupied.empty
    assert int(occupied["resolution"].min()) >= int(params["facility_floor_resolution"])


def test_adaptive_v2_splits_to_singleton_or_stops_at_r13_cap() -> None:
    base = h3.latlng_to_cell(41.8781, -87.6298, 4)
    forced_dense_leaf = sorted(h3.cell_to_children(base, 13))[0]
    lat, lon = h3.cell_to_latlng(forced_dense_leaf)
    facilities = pd.DataFrame(
        [{"facility_id": f"f{i}", "lat": lat, "lon": lon, "asof_date": "2026-02-28"} for i in range(5)]
    )
    params = _v2_params()

    layer = FacilityDensityAdaptiveLayer(version="v2")
    _, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"])),
        params=params,
    )

    occupied = cells[cells["layer_value"] > 0]
    assert not occupied.empty
    assert int(occupied["resolution"].max()) <= int(params["facility_max_resolution"])
    violating = occupied[
        (occupied["layer_value"] > int(params["target_facilities_per_leaf"]))
        & (occupied["resolution"] < int(params["facility_max_resolution"]))
    ]
    assert violating.empty


def test_adaptive_v2_final_partition_has_no_ancestor_descendant_overlap() -> None:
    base = h3.latlng_to_cell(41.8781, -87.6298, 4)
    children_r9 = sorted(h3.cell_to_children(base, 9))
    facilities = _facilities_from_cells([children_r9[0], children_r9[1], children_r9[2]])
    params = _v2_params()

    layer = FacilityDensityAdaptiveLayer(version="v2")
    _, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"])),
        params=params,
    )

    assert not cells["h3"].duplicated().any()
    assert not _has_ancestor_descendant_overlap(cells)
