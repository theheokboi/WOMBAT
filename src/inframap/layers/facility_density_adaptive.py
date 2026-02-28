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
            "distance_semantics": "h3_count_threshold_split",
            "params": ["min_resolution", "max_resolution", "split_threshold"],
        }

    def compute(
        self, canonical_store: dict[str, pd.DataFrame], layer_store: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        facilities = canonical_store["facilities"]
        min_resolution = int(params["min_resolution"])
        max_resolution = int(params["max_resolution"])
        split_threshold = int(params["split_threshold"])

        if min_resolution < 0 or max_resolution < min_resolution or max_resolution > 15:
            raise ValueError("Invalid adaptive resolution range")
        if split_threshold < 1:
            raise ValueError("split_threshold must be >= 1")

        if facilities.empty:
            empty = pd.DataFrame(columns=["h3", "resolution", "layer_value", "layer_id", "asof_date"])
            metadata = {
                "layer_name": "facility_density_adaptive",
                "layer_version": self.version,
                "params": {
                    "min_resolution": min_resolution,
                    "max_resolution": max_resolution,
                    "split_threshold": split_threshold,
                },
                "distance_semantics": "h3_count_threshold_split",
            }
            return metadata, empty

        working = facilities[["lat", "lon", "asof_date"]].copy()
        for resolution in range(min_resolution, max_resolution + 1):
            col = f"h3_r{resolution}"
            working[col] = working.apply(
                lambda row: h3.latlng_to_cell(float(row["lat"]), float(row["lon"]), resolution), axis=1
            )

        active = pd.DataFrame(
            {
                "row_id": working.index,
                "resolution": min_resolution,
                "h3": working[f"h3_r{min_resolution}"],
            }
        )

        while True:
            grouped = (
                active.groupby(["resolution", "h3"], sort=True)["row_id"]
                .count()
                .reset_index(name="layer_value")
            )
            split_groups = grouped[
                (grouped["layer_value"] > split_threshold) & (grouped["resolution"] < max_resolution)
            ]
            if split_groups.empty:
                break
            for _, split in split_groups.iterrows():
                resolution = int(split["resolution"])
                cell = str(split["h3"])
                mask = (active["resolution"] == resolution) & (active["h3"] == cell)
                row_ids = active.loc[mask, "row_id"].to_numpy()
                next_resolution = resolution + 1
                active.loc[mask, "resolution"] = next_resolution
                active.loc[mask, "h3"] = working.loc[row_ids, f"h3_r{next_resolution}"].to_numpy()

        annotated = active.merge(working[["asof_date"]], left_on="row_id", right_index=True, how="left")
        cells = (
            annotated.groupby(["h3", "resolution"], sort=True, as_index=False)
            .agg(layer_value=("row_id", "count"), asof_date=("asof_date", "max"))
            .sort_values(by=["resolution", "h3"])
            .reset_index(drop=True)
        )
        cells["layer_id"] = f"facility_density_adaptive:{self.version}"
        cells = cells[["h3", "resolution", "layer_value", "layer_id", "asof_date"]]
        metadata = {
            "layer_name": "facility_density_adaptive",
            "layer_version": self.version,
            "params": {
                "min_resolution": min_resolution,
                "max_resolution": max_resolution,
                "split_threshold": split_threshold,
            },
            "distance_semantics": "h3_count_threshold_split",
        }
        return metadata, cells

    def validate(self, artifacts: dict[str, Any]) -> None:
        cells = artifacts["cells"]
        if cells.empty:
            return
        if cells["h3"].duplicated().any():
            raise ValueError("Adaptive facility layer has duplicate h3 cells")
        if (cells["layer_value"] < 1).any():
            raise ValueError("Adaptive facility layer has invalid facility counts")
