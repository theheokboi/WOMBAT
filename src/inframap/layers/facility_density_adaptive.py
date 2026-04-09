from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import h3
import pandas as pd

from inframap.layers.facility_density_policies import _AdaptiveCoverageIndex, build_adaptive_policy
from inframap.layers.facility_density_policies.base import FacilityDensityAdaptivePolicy


@dataclass
class FacilityDensityAdaptiveLayer:
    version: str
    _policy: FacilityDensityAdaptivePolicy = field(init=False, repr=False)
    _policy_helper_defaults: dict[str, Any] = field(init=False, repr=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._policy = build_adaptive_policy(self.version)
        self._policy_helper_defaults = {
            "_adjacency_counters": getattr(self._policy, "_adjacency_counters"),
            "_compact_sparse_sibling_leaves": getattr(self._policy, "_compact_sparse_sibling_leaves"),
        }

    def spec(self) -> dict[str, Any]:
        return self._policy.spec()

    def compute(
        self, canonical_store: dict[str, pd.DataFrame], layer_store: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        self._sync_policy_overrides()
        return self._policy.compute(canonical_store=canonical_store, layer_store=layer_store, params=params)

    def _sync_policy_overrides(self) -> None:
        for name, default in self._policy_helper_defaults.items():
            setattr(self._policy, name, self.__dict__.get(name, default))

    def _adjacency_counters(
        self,
        leaves: dict[str, int],
        max_neighbor_resolution_delta: int,
        candidate_cells: set[str] | None = None,
    ) -> dict[str, int]:
        helper = self._policy_helper_defaults["_adjacency_counters"]
        return helper(
            leaves=leaves,
            max_neighbor_resolution_delta=max_neighbor_resolution_delta,
            candidate_cells=candidate_cells,
        )

    def _compact_sparse_sibling_leaves(
        self,
        leaves: dict[str, int],
        *,
        min_output_resolution: int,
        base_resolution: int,
        empty_interior_max_resolution: int,
        facility_floor_resolution: int,
        facility_max_resolution: int,
        facility_floor_offset: int = 1,
        max_neighbor_resolution_delta: int,
        intersects_domain: Any,
        is_boundary_band: Any,
        is_near_occupied: Any,
        compact_empty_near_occupied: bool,
        adaptive_counters: dict[str, Any],
    ) -> dict[str, int]:
        helper = self._policy_helper_defaults["_compact_sparse_sibling_leaves"]
        return helper(
            leaves=leaves,
            min_output_resolution=min_output_resolution,
            base_resolution=base_resolution,
            empty_interior_max_resolution=empty_interior_max_resolution,
            facility_floor_resolution=facility_floor_resolution,
            facility_floor_offset=facility_floor_offset,
            facility_max_resolution=facility_max_resolution,
            max_neighbor_resolution_delta=max_neighbor_resolution_delta,
            intersects_domain=intersects_domain,
            is_boundary_band=is_boundary_band,
            is_near_occupied=is_near_occupied,
            compact_empty_near_occupied=compact_empty_near_occupied,
            adaptive_counters=adaptive_counters,
        )

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

        cell_set = {str(cell) for cell in cells["h3"].astype(str).tolist()}
        for cell in sorted(cell_set, key=lambda value: h3.get_resolution(value)):
            resolution = h3.get_resolution(cell)
            for ancestor_resolution in range(resolution - 1, -1, -1):
                ancestor = h3.cell_to_parent(cell, ancestor_resolution)
                if ancestor in cell_set:
                    raise ValueError("Adaptive facility layer has overlapping ancestor/descendant leaves")


__all__ = ["FacilityDensityAdaptiveLayer", "_AdaptiveCoverageIndex"]
