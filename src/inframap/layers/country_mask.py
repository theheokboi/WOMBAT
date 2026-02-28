from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import h3
import pandas as pd
from shapely.geometry import shape


@dataclass
class CountryMaskLayer:
    version: str
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
            "distance_semantics": "centroid_in_polygon",
            "params": ["resolution", "membership_rule", "polygon_dataset", "exclude_iso_a2"],
        }

    def compute(
        self, canonical_store: dict[str, pd.DataFrame], layer_store: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        facilities = canonical_store["facilities"]
        resolution = int(params["resolution"])
        rule = str(params["membership_rule"])
        dataset = str(params["polygon_dataset"])
        exclude_iso = {str(code).upper() for code in params.get("exclude_iso_a2", [])}

        polygons = self._load_polygons(dataset, exclude_iso=exclude_iso)
        # Deterministic rule: first country in sorted ISO order claims each cell.
        cell_to_country: dict[str, tuple[str, str]] = {}
        for iso, name, polygon in polygons:
            candidate_cells = sorted(self._polygon_to_cells(polygon, resolution, rule))
            for cell in candidate_cells:
                if cell in cell_to_country:
                    continue
                cell_to_country[cell] = (iso, name)
        country_colors = self._build_country_colors(cell_to_country)

        rows: list[dict[str, Any]] = []
        max_asof = facilities["asof_date"].max() if "asof_date" in facilities.columns else None
        for cell in sorted(cell_to_country.keys()):
            iso, name = cell_to_country[cell]
            color_idx = country_colors[iso]
            rows.append(
                {
                    "h3": cell,
                    "resolution": resolution,
                    "layer_value": iso,
                    "country_name": name,
                    "country_color": color_idx,
                    "country_color_hex": self.color_palette[color_idx],
                    "layer_id": f"country_mask:{self.version}",
                    "asof_date": max_asof,
                }
            )

        cells = pd.DataFrame(rows).sort_values(by=["h3"]).reset_index(drop=True)
        metadata = {
            "layer_name": "country_mask",
            "layer_version": self.version,
            "params": {
                "resolution": resolution,
                "membership_rule": rule,
                "polygon_dataset": dataset,
                "exclude_iso_a2": sorted(exclude_iso),
            },
            "polygon_dataset_source": "Natural Earth admin-0 subset",
            "distance_semantics": "centroid_in_polygon",
            "country_color_palette": list(self.color_palette),
            "country_color_map": {iso: idx for iso, idx in sorted(country_colors.items())},
        }
        return metadata, cells

    def _polygon_to_cells(self, polygon: Any, resolution: int, rule: str) -> list[str]:
        if rule != "centroid_in_polygon":
            raise ValueError(f"Unsupported membership rule: {rule}")
        geojson = polygon.__geo_interface__
        return list(h3.geo_to_cells(geojson, resolution))

    def _load_polygons(self, path: str, exclude_iso: set[str]) -> list[tuple[str, str, Any]]:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        polygons = []
        for feature in data["features"]:
            iso = str(feature["properties"]["iso_a2"]).upper()
            if iso in exclude_iso:
                continue
            name = str(feature["properties"]["name"])
            geom = shape(feature["geometry"])
            polygons.append((iso, name, geom))
        polygons.sort(key=lambda x: x[0])
        return polygons

    def _build_country_colors(self, cell_to_country: dict[str, tuple[str, str]]) -> dict[str, int]:
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
