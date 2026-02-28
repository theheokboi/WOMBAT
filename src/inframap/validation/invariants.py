from __future__ import annotations

from typing import Any

import h3
import pandas as pd


def _adaptive_neighbor_smoothing_max_delta(metadata: dict[str, Any]) -> int | None:
    params = metadata.get("params")
    if isinstance(params, dict):
        for key in (
            "max_neighbor_resolution_delta",
            "neighbor_smoothing_max_delta",
            "smoothing_adjacency_max_delta",
        ):
            value = params.get(key)
            if value is not None:
                return int(value)
    smoothing = metadata.get("smoothing")
    if isinstance(smoothing, dict):
        value = smoothing.get("max_neighbor_delta")
        if value is not None:
            return int(value)
    return None


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
            resolutions = cells["resolution"].astype(int)
            if layer_name == "facility_density_adaptive":
                if ((resolutions < 0) | (resolutions > 13)).any():
                    raise ValueError("Invariant failed: adaptive layer has invalid resolution range")
            elif (resolutions <= 0).any():
                raise ValueError(f"Invariant failed: invalid resolution values for {layer_name}")

        if layer_name == "metro_density_core":
            seed = metadata.get("seed_cell")
            if seed and seed not in set(cells["h3"]):
                raise ValueError("Invariant failed: metro seed cell missing from output")

        if layer_name == "country_mask" and not cells.empty:
            if cells["h3"].duplicated().any():
                raise ValueError("Invariant failed: country mask has duplicate h3 assignments")

        if layer_name == "facility_density_adaptive" and not cells.empty:
            if cells["h3"].duplicated().any():
                raise ValueError("Invariant failed: adaptive layer has duplicate h3 assignments")
            encoded_resolution = cells["h3"].astype(str).map(h3.get_resolution)
            if not encoded_resolution.equals(cells["resolution"].astype(int)):
                raise ValueError("Invariant failed: adaptive layer has h3/resolution mismatch")
            if "layer_value" in cells.columns:
                occupied = cells[cells["layer_value"].astype(int) > 0]
                if not occupied.empty and (occupied["resolution"].astype(int) < 9).any():
                    raise ValueError("Invariant failed: adaptive occupied cells must be at least r9")
            adaptive_cells = {str(cell) for cell in cells["h3"].astype(str).tolist()}
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

            for cell in sorted(adaptive_cells, key=lambda c: h3.get_resolution(c)):
                resolution = h3.get_resolution(cell)
                for ancestor_resolution in range(resolution - 1, -1, -1):
                    if parent_cell(cell, ancestor_resolution) in adaptive_cells:
                        raise ValueError("Invariant failed: adaptive ancestor/descendant overlap")
            max_neighbor_delta = _adaptive_neighbor_smoothing_max_delta(metadata)
            if max_neighbor_delta is not None:
                if max_neighbor_delta < 0:
                    raise ValueError("Invariant failed: adaptive smoothing max delta must be non-negative")
                resolution_by_cell = {cell: h3.get_resolution(cell) for cell in adaptive_cells}
                by_resolution: dict[int, set[str]] = {resolution: set() for resolution in range(14)}
                for cell, resolution in resolution_by_cell.items():
                    by_resolution[resolution].add(cell)
                neighbor_cache: dict[str, list[str]] = {}

                def covering_leaf_for_neighbor(cell: str, resolution: int) -> tuple[str, int] | None:
                    for ancestor_resolution in range(resolution, -1, -1):
                        ancestor = parent_cell(cell, ancestor_resolution)
                        if ancestor in by_resolution[ancestor_resolution]:
                            return ancestor, ancestor_resolution
                    return None

                violating_pairs: set[tuple[str, int, str, int, int]] = set()
                for cell in sorted(adaptive_cells, key=lambda c: (resolution_by_cell[c], c)):
                    resolution = resolution_by_cell[cell]
                    if cell in neighbor_cache:
                        neighbors = neighbor_cache[cell]
                    else:
                        neighbors = [str(neighbor) for neighbor in h3.grid_disk(cell, 1)]
                        neighbor_cache[cell] = neighbors
                    for neighbor_str in neighbors:
                        if neighbor_str == cell:
                            continue
                        covered = covering_leaf_for_neighbor(neighbor_str, resolution)
                        if covered is None:
                            continue
                        neighbor_leaf, neighbor_resolution = covered
                        delta = abs(resolution - neighbor_resolution)
                        if delta > max_neighbor_delta:
                            left = (cell, resolution)
                            right = (neighbor_leaf, neighbor_resolution)
                            if right < left:
                                left, right = right, left
                            violating_pairs.add((left[0], left[1], right[0], right[1], delta))
                if violating_pairs:
                    samples = sorted(violating_pairs)[:3]
                    sample_text = ", ".join(
                        f"{left}@r{left_res}<->{right}@r{right_res} (delta={delta})"
                        for left, left_res, right, right_res, delta in samples
                    )
                    raise ValueError(
                        "Invariant failed: adaptive smoothing adjacency delta exceeds configured maximum "
                        f"(max_allowed_delta={max_neighbor_delta}, violating_pairs={len(violating_pairs)}, "
                        f"sample=[{sample_text}])"
                    )
