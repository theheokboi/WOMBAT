from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import h3
import pandas as pd

from inframap.layers.facility_density_policies.v3 import (
    FacilityDensityAdaptiveV3Policy,
    _AdaptiveCoverageIndex,
)


@dataclass
class FacilityDensityAdaptiveV4Policy(FacilityDensityAdaptiveV3Policy):
    def spec(self) -> dict[str, Any]:
        spec = super().spec()
        spec["version"] = self.version
        spec["policy_name"] = "facility_hierarchical_partition_v4"
        return spec

    def compute(
        self, canonical_store: dict[str, pd.DataFrame], layer_store: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        facilities = canonical_store["facilities"]

        configured_base_resolution = int(params["base_resolution"])
        base_resolution = configured_base_resolution
        min_output_resolution = int(params.get("min_output_resolution", 5))
        empty_compact_min_resolution = int(params["empty_compact_min_resolution"])
        facility_floor_resolution = int(params["facility_floor_resolution"])
        facility_max_resolution = int(params["facility_max_resolution"])
        target_facilities_per_leaf = int(params["target_facilities_per_leaf"])
        empty_interior_max_resolution = int(params["empty_interior_max_resolution"])
        empty_refine_country_edge_k = self._empty_refine_country_edge_k(params)
        empty_refine_near_occupied_k = int(params["empty_refine_near_occupied_k"])
        compact_empty_near_occupied = bool(params.get("compact_empty_near_occupied", False))
        max_neighbor_resolution_delta = int(params["max_neighbor_resolution_delta"])
        sparse_occupied_min_resolution = max(min_output_resolution, facility_floor_resolution - 1)

        if not (0 <= min_output_resolution <= 9):
            raise ValueError("min_output_resolution must satisfy 0 <= value <= 9")
        if not (0 <= facility_floor_resolution <= facility_max_resolution <= 9):
            raise ValueError("facility resolutions must satisfy 0 <= floor <= max <= 9")
        if min_output_resolution > facility_max_resolution:
            raise ValueError("min_output_resolution must be <= facility_max_resolution")
        if target_facilities_per_leaf < 1:
            raise ValueError("target_facilities_per_leaf must be >= 1")
        if empty_refine_country_edge_k < 0:
            raise ValueError("empty_refine_country_edge_k must be >= 0")
        if empty_refine_near_occupied_k < 0:
            raise ValueError("empty_refine_near_occupied_k must be >= 0")
        if max_neighbor_resolution_delta < 0:
            raise ValueError("max_neighbor_resolution_delta must be >= 0")

        adaptive_counters: dict[str, Any] = {
            "initial_recursion_seconds": 0.0,
            "neighbor_smoothing_seconds": 0.0,
            "post_compaction_seconds": 0.0,
            "country_intersection_filter_seconds": 0.0,
            "covering_leaf_lookup_count": 0,
            "parent_cell_lookup_count": 0,
            "smoothing_candidate_count": 0,
            "smoothing_refinement_count": 0,
            "compaction_candidate_count": 0,
            "compaction_accept_count": 0,
            "leaf_count_total": 0,
        }

        country_artifacts = layer_store.get("country_mask")
        if not isinstance(country_artifacts, dict) or "cells" not in country_artifacts:
            raise ValueError("facility_density_adaptive requires country_mask layer artifacts")
        country_metadata = country_artifacts.get("metadata", {})
        if isinstance(country_metadata, dict):
            country_params = country_metadata.get("params", {})
            if isinstance(country_params, dict):
                country_mode = str(country_params.get("mode", ""))
                country_resolution = country_params.get("resolution")
                if country_mode == "fixed_resolution" and country_resolution is not None:
                    base_resolution = int(country_resolution)
        if not (0 <= empty_compact_min_resolution <= base_resolution <= 13):
            raise ValueError("empty_compact_min_resolution and base_resolution must satisfy 0 <= min <= base <= 13")
        if not (base_resolution <= empty_interior_max_resolution <= facility_floor_resolution - 1):
            raise ValueError(
                "empty_interior_max_resolution must satisfy base_resolution <= value <= facility_floor_resolution - 1"
            )
        coverage_domain = f"country_mask_r{base_resolution}"
        country_cells = country_artifacts["cells"]
        if not isinstance(country_cells, pd.DataFrame) or "h3" not in country_cells.columns:
            raise ValueError("country_mask artifacts must provide a cells dataframe with h3 column")

        domain_r4_set: set[str] = set()
        for raw_cell in country_cells["h3"].astype(str).tolist():
            cell = str(raw_cell)
            resolution = h3.get_resolution(cell)
            if resolution == base_resolution:
                domain_r4_set.add(cell)
            elif resolution < base_resolution:
                domain_r4_set.update(str(child) for child in h3.cell_to_children(cell, base_resolution))
            else:
                domain_r4_set.add(h3.cell_to_parent(cell, base_resolution))
        domain_r4 = sorted(domain_r4_set)
        if not domain_r4:
            empty = pd.DataFrame(columns=["h3", "resolution", "layer_value", "layer_id", "asof_date"])
            metadata = self._metadata(
                params={
                    "base_resolution": base_resolution,
                    "configured_base_resolution": configured_base_resolution,
                    "min_output_resolution": min_output_resolution,
                    "empty_compact_min_resolution": empty_compact_min_resolution,
                    "facility_floor_resolution": facility_floor_resolution,
                    "facility_max_resolution": facility_max_resolution,
                    "target_facilities_per_leaf": target_facilities_per_leaf,
                    "empty_interior_max_resolution": empty_interior_max_resolution,
                    "empty_refine_country_edge_k": empty_refine_country_edge_k,
                    "empty_refine_boundary_band_k": empty_refine_country_edge_k,
                    "empty_refine_near_occupied_k": empty_refine_near_occupied_k,
                    "compact_empty_near_occupied": compact_empty_near_occupied,
                    "max_neighbor_resolution_delta": max_neighbor_resolution_delta,
                },
                counters={
                    "adjacency_checks": 0,
                    "violating_neighbor_pairs": 0,
                    "max_neighbor_delta_observed": 0,
                    "smoothing_iterations": 0,
                },
                coverage_domain=coverage_domain,
            )
            metadata["adaptive_counters"] = dict(adaptive_counters)
            return metadata, empty

        domain_r4_set = set(domain_r4)
        parent_cache: dict[tuple[str, int], str] = {}

        def parent_cell(cell: str, resolution: int) -> str:
            adaptive_counters["parent_cell_lookup_count"] = int(adaptive_counters["parent_cell_lookup_count"]) + 1
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
            for neighbor in neighbors_within_k(cell, resolution, empty_refine_country_edge_k):
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
                must_split_for_sparse_floor = resolution < sparse_occupied_min_resolution
                must_split_for_density = (
                    facility_count > target_facilities_per_leaf and resolution < facility_max_resolution
                )
                if not must_split_for_sparse_floor and not must_split_for_density:
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

        initial_recursion_started = perf_counter()
        for root in roots:
            recurse(str(root), empty_compact_min_resolution)
        adaptive_counters["initial_recursion_seconds"] = perf_counter() - initial_recursion_started

        def refine_leaf(
            cell: str,
            resolution: int,
            facility_count: int,
            required_min_resolution: int | None = None,
        ) -> tuple[bool, list[str]]:
            allowed_max_resolution = max_allowed_resolution(cell, resolution, facility_count)
            if required_min_resolution is not None and facility_count == 0:
                allowed_max_resolution = max(
                    allowed_max_resolution,
                    min(int(required_min_resolution), facility_max_resolution),
                )
            if resolution >= allowed_max_resolution:
                return False, []
            next_resolution = resolution + 1
            children = sorted(h3.cell_to_children(cell, next_resolution))
            del leaves[cell]
            kept_children: list[str] = []
            for child in children:
                child_str = str(child)
                if intersects_domain(child_str, next_resolution):
                    leaves[child_str] = count_by_resolution[next_resolution].get(child_str, 0)
                    kept_children.append(child_str)
            return True, kept_children

        coverage_index = _AdaptiveCoverageIndex.from_leaves(leaves, parent_cell)

        def source_contributions(cell: str) -> dict[str, int]:
            adaptive_counters["smoothing_candidate_count"] = int(adaptive_counters["smoothing_candidate_count"]) + 1
            if cell not in leaves:
                return {}
            resolution = h3.get_resolution(cell)
            contributions: dict[str, int] = {}
            for neighbor in neighbors_within_k(cell, resolution, 1):
                if neighbor == cell:
                    continue
                adaptive_counters["covering_leaf_lookup_count"] = int(adaptive_counters["covering_leaf_lookup_count"]) + 1
                covered = coverage_index.covering_leaf_for_neighbor(neighbor, resolution, parent_cell)
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
                candidate_required = finer_resolution - max_neighbor_resolution_delta
                current_required = contributions.get(coarse_cell)
                if current_required is None or candidate_required > current_required:
                    contributions[coarse_cell] = candidate_required
            return contributions

        source_to_candidates: dict[str, dict[str, int]] = {}
        candidate_to_sources: dict[str, dict[str, int]] = {}
        smoothing_candidates: dict[str, int] = {}

        def remove_source(cell: str) -> None:
            old_contributions = source_to_candidates.pop(cell, {})
            for candidate_cell in old_contributions:
                sources = candidate_to_sources.get(candidate_cell)
                if sources is None:
                    continue
                sources.pop(cell, None)
                if sources:
                    smoothing_candidates[candidate_cell] = max(sources.values())
                else:
                    candidate_to_sources.pop(candidate_cell, None)
                    smoothing_candidates.pop(candidate_cell, None)

        def add_source(cell: str) -> None:
            remove_source(cell)
            contributions = source_contributions(cell)
            if not contributions:
                return
            source_to_candidates[cell] = contributions
            for candidate_cell, required_min_resolution in contributions.items():
                sources = candidate_to_sources.setdefault(candidate_cell, {})
                sources[cell] = required_min_resolution
                smoothing_candidates[candidate_cell] = max(sources.values())

        def collect_affected_smoothing_cells(changed_cells_by_resolution: dict[int, set[str]]) -> set[str]:
            affected: set[str] = set()
            for resolution, changed_cells in changed_cells_by_resolution.items():
                for seed in sorted(changed_cells):
                    for neighbor in neighbors_within_k(seed, resolution, 1):
                        adaptive_counters["covering_leaf_lookup_count"] = int(adaptive_counters["covering_leaf_lookup_count"]) + 1
                        covered = coverage_index.covering_leaf_for_neighbor(neighbor, resolution, parent_cell)
                        if covered is None:
                            continue
                        affected.add(covered[0])
            return affected

        smoothing_started = perf_counter()
        for cell in sorted(leaves, key=lambda value: (h3.get_resolution(value), value)):
            add_source(cell)

        smoothing_iterations = 0
        while smoothing_candidates:
            ordered_candidates = sorted(smoothing_candidates, key=lambda item: (h3.get_resolution(item), item))
            refined = False
            for candidate_cell in ordered_candidates:
                if candidate_cell not in leaves:
                    smoothing_candidates.pop(candidate_cell, None)
                    continue
                candidate_resolution = h3.get_resolution(candidate_cell)
                required_min_resolution = smoothing_candidates.get(candidate_cell)
                if required_min_resolution is None:
                    continue
                if candidate_resolution >= required_min_resolution:
                    smoothing_candidates.pop(candidate_cell, None)
                    continue
                candidate_count = leaves[candidate_cell]
                refined_ok, kept_children = refine_leaf(
                    candidate_cell,
                    candidate_resolution,
                    candidate_count,
                    required_min_resolution=required_min_resolution,
                )
                if not refined_ok:
                    smoothing_candidates.pop(candidate_cell, None)
                    continue
                smoothing_iterations += 1
                adaptive_counters["smoothing_refinement_count"] = int(adaptive_counters["smoothing_refinement_count"]) + 1
                remove_source(candidate_cell)
                candidate_to_sources.pop(candidate_cell, None)
                smoothing_candidates.pop(candidate_cell, None)
                coverage_index.remove_leaf(candidate_cell, candidate_resolution, parent_cell)
                changed_cells_by_resolution: dict[int, set[str]] = {
                    resolution: set() for resolution in range(candidate_resolution + 2)
                }
                for ancestor_resolution in range(candidate_resolution + 1):
                    changed_cells_by_resolution[ancestor_resolution].add(parent_cell(candidate_cell, ancestor_resolution))
                next_resolution = candidate_resolution + 1
                for child_cell in kept_children:
                    coverage_index.add_leaf(child_cell, next_resolution, parent_cell)
                    for ancestor_resolution in range(next_resolution + 1):
                        changed_cells_by_resolution[ancestor_resolution].add(parent_cell(child_cell, ancestor_resolution))
                affected_cells = collect_affected_smoothing_cells(changed_cells_by_resolution)
                for affected_cell in sorted(affected_cells, key=lambda value: (h3.get_resolution(value), value)):
                    add_source(affected_cell)
                refined = True
                break
            if not refined:
                break
        adaptive_counters["neighbor_smoothing_seconds"] = perf_counter() - smoothing_started

        compaction_started = perf_counter()
        leaves = self._compact_sparse_sibling_leaves(
            leaves=leaves,
            min_output_resolution=min_output_resolution,
            base_resolution=base_resolution,
            empty_interior_max_resolution=empty_interior_max_resolution,
            facility_floor_resolution=facility_floor_resolution,
            facility_max_resolution=facility_max_resolution,
            max_neighbor_resolution_delta=max_neighbor_resolution_delta,
            intersects_domain=intersects_domain,
            is_boundary_band=is_boundary_band,
            is_near_occupied=is_near_occupied,
            compact_empty_near_occupied=compact_empty_near_occupied,
            adaptive_counters=adaptive_counters,
        )
        adaptive_counters["post_compaction_seconds"] = perf_counter() - compaction_started

        adjacency_counters = self._adjacency_counters(
            leaves=leaves,
            max_neighbor_resolution_delta=max_neighbor_resolution_delta,
        )
        if adjacency_counters["violating_neighbor_pairs"] > 0:
            raise ValueError(
                "Adaptive facility layer violates max_neighbor_resolution_delta after smoothing; "
                f"violating_pairs={adjacency_counters['violating_neighbor_pairs']}, "
                f"max_delta_observed={adjacency_counters['max_neighbor_delta_observed']}, "
                f"allowed={max_neighbor_resolution_delta}"
            )
        adjacency_counters["smoothing_iterations"] = smoothing_iterations
        adaptive_counters.update(adjacency_counters)
        adaptive_counters["smoothing_iterations"] = smoothing_iterations

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
        filter_started = perf_counter()
        output, country_intersection_filter_applied = self._filter_to_country_intersection(
            output=output,
            country_metadata=country_metadata,
        )
        adaptive_counters["country_intersection_filter_seconds"] = perf_counter() - filter_started
        country_intersection_cells_dropped = int(len(leaves) - len(output))
        adaptive_counters["leaf_count_total"] = int(len(output))

        metadata = self._metadata(
            params={
                "base_resolution": base_resolution,
                "configured_base_resolution": configured_base_resolution,
                "min_output_resolution": min_output_resolution,
                "empty_compact_min_resolution": empty_compact_min_resolution,
                "facility_floor_resolution": facility_floor_resolution,
                "facility_max_resolution": facility_max_resolution,
                "target_facilities_per_leaf": target_facilities_per_leaf,
                "empty_interior_max_resolution": empty_interior_max_resolution,
                "empty_refine_country_edge_k": empty_refine_country_edge_k,
                "empty_refine_boundary_band_k": empty_refine_country_edge_k,
                "empty_refine_near_occupied_k": empty_refine_near_occupied_k,
                "compact_empty_near_occupied": compact_empty_near_occupied,
                "max_neighbor_resolution_delta": max_neighbor_resolution_delta,
            },
            counters=adjacency_counters,
            coverage_domain=coverage_domain,
        )
        metadata["adaptive_counters"] = dict(adaptive_counters)
        metadata["country_intersection_filter_applied"] = bool(country_intersection_filter_applied)
        metadata["country_intersection_cells_dropped"] = country_intersection_cells_dropped
        return metadata, output

    def _compact_sparse_sibling_leaves(
        self,
        leaves: dict[str, int],
        *,
        min_output_resolution: int,
        base_resolution: int,
        empty_interior_max_resolution: int,
        facility_floor_resolution: int,
        facility_max_resolution: int,
        max_neighbor_resolution_delta: int,
        intersects_domain: Any,
        is_boundary_band: Any,
        is_near_occupied: Any,
        compact_empty_near_occupied: bool,
        adaptive_counters: dict[str, Any],
    ) -> dict[str, int]:
        leaves = dict(leaves)
        parent_cache: dict[tuple[str, int], str] = {}
        adaptive_counters.setdefault("compaction_candidate_count", 0)
        adaptive_counters.setdefault("compaction_accept_count", 0)

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

        def can_compact_parent(cell: str, resolution: int, facility_count: int) -> bool:
            if facility_count > 0:
                return False
            if resolution < min_output_resolution:
                return False
            if resolution < base_resolution:
                return False
            if is_boundary_band(cell, resolution):
                return False
            if is_near_occupied(cell, resolution):
                if not compact_empty_near_occupied:
                    return False
                return resolution <= facility_floor_resolution - 1
            return resolution <= min(empty_interior_max_resolution, facility_floor_resolution - 1)

        def affected_cells_for_compaction(candidate_parent: str) -> set[str]:
            parent_resolution = h3.get_resolution(candidate_parent)
            parent_ring = {str(cell) for cell in h3.grid_disk(candidate_parent, 1)}
            coarse_ring_by_resolution: dict[int, set[str]] = {}
            affected: set[str] = set()
            for leaf_cell in leaves:
                resolution = h3.get_resolution(leaf_cell)
                if resolution >= parent_resolution:
                    if parent_cell(leaf_cell, parent_resolution) in parent_ring:
                        affected.add(leaf_cell)
                    continue
                ring = coarse_ring_by_resolution.get(resolution)
                if ring is None:
                    ring = {str(cell) for cell in h3.grid_disk(parent_cell(candidate_parent, resolution), 1)}
                    coarse_ring_by_resolution[resolution] = ring
                if leaf_cell in ring:
                    affected.add(leaf_cell)
            return affected

        while True:
            compacted = False
            leaves_by_resolution: dict[int, set[str]] = {resolution: set() for resolution in range(14)}
            for leaf_cell in leaves:
                leaves_by_resolution[h3.get_resolution(leaf_cell)].add(leaf_cell)

            for resolution in range(facility_max_resolution, min_output_resolution, -1):
                candidate_parents: set[str] = set()
                for leaf_cell in sorted(leaves_by_resolution[resolution]):
                    candidate_parents.add(parent_cell(leaf_cell, resolution - 1))

                for candidate_parent in sorted(candidate_parents):
                    adaptive_counters["compaction_candidate_count"] = int(adaptive_counters["compaction_candidate_count"]) + 1
                    if not intersects_domain(candidate_parent, resolution - 1):
                        continue
                    children = [
                        str(child)
                        for child in sorted(h3.cell_to_children(candidate_parent, resolution))
                        if intersects_domain(str(child), resolution)
                    ]
                    if len(children) < 2:
                        continue
                    if any(child not in leaves for child in children):
                        continue
                    facility_count = sum(int(leaves[child]) for child in children)
                    if not can_compact_parent(candidate_parent, resolution - 1, facility_count):
                        continue

                    original_children = {child: leaves[child] for child in children}
                    for child in children:
                        del leaves[child]
                    leaves[candidate_parent] = facility_count

                    counters = self._adjacency_counters(
                        leaves=leaves,
                        max_neighbor_resolution_delta=max_neighbor_resolution_delta,
                        candidate_cells=affected_cells_for_compaction(candidate_parent),
                    )
                    if counters["violating_neighbor_pairs"] > 0:
                        del leaves[candidate_parent]
                        leaves.update(original_children)
                        continue

                    adaptive_counters["compaction_accept_count"] = int(adaptive_counters["compaction_accept_count"]) + 1
                    compacted = True
                    break
                if compacted:
                    break
            if not compacted:
                break

        return leaves

    def _metadata(
        self,
        params: dict[str, Any],
        counters: dict[str, int] | None = None,
        coverage_domain: str = "country_mask_dynamic_base_resolution",
    ) -> dict[str, Any]:
        metadata = super()._metadata(params=params, counters=counters, coverage_domain=coverage_domain)
        metadata["layer_version"] = self.version
        metadata["policy_name"] = "facility_hierarchical_partition_v4"
        metadata["stopping_rules"]["facility_branch"] = {
            "rule": "sparse_until_floor_minus_one_then_density",
            "sparse_min_resolution": max(params["min_output_resolution"], params["facility_floor_resolution"] - 1),
            "dense_refine_trigger_count_exclusive": params["target_facilities_per_leaf"],
            "dense_refine_floor_resolution": params["facility_floor_resolution"],
            "max_resolution": params["facility_max_resolution"],
        }
        metadata["stopping_rules"]["post_compaction"] = {
            "rule": "merge_empty_sibling_groups_when_safe",
            "occupied_parent_max_facility_count": 0,
            "occupied_singleton_compaction_enabled": False,
            "empty_near_occupied_enabled": params["compact_empty_near_occupied"],
            "respects_boundary_band": True,
        }
        return metadata
