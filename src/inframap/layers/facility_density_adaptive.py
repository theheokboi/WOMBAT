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
            "policy_name": "facility_hierarchical_partition_v2",
            "coverage_domain": "country_mask_r4",
            "params": [
                "base_resolution",
                "empty_compact_min_resolution",
                "facility_floor_resolution",
                "facility_max_resolution",
                "target_facilities_per_leaf",
                "allow_domain_expansion",
                "allow_cross_border_compaction",
            ],
        }

    def compute(
        self, canonical_store: dict[str, pd.DataFrame], layer_store: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        facilities = canonical_store["facilities"]

        base_resolution = int(params["base_resolution"])
        empty_compact_min_resolution = int(params["empty_compact_min_resolution"])
        facility_floor_resolution = int(params["facility_floor_resolution"])
        facility_max_resolution = int(params["facility_max_resolution"])
        target_facilities_per_leaf = int(params["target_facilities_per_leaf"])
        allow_domain_expansion = bool(params["allow_domain_expansion"])
        allow_cross_border_compaction = bool(params["allow_cross_border_compaction"])

        if base_resolution != 4:
            raise ValueError("base_resolution must be 4 for facility_hierarchical_partition_v2")
        if empty_compact_min_resolution != 0:
            raise ValueError("empty_compact_min_resolution must be 0 for facility_hierarchical_partition_v2")
        if facility_floor_resolution != 9:
            raise ValueError("facility_floor_resolution must be 9 for facility_hierarchical_partition_v2")
        if facility_max_resolution != 13:
            raise ValueError("facility_max_resolution must be 13 for facility_hierarchical_partition_v2")
        if target_facilities_per_leaf != 1:
            raise ValueError("target_facilities_per_leaf must be 1 for facility_hierarchical_partition_v2")
        if not allow_domain_expansion:
            raise ValueError("allow_domain_expansion must be true for facility_hierarchical_partition_v2")
        if not allow_cross_border_compaction:
            raise ValueError("allow_cross_border_compaction must be true for facility_hierarchical_partition_v2")

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
                    "empty_compact_min_resolution": empty_compact_min_resolution,
                    "facility_floor_resolution": facility_floor_resolution,
                    "facility_max_resolution": facility_max_resolution,
                    "target_facilities_per_leaf": target_facilities_per_leaf,
                    "allow_domain_expansion": allow_domain_expansion,
                    "allow_cross_border_compaction": allow_cross_border_compaction,
                }
            )
            return metadata, empty

        domain_r4_set = set(domain_r4)
        domain_ancestors_by_resolution = {
            resolution: {h3.cell_to_parent(cell, resolution) for cell in domain_r4_set}
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
                    lambda cell: h3.cell_to_parent(cell, resolution)
                )
            else:
                series = facilities_in_domain[f"h3_r{resolution}"]
            count_by_resolution[resolution] = {
                str(cell): int(count) for cell, count in series.value_counts(sort=False).items()
            }

        roots = sorted(domain_ancestors_by_resolution[empty_compact_min_resolution])
        leaves: list[tuple[str, int, int]] = []

        def intersects_domain(cell: str, resolution: int) -> bool:
            if resolution < base_resolution:
                return cell in domain_ancestors_by_resolution[resolution]
            if resolution == base_resolution:
                return cell in domain_r4_set
            return h3.cell_to_parent(cell, base_resolution) in domain_r4_set

        def recurse(cell: str, resolution: int) -> None:
            facility_count = count_by_resolution[resolution].get(cell, 0)
            if facility_count == 0:
                leaves.append((cell, resolution, 0))
                return

            must_split_for_floor = resolution < facility_floor_resolution
            must_split_for_density = (
                facility_count > target_facilities_per_leaf and resolution < facility_max_resolution
            )
            if not must_split_for_floor and not must_split_for_density:
                leaves.append((cell, resolution, facility_count))
                return

            next_resolution = resolution + 1
            children = sorted(h3.cell_to_children(cell, next_resolution))
            for child in children:
                if intersects_domain(child, next_resolution):
                    recurse(str(child), next_resolution)

        for root in roots:
            recurse(str(root), empty_compact_min_resolution)

        # Deterministic mixed-resolution leaf output.
        output = pd.DataFrame(leaves, columns=["h3", "resolution", "layer_value"])
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
                "empty_compact_min_resolution": empty_compact_min_resolution,
                "facility_floor_resolution": facility_floor_resolution,
                "facility_max_resolution": facility_max_resolution,
                "target_facilities_per_leaf": target_facilities_per_leaf,
                "allow_domain_expansion": allow_domain_expansion,
                "allow_cross_border_compaction": allow_cross_border_compaction,
            }
        )
        return metadata, output

    def _metadata(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "layer_name": "facility_density_adaptive",
            "layer_version": self.version,
            "policy_name": "facility_hierarchical_partition_v2",
            "coverage_domain": "country_mask_r4",
            "params": params,
            "stopping_rules": {
                "empty_branch": {
                    "rule": "compact_upward",
                    "min_resolution": params["empty_compact_min_resolution"],
                    "allow_domain_expansion": params["allow_domain_expansion"],
                    "allow_cross_border_compaction": params["allow_cross_border_compaction"],
                },
                "facility_branch": {
                    "min_resolution": params["facility_floor_resolution"],
                    "target_facilities_per_leaf": params["target_facilities_per_leaf"],
                    "max_resolution": params["facility_max_resolution"],
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

        if ((cells["resolution"] < 0) | (cells["resolution"] > 13)).any():
            raise ValueError("Adaptive facility layer has cells outside allowed resolution range [0, 13]")

        encoded_resolution = cells["h3"].astype(str).map(h3.get_resolution)
        if not encoded_resolution.equals(cells["resolution"].astype(int)):
            raise ValueError("Adaptive facility layer has resolution column mismatched with h3 cell resolution")

        if (cells["layer_value"] < 0).any():
            raise ValueError("Adaptive facility layer has negative facility counts")

        facility_bearing = cells[cells["layer_value"] > 0]
        if not facility_bearing.empty and (facility_bearing["resolution"] < 9).any():
            raise ValueError("Adaptive facility layer has facility-bearing cells coarser than r9")

        cell_set = {str(cell) for cell in cells["h3"].astype(str).tolist()}
        for cell in sorted(cell_set, key=lambda value: h3.get_resolution(value)):
            resolution = h3.get_resolution(cell)
            for ancestor_resolution in range(resolution - 1, -1, -1):
                ancestor = h3.cell_to_parent(cell, ancestor_resolution)
                if ancestor in cell_set:
                    raise ValueError("Adaptive facility layer has overlapping ancestor/descendant leaves")
