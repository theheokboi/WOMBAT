from pathlib import Path

from inframap.config import LayerConfig, LayersConfig, load_layers_config, load_system_config
from inframap.manifest import build_run_manifest, compute_code_hash, compute_inputs_hash


def test_load_system_and_layers_config() -> None:
    system = load_system_config(Path("configs/system.yaml"))
    layers = load_layers_config(Path("configs/layers.yaml"))
    assert system.config_version == 1
    assert len(system.inputs) >= 1
    assert layers.layers_version == 1
    assert {layer.name for layer in layers.layers} == {
        "metro_density_core",
        "country_mask",
        "facility_density_adaptive",
    }
    adaptive = next(layer for layer in layers.layers if layer.name == "facility_density_adaptive")
    assert adaptive.version == "v2"
    assert adaptive.params == {
        "base_resolution": 4,
        "empty_compact_min_resolution": 0,
        "facility_floor_resolution": 9,
        "facility_max_resolution": 13,
        "target_facilities_per_leaf": 1,
        "allow_domain_expansion": True,
        "allow_cross_border_compaction": True,
    }


def test_manifest_hashes_are_deterministic() -> None:
    system = load_system_config(Path("configs/system.yaml"))
    layers = load_layers_config(Path("configs/layers.yaml"))
    manifest_a = build_run_manifest(system, layers, code_dir=Path("src"))
    manifest_b = build_run_manifest(system, layers, code_dir=Path("src"))
    assert manifest_a.inputs_hash == manifest_b.inputs_hash
    assert manifest_a.config_hash == manifest_b.config_hash
    assert manifest_a.code_hash == manifest_b.code_hash
    assert manifest_a.run_id == manifest_b.run_id


def test_compute_code_hash_changes_when_source_changes(tmp_path: Path) -> None:
    code_dir = tmp_path / "src"
    code_dir.mkdir(parents=True, exist_ok=True)
    target = code_dir / "example.py"
    target.write_text("x = 1\n", encoding="utf-8")

    hash_a = compute_code_hash(code_dir)
    target.write_text("x = 2\n", encoding="utf-8")
    hash_b = compute_code_hash(code_dir)

    assert hash_a != hash_b


def test_inputs_hash_includes_layer_polygon_dataset(tmp_path: Path) -> None:
    system = load_system_config(Path("configs/system.yaml"))
    layers = load_layers_config(Path("configs/layers.yaml"))

    dataset = tmp_path / "country_subset.geojson"
    dataset.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")

    rewritten_layers = []
    for layer in layers.layers:
        params = dict(layer.params)
        if layer.name == "country_mask":
            params["polygon_dataset"] = str(dataset)
        rewritten_layers.append(
            LayerConfig(
                name=layer.name,
                plugin=layer.plugin,
                version=layer.version,
                params=params,
            )
        )
    local_layers = LayersConfig(layers_version=layers.layers_version, layers=rewritten_layers)

    hash_a = compute_inputs_hash(system, local_layers)
    dataset.write_text('{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"iso_a2":"US","name":"US"},"geometry":{"type":"Polygon","coordinates":[[[-1,0],[1,0],[1,1],[-1,1],[-1,0]]]}}]}', encoding="utf-8")
    hash_b = compute_inputs_hash(system, local_layers)

    assert hash_a != hash_b


def test_manifest_config_hash_changes_when_adaptive_params_change() -> None:
    system = load_system_config(Path("configs/system.yaml"))
    layers = load_layers_config(Path("configs/layers.yaml"))

    manifest_a = build_run_manifest(system, layers, code_dir=Path("src"))

    rewritten_layers = []
    for layer in layers.layers:
        params = dict(layer.params)
        if layer.name == "facility_density_adaptive":
            params["target_facilities_per_leaf"] = 2
        rewritten_layers.append(
            LayerConfig(
                name=layer.name,
                plugin=layer.plugin,
                version=layer.version,
                params=params,
            )
        )
    local_layers = LayersConfig(layers_version=layers.layers_version, layers=rewritten_layers)

    manifest_b = build_run_manifest(system, local_layers, code_dir=Path("src"))
    assert manifest_a.config_hash != manifest_b.config_hash
