from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class InputSourceConfig:
    path: str
    source_name: str


@dataclass(frozen=True)
class PathConfig:
    runs_root: str
    staging_root: str
    published_root: str


@dataclass(frozen=True)
class UIConfig:
    center: list[float]
    zoom: int
    drilldown_resolution: int


@dataclass(frozen=True)
class SystemConfig:
    config_version: int
    allowed_h3_resolutions: list[int]
    canonical_h3_resolutions: list[int]
    country_mask_resolution: int
    zoom_to_h3_resolution: dict[int, int]
    ui: UIConfig
    inputs: list[InputSourceConfig]
    paths: PathConfig


@dataclass(frozen=True)
class LayerConfig:
    name: str
    plugin: str
    version: str
    params: dict[str, Any]


@dataclass(frozen=True)
class LayersConfig:
    layers_version: int
    layers: list[LayerConfig]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_system_config(path: Path) -> SystemConfig:
    raw = _load_yaml(path)
    return SystemConfig(
        config_version=int(raw["config_version"]),
        allowed_h3_resolutions=[int(v) for v in raw["allowed_h3_resolutions"]],
        canonical_h3_resolutions=[int(v) for v in raw["canonical_h3_resolutions"]],
        country_mask_resolution=int(raw["country_mask_resolution"]),
        zoom_to_h3_resolution={int(k): int(v) for k, v in raw["zoom_to_h3_resolution"].items()},
        ui=UIConfig(
            center=[float(raw["ui"]["center"][0]), float(raw["ui"]["center"][1])],
            zoom=int(raw["ui"]["zoom"]),
            drilldown_resolution=int(raw["ui"]["drilldown_resolution"]),
        ),
        inputs=[
            InputSourceConfig(path=str(item["path"]), source_name=str(item["source_name"]))
            for item in raw["inputs"]
        ],
        paths=PathConfig(
            runs_root=str(raw["paths"]["runs_root"]),
            staging_root=str(raw["paths"]["staging_root"]),
            published_root=str(raw["paths"]["published_root"]),
        ),
    )


def load_layers_config(path: Path) -> LayersConfig:
    raw = _load_yaml(path)
    return LayersConfig(
        layers_version=int(raw["layers_version"]),
        layers=[
            LayerConfig(
                name=str(item["name"]),
                plugin=str(item["plugin"]),
                version=str(item["version"]),
                params=dict(item.get("params", {})),
            )
            for item in raw["layers"]
        ],
    )


def serialize_config(system: SystemConfig, layers: LayersConfig) -> bytes:
    # Deterministic config serialization for stable hashing.
    payload = {
        "system": {
            "config_version": system.config_version,
            "allowed_h3_resolutions": system.allowed_h3_resolutions,
            "canonical_h3_resolutions": system.canonical_h3_resolutions,
            "country_mask_resolution": system.country_mask_resolution,
            "zoom_to_h3_resolution": system.zoom_to_h3_resolution,
            "ui": {
                "center": system.ui.center,
                "zoom": system.ui.zoom,
                "drilldown_resolution": system.ui.drilldown_resolution,
            },
            "inputs": [
                {"path": entry.path, "source_name": entry.source_name}
                for entry in sorted(system.inputs, key=lambda x: (x.path, x.source_name))
            ],
            "paths": {
                "runs_root": system.paths.runs_root,
                "staging_root": system.paths.staging_root,
                "published_root": system.paths.published_root,
            },
        },
        "layers": {
            "layers_version": layers.layers_version,
            "layers": [
                {
                    "name": layer.name,
                    "plugin": layer.plugin,
                    "version": layer.version,
                    "params": layer.params,
                }
                for layer in sorted(layers.layers, key=lambda x: x.name)
            ],
        },
    }
    return yaml.safe_dump(payload, sort_keys=True).encode("utf-8")
