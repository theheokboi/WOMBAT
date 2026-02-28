from __future__ import annotations

from typing import Any

import pandas as pd


def run_invariants(
    facilities: pd.DataFrame,
    layer_artifacts: dict[str, dict[str, Any]],
    required_h3_resolutions: list[int],
) -> None:
    if facilities["facility_id"].duplicated().any():
        raise ValueError("Invariant failed: facility_id must be unique")

    if not facilities["lat"].between(-90.0, 90.0).all():
        raise ValueError("Invariant failed: invalid latitude")
    if not facilities["lon"].between(-180.0, 180.0).all():
        raise ValueError("Invariant failed: invalid longitude")

    for resolution in required_h3_resolutions:
        col = f"h3_r{resolution}"
        if col not in facilities.columns:
            raise ValueError(f"Invariant failed: missing H3 column {col}")
        if facilities[col].isnull().any():
            raise ValueError(f"Invariant failed: null H3 values in {col}")

    for layer_name, artifacts in layer_artifacts.items():
        metadata = artifacts.get("metadata", {})
        cells = artifacts.get("cells")
        if not metadata.get("layer_name"):
            raise ValueError(f"Invariant failed: layer metadata missing name for {layer_name}")
        if not metadata.get("layer_version"):
            raise ValueError(f"Invariant failed: layer metadata missing version for {layer_name}")
        if cells is None:
            raise ValueError(f"Invariant failed: missing cells for {layer_name}")

        if not cells.empty:
            if "resolution" not in cells.columns:
                raise ValueError(f"Invariant failed: layer {layer_name} missing resolution")
            if (cells["resolution"] <= 0).any():
                raise ValueError(f"Invariant failed: invalid resolution values for {layer_name}")

        if layer_name == "metro_density_core":
            seed = metadata.get("seed_cell")
            if seed and seed not in set(cells["h3"]):
                raise ValueError("Invariant failed: metro seed cell missing from output")

        if layer_name == "country_mask" and not cells.empty:
            if cells["h3"].duplicated().any():
                raise ValueError("Invariant failed: country mask has duplicate h3 assignments")
