from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import warnings

import h3
import pandas as pd
from shapely.geometry import Polygon, shape


@dataclass
class CountryMaskLayer:
    version: str
    legacy_world_dataset_path: str = (
        "data/reference/natural_earth_admin0_subset.geojson"
    )
    color_palette: tuple[str, ...] = (
        "#1d4ed8",
        "#dc2626",
        "#16a34a",
        "#ca8a04",
        "#7c3aed",
        "#0f766e",
        "#be123c",
        "#1f2937",
    )

    def spec(self) -> dict[str, Any]:
        return {
            "name": "country_mask",
            "version": self.version,
            "distance_semantics": "fixed_overlap_ratio_or_quadtree_classify_split",
            "params": [
                "mode",
                "resolution",
                "membership_rule",
                "base_resolution",
                "max_resolution",
                "base_contain",
                "inside_epsilon",
                "outside_epsilon",
                "polygon_dataset",
                "polygon_dataset_dir",
                "include_iso_a2",
                "exclude_iso_a2",
            ],
        }

    def compute(
        self,
        canonical_store: dict[str, pd.DataFrame],
        layer_store: dict[str, Any],
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        facilities = canonical_store["facilities"]
        progress_cb = params.get("_progress_cb")
        if not callable(progress_cb):
            progress_cb = None
        mode = str(params.get("mode", "fixed_resolution"))
        rule = str(params.get("membership_rule", "overlap_ratio"))
        dataset = params.get("polygon_dataset")
        dataset_dir = params.get("polygon_dataset_dir")
        include_iso = {str(code).upper() for code in params.get("include_iso_a2", [])}
        exclude_iso = {str(code).upper() for code in params.get("exclude_iso_a2", [])}
        dataset_is_legacy_world = False
        selected_datasets: list[str] = []
        dataset_source = "geojson_file"

        if isinstance(dataset_dir, str):
            if not include_iso:
                raise ValueError(
                    "country_mask requires non-empty include_iso_a2 when polygon_dataset_dir is set"
                )
            polygons, selected_datasets = self._load_polygons_from_dir(
                dataset_dir,
                include_iso=include_iso,
                exclude_iso=exclude_iso,
            )
            dataset_source = "country_geojson_directory"
            dataset = None
        elif isinstance(dataset, str):
            dataset_is_legacy_world = dataset == self.legacy_world_dataset_path
            if dataset_is_legacy_world:
                warnings.warn(
                    (
                        "country_mask polygon_dataset is using deprecated legacy world file "
                        f"'{self.legacy_world_dataset_path}'. Migrate to per-country dataset selection "
                        "(e.g., files under data/countries with explicit ISO selection per run)."
                    ),
                    UserWarning,
                    stacklevel=2,
                )
            polygons = self._load_polygons_from_dataset(
                dataset, exclude_iso=exclude_iso
            )
            selected_datasets = [dataset]
            include_iso = {iso for iso, _, _ in polygons}
            dataset_source = (
                "Natural Earth admin-0 subset"
                if dataset_is_legacy_world
                else "geojson_file"
            )
        else:
            raise ValueError(
                "country_mask requires either polygon_dataset or polygon_dataset_dir"
            )

        # Deterministic rule: first country in sorted ISO order claims each cell.
        cell_to_country: dict[str, tuple[str, str]] = {}
        total_polygons = len(polygons)
        if progress_cb is not None and total_polygons > 0:
            progress_cb(f"polygons loaded: {total_polygons}")
        if mode == "fixed_resolution":
            resolution = int(params["resolution"])
            for idx, (iso, name, polygon) in enumerate(polygons, start=1):
                if progress_cb is not None:
                    progress_cb(f"polygon {idx}/{total_polygons} iso={iso} mode={mode}")
                candidate_cells = sorted(
                    self._polygon_to_cells_fixed(polygon, resolution, rule)
                )
                for cell in candidate_cells:
                    if cell in cell_to_country:
                        continue
                    cell_to_country[cell] = (iso, name)
            base_resolution = None
            max_resolution = resolution
            base_contain = None
            inside_epsilon = None
            outside_epsilon = None
        elif mode == "quadtree_classify_split":
            base_resolution = int(params["base_resolution"])
            max_resolution = int(params["max_resolution"])
            if not (0 <= base_resolution <= max_resolution <= 13):
                raise ValueError(
                    "country_mask quadtree requires 0 <= base_resolution <= max_resolution <= 13"
                )
            base_contain = str(params.get("base_contain", "overlap"))
            if base_contain not in {"center", "full", "overlap", "bbox_overlap"}:
                raise ValueError(f"Unsupported base_contain: {base_contain}")
            inside_epsilon = float(params.get("inside_epsilon", 1e-6))
            outside_epsilon = float(params.get("outside_epsilon", 1e-9))
            if not (0.0 <= outside_epsilon <= 1.0):
                raise ValueError("outside_epsilon must be within [0, 1]")
            if not (0.0 <= inside_epsilon <= 1.0):
                raise ValueError("inside_epsilon must be within [0, 1]")

            for idx, (iso, name, polygon) in enumerate(polygons, start=1):
                if progress_cb is not None:
                    progress_cb(f"polygon {idx}/{total_polygons} iso={iso} mode={mode}")

                def polygon_progress(note: str, *, _idx: int = idx, _iso: str = iso) -> None:
                    assert progress_cb is not None
                    progress_cb(f"polygon {_idx}/{total_polygons} iso={_iso} mode={mode} {note}")

                candidate_cells = sorted(
                    self._polygon_to_cells_quadtree_classify_split(
                        polygon=polygon,
                        base_resolution=base_resolution,
                        max_resolution=max_resolution,
                        base_contain=base_contain,
                        inside_epsilon=inside_epsilon,
                        outside_epsilon=outside_epsilon,
                        progress_cb=polygon_progress if progress_cb is not None else None,
                    )
                )
                for cell in candidate_cells:
                    if cell in cell_to_country:
                        continue
                    cell_to_country[cell] = (iso, name)
            resolution = None
        else:
            raise ValueError(f"Unsupported country_mask mode: {mode}")
        if progress_cb is not None:
            progress_cb(f"polygon processing complete: {total_polygons} total")

        country_colors = self._build_country_colors(cell_to_country)

        rows: list[dict[str, Any]] = []
        max_asof = (
            facilities["asof_date"].max() if "asof_date" in facilities.columns else None
        )
        for cell in sorted(cell_to_country.keys()):
            iso, name = cell_to_country[cell]
            color_idx = country_colors[iso]
            rows.append(
                {
                    "h3": cell,
                    "resolution": h3.get_resolution(cell),
                    "layer_value": iso,
                    "country_name": name,
                    "country_color": color_idx,
                    "country_color_hex": self.color_palette[color_idx],
                    "layer_id": f"country_mask:{self.version}",
                    "asof_date": max_asof,
                }
            )

        cells = pd.DataFrame(
            rows,
            columns=[
                "h3",
                "resolution",
                "layer_value",
                "country_name",
                "country_color",
                "country_color_hex",
                "layer_id",
                "asof_date",
            ],
        )
        if not cells.empty:
            cells = cells.sort_values(by=["h3"]).reset_index(drop=True)
        metadata = {
            "layer_name": "country_mask",
            "layer_version": self.version,
            "params": {
                "mode": mode,
                "resolution": resolution,
                "membership_rule": rule,
                "base_resolution": base_resolution,
                "max_resolution": max_resolution,
                "base_contain": base_contain,
                "inside_epsilon": inside_epsilon,
                "outside_epsilon": outside_epsilon,
                "polygon_dataset": dataset,
                "polygon_dataset_dir": (
                    str(dataset_dir) if isinstance(dataset_dir, str) else None
                ),
                "include_iso_a2": sorted(include_iso),
                "exclude_iso_a2": sorted(exclude_iso),
            },
            "polygon_dataset_source": dataset_source,
            "polygon_dataset_files": sorted(selected_datasets),
            "polygon_dataset_deprecated": dataset_is_legacy_world,
            "polygon_dataset_deprecation_notice": (
                "legacy_world_dataset_deprecated_use_country_selection"
                if dataset_is_legacy_world
                else None
            ),
            "distance_semantics": (
                "fixed_resolution_overlap_ratio"
                if mode == "fixed_resolution"
                else "quadtree_classify_split_overlap_ratio"
            ),
            "country_color_palette": list(self.color_palette),
            "country_color_map": {
                iso: idx for iso, idx in sorted(country_colors.items())
            },
        }
        return metadata, cells

    def _polygon_to_cells_fixed(
        self, polygon: Any, resolution: int, rule: str
    ) -> list[str]:
        if rule != "overlap_ratio":
            raise ValueError(f"Unsupported membership rule: {rule}")
        # Fixed mode applies deterministic overlap-ratio membership at one resolution.
        candidates = self._shape_to_cells(
            polygon=polygon,
            resolution=resolution,
            contain="overlap",
        )
        selected = [
            str(cell)
            for cell in sorted(candidates)
            if self._overlap_ratio(cell=str(cell), polygon=polygon) > 0.0
        ]
        return selected

    def _polygon_to_cells_quadtree_classify_split(
        self,
        polygon: Any,
        base_resolution: int,
        max_resolution: int,
        base_contain: str,
        inside_epsilon: float,
        outside_epsilon: float,
        progress_cb: Callable[[str], None] | None = None,
    ) -> list[str]:
        base_cells = self._shape_to_cells(
            polygon=polygon, resolution=base_resolution, contain=base_contain
        )
        leaves: set[str] = set()
        current_cells = sorted(base_cells)
        if progress_cb is not None:
            progress_cb(f"base_resolution=r{base_resolution} base_cells={len(current_cells)}")

        for next_resolution in range(base_resolution + 1, max_resolution + 1):
            if not current_cells:
                if progress_cb is not None:
                    progress_cb(f"frontier_empty_before_r{next_resolution}")
                break
            next_cells: list[str] = []
            inside_count = 0
            outside_count = 0
            split_count = 0
            total_current = len(current_cells)
            for idx, cell in enumerate(current_cells, start=1):
                ratio = self._overlap_ratio(cell=cell, polygon=polygon)
                if ratio >= (1.0 - inside_epsilon):
                    leaves.add(cell)
                    inside_count += 1
                elif ratio <= outside_epsilon:
                    outside_count += 1
                    continue
                else:
                    next_cells.extend(
                        str(child)
                        for child in sorted(h3.cell_to_children(cell, next_resolution))
                    )
                    split_count += 1
                if progress_cb is not None and (idx % 2000 == 0 or idx == total_current):
                    progress_cb(
                        f"scan_r{next_resolution - 1} {idx}/{total_current} "
                        f"inside={inside_count} outside={outside_count} split={split_count} "
                        f"next_frontier={len(next_cells)} leaves={len(leaves)}"
                    )
            current_cells = next_cells
            if progress_cb is not None:
                progress_cb(f"advance_to_r{next_resolution} frontier={len(current_cells)} leaves={len(leaves)}")

        total_final = len(current_cells)
        accepted_final = 0
        for idx, cell in enumerate(current_cells, start=1):
            ratio = self._overlap_ratio(cell=cell, polygon=polygon)
            if ratio > outside_epsilon:
                leaves.add(cell)
                accepted_final += 1
            if progress_cb is not None and (idx % 2000 == 0 or idx == total_final):
                progress_cb(f"final_r{max_resolution} {idx}/{total_final} accepted={accepted_final} leaves={len(leaves)}")
        if progress_cb is not None:
            progress_cb(f"quadtree_done leaves={len(leaves)}")
        return sorted(leaves)

    def _shape_to_cells(self, polygon: Any, resolution: int, contain: str) -> list[str]:
        if contain == "center":
            return list(h3.geo_to_cells(polygon.__geo_interface__, resolution))
        h3shape = h3.geo_to_h3shape(polygon.__geo_interface__)
        return list(
            h3.h3shape_to_cells_experimental(
                h3shape=h3shape, res=resolution, contain=contain
            )
        )

    def _cell_polygon(self, cell: str) -> Polygon:
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
        return Polygon(ring)

    def _overlap_ratio(self, cell: str, polygon: Any) -> float:
        poly = self._cell_polygon(cell)
        if poly.is_empty or poly.area == 0:
            return 0.0
        return float(poly.intersection(polygon).area / poly.area)

    def _load_polygons_from_dataset(
        self, path: str, exclude_iso: set[str]
    ) -> list[tuple[str, str, Any]]:
        fallback_iso = Path(path).stem.upper()
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        polygons = []
        for feature in data["features"]:
            iso = self._feature_country_iso(feature, fallback_iso=fallback_iso)
            if iso in exclude_iso:
                continue
            name = self._feature_country_name(feature, default=iso)
            geom = shape(feature["geometry"])
            polygons.append((iso, name, geom))
        polygons.sort(key=lambda x: x[0])
        return polygons

    def _load_polygons_from_dir(
        self, directory: str, include_iso: set[str], exclude_iso: set[str]
    ) -> tuple[list[tuple[str, str, Any]], list[str]]:
        polygons: list[tuple[str, str, Any]] = []
        selected_files: list[str] = []
        for iso in sorted(include_iso - exclude_iso):
            path = Path(directory) / f"{iso}.geojson"
            if not path.exists():
                raise ValueError(
                    f"country_mask missing dataset for ISO '{iso}' at {path}"
                )
            selected_files.append(str(path))
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            for feature in data["features"]:
                feature_iso = self._feature_country_iso(feature, fallback_iso=iso)
                if feature_iso in exclude_iso:
                    continue
                name = self._feature_country_name(feature, default=feature_iso)
                geom = shape(feature["geometry"])
                polygons.append((feature_iso, name, geom))
        polygons.sort(key=lambda x: x[0])
        return polygons, selected_files

    def _feature_country_iso(self, feature: dict[str, Any], fallback_iso: str) -> str:
        properties = feature.get("properties", {})
        for key in ("iso_a2", "ISO_A2", "GID_0"):
            value = properties.get(key)
            if value:
                return str(value).upper()[:2]
        return fallback_iso

    def _feature_country_name(self, feature: dict[str, Any], default: str) -> str:
        properties = feature.get("properties", {})
        for key in ("name", "NAME", "COUNTRY", "NAME_0"):
            value = properties.get(key)
            if value:
                return str(value)
        return default

    def _build_country_colors(
        self, cell_to_country: dict[str, tuple[str, str]]
    ) -> dict[str, int]:
        codes = sorted({iso for iso, _ in cell_to_country.values()})
        adjacency: dict[str, set[str]] = {iso: set() for iso in codes}
        for cell, (iso, _) in cell_to_country.items():
            for neighbor in h3.grid_disk(cell, 1):
                other = cell_to_country.get(neighbor)
                if other is None:
                    continue
                other_iso, _ = other
                if other_iso == iso:
                    continue
                adjacency[iso].add(other_iso)
                adjacency[other_iso].add(iso)

        assignments: dict[str, int] = {}
        for iso in sorted(codes, key=lambda item: (-len(adjacency[item]), item)):
            used = {assignments[n] for n in adjacency[iso] if n in assignments}
            color_idx = 0
            while color_idx in used:
                color_idx += 1
            if color_idx >= len(self.color_palette):
                color_idx = color_idx % len(self.color_palette)
            assignments[iso] = color_idx
        return assignments

    def validate(self, artifacts: dict[str, Any]) -> None:
        cells = artifacts["cells"]
        if not cells.empty and cells["h3"].duplicated().any():
            raise ValueError("Country mask has duplicate h3 cells")
        if cells.empty:
            return
        cell_set = {str(value) for value in cells["h3"].astype(str).tolist()}
        for cell in sorted(cell_set, key=lambda value: h3.get_resolution(value)):
            resolution = h3.get_resolution(cell)
            for ancestor_resolution in range(resolution - 1, -1, -1):
                if h3.cell_to_parent(cell, ancestor_resolution) in cell_set:
                    raise ValueError("Country mask has ancestor/descendant overlap")
