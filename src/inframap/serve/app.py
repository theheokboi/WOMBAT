from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import h3
import mapbox_vector_tile
import mercantile
import pandas as pd
import shapefile
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from inframap.config import SystemConfig, load_system_config
from inframap.agent.runtime_estimator import estimate_world_runtime


class DataStore:
    def __init__(self, runs_root: Path, published_root: Path, staging_root: Path | None = None):
        self.runs_root = runs_root
        self.published_root = published_root
        self.staging_root = staging_root

    def latest_pointer(self) -> dict[str, str]:
        for pointer_name in ("latest-dev", "latest"):
            pointer_path = self.published_root / pointer_name
            if not pointer_path.exists():
                continue
            run_id = pointer_path.read_text(encoding="utf-8").strip()
            if not run_id:
                continue
            lane = "dev" if pointer_name == "latest-dev" else "legacy"
            return {"pointer": pointer_name, "lane": lane, "run_id": run_id}
        raise HTTPException(status_code=404, detail="No published run (expected pointer latest-dev or latest)")

    def latest_run_id(self) -> str:
        return self.latest_pointer()["run_id"]

    def run_root(self, run_id: str | None = None) -> Path:
        rid = run_id or self.latest_run_id()
        root = self.runs_root / rid
        if not root.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {rid}")
        return root


def _load_layer_metadata(run_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for layer_dir in sorted((run_root / "layers").glob("*")):
        for version_dir in sorted(layer_dir.glob("*")):
            metadata_path = version_dir / "layer_metadata.json"
            if metadata_path.exists():
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
                items.append(payload)
    return items


def _latest_layer_metadata_for(run_root: Path, layer_name: str) -> dict[str, Any] | None:
    candidates = [m for m in _load_layer_metadata(run_root) if m.get("layer_name") == layer_name]
    if not candidates:
        return None
    return candidates[-1]


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _first_int(payload: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _adaptive_adjacency_health(adaptive_metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(adaptive_metadata, dict):
        return {"status": "unknown", "adjacency_checks": None, "adjacency_violations": None, "sample": []}

    top_level_checks = _first_int(
        adaptive_metadata,
        ("adjacency_checks", "neighbor_adjacency_checks", "smoothing_adjacency_checks"),
    )
    top_level_violations = _first_int(
        adaptive_metadata,
        (
            "violating_neighbor_pairs",
            "adjacency_violations",
            "neighbor_adjacency_violations",
            "smoothing_adjacency_violations",
        ),
    )
    top_level_max_delta = _first_int(
        adaptive_metadata,
        ("max_neighbor_delta_observed", "neighbor_max_delta_observed", "smoothing_max_delta_observed"),
    )

    counters = adaptive_metadata.get("adaptive_counters")
    if not isinstance(counters, dict):
        counters = adaptive_metadata.get("counters")
    if not isinstance(counters, dict):
        counters = {}

    checks = _first_int(counters, ("adjacency_checks", "neighbor_adjacency_checks", "smoothing_adjacency_checks"))
    violations = _first_int(
        counters,
        ("adjacency_violations", "neighbor_adjacency_violations", "smoothing_adjacency_violations"),
    )
    sample = counters.get("adjacency_violation_samples")
    if not isinstance(sample, list):
        sample = counters.get("neighbor_adjacency_violation_samples")
    if not isinstance(sample, list):
        sample = counters.get("smoothing_adjacency_violation_samples")
    if not isinstance(sample, list):
        sample = []
    sample = sample[:3]

    checks = checks if checks is not None else top_level_checks
    violations = violations if violations is not None else top_level_violations

    if checks is None and violations is None:
        status = "unknown"
    elif (violations or 0) > 0:
        status = "violations_detected"
    else:
        status = "ok"
    violation_rate = None
    if checks is not None and checks > 0 and violations is not None:
        violation_rate = violations / checks
    return {
        "status": status,
        "adjacency_checks": checks,
        "adjacency_violations": violations,
        "max_neighbor_delta_observed": top_level_max_delta,
        "violation_rate": violation_rate,
        "sample": sample,
    }


def _latest_calibration_report() -> tuple[str, dict[str, Any]] | None:
    calibration_root = Path("artifacts") / "calibration"
    if not calibration_root.exists():
        return None
    candidates = sorted(
        directory
        for directory in calibration_root.iterdir()
        if directory.is_dir() and (directory / "report.json").exists()
    )
    if not candidates:
        return None
    latest = candidates[-1]
    payload = json.loads((latest / "report.json").read_text(encoding="utf-8"))
    if "calibration_id" not in payload:
        payload = {"calibration_id": latest.name, **payload}
    return latest.name, payload


def _estimate_runtime_from_calibration(report: dict[str, Any]) -> dict[str, Any]:
    calibration_report = {
        "facilities": int(report.get("facility_count", report.get("facility_count_total", 0)) or 0),
        "domain_r4_cell_count": int(report.get("domain_r4_cell_count", 0) or 0),
        "adaptive_leaf_count": int(
            report.get("adaptive_leaf_count")
            or ((report.get("adaptive_counters") or {}).get("leaf_count_total", 0))
            or 0
        ),
        "smoothing_iterations": int(
            report.get("smoothing_iterations")
            or ((report.get("adaptive_counters") or {}).get("smoothing_iterations", 0))
            or 0
        ),
        "adjacency_checks": int(
            report.get("adjacency_checks")
            or ((report.get("invariant_counters") or {}).get("adjacency_checks", 0))
            or 0
        ),
        "runtime_seconds": float(
            report.get("runtime_seconds")
            or report.get("run_duration_seconds")
            or (report.get("stage_durations_seconds") or {}).get("total", 0)
            or 0.0
        ),
    }
    driver_snapshot = {
        "facilities": calibration_report["facilities"],
        "domain_r4_cell_count": calibration_report["domain_r4_cell_count"],
        "adaptive_leaf_count": calibration_report["adaptive_leaf_count"],
        "smoothing_iterations": calibration_report["smoothing_iterations"],
        "adjacency_checks": calibration_report["adjacency_checks"],
    }
    return estimate_world_runtime(
        calibration_reports=[calibration_report],
        world_driver_snapshot=driver_snapshot,
    )


def _tile_bbox(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    bounds = mercantile.bounds(x, y, z)
    return bounds.west, bounds.south, bounds.east, bounds.north


def _point_in_bbox(lon: float, lat: float, bbox: tuple[float, float, float, float]) -> bool:
    minx, miny, maxx, maxy = bbox
    return minx <= lon <= maxx and miny <= lat <= maxy


def _cell_polygon_coords(cell: str) -> list[list[float]]:
    ring: list[list[float]] = []
    prev_lon: float | None = None
    for lat, lon in h3.cell_to_boundary(cell):
        adj_lon = float(lon)
        if prev_lon is not None:
            while adj_lon - prev_lon > 180:
                adj_lon -= 360
            while adj_lon - prev_lon < -180:
                adj_lon += 360
        ring.append([adj_lon, float(lat)])
        prev_lon = adj_lon
    ring.append(ring[0])
    return ring


def _available_osm_countries(openstreetmap_root: Path) -> list[str]:
    if not openstreetmap_root.exists():
        return []
    countries: list[str] = []
    for path in sorted(openstreetmap_root.iterdir()):
        code = path.name.strip().upper()
        if not (path.is_dir() and len(code) == 2 and code.isalpha()):
            continue
        has_roads = (path / "gis_osm_roads_free_1.shp").exists()
        has_railways = (path / "gis_osm_railways_free_1.shp").exists()
        if has_roads or has_railways:
            countries.append(code)
    return countries


def _available_osm_graph_countries(openstreetmap_root: Path, graph_variant: Literal["raw", "collapsed"]) -> list[str]:
    if not openstreetmap_root.exists():
        return []
    countries: list[str] = []
    edges_filename = "major_roads_edges.geojson"
    if graph_variant == "collapsed":
        edges_filename = "major_roads_edges_collapsed.geojson"
    for path in sorted(openstreetmap_root.iterdir()):
        code = path.name.strip().upper()
        if not (path.is_dir() and len(code) == 2 and code.isalpha()):
            continue
        if (path / edges_filename).exists():
            countries.append(code)
    return countries


def _iter_shape_records(path: Path):
    if not path.exists():
        return
    try:
        reader = shapefile.Reader(str(path))
    except (OSError, shapefile.ShapefileException):
        return
    fields = [field[0] for field in reader.fields if field[0] != "DeletionFlag"]
    for item in reader.iterShapeRecords():
        properties = {field: item.record[index] for index, field in enumerate(fields)}
        yield properties, dict(item.shape.__geo_interface__)


def _iter_geojson_features(path: Path):
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    features = payload.get("features", [])
    if not isinstance(features, list):
        return
    for feature in features:
        if isinstance(feature, dict):
            yield feature


@lru_cache(maxsize=16)
def _osm_transport_features_for_country(country_code: str, country_root: Path) -> tuple[dict[str, Any], ...]:
    features: list[dict[str, Any]] = []

    roads_path = country_root / "gis_osm_roads_free_1.shp"
    for properties, geometry in _iter_shape_records(roads_path):
        fclass = str(properties.get("fclass", "")).strip().lower()
        if fclass not in {"motorway", "trunk"}:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "country_code": country_code,
                    "transport_class": fclass,
                },
            }
        )

    railways_path = country_root / "gis_osm_railways_free_1.shp"
    for properties, geometry in _iter_shape_records(railways_path):
        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "country_code": country_code,
                    "transport_class": "rail",
                },
            }
        )
    return tuple(features)


@lru_cache(maxsize=16)
def _osm_transport_graph_components_for_country(
    country_code: str,
    country_root: Path,
    graph_variant: Literal["raw", "collapsed"],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    edge_features: list[dict[str, Any]] = []
    node_features: list[dict[str, Any]] = []
    edges_filename = "major_roads_edges.geojson"
    nodes_filename = "major_roads_nodes.geojson"
    if graph_variant == "collapsed":
        edges_filename = "major_roads_edges_collapsed.geojson"
        nodes_filename = "major_roads_nodes_collapsed.geojson"

    edges_path = country_root / edges_filename
    for feature in _iter_geojson_features(edges_path):
        properties = feature.get("properties", {})
        if not isinstance(properties, dict):
            continue
        road_class = str(properties.get("road_class", "")).strip().lower()
        if not road_class:
            continue
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            continue
        merged_properties = dict(properties)
        merged_properties["country_code"] = country_code
        merged_properties["transport_class"] = road_class
        merged_properties["graph_feature_type"] = "edge"
        edge_features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": merged_properties,
            }
        )

    nodes_path = country_root / nodes_filename
    for feature in _iter_geojson_features(nodes_path):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            continue
        if str(geometry.get("type", "")).strip() != "Point":
            continue
        merged_properties = dict(properties)
        merged_properties["country_code"] = country_code
        merged_properties["transport_class"] = "graph_node"
        merged_properties["graph_feature_type"] = "node"
        node_features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": merged_properties,
            }
        )

    return tuple(edge_features), tuple(node_features)


def create_app(
    runs_root: Path,
    published_root: Path,
    system_config: SystemConfig | None = None,
    openstreetmap_root: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Infrastructure Map API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    store = DataStore(
        runs_root=runs_root,
        published_root=published_root,
        staging_root=Path(system_config.paths.staging_root) if system_config else None,
    )
    system = system_config or load_system_config(Path("configs/system.yaml"))
    runtime_expectations = {
        "make_run": {"typical_minutes": "4-10", "slow_path_minutes": "15-30"},
        "adaptive_compute": {"typical_minutes": "1-4", "slow_path_minutes": "8-20"},
        "integration_tests": {"typical_minutes": "1-3", "slow_path_minutes": "5-8"},
        "heartbeat": {
            "expected_interval_seconds": 10,
            "warn_after_no_output_seconds": 90,
            "escalate_after_no_output_seconds": 300,
            "stalled_after_no_output_seconds": 600,
        },
    }
    osm_root = openstreetmap_root or Path("data/openstreetmap")

    def build_run_status_payload(
        run_id: str,
        *,
        pointer: str | None,
        lane: str | None,
    ) -> dict[str, Any]:
        run_root = store.run_root(run_id)
        layer_metadata = _load_layer_metadata(run_root)
        adaptive = next((m for m in layer_metadata if m.get("layer_name") == "facility_density_adaptive"), None)
        metrics = _read_json_if_exists(run_root / "reports" / "metrics.json") or {}
        progress_path = run_root / "reports" / "progress.jsonl"
        latest_progress = None
        if progress_path.exists():
            lines = [line for line in progress_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                latest_progress = json.loads(lines[-1])
        return {
            "run_id": run_id,
            "pointer": pointer,
            "lane": lane,
            "runtime_expectations": runtime_expectations,
            "metrics": metrics,
            "adaptive_policy": {
                "layer_version": adaptive.get("layer_version") if adaptive else None,
                "policy_name": adaptive.get("policy_name") if adaptive else None,
                "params": adaptive.get("params") if adaptive else None,
                "adjacency_health": _adaptive_adjacency_health(adaptive),
            },
            "latest_progress_event": latest_progress,
        }

    @app.get("/v1/runs/latest")
    def get_latest_run() -> dict[str, Any]:
        pointer_info = store.latest_pointer()
        run_id = pointer_info["run_id"]
        manifest_path = store.run_root(run_id) / "reports" / "run_manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {**payload, "pointer": pointer_info["pointer"], "lane": pointer_info["lane"]}

    @app.get("/v1/runs/latest/status")
    def latest_run_status() -> dict[str, Any]:
        pointer_info = store.latest_pointer()
        return build_run_status_payload(
            pointer_info["run_id"],
            pointer=pointer_info["pointer"],
            lane=pointer_info["lane"],
        )

    @app.get("/v1/runs/{run_id}/status")
    def run_status(run_id: str) -> dict[str, Any]:
        pointer = None
        lane = None
        try:
            pointer_info = store.latest_pointer()
            if pointer_info["run_id"] == run_id:
                pointer = pointer_info["pointer"]
                lane = pointer_info["lane"]
        except HTTPException:
            pass
        return build_run_status_payload(run_id, pointer=pointer, lane=lane)

    @app.get("/v1/runs/catalog")
    def runs_catalog(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
        run_dirs = [path for path in store.runs_root.iterdir() if path.is_dir()] if store.runs_root.exists() else []
        run_dirs = sorted(run_dirs, key=lambda path: path.stat().st_mtime, reverse=True)
        items: list[dict[str, Any]] = []
        for run_dir in run_dirs[:limit]:
            run_id = run_dir.name
            country_meta = _latest_layer_metadata_for(run_dir, "country_mask") or {}
            adaptive_meta = _latest_layer_metadata_for(run_dir, "facility_density_adaptive") or {}
            country_params = country_meta.get("params", {}) if isinstance(country_meta, dict) else {}
            adaptive_params = adaptive_meta.get("params", {}) if isinstance(adaptive_meta, dict) else {}
            item = {
                "run_id": run_id,
                "country_mask_mode": country_params.get("mode"),
                "country_mask_resolution": country_params.get("resolution"),
                "country_mask_base_resolution": country_params.get("base_resolution"),
                "adaptive_base_resolution": adaptive_params.get("base_resolution"),
                "include_iso_a2": country_params.get("include_iso_a2", []),
                "exclude_iso_a2": country_params.get("exclude_iso_a2", []),
            }
            items.append(item)

        latest_run_id = None
        try:
            latest_run_id = store.latest_run_id()
        except HTTPException:
            latest_run_id = None
        return {"latest_run_id": latest_run_id, "runs": items}

    @app.get("/v1/runs/active/status")
    def active_run_status() -> dict[str, Any]:
        staging_root = store.staging_root or Path(system.paths.staging_root)
        active_path = staging_root / "active_run.json"
        if not active_path.exists():
            return {"active": False, "runtime_expectations": runtime_expectations}
        active = json.loads(active_path.read_text(encoding="utf-8"))
        run_id = active.get("run_id")
        progress_path = staging_root / str(run_id) / "reports" / "progress.jsonl"
        latest_progress = None
        if progress_path.exists():
            lines = [line for line in progress_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                latest_progress = json.loads(lines[-1])
        return {
            "active": True,
            "runtime_expectations": runtime_expectations,
            "active_status": active,
            "latest_progress_event": latest_progress,
            "published_note": "This status is from staging and not yet published.",
        }

    @app.get("/v1/calibration/latest")
    def calibration_latest() -> dict[str, Any]:
        latest = _latest_calibration_report()
        if latest is None:
            raise HTTPException(status_code=404, detail="No calibration report found")
        _, report = latest
        return report

    @app.get("/v1/calibration/estimates/gb")
    def calibration_gb_estimate() -> dict[str, Any]:
        latest = _latest_calibration_report()
        if latest is None:
            raise HTTPException(status_code=404, detail="No calibration report found")
        calibration_id, report = latest
        return {
            "calibration_id": calibration_id,
            "country": "GB",
            "estimate_basis": "latest_calibration_report",
            "estimate": _estimate_runtime_from_calibration(report=report),
        }

    @app.get("/v1/calibration/estimates/world")
    def calibration_world_estimate() -> dict[str, Any]:
        # Backward-compatible alias retained for existing clients.
        payload = calibration_gb_estimate()
        return {
            **payload,
            "deprecated": True,
            "deprecated_alias_for": "/v1/calibration/estimates/gb",
        }

    @app.get("/v1/layers")
    def list_layers(run_id: str | None = None) -> dict[str, Any]:
        run_id = run_id or store.latest_run_id()
        metadata = _load_layer_metadata(store.run_root(run_id))
        return {"run_id": run_id, "layers": metadata}

    @app.get("/v1/layers/{layer}/metadata")
    def get_layer_metadata(layer: str, run_id: str | None = None) -> dict[str, Any]:
        run_id = run_id or store.latest_run_id()
        candidates = [m for m in _load_layer_metadata(store.run_root(run_id)) if m.get("layer_name") == layer]
        if not candidates:
            raise HTTPException(status_code=404, detail=f"Layer not found: {layer}")
        return {"run_id": run_id, **candidates[-1]}

    @app.get("/v1/layers/{layer}/cells")
    def get_layer_cells(
        layer: str,
        limit: int = 200000,
        split_threshold: int | None = Query(default=None, ge=1),
        run_id: str | None = None,
    ) -> dict[str, Any]:
        run_id = run_id or store.latest_run_id()
        run_root = store.run_root(run_id)
        layer_root = run_root / "layers" / layer
        versions = sorted(layer_root.glob("*")) if layer_root.exists() else []
        if not versions:
            raise HTTPException(status_code=404, detail=f"Layer not found: {layer}")
        latest_layer_dir = versions[-1]
        if split_threshold is not None:
            if layer == "facility_density_adaptive":
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "split_threshold preview is deprecated for facility_density_adaptive; "
                        "query published cells without split_threshold"
                    ),
                )
            raise HTTPException(
                status_code=400,
                detail=f"split_threshold is not supported for layer: {layer}",
            )
        cells = pd.read_parquet(latest_layer_dir / "cells.parquet")
        cells = cells.head(limit)
        features = []
        for _, row in cells.iterrows():
            cell = str(row["h3"])
            props = {
                "h3": cell,
                "layer_name": layer,
                "layer_value": str(row.get("layer_value", "")),
                "resolution": int(row.get("resolution", 0)),
            }
            for optional_key in ["country_name", "country_color", "country_color_hex"]:
                if optional_key in row and pd.notna(row[optional_key]):
                    props[optional_key] = row[optional_key]
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [_cell_polygon_coords(cell)]},
                    "properties": props,
                }
            )
        return {"run_id": run_id, "type": "FeatureCollection", "features": features}

    @app.get("/v1/facilities")
    def get_facilities(
        source: str | None = None,
        org: str | None = None,
        h3_cell: str | None = Query(default=None, alias="h3"),
        limit: int = 10000,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        run_id = run_id or store.latest_run_id()
        facilities = pd.read_parquet(store.run_root(run_id) / "canonical" / "facilities.parquet")
        if source:
            facilities = facilities[facilities["source_name"] == source]
        if org:
            facilities = facilities[facilities["org_name"] == org]
        if h3_cell:
            drill_col = f"h3_r{system.ui.drilldown_resolution}"
            if drill_col in facilities.columns:
                facilities = facilities[facilities[drill_col] == h3_cell]

        facilities = facilities.head(limit)
        features = []
        for _, row in facilities.iterrows():
            props = row.to_dict()
            lat = float(props.pop("lat"))
            lon = float(props.pop("lon"))
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": props,
                }
            )

        return {"run_id": run_id, "type": "FeatureCollection", "features": features}

    @app.get("/v1/tiles/{z}/{x}/{y}.mvt")
    def get_tile(z: int, x: int, y: int) -> Response:
        run_id = store.latest_run_id()
        run_root = store.run_root(run_id)
        facilities = pd.read_parquet(run_root / "canonical" / "facilities.parquet")
        bbox = _tile_bbox(z, x, y)

        facility_features = []
        for i, (_, row) in enumerate(facilities.iterrows()):
            lon = float(row["lon"])
            lat = float(row["lat"])
            if not _point_in_bbox(lon, lat, bbox):
                continue
            facility_features.append(
                {
                    "id": i,
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "facility_id": row["facility_id"],
                        "org_name": row["org_name"],
                        "source_name": row["source_name"],
                        "h3": row.get(f"h3_r{system.ui.drilldown_resolution}", ""),
                        "layer_name": "facilities",
                    },
                }
            )

        h3_features = []
        for layer_name in ["metro_density_core", "country_mask", "facility_density_adaptive"]:
            layer_dirs = sorted((run_root / "layers" / layer_name).glob("*"))
            if not layer_dirs:
                continue
            cells = pd.read_parquet(layer_dirs[-1] / "cells.parquet")
            for i, (_, row) in enumerate(cells.iterrows()):
                cell = str(row["h3"])
                lat, lon = h3.cell_to_latlng(cell)
                if not _point_in_bbox(lon, lat, bbox):
                    continue
                h3_features.append(
                    {
                        "id": f"{layer_name}-{i}",
                        "geometry": {"type": "Polygon", "coordinates": [_cell_polygon_coords(cell)]},
                        "properties": {
                            "h3": cell,
                            "layer_name": layer_name,
                            "layer_value": str(row.get("layer_value", "")),
                            "resolution": int(row.get("resolution", 0)),
                        },
                    }
                )

        tile = mapbox_vector_tile.encode(
            [
                {"name": "facility_points", "features": facility_features},
                {"name": "h3_cells", "features": h3_features},
            ],
            default_options={"quantize_bounds": bbox, "extents": 4096},
        )
        return Response(content=tile, media_type="application/vnd.mapbox-vector-tile")

    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        run_id = None
        pointer = None
        lane = None
        try:
            pointer_info = store.latest_pointer()
            run_id = pointer_info["run_id"]
            pointer = pointer_info["pointer"]
            lane = pointer_info["lane"]
        except HTTPException:
            pass
        return {"status": "ok", "run_id": run_id, "pointer": pointer, "lane": lane}

    @app.get("/v1/ui/config")
    def ui_config() -> dict[str, Any]:
        return {
            "center": system.ui.center,
            "zoom": system.ui.zoom,
            "drilldown_resolution": system.ui.drilldown_resolution,
            "zoom_to_h3_resolution": system.zoom_to_h3_resolution,
        }

    @app.get("/v1/osm/transport")
    def osm_transport_overlay(
        country: str | None = Query(default=None, min_length=2, max_length=2),
        limit: int = Query(default=200000, ge=1, le=500000),
        source: Literal["shapefile", "graph"] = Query(default="shapefile"),
        graph_variant: Literal["raw", "collapsed"] = Query(default="raw"),
        include_nodes: bool = Query(default=False),
    ) -> dict[str, Any]:
        if source == "graph":
            available_countries = _available_osm_graph_countries(osm_root, graph_variant)
        else:
            available_countries = _available_osm_countries(osm_root)
        features: list[dict[str, Any]] = []
        target_countries = available_countries
        if country:
            country_code = country.strip().upper()
            if country_code not in available_countries:
                raise HTTPException(status_code=404, detail=f"OSM transport data unavailable for country: {country_code}")
            target_countries = [country_code]

        for country_code in target_countries:
            country_root = osm_root / country_code
            if source == "graph":
                edge_features, node_features = _osm_transport_graph_components_for_country(
                    country_code,
                    country_root,
                    graph_variant,
                )
                features.extend(edge_features)
                if include_nodes:
                    features.extend(node_features)
            else:
                features.extend(_osm_transport_features_for_country(country_code, country_root))
            if len(features) >= limit:
                break

        selected_features = features[:limit]
        class_source = selected_features
        if source == "graph":
            class_source = [
                feature
                for feature in selected_features
                if feature.get("properties", {}).get("graph_feature_type") != "node"
            ]
        classes = sorted(
            {
                str(feature.get("properties", {}).get("transport_class", "")).strip()
                for feature in class_source
                if feature.get("properties")
            }
        )
        return {
            "type": "FeatureCollection",
            "source": source,
            "run_agnostic": True,
            "country": country.strip().upper() if country else None,
            "available_countries": available_countries,
            "classes": classes,
            "feature_count": len(selected_features),
            "features": selected_features,
        }

    @app.get("/", include_in_schema=False)
    def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/", status_code=307)

    @app.get("/ar", include_in_schema=False)
    @app.get("/ar/", include_in_schema=False)
    def argentina_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/?country=AR", status_code=307)

    @app.get("/demo", include_in_schema=False)
    @app.get("/demo/", include_in_schema=False)
    def demo_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/?country=DEMO", status_code=307)

    @app.get("/{country_code}", include_in_schema=False)
    @app.get("/{country_code}/", include_in_schema=False)
    def country_redirect(country_code: str) -> RedirectResponse:
        code = country_code.strip().upper()
        if len(code) != 2 or not code.isalpha() or code in {"UI", "V1"}:
            raise HTTPException(status_code=404, detail="Not Found")
        return RedirectResponse(url=f"/ui/?country={code}", status_code=307)

    frontend_dir = Path("frontend")
    if frontend_dir.exists():
        app.mount("/ui", StaticFiles(directory=frontend_dir, html=True), name="ui")

    return app


_DEFAULT_SYSTEM = load_system_config(Path("configs/system.yaml"))
app = create_app(
    runs_root=Path(_DEFAULT_SYSTEM.paths.runs_root),
    published_root=Path(_DEFAULT_SYSTEM.paths.published_root),
    system_config=_DEFAULT_SYSTEM,
)
