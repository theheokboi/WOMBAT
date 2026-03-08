import json
from pathlib import Path
from typing import Any

import h3
import pandas as pd
import pytest
from shapely.geometry import Polygon, shape

from inframap.layers.facility_density_adaptive import FacilityDensityAdaptiveLayer


def _v3_params() -> dict[str, int | bool]:
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


def _max_neighbor_resolution_delta(cells: pd.DataFrame) -> int:
    adaptive_cells = {str(cell) for cell in cells["h3"].astype(str).tolist()}
    if not adaptive_cells:
        return 0
    resolution_by_cell = {cell: h3.get_resolution(cell) for cell in adaptive_cells}
    by_resolution: dict[int, set[str]] = {resolution: set() for resolution in range(14)}
    for cell, resolution in resolution_by_cell.items():
        by_resolution[resolution].add(cell)
    parent_cache: dict[tuple[str, int], str] = {}

    def parent_cell(cell: str, resolution: int) -> str:
        key = (cell, resolution)
        cached = parent_cache.get(key)
        if cached is not None:
            return cached
        if h3.get_resolution(cell) == resolution:
            parent_cache[key] = cell
        else:
            parent_cache[key] = h3.cell_to_parent(cell, resolution)
        return parent_cache[key]

    def covering_leaf_for_neighbor(cell: str, resolution: int) -> int | None:
        for ancestor_resolution in range(resolution, -1, -1):
            ancestor = parent_cell(cell, ancestor_resolution)
            if ancestor in by_resolution[ancestor_resolution]:
                return ancestor_resolution
        return None

    max_delta = 0
    for cell in sorted(adaptive_cells, key=lambda c: (resolution_by_cell[c], c)):
        resolution = resolution_by_cell[cell]
        for neighbor in [str(value) for value in h3.grid_disk(cell, 1)]:
            if neighbor == cell:
                continue
            neighbor_resolution = covering_leaf_for_neighbor(neighbor, resolution)
            if neighbor_resolution is None:
                continue
            max_delta = max(max_delta, abs(resolution - neighbor_resolution))
    return max_delta


def _cell_overlap_ratio(cell: str, polygon: Any) -> float:
    ring = []
    prev_lon: float | None = None
    for lat, lon in h3.cell_to_boundary(cell):
        adj_lon = float(lon)
        if prev_lon is not None:
            while adj_lon - prev_lon > 180:
                adj_lon -= 360
            while adj_lon - prev_lon < -180:
                adj_lon += 360
        ring.append((adj_lon, float(lat)))
        prev_lon = adj_lon
    ring.append(ring[0])
    poly = Polygon(ring)
    if poly.is_empty or poly.area == 0:
        return 0.0
    return float(poly.intersection(polygon).area / poly.area)


def test_adaptive_v3_empty_domain_compacts_to_coarse_levels() -> None:
    facilities = pd.DataFrame(columns=["facility_id", "lat", "lon", "asof_date"])
    params = _v3_params()

    layer = FacilityDensityAdaptiveLayer(version="v3")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"]), radius=1),
        params=params,
    )

    assert metadata["layer_name"] == "facility_density_adaptive"
    assert metadata["layer_version"] == "v3"
    assert metadata["policy_name"] == "facility_hierarchical_partition_v3"
    assert metadata["coverage_domain"] == "country_mask_r4"
    assert int(cells["resolution"].min()) >= int(params["min_output_resolution"])
    assert int(cells["resolution"].max()) <= int(params["facility_floor_resolution"]) - 1
    assert (cells["resolution"] == int(params["min_output_resolution"])).any()


def test_adaptive_v3_accepts_configurable_min_output_resolution_below_r5() -> None:
    facilities = pd.DataFrame(columns=["facility_id", "lat", "lon", "asof_date"])
    params = _v3_params()
    params["min_output_resolution"] = 3

    layer = FacilityDensityAdaptiveLayer(version="v3")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"]), radius=1),
        params=params,
    )

    assert int(metadata["params"]["min_output_resolution"]) == 3
    assert int(cells["resolution"].min()) >= 3
    assert int(cells["resolution"].min()) < 5


def test_adaptive_v3_filters_non_intersecting_cells_from_country_polygon(tmp_path: Path) -> None:
    polygon_dataset = tmp_path / "tiny_tw.geojson"
    polygon_dataset.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"iso_a2": "TW", "name": "TW"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [121.50, 25.00],
                                    [121.51, 25.00],
                                    [121.51, 25.01],
                                    [121.50, 25.01],
                                    [121.50, 25.00],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    polygon_payload = json.loads(polygon_dataset.read_text(encoding="utf-8"))
    polygon = shape(polygon_payload["features"][0]["geometry"])
    anchor_cell = str(h3.latlng_to_cell(25.005, 121.505, 2))
    params = _v3_params()
    params["base_resolution"] = 2
    params["min_output_resolution"] = 3
    params["facility_floor_resolution"] = 7
    params["facility_max_resolution"] = 7
    params["empty_interior_max_resolution"] = 3
    facilities = pd.DataFrame(columns=["facility_id", "lat", "lon", "asof_date"])
    layer_store = {
        "country_mask": {
            "metadata": {
                "layer_name": "country_mask",
                "layer_version": "v1",
                "params": {
                    "mode": "fixed_resolution",
                    "resolution": 2,
                    "membership_rule": "overlap_ratio",
                    "polygon_dataset": str(polygon_dataset),
                    "exclude_iso_a2": [],
                },
            },
            "cells": pd.DataFrame([{"h3": anchor_cell, "resolution": 2, "layer_value": "TW", "country_name": "TW"}]),
        }
    }

    layer = FacilityDensityAdaptiveLayer(version="v3")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=layer_store,
        params=params,
    )

    assert metadata["country_intersection_filter_applied"] is True
    assert int(metadata["country_intersection_cells_dropped"]) > 0
    assert not cells.empty
    assert all(_cell_overlap_ratio(str(cell), polygon) > 0.0 for cell in cells["h3"].astype(str).tolist())


def test_adaptive_v3_uses_fixed_country_mask_resolution_as_base() -> None:
    facilities = pd.DataFrame(columns=["facility_id", "lat", "lon", "asof_date"])
    params = _v3_params()
    fixed_base_resolution = 2
    layer_store = _country_mask_store(base_resolution=fixed_base_resolution, radius=1)
    layer_store["country_mask"]["metadata"] = {
        "layer_name": "country_mask",
        "layer_version": "v1",
        "params": {
            "mode": "fixed_resolution",
            "resolution": fixed_base_resolution,
        },
    }

    layer = FacilityDensityAdaptiveLayer(version="v3")
    metadata, _ = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=layer_store,
        params=params,
    )

    assert metadata["coverage_domain"] == "country_mask_r2"
    assert int(metadata["params"]["base_resolution"]) == 2
    assert int(metadata["params"]["configured_base_resolution"]) == 4


def test_adaptive_v3_enforces_occupied_floor_r9() -> None:
    base = h3.latlng_to_cell(41.8781, -87.6298, 4)
    child = sorted(h3.cell_to_children(base, 9))[0]
    facilities = _facilities_from_cells([child])
    params = _v3_params()

    layer = FacilityDensityAdaptiveLayer(version="v3")
    _, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"])),
        params=params,
    )

    occupied = cells[cells["layer_value"] > 0]
    assert not occupied.empty
    assert int(occupied["resolution"].min()) >= int(params["facility_floor_resolution"])


def test_adaptive_v3_collision_splits_to_singleton_or_stops_at_r9_cap() -> None:
    base = h3.latlng_to_cell(41.8781, -87.6298, 4)
    forced_dense_leaf = sorted(h3.cell_to_children(base, 9))[0]
    lat, lon = h3.cell_to_latlng(forced_dense_leaf)
    facilities = pd.DataFrame(
        [{"facility_id": f"f{i}", "lat": lat, "lon": lon, "asof_date": "2026-02-28"} for i in range(5)]
    )
    params = _v3_params()

    layer = FacilityDensityAdaptiveLayer(version="v3")
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


def test_adaptive_v3_boundary_near_occupied_cells_refine_to_floor() -> None:
    base = h3.latlng_to_cell(41.8781, -87.6298, 4)
    occupied_r9 = sorted(h3.cell_to_children(base, 9))[0]
    facilities = _facilities_from_cells([occupied_r9])
    params = _v3_params()

    layer = FacilityDensityAdaptiveLayer(version="v3")
    _, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"]), radius=1),
        params=params,
    )

    floor_resolution = int(params["facility_floor_resolution"])
    occupied_floor = cells[(cells["resolution"] == floor_resolution) & (cells["layer_value"] > 0)]
    assert len(occupied_floor) == 1
    occupied_cell_r9 = str(occupied_floor.iloc[0]["h3"])
    occupied_parent_r8 = h3.cell_to_parent(occupied_cell_r9, floor_resolution - 1)

    near_empty_r8 = cells[
        (cells["resolution"] == floor_resolution - 1)
        & (cells["layer_value"] == 0)
        & cells["h3"].astype(str).isin({str(n) for n in h3.grid_disk(occupied_parent_r8, 1)})
    ]
    assert not near_empty_r8.empty


def test_adaptive_v3_final_partition_has_no_ancestor_descendant_overlap() -> None:
    base = h3.latlng_to_cell(41.8781, -87.6298, 4)
    children_r9 = sorted(h3.cell_to_children(base, 9))
    facilities = _facilities_from_cells([children_r9[0], children_r9[1], children_r9[2]])
    params = _v3_params()

    layer = FacilityDensityAdaptiveLayer(version="v3")
    _, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"])),
        params=params,
    )

    assert not cells["h3"].duplicated().any()
    assert not _has_ancestor_descendant_overlap(cells)


def test_adaptive_v3_repeat_runs_are_deterministic() -> None:
    base = h3.latlng_to_cell(41.8781, -87.6298, 4)
    children_r9 = sorted(h3.cell_to_children(base, 9))
    facilities = _facilities_from_cells([children_r9[0], children_r9[0], children_r9[2]])
    params = _v3_params()

    layer = FacilityDensityAdaptiveLayer(version="v3")
    metadata_a, cells_a = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"])),
        params=params,
    )
    metadata_b, cells_b = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"])),
        params=params,
    )

    assert metadata_a == metadata_b
    subset_a = cells_a[["h3", "resolution", "layer_value"]].sort_values(["resolution", "h3"]).reset_index(drop=True)
    subset_b = cells_b[["h3", "resolution", "layer_value"]].sort_values(["resolution", "h3"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(subset_a, subset_b, check_like=False)


def test_adaptive_v3_neighbor_delta_respects_configured_limit_for_dense_local_case() -> None:
    facilities = _facilities_from_cells(["8d2664c2abaa53f", "8d2664c2aba343f"])
    params = _v3_params()

    layer = FacilityDensityAdaptiveLayer(version="v3")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=_country_mask_store(base_resolution=int(params["base_resolution"]), radius=2),
        params=params,
    )

    assert int(cells["resolution"].min()) >= int(params["min_output_resolution"])
    assert int(cells["resolution"].max()) <= int(params["facility_max_resolution"])
    observed_max_delta = _max_neighbor_resolution_delta(cells)
    assert observed_max_delta <= int(params["max_neighbor_resolution_delta"])
    assert int(metadata["adjacency_checks"]) > 0
    assert int(metadata["violating_neighbor_pairs"]) == 0
    assert int(metadata["max_neighbor_delta_observed"]) == observed_max_delta
    assert int(metadata["smoothing_iterations"]) >= 0


def test_adaptive_v3_adjacency_counters_detect_violating_pair() -> None:
    layer = FacilityDensityAdaptiveLayer(version="v3")
    counters = layer._adjacency_counters(
        leaves={"852664c3fffffff": 0, "862664c57ffffff": 0},
        max_neighbor_resolution_delta=0,
    )
    assert int(counters["adjacency_checks"]) > 0
    assert int(counters["max_neighbor_delta_observed"]) == 1
    assert int(counters["violating_neighbor_pairs"]) > 0


def test_adaptive_v3_compacts_full_empty_sibling_group_to_parent() -> None:
    layer = FacilityDensityAdaptiveLayer(version="v3")
    parent = str(h3.latlng_to_cell(41.8781, -87.6298, 5))
    children = {str(child): 0 for child in sorted(h3.cell_to_children(parent, 6))}

    compacted = layer._compact_empty_sibling_leaves(
        leaves=children,
        min_output_resolution=5,
        base_resolution=4,
        empty_interior_max_resolution=7,
        facility_floor_resolution=9,
        max_neighbor_resolution_delta=1,
        intersects_domain=lambda cell, resolution: True,
        is_boundary_band=lambda cell, resolution: False,
        is_near_occupied=lambda cell, resolution: False,
        compact_empty_near_occupied=True,
    )

    assert compacted == {parent: 0}


def test_adaptive_v3_compacts_empty_near_occupied_sibling_group_when_enabled() -> None:
    layer = FacilityDensityAdaptiveLayer(version="v3")
    parent = str(h3.latlng_to_cell(41.8781, -87.6298, 5))
    children = {str(child): 0 for child in sorted(h3.cell_to_children(parent, 6))}

    compacted = layer._compact_empty_sibling_leaves(
        leaves=children,
        min_output_resolution=5,
        base_resolution=4,
        empty_interior_max_resolution=4,
        facility_floor_resolution=9,
        max_neighbor_resolution_delta=1,
        intersects_domain=lambda cell, resolution: True,
        is_boundary_band=lambda cell, resolution: False,
        is_near_occupied=lambda cell, resolution: cell == parent,
        compact_empty_near_occupied=True,
    )

    assert compacted == {parent: 0}


def test_adaptive_v3_does_not_compact_empty_near_occupied_sibling_group_when_disabled() -> None:
    layer = FacilityDensityAdaptiveLayer(version="v3")
    parent = str(h3.latlng_to_cell(41.8781, -87.6298, 5))
    children = {str(child): 0 for child in sorted(h3.cell_to_children(parent, 6))}

    compacted = layer._compact_empty_sibling_leaves(
        leaves=children,
        min_output_resolution=5,
        base_resolution=4,
        empty_interior_max_resolution=4,
        facility_floor_resolution=9,
        max_neighbor_resolution_delta=1,
        intersects_domain=lambda cell, resolution: True,
        is_boundary_band=lambda cell, resolution: False,
        is_near_occupied=lambda cell, resolution: cell == parent,
        compact_empty_near_occupied=False,
    )

    assert compacted == children


def test_adaptive_v3_does_not_compact_boundary_sibling_group() -> None:
    layer = FacilityDensityAdaptiveLayer(version="v3")
    parent = str(h3.latlng_to_cell(41.8781, -87.6298, 5))
    children = {str(child): 0 for child in sorted(h3.cell_to_children(parent, 6))}

    compacted = layer._compact_empty_sibling_leaves(
        leaves=children,
        min_output_resolution=5,
        base_resolution=4,
        empty_interior_max_resolution=7,
        facility_floor_resolution=9,
        max_neighbor_resolution_delta=1,
        intersects_domain=lambda cell, resolution: True,
        is_boundary_band=lambda cell, resolution: cell == parent,
        is_near_occupied=lambda cell, resolution: False,
        compact_empty_near_occupied=True,
    )

    assert compacted == children


def test_adaptive_v3_does_not_compact_when_merge_would_violate_neighbor_delta() -> None:
    layer = FacilityDensityAdaptiveLayer(version="v3")
    parent = str(h3.latlng_to_cell(41.8781, -87.6298, 5))
    parent_children = [str(child) for child in sorted(h3.cell_to_children(parent, 6))]
    neighbor_parent = next(str(cell) for cell in h3.grid_disk(parent, 1) if str(cell) != parent)
    neighbor_children = [str(child) for child in sorted(h3.cell_to_children(neighbor_parent, 6))]
    split_neighbor = next(
        child
        for child in neighbor_children
        if any(str(adjacent) in parent_children for adjacent in h3.grid_disk(child, 1) if str(adjacent) != child)
    )
    leaves = {child: 0 for child in parent_children}
    for child in neighbor_children:
        if child == split_neighbor:
            continue
        leaves[child] = 0
    leaves.update({str(child): 0 for child in sorted(h3.cell_to_children(split_neighbor, 7))})

    compacted = layer._compact_empty_sibling_leaves(
        leaves=leaves,
        min_output_resolution=5,
        base_resolution=4,
        empty_interior_max_resolution=4,
        facility_floor_resolution=9,
        max_neighbor_resolution_delta=1,
        intersects_domain=lambda cell, resolution: True,
        is_boundary_band=lambda cell, resolution: False,
        is_near_occupied=lambda cell, resolution: cell == parent,
        compact_empty_near_occupied=True,
    )

    assert compacted == leaves


def test_adaptive_v3_fails_closed_when_final_adjacency_check_violates_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    facilities = _facilities_from_cells(["8d2664c2abaa53f"])
    params = _v3_params()
    layer = FacilityDensityAdaptiveLayer(version="v3")

    monkeypatch.setattr(
        layer,
        "_adjacency_counters",
        lambda leaves, max_neighbor_resolution_delta, candidate_cells=None: {
            "adjacency_checks": 3,
            "violating_neighbor_pairs": 1,
            "max_neighbor_delta_observed": int(max_neighbor_resolution_delta) + 1,
        },
    )

    with pytest.raises(ValueError, match="violates max_neighbor_resolution_delta after smoothing"):
        layer.compute(
            canonical_store={"facilities": facilities},
            layer_store=_country_mask_store(base_resolution=int(params["base_resolution"]), radius=1),
            params=params,
        )
