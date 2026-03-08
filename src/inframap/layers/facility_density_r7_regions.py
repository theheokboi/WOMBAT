from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import h3
import pandas as pd


@dataclass
class FacilityDensityR7RegionsLayer:
    version: str

    def spec(self) -> dict[str, Any]:
        return {
            "name": "facility_density_r7_regions",
            "version": self.version,
            "distance_semantics": "h3_grid_connected_components",
            "params": ["source_layer", "target_resolution"],
        }

    def compute(
        self, canonical_store: dict[str, pd.DataFrame], layer_store: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        del canonical_store

        source_layer = str(params.get("source_layer", "facility_density_adaptive"))
        target_resolution = int(params.get("target_resolution", 7))
        if target_resolution != 7:
            raise ValueError("facility_density_r7_regions currently only supports target_resolution=7")

        source_artifacts = layer_store.get(source_layer)
        if not isinstance(source_artifacts, dict):
            raise ValueError(f"facility_density_r7_regions requires source layer artifacts: {source_layer}")
        source_cells = source_artifacts.get("cells")
        if not isinstance(source_cells, pd.DataFrame):
            raise ValueError(f"facility_density_r7_regions source layer is missing cells dataframe: {source_layer}")

        source_metadata = source_artifacts.get("metadata", {})
        source_version = (
            str(source_metadata.get("layer_version"))
            if isinstance(source_metadata, dict) and source_metadata.get("layer_version") is not None
            else None
        )

        required = {"h3", "resolution"}
        missing = sorted(required.difference(source_cells.columns))
        if missing:
            raise ValueError(
                "facility_density_r7_regions source layer cells missing required columns: "
                + ", ".join(missing)
            )

        r7_cells = source_cells[source_cells["resolution"].astype(int) == target_resolution].copy()
        if r7_cells.empty:
            empty = pd.DataFrame(
                columns=[
                    "h3",
                    "resolution",
                    "layer_value",
                    "cluster_id",
                    "cluster_anchor_h3",
                    "cluster_cell_count",
                    "region_h3",
                    "region_lat",
                    "region_lon",
                    "source_layer",
                    "source_layer_version",
                    "layer_id",
                    "asof_date",
                ]
            )
            metadata = self._metadata(
                source_layer=source_layer,
                source_version=source_version,
                target_resolution=target_resolution,
                cluster_count=0,
                emitted_cell_count=0,
            )
            return metadata, empty

        cell_set = {str(cell) for cell in r7_cells["h3"].astype(str).tolist()}
        cluster_rows: list[dict[str, Any]] = []
        assigned: set[str] = set()
        clusters: list[list[str]] = []

        for seed in sorted(cell_set):
            if seed in assigned:
                continue
            cluster = self._connected_component(cell_set=cell_set, seed=seed)
            assigned.update(cluster)
            clusters.append(sorted(cluster))

        cluster_anchor_to_cells = {cluster[0]: cluster for cluster in sorted(clusters, key=lambda cells: cells[0])}
        source_lookup = r7_cells.set_index(r7_cells["h3"].astype(str))
        for cluster_anchor, cluster in cluster_anchor_to_cells.items():
            cluster_id = f"r7c:{cluster_anchor}"
            cluster_size = len(cluster)
            region_h3, region_lat, region_lon = self._representative_region_point(cluster)
            for cell in cluster:
                row = source_lookup.loc[cell]
                cluster_rows.append(
                    {
                        "h3": cell,
                        "resolution": target_resolution,
                        "layer_value": int(row["layer_value"]) if "layer_value" in row and pd.notna(row["layer_value"]) else 0,
                        "cluster_id": cluster_id,
                        "cluster_anchor_h3": cluster_anchor,
                        "cluster_cell_count": cluster_size,
                        "region_h3": region_h3,
                        "region_lat": region_lat,
                        "region_lon": region_lon,
                        "source_layer": source_layer,
                        "source_layer_version": source_version,
                        "layer_id": f"facility_density_r7_regions:{self.version}",
                        "asof_date": row["asof_date"] if "asof_date" in row and pd.notna(row["asof_date"]) else None,
                    }
                )

        cells = pd.DataFrame(cluster_rows).sort_values(by=["cluster_anchor_h3", "h3"]).reset_index(drop=True)
        metadata = self._metadata(
            source_layer=source_layer,
            source_version=source_version,
            target_resolution=target_resolution,
            cluster_count=len(cluster_anchor_to_cells),
            emitted_cell_count=len(cells),
        )
        return metadata, cells

    def _connected_component(self, cell_set: set[str], seed: str) -> set[str]:
        queue = deque([seed])
        seen: set[str] = set()
        while queue:
            current = queue.popleft()
            if current in seen or current not in cell_set:
                continue
            seen.add(current)
            for neighbor in sorted(str(value) for value in h3.grid_disk(current, 1)):
                if neighbor != current and neighbor in cell_set and neighbor not in seen:
                    queue.append(neighbor)
        return seen

    def _representative_region_point(self, cluster: list[str]) -> tuple[str, float, float]:
        centers = {cell: h3.cell_to_latlng(cell) for cell in cluster}
        centroid_lat = sum(lat for lat, _ in centers.values()) / len(centers)
        centroid_lon = sum(lon for _, lon in centers.values()) / len(centers)
        region_h3 = min(
            cluster,
            key=lambda cell: (
                (centers[cell][0] - centroid_lat) ** 2 + (centers[cell][1] - centroid_lon) ** 2,
                cell,
            ),
        )
        region_lat, region_lon = centers[region_h3]
        return region_h3, float(region_lat), float(region_lon)

    def _metadata(
        self,
        *,
        source_layer: str,
        source_version: str | None,
        target_resolution: int,
        cluster_count: int,
        emitted_cell_count: int,
    ) -> dict[str, Any]:
        return {
            "layer_name": "facility_density_r7_regions",
            "layer_version": self.version,
            "params": {
                "source_layer": source_layer,
                "target_resolution": target_resolution,
            },
            "source_layer": source_layer,
            "source_layer_version": source_version,
            "distance_semantics": "h3_grid_connected_components",
            "cluster_count": cluster_count,
            "emitted_cell_count": emitted_cell_count,
        }

    def validate(self, artifacts: dict[str, Any]) -> None:
        cells = artifacts["cells"]
        metadata = artifacts.get("metadata", {})
        if cells.empty:
            return

        if cells["h3"].duplicated().any():
            raise ValueError("facility_density_r7_regions has duplicate h3 cells")

        target_resolution = int(metadata.get("params", {}).get("target_resolution", 7))
        if target_resolution != 7:
            raise ValueError("facility_density_r7_regions metadata must declare target_resolution=7")

        encoded_resolution = cells["h3"].astype(str).map(h3.get_resolution)
        if not encoded_resolution.equals(cells["resolution"].astype(int)):
            raise ValueError("facility_density_r7_regions has resolution column mismatched with h3 cell resolution")
        if (cells["resolution"].astype(int) != target_resolution).any():
            raise ValueError("facility_density_r7_regions emitted non-r7 cells")

        for cluster_id, cluster_cells in cells.groupby("cluster_id", sort=True):
            cluster_h3 = sorted(cluster_cells["h3"].astype(str).tolist())
            cluster_anchor = str(cluster_cells["cluster_anchor_h3"].iloc[0])
            if cluster_anchor != cluster_h3[0]:
                raise ValueError("facility_density_r7_regions cluster anchor must be the lexicographically smallest cell")
            if str(cluster_id) != f"r7c:{cluster_anchor}":
                raise ValueError("facility_density_r7_regions cluster_id must be derived from cluster anchor")
            declared_size = int(cluster_cells["cluster_cell_count"].iloc[0])
            if declared_size != len(cluster_h3):
                raise ValueError("facility_density_r7_regions cluster_cell_count mismatch")

            cluster_set = set(cluster_h3)
            component = self._connected_component(cell_set=cluster_set, seed=cluster_anchor)
            if component != cluster_set:
                raise ValueError("facility_density_r7_regions cluster must be a connected component")

            if {"region_h3", "region_lat", "region_lon"}.difference(cluster_cells.columns):
                raise ValueError("facility_density_r7_regions missing representative region coordinate fields")
            if cluster_cells["region_h3"].astype(str).nunique() != 1:
                raise ValueError("facility_density_r7_regions region_h3 must be identical within a cluster")
            if cluster_cells["region_lat"].astype(float).nunique() != 1:
                raise ValueError("facility_density_r7_regions region_lat must be identical within a cluster")
            if cluster_cells["region_lon"].astype(float).nunique() != 1:
                raise ValueError("facility_density_r7_regions region_lon must be identical within a cluster")

            region_h3 = str(cluster_cells["region_h3"].iloc[0])
            if region_h3 not in cluster_set:
                raise ValueError("facility_density_r7_regions region_h3 must belong to the cluster")
            region_lat = float(cluster_cells["region_lat"].iloc[0])
            region_lon = float(cluster_cells["region_lon"].iloc[0])
            expected_lat, expected_lon = h3.cell_to_latlng(region_h3)
            if abs(region_lat - float(expected_lat)) > 1e-12 or abs(region_lon - float(expected_lon)) > 1e-12:
                raise ValueError("facility_density_r7_regions region coordinates must match region_h3 center")
