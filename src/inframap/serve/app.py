from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import h3
import mapbox_vector_tile
import mercantile
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from inframap.config import SystemConfig, load_system_config


class DataStore:
    def __init__(self, runs_root: Path, published_root: Path):
        self.runs_root = runs_root
        self.published_root = published_root

    def latest_run_id(self) -> str:
        latest_file = self.published_root / "latest"
        if not latest_file.exists():
            raise HTTPException(status_code=404, detail="No published run")
        return latest_file.read_text(encoding="utf-8").strip()

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


def create_app(runs_root: Path, published_root: Path, system_config: SystemConfig | None = None) -> FastAPI:
    app = FastAPI(title="Infrastructure Map API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    store = DataStore(runs_root=runs_root, published_root=published_root)
    system = system_config or load_system_config(Path("configs/system.yaml"))

    @app.get("/v1/runs/latest")
    def get_latest_run() -> dict[str, Any]:
        run_id = store.latest_run_id()
        manifest_path = store.run_root(run_id) / "reports" / "run_manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return payload

    @app.get("/v1/layers")
    def list_layers() -> dict[str, Any]:
        run_id = store.latest_run_id()
        metadata = _load_layer_metadata(store.run_root(run_id))
        return {"run_id": run_id, "layers": metadata}

    @app.get("/v1/layers/{layer}/metadata")
    def get_layer_metadata(layer: str) -> dict[str, Any]:
        run_id = store.latest_run_id()
        candidates = [m for m in _load_layer_metadata(store.run_root(run_id)) if m.get("layer_name") == layer]
        if not candidates:
            raise HTTPException(status_code=404, detail=f"Layer not found: {layer}")
        return {"run_id": run_id, **candidates[-1]}

    @app.get("/v1/layers/{layer}/cells")
    def get_layer_cells(layer: str, limit: int = 200000) -> dict[str, Any]:
        run_id = store.latest_run_id()
        run_root = store.run_root(run_id)
        layer_root = run_root / "layers" / layer
        versions = sorted(layer_root.glob("*")) if layer_root.exists() else []
        if not versions:
            raise HTTPException(status_code=404, detail=f"Layer not found: {layer}")
        cells = pd.read_parquet(versions[-1] / "cells.parquet").head(limit)
        features = []
        for _, row in cells.iterrows():
            cell = str(row["h3"])
            props = {
                "h3": cell,
                "layer_name": layer,
                "layer_value": str(row.get("layer_value", "")),
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
    ) -> dict[str, Any]:
        run_id = store.latest_run_id()
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
        for layer_name in ["metro_density_core", "country_mask"]:
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
        try:
            run_id = store.latest_run_id()
        except HTTPException:
            pass
        return {"status": "ok", "run_id": run_id}

    @app.get("/v1/ui/config")
    def ui_config() -> dict[str, Any]:
        return {
            "center": system.ui.center,
            "zoom": system.ui.zoom,
            "drilldown_resolution": system.ui.drilldown_resolution,
            "zoom_to_h3_resolution": system.zoom_to_h3_resolution,
        }

    @app.get("/", include_in_schema=False)
    def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/", status_code=307)

    frontend_dir = Path("frontend")
    if frontend_dir.exists():
        app.mount("/ui", StaticFiles(directory=frontend_dir, html=True), name="ui")

    return app


app = create_app(
    runs_root=Path(load_system_config(Path("configs/system.yaml")).paths.runs_root),
    published_root=Path(load_system_config(Path("configs/system.yaml")).paths.published_root),
)
