from __future__ import annotations

from importlib import import_module
from typing import Any

from inframap.config import LayersConfig
from inframap.layers.base import LayerPlugin


def _load_plugin(plugin_path: str, version: str) -> LayerPlugin:
    module_name, class_name = plugin_path.split(":", 1)
    module = import_module(module_name)
    klass: Any = getattr(module, class_name)
    return klass(version=version)


def build_layer_registry(layers_config: LayersConfig) -> dict[str, LayerPlugin]:
    registry: dict[str, LayerPlugin] = {}
    for layer in layers_config.layers:
        registry[layer.name] = _load_plugin(layer.plugin, layer.version)
    return registry
