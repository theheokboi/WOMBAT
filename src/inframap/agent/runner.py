from __future__ import annotations

import json
from pathlib import Path
from shutil import copy2
from shutil import rmtree
from time import perf_counter

import pandas as pd

from inframap.config import LayersConfig, SystemConfig
from inframap.ingest.pipeline import ingest_and_normalize, write_canonical_outputs
from inframap.layers.registry import build_layer_registry
from inframap.manifest import build_run_manifest, manifest_to_dict
from inframap.publish.pipeline import atomic_publish
from inframap.validation.invariants import run_invariants


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def run_pipeline(system: SystemConfig, layers: LayersConfig) -> str:
    started = perf_counter()
    manifest = build_run_manifest(system, layers, code_dir=Path("src"))

    staging_root = Path(system.paths.staging_root)
    run_stage = staging_root / manifest.run_id
    runs_root = Path(system.paths.runs_root)
    published_run = runs_root / manifest.run_id
    if published_run.exists():
        return manifest.run_id
    if run_stage.exists():
        rmtree(run_stage)

    inputs_dir = run_stage / "inputs"
    canonical_dir = run_stage / "canonical"
    layers_dir = run_stage / "layers"
    reports_dir = run_stage / "reports"
    for directory in [inputs_dir, canonical_dir, layers_dir, reports_dir]:
        _mkdir(directory)

    source_inputs: list[tuple[Path, str]] = []
    for source in sorted(system.inputs, key=lambda x: x.path):
        src_path = Path(source.path)
        copied_path = inputs_dir / src_path.name
        copy2(src_path, copied_path)
        source_inputs.append((copied_path, source.source_name))

    facilities, organizations, invalid_count = ingest_and_normalize(
        source_inputs,
        canonical_h3_resolutions=sorted(
            set(system.canonical_h3_resolutions + [system.country_mask_resolution])
        ),
    )
    write_canonical_outputs(canonical_dir, facilities, organizations)

    registry = build_layer_registry(layers)
    layer_artifacts: dict[str, dict[str, object]] = {}
    layer_duration_seconds: dict[str, float] = {}
    for layer_cfg in layers.layers:
        plugin = registry[layer_cfg.name]
        layer_started = perf_counter()
        metadata, cells = plugin.compute(
            canonical_store={"facilities": facilities, "organizations": organizations},
            layer_store=layer_artifacts,
            params=layer_cfg.params,
        )
        plugin.validate({"metadata": metadata, "cells": cells})

        layer_path = layers_dir / layer_cfg.name / layer_cfg.version
        _mkdir(layer_path)
        cells.sort_values(by=["h3"]).reset_index(drop=True).to_parquet(layer_path / "cells.parquet", index=False)
        _write_json(layer_path / "layer_metadata.json", metadata)
        layer_artifacts[layer_cfg.name] = {"metadata": metadata, "cells": cells}
        layer_duration_seconds[layer_cfg.name] = perf_counter() - layer_started

    run_invariants(
        facilities=facilities,
        layer_artifacts=layer_artifacts,
        required_h3_resolutions=system.canonical_h3_resolutions,
    )

    _write_json(reports_dir / "run_manifest.json", manifest_to_dict(manifest))
    metrics = {
        "run_success": 1,
        "run_duration_seconds": perf_counter() - started,
        "facility_count_total": int(len(facilities)),
        "facility_count_by_source": {
            key: int(value)
            for key, value in facilities.groupby("source_name")["facility_id"].count().to_dict().items()
        },
        "invalid_record_count": int(invalid_count),
        "layer_compute_duration_seconds": layer_duration_seconds,
        "publish_timestamp": manifest.run_id,
        "run_id": manifest.run_id,
    }
    _write_json(reports_dir / "metrics.json", metrics)

    atomic_publish(
        run_id=manifest.run_id,
        staging_root=staging_root,
        runs_root=runs_root,
        published_root=Path(system.paths.published_root),
        blocking_checks_passed=True,
    )
    return manifest.run_id
