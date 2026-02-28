from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import h3
import pandas as pd


@dataclass
class FacilityDensityAdaptiveLayer:
    version: str

    def spec(self) -> dict[str, Any]:
        return {
            "name": "facility_density_adaptive",
            "version": self.version,
            "distance_semantics": "hierarchical_partition_over_country_mask",
            "policy_name": "facility_hierarchical_partition_v3",
            "coverage_domain": "country_mask_r4",
            "params": [
                "base_resolution",
                "min_output_resolution",
                "empty_compact_min_resolution",
                "facility_floor_resolution",
                "facility_max_resolution",
                "target_facilities_per_leaf",
                "empty_interior_max_resolution",
                "empty_refine_boundary_band_k",
                "empty_refine_near_occupied_k",
                "max_neighbor_resolution_delta",
            ],
        }

    def compute(
        self, canonical_store: dict[str, pd.DataFrame], layer_store: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        facilities = canonical_store["facilities"]

        base_resolution = int(params["base_resolution"])
        min_output_resolution = int(params.get("min_output_resolution", 5))
        empty_compact_min_resolution = int(params["empty_compact_min_resolution"])
        facility_floor_resolution = int(params["facility_floor_resolution"])
        facility_max_resolution = int(params["facility_max_resolution"])
        target_facilities_per_leaf = int(params["target_facilities_per_leaf"])
        empty_interior_max_resolution = int(params["empty_interior_max_resolution"])
        empty_refine_boundary_band_k = int(params["empty_refine_boundary_band_k"])
        empty_refine_near_occupied_k = int(params["empty_refine_near_occupied_k"])
        max_neighbor_resolution_delta = int(params["max_neighbor_resolution_delta"])

        if not (5 <= min_output_resolution <= 9):
            raise ValueError("min_output_resolution must satisfy 5 <= value <= 9")
        if not (0 <= empty_compact_min_resolution <= base_resolution <= 13):
            raise ValueError("empty_compact_min_resolution and base_resolution must satisfy 0 <= min <= base <= 13")
        if not (0 <= facility_floor_resolution <= facility_max_resolution <= 9):
            raise ValueError("facility resolutions must satisfy 0 <= floor <= max <= 9")
        if min_output_resolution > facility_max_resolution:
            raise ValueError("min_output_resolution must be <= facility_max_resolution")
        if target_facilities_per_leaf < 1:
            raise ValueError("target_facilities_per_leaf must be >= 1")
        if not (base_resolution <= empty_interior_max_resolution <= facility_floor_resolution - 1):
            raise ValueError(
                "empty_interior_max_resolution must satisfy base_resolution <= value <= facility_floor_resolution - 1"
            )
        if empty_refine_boundary_band_k < 0:
            raise ValueError("empty_refine_boundary_band_k must be >= 0")
        if empty_refine_near_occupied_k < 0:
            raise ValueError("empty_refine_near_occupied_k must be >= 0")
        if max_neighbor_resolution_delta < 0:
            raise ValueError("max_neighbor_resolution_delta must be >= 0")

        country_artifacts = layer_store.get("country_mask")
        if not isinstance(country_artifacts, dict) or "cells" not in country_artifacts:
            raise ValueError("facility_density_adaptive requires country_mask layer artifacts")
        country_cells = country_artifacts["cells"]
        if not isinstance(country_cells, pd.DataFrame) or "h3" not in country_cells.columns:
            raise ValueError("country_mask artifacts must provide a cells dataframe with h3 column")

        domain_r4 = sorted({str(cell) for cell in country_cells["h3"].astype(str).tolist()})
        if not domain_r4:
            empty = pd.DataFrame(columns=["h3", "resolution", "layer_value", "layer_id", "asof_date"])
            metadata = self._metadata(
                params={
                    "base_resolution": base_resolution,
                    "min_output_resolution": min_output_resolution,
                    "empty_compact_min_resolution": empty_compact_min_resolution,
                    "facility_floor_resolution": facility_floor_resolution,
                    "facility_max_resolution": facility_max_resolution,
                    "target_facilities_per_leaf": target_facilities_per_leaf,
                    "empty_interior_max_resolution": empty_interior_max_resolution,
                    "empty_refine_boundary_band_k": empty_refine_boundary_band_k,
                    "empty_refine_near_occupied_k": empty_refine_near_occupied_k,
                    "max_neighbor_resolution_delta": max_neighbor_resolution_delta,
                }
            )
            return metadata, empty

        domain_r4_set = set(domain_r4)
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
            resolution: {parent_cell(cell, resolution) for cell in domain_r4_set}
            for resolution in range(empty_compact_min_resolution, base_resolution)
        }

        working = facilities[["lat", "lon", "asof_date"]].copy()
        for resolution in range(base_resolution, facility_max_resolution + 1):
            col = f"h3_r{resolution}"
            working[col] = [
                h3.latlng_to_cell(float(lat), float(lon), resolution)
                for lat, lon in zip(working["lat"].tolist(), working["lon"].tolist(), strict=False)
            ]

        if working.empty:
            facilities_in_domain = working
        else:
            facilities_in_domain = working[working[f"h3_r{base_resolution}"].isin(domain_r4_set)].copy()

        count_by_resolution: dict[int, dict[str, int]] = {}
        for resolution in range(empty_compact_min_resolution, facility_max_resolution + 1):
            if facilities_in_domain.empty:
                count_by_resolution[resolution] = {}
                continue
            if resolution < base_resolution:
                series = facilities_in_domain[f"h3_r{base_resolution}"].map(
                    lambda cell: parent_cell(str(cell), resolution)
                )
            else:
                series = facilities_in_domain[f"h3_r{resolution}"]
            count_by_resolution[resolution] = {
                str(cell): int(count) for cell, count in series.value_counts(sort=False).items()
            }

        roots = sorted(domain_ancestors_by_resolution[empty_compact_min_resolution])
        leaves: dict[str, int] = {}

        def intersects_domain(cell: str, resolution: int) -> bool:
            if resolution < base_resolution:
                return cell in domain_ancestors_by_resolution[resolution]
            if resolution == base_resolution:
                return cell in domain_r4_set
            return parent_cell(cell, base_resolution) in domain_r4_set

        neighbors_cache: dict[tuple[str, int], list[str]] = {}

        def neighbors_within_k(cell: str, resolution: int, k: int) -> list[str]:
            key = (cell, k)
            cached = neighbors_cache.get(key)
            if cached is not None:
                return cached
            if k <= 0:
                return [cell]
            neighbors = sorted(str(neighbor) for neighbor in h3.grid_disk(cell, k))
            neighbors_cache[key] = [neighbor for neighbor in neighbors if h3.get_resolution(neighbor) == resolution]
            return neighbors_cache[key]

        def is_boundary_band(cell: str, resolution: int) -> bool:
            for neighbor in neighbors_within_k(cell, resolution, empty_refine_boundary_band_k):
                if not intersects_domain(neighbor, resolution):
                    return True
            return False

        def is_near_occupied(cell: str, resolution: int) -> bool:
            occupied = count_by_resolution[resolution]
            for neighbor in neighbors_within_k(cell, resolution, empty_refine_near_occupied_k):
                if neighbor == cell:
                    continue
                if occupied.get(neighbor, 0) > 0:
                    return True
            return False

        def max_allowed_resolution(cell: str, resolution: int, facility_count: int) -> int:
            if facility_count > 0:
                return facility_max_resolution
            if resolution < base_resolution:
                return max(min_output_resolution, facility_floor_resolution - 1)
            if is_boundary_band(cell, resolution) or is_near_occupied(cell, resolution):
                return max(min_output_resolution, facility_floor_resolution - 1)
            return max(min_output_resolution, min(empty_interior_max_resolution, facility_floor_resolution - 1))

        def add_leaf(cell: str, facility_count: int) -> None:
            leaves[str(cell)] = int(facility_count)

        def recurse(cell: str, resolution: int) -> None:
            facility_count = count_by_resolution[resolution].get(cell, 0)
            if facility_count > 0:
                must_split_for_floor = resolution < facility_floor_resolution
                must_split_for_density = (
                    facility_count > target_facilities_per_leaf and resolution < facility_max_resolution
                )
                if not must_split_for_floor and not must_split_for_density:
                    add_leaf(cell, facility_count)
                    return

                next_resolution = resolution + 1
                children = sorted(h3.cell_to_children(cell, next_resolution))
                for child in children:
                    child_str = str(child)
                    if intersects_domain(child_str, next_resolution):
                        recurse(child_str, next_resolution)
                return

            must_split_for_hierarchy = resolution < base_resolution
            boundary_or_near_occupied = is_boundary_band(cell, resolution) or is_near_occupied(cell, resolution)
            must_split_for_refinement = (
                boundary_or_near_occupied and resolution < facility_floor_resolution - 1
            )
            must_split_for_min_output = resolution < min_output_resolution
            if must_split_for_hierarchy or must_split_for_refinement or must_split_for_min_output:
                next_resolution = resolution + 1
                children = sorted(h3.cell_to_children(cell, next_resolution))
                for child in children:
                    child_str = str(child)
                    if intersects_domain(child_str, next_resolution):
                        recurse(child_str, next_resolution)
                return

            add_leaf(cell, 0)

        for root in roots:
            recurse(str(root), empty_compact_min_resolution)

        def leaf_sets_by_resolution() -> dict[int, set[str]]:
            by_resolution: dict[int, set[str]] = {resolution: set() for resolution in range(14)}
            for cell in leaves:
                by_resolution[h3.get_resolution(cell)].add(cell)
            return by_resolution

        def covering_leaf_for_neighbor(cell: str, resolution: int, by_resolution: dict[int, set[str]]) -> tuple[str, int] | None:
            for ancestor_resolution in range(resolution, -1, -1):
                ancestor = parent_cell(cell, ancestor_resolution)
                if ancestor in by_resolution[ancestor_resolution]:
                    return ancestor, ancestor_resolution
            return None

        def refine_leaf(
            cell: str,
            resolution: int,
            facility_count: int,
            required_min_resolution: int | None = None,
        ) -> bool:
            allowed_max_resolution = max_allowed_resolution(cell, resolution, facility_count)
            # Neighbor smoothing is a hard output guarantee; allow empty leaves to
            # refine past their normal cap only when required to satisfy it.
            if required_min_resolution is not None and facility_count == 0:
                allowed_max_resolution = max(
                    allowed_max_resolution,
                    min(int(required_min_resolution), facility_max_resolution),
                )
            if resolution >= allowed_max_resolution:
                return False
            next_resolution = resolution + 1
            children = sorted(h3.cell_to_children(cell, next_resolution))
            del leaves[cell]
            for child in children:
                child_str = str(child)
                if intersects_domain(child_str, next_resolution):
                    leaves[child_str] = count_by_resolution[next_resolution].get(child_str, 0)
            return True

        # Deterministic neighbor smoothing: refine the coarser side while allowed.
        while True:
            by_resolution = leaf_sets_by_resolution()
            resolution_by_leaf = {cell: h3.get_resolution(cell) for cell in leaves}
            coarse_candidates: dict[str, int] = {}
            for cell in sorted(leaves, key=lambda value: (resolution_by_leaf[value], value)):
                resolution = resolution_by_leaf[cell]
                same_resolution_neighbors = neighbors_within_k(cell, resolution, 1)
                for neighbor in same_resolution_neighbors:
                    if neighbor == cell:
                        continue
                    covered = covering_leaf_for_neighbor(neighbor, resolution, by_resolution)
                    if covered is None:
                        continue
                    neighbor_leaf, neighbor_resolution = covered
                    delta = abs(resolution - neighbor_resolution)
                    if delta <= max_neighbor_resolution_delta:
                        continue
                    if resolution < neighbor_resolution:
                        coarse_cell = cell
                        finer_resolution = neighbor_resolution
                    elif neighbor_resolution < resolution:
                        coarse_cell = neighbor_leaf
                        finer_resolution = resolution
                    else:
                        continue
                    required_min_resolution = finer_resolution - max_neighbor_resolution_delta
                    current_required = coarse_candidates.get(coarse_cell)
                    if current_required is None or required_min_resolution > current_required:
                        coarse_candidates[coarse_cell] = required_min_resolution

            if not coarse_candidates:
                break

            refined = False
            for candidate_cell in sorted(
                coarse_candidates,
                key=lambda item: (resolution_by_leaf.get(item, 14), item),
            ):
                if candidate_cell not in leaves:
                    continue
                candidate_resolution = resolution_by_leaf[candidate_cell]
                candidate_count = leaves[candidate_cell]
                required_min_resolution = coarse_candidates[candidate_cell]
                if candidate_resolution >= required_min_resolution:
                    continue
                if refine_leaf(
                    candidate_cell,
                    candidate_resolution,
                    candidate_count,
                    required_min_resolution=required_min_resolution,
                ):
                    refined = True
                    break
            if not refined:
                break

        # Deterministic mixed-resolution leaf output.
        output = pd.DataFrame(
            [(cell, h3.get_resolution(cell), count) for cell, count in leaves.items()],
            columns=["h3", "resolution", "layer_value"],
        )
        output = output.sort_values(by=["resolution", "h3"]).reset_index(drop=True)
        output["layer_id"] = f"facility_density_adaptive:{self.version}"

        max_asof = (
            facilities_in_domain["asof_date"].max() if "asof_date" in facilities_in_domain.columns else None
        )
        output["asof_date"] = max_asof
        output = output[["h3", "resolution", "layer_value", "layer_id", "asof_date"]]

        metadata = self._metadata(
            params={
                "base_resolution": base_resolution,
                "min_output_resolution": min_output_resolution,
                "empty_compact_min_resolution": empty_compact_min_resolution,
                "facility_floor_resolution": facility_floor_resolution,
                "facility_max_resolution": facility_max_resolution,
                "target_facilities_per_leaf": target_facilities_per_leaf,
                "empty_interior_max_resolution": empty_interior_max_resolution,
                "empty_refine_boundary_band_k": empty_refine_boundary_band_k,
                "empty_refine_near_occupied_k": empty_refine_near_occupied_k,
                "max_neighbor_resolution_delta": max_neighbor_resolution_delta,
            }
        )
        return metadata, output

    def _metadata(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "layer_name": "facility_density_adaptive",
            "layer_version": self.version,
            "policy_name": "facility_hierarchical_partition_v3",
            "coverage_domain": "country_mask_r4",
            "params": params,
            "stopping_rules": {
                "empty_branch": {
                    "rule": "hierarchy_then_topology_refine",
                    "hierarchy_required_below_resolution": params["base_resolution"],
                    "min_output_resolution": params["min_output_resolution"],
                    "boundary_or_near_occupied_max_resolution": params["facility_floor_resolution"] - 1,
                    "empty_interior_max_resolution": params["empty_interior_max_resolution"],
                    "boundary_band_k": params["empty_refine_boundary_band_k"],
                    "near_occupied_k": params["empty_refine_near_occupied_k"],
                },
                "facility_branch": {
                    "min_resolution": params["facility_floor_resolution"],
                    "target_facilities_per_leaf": params["target_facilities_per_leaf"],
                    "max_resolution": params["facility_max_resolution"],
                },
                "neighbor_smoothing": {
                    "rule": "refine_coarser_side_until_delta_or_cap",
                    "max_neighbor_resolution_delta": params["max_neighbor_resolution_delta"],
                    "occupied_max_resolution": params["facility_max_resolution"],
                    "empty_max_resolution": params["facility_floor_resolution"] - 1,
                },
                "output_bounds": {
                    "min_resolution": params["min_output_resolution"],
                    "max_resolution": 9,
                },
            },
            "distance_semantics": "hierarchical_partition_over_country_mask",
        }

    def validate(self, artifacts: dict[str, Any]) -> None:
        cells = artifacts["cells"]
        if cells.empty:
            return

        if cells["h3"].duplicated().any():
            raise ValueError("Adaptive facility layer has duplicate h3 cells")

        metadata = artifacts.get("metadata", {})
        metadata_params = metadata.get("params", {}) if isinstance(metadata, dict) else {}
        min_output_resolution = int(metadata_params.get("min_output_resolution", 5))

        if ((cells["resolution"] < min_output_resolution) | (cells["resolution"] > 9)).any():
            raise ValueError(
                f"Adaptive facility layer has cells outside allowed output resolution range [{min_output_resolution}, 9]"
            )

        encoded_resolution = cells["h3"].astype(str).map(h3.get_resolution)
        if not encoded_resolution.equals(cells["resolution"].astype(int)):
            raise ValueError("Adaptive facility layer has resolution column mismatched with h3 cell resolution")

        if (cells["layer_value"] < 0).any():
            raise ValueError("Adaptive facility layer has negative facility counts")

        facility_floor_resolution = int(metadata_params.get("facility_floor_resolution", 9))
        facility_bearing = cells[cells["layer_value"] > 0]
        if not facility_bearing.empty and (facility_bearing["resolution"] < facility_floor_resolution).any():
            raise ValueError(
                f"Adaptive facility layer has facility-bearing cells coarser than r{facility_floor_resolution}"
            )

        cell_set = {str(cell) for cell in cells["h3"].astype(str).tolist()}
        for cell in sorted(cell_set, key=lambda value: h3.get_resolution(value)):
            resolution = h3.get_resolution(cell)
            for ancestor_resolution in range(resolution - 1, -1, -1):
                ancestor = h3.cell_to_parent(cell, ancestor_resolution)
                if ancestor in cell_set:
                    raise ValueError("Adaptive facility layer has overlapping ancestor/descendant leaves")
