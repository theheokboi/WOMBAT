import h3
import pandas as pd
import pytest

from inframap.layers.facility_density_r7_regions import FacilityDensityR7RegionsLayer


def _source_artifacts(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {
        "facility_density_adaptive": {
            "metadata": {
                "layer_name": "facility_density_adaptive",
                "layer_version": "v3",
            },
            "cells": pd.DataFrame(rows),
        }
    }


def _representative_region_h3(cluster: list[str]) -> str:
    centers = {cell: h3.cell_to_latlng(cell) for cell in cluster}
    centroid_lat = sum(lat for lat, _ in centers.values()) / len(centers)
    centroid_lon = sum(lon for _, lon in centers.values()) / len(centers)
    return min(
        cluster,
        key=lambda cell: (
            (centers[cell][0] - centroid_lat) ** 2 + (centers[cell][1] - centroid_lon) ** 2,
            cell,
        ),
    )


def test_r7_regions_filters_to_r7_and_assigns_connected_cluster_ids() -> None:
    base = str(h3.latlng_to_cell(25.0330, 121.5654, 7))
    adjacent = sorted(str(cell) for cell in h3.grid_disk(base, 1) if str(cell) != base)[0]
    remote = str(h3.latlng_to_cell(35.6764, 139.6500, 7))
    coarse = str(h3.cell_to_parent(base, 6))
    layer = FacilityDensityR7RegionsLayer(version="v1")

    metadata, cells = layer.compute(
        canonical_store={},
        layer_store=_source_artifacts(
            [
                {"h3": base, "resolution": 7, "layer_value": 2, "asof_date": "2026-03-08"},
                {"h3": adjacent, "resolution": 7, "layer_value": 0, "asof_date": "2026-03-08"},
                {"h3": remote, "resolution": 7, "layer_value": 5, "asof_date": "2026-03-08"},
                {"h3": coarse, "resolution": 6, "layer_value": 0, "asof_date": "2026-03-08"},
            ]
        ),
        params={"source_layer": "facility_density_adaptive", "target_resolution": 7},
    )

    assert metadata["layer_name"] == "facility_density_r7_regions"
    assert metadata["layer_version"] == "v1"
    assert metadata["source_layer"] == "facility_density_adaptive"
    assert metadata["source_layer_version"] == "v3"
    assert metadata["cluster_count"] == 2
    assert metadata["emitted_cell_count"] == 3
    assert set(cells["h3"]) == {base, adjacent, remote}
    assert set(cells["resolution"].astype(int)) == {7}

    shared_cluster = set(cells[cells["h3"].isin([base, adjacent])]["cluster_id"].astype(str).tolist())
    assert len(shared_cluster) == 1
    assert next(iter(shared_cluster)) == f"r7c:{min(base, adjacent)}"
    shared_region_h3 = _representative_region_h3([base, adjacent])
    shared_rows = cells[cells["h3"].isin([base, adjacent])]
    assert set(shared_rows["region_h3"].astype(str)) == {shared_region_h3}
    expected_shared_lat, expected_shared_lon = h3.cell_to_latlng(shared_region_h3)
    assert set(shared_rows["region_lat"].astype(float)) == {float(expected_shared_lat)}
    assert set(shared_rows["region_lon"].astype(float)) == {float(expected_shared_lon)}
    remote_row = cells[cells["h3"] == remote].iloc[0]
    assert str(remote_row["cluster_id"]) == f"r7c:{remote}"
    assert int(remote_row["cluster_cell_count"]) == 1
    assert str(remote_row["region_h3"]) == remote
    remote_lat, remote_lon = h3.cell_to_latlng(remote)
    assert float(remote_row["region_lat"]) == float(remote_lat)
    assert float(remote_row["region_lon"]) == float(remote_lon)


def test_r7_regions_returns_empty_when_source_has_no_r7_cells() -> None:
    coarse = str(h3.latlng_to_cell(25.0330, 121.5654, 6))
    layer = FacilityDensityR7RegionsLayer(version="v1")

    metadata, cells = layer.compute(
        canonical_store={},
        layer_store=_source_artifacts([{"h3": coarse, "resolution": 6, "layer_value": 0, "asof_date": "2026-03-08"}]),
        params={"source_layer": "facility_density_adaptive", "target_resolution": 7},
    )

    assert cells.empty
    assert metadata["cluster_count"] == 0
    assert metadata["emitted_cell_count"] == 0


def test_r7_regions_requires_adaptive_source_layer() -> None:
    layer = FacilityDensityR7RegionsLayer(version="v1")

    with pytest.raises(ValueError, match="requires source layer artifacts"):
        layer.compute(
            canonical_store={},
            layer_store={},
            params={"source_layer": "facility_density_adaptive", "target_resolution": 7},
        )


def test_r7_regions_validate_rejects_disconnected_cluster() -> None:
    first = str(h3.latlng_to_cell(25.0330, 121.5654, 7))
    second = str(h3.latlng_to_cell(35.6764, 139.6500, 7))
    anchor = min(first, second)
    layer = FacilityDensityR7RegionsLayer(version="v1")

    with pytest.raises(ValueError, match="connected component"):
        layer.validate(
            {
                "metadata": {
                    "layer_name": "facility_density_r7_regions",
                    "layer_version": "v1",
                    "params": {"target_resolution": 7},
                },
                "cells": pd.DataFrame(
                    [
                        {
                            "h3": first,
                            "resolution": 7,
                            "layer_value": 1,
                            "cluster_id": f"r7c:{anchor}",
                            "cluster_anchor_h3": anchor,
                            "cluster_cell_count": 2,
                            "region_h3": anchor,
                            "region_lat": h3.cell_to_latlng(anchor)[0],
                            "region_lon": h3.cell_to_latlng(anchor)[1],
                            "source_layer": "facility_density_adaptive",
                            "source_layer_version": "v3",
                            "layer_id": "facility_density_r7_regions:v1",
                            "asof_date": "2026-03-08",
                        },
                        {
                            "h3": second,
                            "resolution": 7,
                            "layer_value": 1,
                            "cluster_id": f"r7c:{anchor}",
                            "cluster_anchor_h3": anchor,
                            "cluster_cell_count": 2,
                            "region_h3": anchor,
                            "region_lat": h3.cell_to_latlng(anchor)[0],
                            "region_lon": h3.cell_to_latlng(anchor)[1],
                            "source_layer": "facility_density_adaptive",
                            "source_layer_version": "v3",
                            "layer_id": "facility_density_r7_regions:v1",
                            "asof_date": "2026-03-08",
                        },
                    ]
                ),
            }
        )
