from __future__ import annotations

import json
from datetime import datetime, timezone
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


def _append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def run_pipeline(
    system: SystemConfig,
    layers: LayersConfig,
    *,
    latest_pointer: str = "latest-dev",
    compatibility_alias: str | None = "latest",
    enforce_blocking_checks: bool = False,
    run_invariants_check: bool = False,
) -> str:
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
    progress_path = reports_dir / "progress.jsonl"
    active_status_path = staging_root / "active_run.json"
    expected_runtime_seconds = {
        "make_run_typical": {"min": 240, "max": 600},
        "make_run_slow_path": {"min": 900, "max": 1800},
        "adaptive_compute_typical": {"min": 60, "max": 240},
        "adaptive_compute_slow_path": {"min": 480, "max": 1200},
        "integration_test_typical": {"min": 60, "max": 180},
        "integration_test_slow_path": {"min": 300, "max": 480},
    }
    stage_started_at: dict[str, float] = {}
    stage_duration_seconds: dict[str, float] = {}

    def heartbeat(stage: str, status: str, note: str = "", layer_name: str | None = None) -> None:
        now = perf_counter()
        payload = {
            "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "run_id": manifest.run_id,
            "stage": stage,
            "status": status,
            "elapsed_s": round(now - started, 6),
        }
        if note:
            payload["note"] = note
        if layer_name:
            payload["layer_name"] = layer_name
        _append_jsonl(progress_path, payload)
        active_payload = {
            "run_id": manifest.run_id,
            "status": status,
            "stage": stage,
            "elapsed_s": payload["elapsed_s"],
            "ts_utc": payload["ts_utc"],
            "expected_runtime_seconds": expected_runtime_seconds,
        }
        if note:
            active_payload["note"] = note
        if layer_name:
            active_payload["layer_name"] = layer_name
        active_status_path.write_text(json.dumps(active_payload, sort_keys=True, indent=2), encoding="utf-8")

    def mark_stage_start(stage_name: str) -> None:
        stage_started_at[stage_name] = perf_counter()
        heartbeat(stage_name, "in_progress")

    def mark_stage_finish(stage_name: str, note: str = "") -> None:
        started_at = stage_started_at.get(stage_name)
        if started_at is not None:
            stage_duration_seconds[stage_name] = perf_counter() - started_at
        heartbeat(stage_name, "complete", note=note)

    source_inputs: list[tuple[Path, str]] = []
    try:
        mark_stage_start("ingest")
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
        mark_stage_finish("ingest")

        mark_stage_start("canonicalize")
        write_canonical_outputs(canonical_dir, facilities, organizations)
        mark_stage_finish("canonicalize")

        registry = build_layer_registry(layers)
        layer_artifacts: dict[str, dict[str, object]] = {}
        layer_duration_seconds: dict[str, float] = {}
        for layer_cfg in layers.layers:
            stage_name = f"layer:{layer_cfg.name}"
            mark_stage_start(stage_name)
            plugin = registry[layer_cfg.name]
            layer_started = perf_counter()
            layer_params = dict(layer_cfg.params)

            def layer_progress(note: str, *, _stage: str = stage_name, _layer: str = layer_cfg.name) -> None:
                heartbeat(_stage, "in_progress", note=note, layer_name=_layer)

            layer_params["_progress_cb"] = layer_progress
            metadata, cells = plugin.compute(
                canonical_store={"facilities": facilities, "organizations": organizations},
                layer_store=layer_artifacts,
                params=layer_params,
            )
            plugin.validate({"metadata": metadata, "cells": cells})

            layer_path = layers_dir / layer_cfg.name / layer_cfg.version
            _mkdir(layer_path)
            cells.sort_values(by=["h3"]).reset_index(drop=True).to_parquet(layer_path / "cells.parquet", index=False)
            _write_json(layer_path / "layer_metadata.json", metadata)
            layer_artifacts[layer_cfg.name] = {"metadata": metadata, "cells": cells}
            layer_duration_seconds[layer_cfg.name] = perf_counter() - layer_started
            mark_stage_finish(stage_name, note=f"cells={len(cells)}")

        if run_invariants_check:
            mark_stage_start("invariants")
            run_invariants(
                facilities=facilities,
                layer_artifacts=layer_artifacts,
                required_h3_resolutions=system.canonical_h3_resolutions,
            )
            mark_stage_finish("invariants")
        else:
            heartbeat("invariants", "skipped", note="dev_mode")

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
            "stage_duration_seconds": {k: round(v, 6) for k, v in sorted(stage_duration_seconds.items())},
            "expected_runtime_seconds": expected_runtime_seconds,
            "publish_timestamp": manifest.run_id,
            "run_id": manifest.run_id,
        }
        _write_json(reports_dir / "metrics.json", metrics)

        mark_stage_start("publish")
        atomic_publish(
            run_id=manifest.run_id,
            staging_root=staging_root,
            runs_root=runs_root,
            published_root=Path(system.paths.published_root),
            blocking_checks_passed=enforce_blocking_checks,
            latest_pointer=latest_pointer,
            compatibility_alias=compatibility_alias,
        )
        progress_path = runs_root / manifest.run_id / "reports" / "progress.jsonl"
        mark_stage_finish("publish", note="pointer_flipped")
        heartbeat("pipeline", "complete")
        return manifest.run_id
    except Exception:
        heartbeat("pipeline", "failed")
        raise
    finally:
        if active_status_path.exists():
            active_status_path.unlink()
