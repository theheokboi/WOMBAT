import json
from pathlib import Path
from typing import Any

import h3
import pandas as pd
import pytest

from inframap.layers.facility_density_adaptive import FacilityDensityAdaptiveLayer
from inframap.layers.facility_density_policies.v4 import FacilityDensityAdaptiveV4Policy


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
        "domain_normalization_seconds",
        "facility_h3_assignment_seconds",
        "facility_count_aggregation_seconds",
        "boundary_band_precompute_seconds",
        "near_occupied_precompute_seconds",
        "smoothing_bootstrap_seconds",
        "smoothing_loop_seconds",
        "compaction_adjacency_seconds",
        "adaptive_cache_read_seconds",
        "adaptive_cache_write_seconds",
        "adaptive_cache_hit",
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
    for key in (
        "domain_normalization_seconds",
        "facility_h3_assignment_seconds",
        "facility_count_aggregation_seconds",
        "boundary_band_precompute_seconds",
        "near_occupied_precompute_seconds",
        "smoothing_bootstrap_seconds",
        "smoothing_loop_seconds",
        "compaction_adjacency_seconds",
        "adaptive_cache_read_seconds",
        "adaptive_cache_write_seconds",
    ):
        assert float(counters[key]) >= 0.0
    assert isinstance(counters["adaptive_cache_hit"], (bool, int))


def _sorted_adaptive_cells(cells: pd.DataFrame) -> pd.DataFrame:
    return cells.sort_values(["resolution", "h3"]).reset_index(drop=True)


def _cache_metadata_files(cache_root: Path) -> list[Path]:
    return sorted(cache_root.rglob("cache_metadata.json"))


def _stable_v4_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    stable = dict(metadata)
    counters = dict(stable.get("adaptive_counters", {}))
    for key in (
        "domain_normalization_seconds",
        "facility_h3_assignment_seconds",
        "facility_count_aggregation_seconds",
        "boundary_band_precompute_seconds",
        "near_occupied_precompute_seconds",
        "smoothing_bootstrap_seconds",
        "smoothing_loop_seconds",
        "compaction_adjacency_seconds",
        "adaptive_cache_read_seconds",
        "adaptive_cache_write_seconds",
        "adaptive_cache_hit",
        "initial_recursion_seconds",
        "neighbor_smoothing_seconds",
        "post_compaction_seconds",
        "country_intersection_filter_seconds",
    ):
        counters.pop(key, None)
    stable["adaptive_counters"] = counters
    return stable


def _run_v4_and_get_cache_entry(
    *,
    workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
    params: dict[str, int | bool] | None = None,
    facilities: pd.DataFrame | None = None,
    layer_store: dict[str, dict[str, pd.DataFrame | dict[str, str]]] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame, Path, dict[str, Any]]:
    workdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(workdir)
    resolved_params = dict(params or _v4_params())
    base_resolution = int(resolved_params["base_resolution"])
    facility_max_resolution = int(resolved_params["facility_max_resolution"])
    if layer_store is None:
        layer_store = _country_mask_store(base_resolution=base_resolution, radius=1)
    if facilities is None:
        base = h3.latlng_to_cell(41.8781, -87.6298, base_resolution)
        occupied = str(sorted(h3.cell_to_children(base, facility_max_resolution))[0])
        facilities = _facilities_from_cells([occupied])

    layer = FacilityDensityAdaptiveLayer(version="v4")
    metadata, cells = layer.compute(
        canonical_store={"facilities": facilities},
        layer_store=layer_store,
        params=resolved_params,
    )
    cache_root = workdir / "data" / "cache" / "facility_density_adaptive" / "v4"
    metadata_files = _cache_metadata_files(cache_root)
    assert len(metadata_files) == 1
    cache_metadata_path = metadata_files[0]
    cache_metadata = json.loads(cache_metadata_path.read_text(encoding="utf-8"))
    return metadata, cells, cache_metadata_path, cache_metadata


def _build_precompute_fixture(
    *,
    facilities: pd.DataFrame,
    country_cells: pd.DataFrame,
    base_resolution: int,
    empty_compact_min_resolution: int,
    facility_max_resolution: int,
) -> tuple[
    set[str],
    dict[int, set[str]],
    dict[int, dict[str, int]],
    Any,
]:
    domain_cells: set[str] = set()
    for raw_cell in country_cells["h3"].astype(str).tolist():
        cell = str(raw_cell)
        resolution = h3.get_resolution(cell)
        if resolution == base_resolution:
            domain_cells.add(cell)
        elif resolution < base_resolution:
            domain_cells.update(str(child) for child in h3.cell_to_children(cell, base_resolution))
        else:
            domain_cells.add(h3.cell_to_parent(cell, base_resolution))

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

    domain_ancestors_by_resolution = {
        resolution: {parent_cell(cell, resolution) for cell in domain_cells}
        for resolution in range(empty_compact_min_resolution, base_resolution)
    }

    working = facilities[["lat", "lon", "asof_date"]].copy()
    for resolution in range(base_resolution, facility_max_resolution + 1):
        working[f"h3_r{resolution}"] = [
            h3.latlng_to_cell(float(lat), float(lon), resolution)
            for lat, lon in zip(working["lat"].tolist(), working["lon"].tolist(), strict=False)
        ]
    if working.empty:
        facilities_in_domain = working
    else:
        facilities_in_domain = working[working[f"h3_r{base_resolution}"].isin(domain_cells)].copy()

    count_by_resolution: dict[int, dict[str, int]] = {}
    for resolution in range(empty_compact_min_resolution, facility_max_resolution + 1):
        if facilities_in_domain.empty:
            count_by_resolution[resolution] = {}
            continue
        if resolution < base_resolution:
            series = facilities_in_domain[f"h3_r{base_resolution}"].map(lambda cell: parent_cell(str(cell), resolution))
        else:
            series = facilities_in_domain[f"h3_r{resolution}"]
        count_by_resolution[resolution] = {
            str(cell): int(count) for cell, count in series.value_counts(sort=False).items()
        }
    return domain_cells, domain_ancestors_by_resolution, count_by_resolution, parent_cell


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


def test_adaptive_v4_precompute_cache_key_ignores_tuning_only_params(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    params = _v4_params()
    _, _, base_metadata_path, base_metadata = _run_v4_and_get_cache_entry(
        workdir=tmp_path / "base",
        monkeypatch=monkeypatch,
        params=params,
    )

    target_tuned = dict(params)
    target_tuned["target_facilities_per_leaf"] = 99
    _, _, target_metadata_path, target_metadata = _run_v4_and_get_cache_entry(
        workdir=tmp_path / "target-tuned",
        monkeypatch=monkeypatch,
        params=target_tuned,
    )

    refine_tuned = dict(params)
    refine_tuned["empty_refine_boundary_band_k"] = 3
    refine_tuned["empty_refine_near_occupied_k"] = 2
    _, _, refine_metadata_path, refine_metadata = _run_v4_and_get_cache_entry(
        workdir=tmp_path / "refine-tuned",
        monkeypatch=monkeypatch,
        params=refine_tuned,
    )

    assert base_metadata_path.parent.name == target_metadata_path.parent.name
    assert base_metadata_path.parent.name == refine_metadata_path.parent.name
    for payload in (base_metadata, target_metadata, refine_metadata):
        assert payload.get("schema_version", payload.get("cache_schema_version")) is not None
        assert isinstance(payload.get("key_parts"), dict)
        assert isinstance(payload.get("summary_counts", payload.get("summary")), dict)
        assert {
            "country_mask_cells_hash",
            "facilities_hash",
            "base_resolution",
            "empty_compact_min_resolution",
            "facility_max_resolution",
            "adaptive_policy_signature",
            "cache_schema_version",
        }.issubset(payload["key_parts"].keys())
        assert "target_facilities_per_leaf" not in payload["key_parts"]
        assert "empty_refine_boundary_band_k" not in payload["key_parts"]
        assert "empty_refine_country_edge_k" not in payload["key_parts"]
        assert "empty_refine_near_occupied_k" not in payload["key_parts"]


def test_adaptive_v4_precompute_cache_key_invalidates_when_precompute_inputs_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_params = _v4_params()
    _, _, base_metadata_path, _ = _run_v4_and_get_cache_entry(
        workdir=tmp_path / "base",
        monkeypatch=monkeypatch,
        params=base_params,
    )
    base_key = base_metadata_path.parent.name

    changed_max = dict(base_params)
    changed_max["facility_max_resolution"] = 9
    _, _, max_metadata_path, _ = _run_v4_and_get_cache_entry(
        workdir=tmp_path / "changed-max",
        monkeypatch=monkeypatch,
        params=changed_max,
    )

    changed_base = dict(base_params)
    changed_base["base_resolution"] = 3
    changed_base["min_output_resolution"] = 3
    changed_base["empty_interior_max_resolution"] = 3
    changed_base["facility_floor_resolution"] = 5
    changed_base["facility_max_resolution"] = 7
    changed_base["facility_floor_offset"] = 1
    _, _, base_resolution_metadata_path, _ = _run_v4_and_get_cache_entry(
        workdir=tmp_path / "changed-base",
        monkeypatch=monkeypatch,
        params=changed_base,
        layer_store=_country_mask_store(base_resolution=3, radius=1),
    )

    base_cell = h3.latlng_to_cell(41.8781, -87.6298, int(base_params["base_resolution"]))
    alternate_facilities = _facilities_from_cells(
        [
            str(sorted(h3.cell_to_children(base_cell, int(base_params["facility_max_resolution"])))[1]),
            str(sorted(h3.cell_to_children(base_cell, int(base_params["facility_max_resolution"])))[2]),
        ]
    )
    _, _, facilities_metadata_path, _ = _run_v4_and_get_cache_entry(
        workdir=tmp_path / "changed-facilities",
        monkeypatch=monkeypatch,
        params=base_params,
        facilities=alternate_facilities,
    )

    _, _, country_mask_metadata_path, _ = _run_v4_and_get_cache_entry(
        workdir=tmp_path / "changed-country-mask",
        monkeypatch=monkeypatch,
        params=base_params,
        layer_store=_country_mask_store(base_resolution=int(base_params["base_resolution"]), radius=0),
    )

    assert len(
        {
            base_key,
            max_metadata_path.parent.name,
            base_resolution_metadata_path.parent.name,
            facilities_metadata_path.parent.name,
            country_mask_metadata_path.parent.name,
        }
    ) == 5
    assert max_metadata_path.parent.name != base_key
    assert base_resolution_metadata_path.parent.name != base_key
    assert facilities_metadata_path.parent.name != base_key
    assert country_mask_metadata_path.parent.name != base_key


def test_adaptive_v4_warm_cache_reads_precompute_and_preserves_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    params = _v4_params()
    metadata_cold, cells_cold, cache_metadata_path, _ = _run_v4_and_get_cache_entry(
        workdir=tmp_path / "cache-behavior",
        monkeypatch=monkeypatch,
        params=params,
    )
    metadata_warm, cells_warm, cache_metadata_path_warm, _ = _run_v4_and_get_cache_entry(
        workdir=tmp_path / "cache-behavior",
        monkeypatch=monkeypatch,
        params=params,
    )

    assert cache_metadata_path == cache_metadata_path_warm
    assert metadata_cold["adaptive_counters"]["adaptive_cache_hit"] is False
    assert metadata_warm["adaptive_counters"]["adaptive_cache_hit"] is True
    assert (cache_metadata_path.parent / "domain_cells.parquet").exists()
    assert (cache_metadata_path.parent / "facility_counts.parquet").exists()

    pd.testing.assert_frame_equal(
        _sorted_adaptive_cells(cells_cold[["h3", "resolution", "layer_value"]]),
        _sorted_adaptive_cells(cells_warm[["h3", "resolution", "layer_value"]]),
        check_like=False,
    )
    assert _stable_v4_metadata(metadata_cold) == _stable_v4_metadata(metadata_warm)


def test_adaptive_v4_refinement_masks_match_old_neighbor_scan_semantics() -> None:
    params = _v4_params()
    params["empty_compact_min_resolution"] = 3
    params["facility_floor_resolution"] = 6
    params["facility_max_resolution"] = 8
    base_resolution = int(params["base_resolution"])
    empty_compact_min_resolution = int(params["empty_compact_min_resolution"])
    facility_max_resolution = int(params["facility_max_resolution"])
    boundary_k = int(params["empty_refine_boundary_band_k"])
    near_occupied_k = int(params["empty_refine_near_occupied_k"])

    center = str(h3.latlng_to_cell(41.8781, -87.6298, base_resolution))
    boundary = next(cell for cell in sorted(str(cell) for cell in h3.grid_disk(center, 1)) if cell != center)
    facilities = _facilities_from_cells(
        [
            str(sorted(h3.cell_to_children(center, facility_max_resolution))[0]),
            str(sorted(h3.cell_to_children(boundary, facility_max_resolution))[0]),
            str(sorted(h3.cell_to_children(boundary, facility_max_resolution))[1]),
        ]
    )
    layer_store = _country_mask_store(base_resolution=base_resolution, radius=1)
    country_cells = layer_store["country_mask"]["cells"]
    domain_cells, domain_ancestors_by_resolution, count_by_resolution, parent_cell = _build_precompute_fixture(
        facilities=facilities,
        country_cells=country_cells,
        base_resolution=base_resolution,
        empty_compact_min_resolution=empty_compact_min_resolution,
        facility_max_resolution=facility_max_resolution,
    )

    def intersects_domain(cell: str, resolution: int) -> bool:
        if resolution < base_resolution:
            return cell in domain_ancestors_by_resolution[resolution]
        if resolution == base_resolution:
            return cell in domain_cells
        return parent_cell(cell, base_resolution) in domain_cells

    neighbors_cache: dict[tuple[str, int, int], list[str]] = {}

    def neighbors_within_k(cell: str, resolution: int, k: int) -> list[str]:
        key = (cell, resolution, k)
        cached = neighbors_cache.get(key)
        if cached is not None:
            return cached
        if k <= 0:
            return [cell]
        neighbors_cache[key] = [
            neighbor
            for neighbor in sorted(str(neighbor) for neighbor in h3.grid_disk(cell, k))
            if h3.get_resolution(neighbor) == resolution
        ]
        return neighbors_cache[key]

    def is_boundary_band_old(cell: str, resolution: int) -> bool:
        return any(not intersects_domain(neighbor, resolution) for neighbor in neighbors_within_k(cell, resolution, boundary_k))

    def is_near_occupied_old(cell: str, resolution: int) -> bool:
        occupied = count_by_resolution[resolution]
        return any(
            neighbor != cell and occupied.get(neighbor, 0) > 0
            for neighbor in neighbors_within_k(cell, resolution, near_occupied_k)
        )

    policy = FacilityDensityAdaptiveV4Policy(version="v4")
    boundary_band_cells_by_resolution = policy._build_boundary_band_cells_by_resolution(
        base_resolution=base_resolution,
        empty_compact_min_resolution=empty_compact_min_resolution,
        facility_max_resolution=facility_max_resolution,
        empty_refine_country_edge_k=boundary_k,
        domain_r4_set=domain_cells,
        domain_ancestors_by_resolution=domain_ancestors_by_resolution,
        intersects_domain=intersects_domain,
        neighbors_within_k=neighbors_within_k,
    )
    near_occupied_cells_by_resolution = policy._build_near_occupied_cells_by_resolution(
        empty_compact_min_resolution=empty_compact_min_resolution,
        facility_max_resolution=facility_max_resolution,
        empty_refine_near_occupied_k=near_occupied_k,
        count_by_resolution=count_by_resolution,
        intersects_domain=intersects_domain,
        neighbors_within_k=neighbors_within_k,
    )

    candidate_cells_by_resolution = {
        3: sorted(domain_ancestors_by_resolution[3]),
        4: sorted(domain_cells),
        5: sorted(
            {
                str(child)
                for parent in (center, boundary)
                for child in h3.cell_to_children(parent, 5)
                if intersects_domain(str(child), 5)
            }
        ),
    }
    for resolution, candidate_cells in candidate_cells_by_resolution.items():
        boundary_mask = boundary_band_cells_by_resolution.get(resolution, set())
        near_occupied_mask = near_occupied_cells_by_resolution.get(resolution, set())
        for cell in candidate_cells:
            assert (cell in boundary_mask) is is_boundary_band_old(cell, resolution)
            assert (cell in near_occupied_mask) is is_near_occupied_old(cell, resolution)
