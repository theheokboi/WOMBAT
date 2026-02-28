from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import h3
import pandas as pd


@dataclass
class MetroDensityCoreLayer:
    version: str

    def spec(self) -> dict[str, Any]:
        return {
            "name": "metro_density_core",
            "version": self.version,
            "distance_semantics": "h3_grid_distance",
            "params": ["resolution", "min_facilities", "core_radius", "enforce_contiguity"],
        }

    def compute(
        self, canonical_store: dict[str, pd.DataFrame], layer_store: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        facilities = canonical_store["facilities"]
        resolution = int(params["resolution"])
        min_facilities = int(params.get("min_facilities", 1))
        core_radius = int(params.get("core_radius", 1))
        enforce_contiguity = bool(params.get("enforce_contiguity", True))

        h3_col = f"h3_r{resolution}"
        if h3_col not in facilities.columns:
            raise ValueError(f"Missing H3 column for resolution {resolution}: {h3_col}")

        counts = (
            facilities.groupby(h3_col, as_index=False)
            .agg(layer_value=("facility_id", "count"), asof_date=("asof_date", "max"))
            .sort_values(by=["layer_value", h3_col], ascending=[False, True])
            .reset_index(drop=True)
        )

        if counts.empty:
            empty = pd.DataFrame(columns=["h3", "resolution", "layer_value", "layer_id", "asof_date"])
            metadata = {
                "layer_name": "metro_density_core",
                "layer_version": self.version,
                "seed_cell": None,
                "params": params,
            }
            return metadata, empty

        seed = str(counts.iloc[0][h3_col])
        disk = set(h3.grid_disk(seed, core_radius))
        candidate = counts[(counts[h3_col].isin(disk)) & (counts["layer_value"] >= min_facilities)].copy()
        candidate_cells = set(candidate[h3_col].astype(str).tolist())

        if enforce_contiguity and seed in candidate_cells:
            candidate_cells = self._connected_component(candidate_cells, seed)
            candidate = candidate[candidate[h3_col].isin(candidate_cells)].copy()

        candidate = candidate.rename(columns={h3_col: "h3"})
        candidate["resolution"] = resolution
        candidate["layer_id"] = f"metro_density_core:{self.version}"
        candidate = candidate[["h3", "resolution", "layer_value", "layer_id", "asof_date"]]
        candidate = candidate.sort_values(by=["h3"]).reset_index(drop=True)

        metadata = {
            "layer_name": "metro_density_core",
            "layer_version": self.version,
            "seed_cell": seed,
            "params": {
                "resolution": resolution,
                "min_facilities": min_facilities,
                "core_radius": core_radius,
                "enforce_contiguity": enforce_contiguity,
            },
            "distance_semantics": "h3_grid_distance",
        }
        return metadata, candidate

    def _connected_component(self, cells: set[str], seed: str) -> set[str]:
        queue = deque([seed])
        seen: set[str] = set()
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            if current not in cells:
                continue
            seen.add(current)
            neighbors = h3.grid_disk(current, 1)
            for neighbor in neighbors:
                if neighbor in cells and neighbor not in seen:
                    queue.append(neighbor)
        return seen

    def validate(self, artifacts: dict[str, Any]) -> None:
        metadata = artifacts["metadata"]
        cells = artifacts["cells"]
        if metadata.get("seed_cell") is not None and metadata["seed_cell"] not in set(cells["h3"]):
            raise ValueError("Metro layer seed cell missing from output cells")
