from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from inframap.agent import runner as runner_module
from inframap.agent.runner import run_pipeline
from inframap.config import build_effective_config_report, load_layers_config, load_system_config
from inframap.manifest import RunManifest


def _system_with_tmp_paths(tmp_path: Path):
    system = load_system_config(Path("configs/system.yaml"))
    return system.__class__(
        config_version=system.config_version,
        allowed_h3_resolutions=system.allowed_h3_resolutions,
        canonical_h3_resolutions=system.canonical_h3_resolutions,
        country_mask_resolution=system.country_mask_resolution,
        zoom_to_h3_resolution=system.zoom_to_h3_resolution,
        ui=system.ui,
        inputs=list(system.inputs),
        paths=system.paths.__class__(
            runs_root=str(tmp_path / "runs"),
            staging_root=str(tmp_path / "staging"),
            published_root=str(tmp_path / "published"),
        ),
    )


def test_build_effective_config_report_records_sources_and_runtime_overrides() -> None:
    system = load_system_config(Path("configs/system.yaml"))
    layers = load_layers_config(Path("configs/layers.yaml"))

    report = build_effective_config_report(
        system,
        layers,
        system_config_path=Path("configs/system.yaml"),
        layers_config_path=Path("configs/layers.yaml"),
        runtime_overrides={
            "country_selection": {
                "source_env_var": "COUNTRIES",
                "raw_value": "TW,JP",
                "countries": ["TW", "JP"],
                "applied_to_layer": "country_mask",
            }
        },
    )

    assert report["config_sources"] == {
        "system_config_path": "configs/system.yaml",
        "layers_config_path": "configs/layers.yaml",
    }
    assert report["runtime_overrides"]["country_selection"]["countries"] == ["TW", "JP"]
    assert report["system"]["paths"]["runs_root"] == "data/runs"


def test_run_pipeline_persists_effective_config_report(tmp_path: Path, monkeypatch) -> None:
    system = _system_with_tmp_paths(tmp_path)
    layers = load_layers_config(Path("configs/layers.yaml"))
    effective_config = build_effective_config_report(
        system,
        layers,
        system_config_path=Path("configs/system.yaml"),
        layers_config_path=Path("configs/layers.yaml"),
        runtime_overrides={
            "country_selection": {
                "source_env_var": "COUNTRIES",
                "raw_value": "TW",
                "countries": ["TW"],
                "applied_to_layer": "country_mask",
            }
        },
    )

    facilities = pd.DataFrame([{"facility_id": "fac-1", "source_name": "TestSource"}])
    organizations = pd.DataFrame([{"organization_id": "org-1"}])

    def fake_ingest_and_normalize(*args, **kwargs):
        return facilities, organizations, 0

    def fake_write_canonical_outputs(canonical_dir: Path, facilities_df: pd.DataFrame, organizations_df: pd.DataFrame) -> None:
        facilities_df.to_parquet(canonical_dir / "facilities.parquet", index=False)
        organizations_df.to_parquet(canonical_dir / "organizations.parquet", index=False)

    class FakePlugin:
        def __init__(self, layer_name: str, version: str):
            self.layer_name = layer_name
            self.version = version

        def compute(self, canonical_store, layer_store, params):
            metadata = {
                "layer_name": self.layer_name,
                "layer_version": self.version,
            }
            cells = pd.DataFrame([{"h3": f"{self.layer_name}-cell", "resolution": 2, "layer_value": 1}])
            return metadata, cells

        def validate(self, artifacts) -> None:
            return None

    def fake_build_layer_registry(layers_config):
        return {layer.name: FakePlugin(layer.name, layer.version) for layer in layers_config.layers}

    monkeypatch.setattr(runner_module, "ingest_and_normalize", fake_ingest_and_normalize)
    monkeypatch.setattr(runner_module, "write_canonical_outputs", fake_write_canonical_outputs)
    monkeypatch.setattr(runner_module, "build_layer_registry", fake_build_layer_registry)
    monkeypatch.setattr(
        runner_module,
        "build_run_manifest",
        lambda system, layers, code_dir: RunManifest(
            run_id="run-test-effective-config",
            inputs_hash="inputs-hash",
            config_hash="config-hash",
            code_hash="code-hash",
        ),
    )

    run_id = run_pipeline(system, layers, effective_config=effective_config)

    report_path = tmp_path / "runs" / run_id / "reports" / "effective_config.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["config_sources"]["system_config_path"] == "configs/system.yaml"
    assert payload["runtime_overrides"]["country_selection"]["countries"] == ["TW"]
    assert payload["layers"]["layers"][1]["name"] == "country_mask"
