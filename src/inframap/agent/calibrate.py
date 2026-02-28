from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from inframap.config import LayersConfig, SystemConfig, load_layers_config, load_system_config
from inframap.ingest.pipeline import ingest_and_normalize
from inframap.layers.registry import build_layer_registry
from inframap.validation.invariants import run_invariants


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def _extract_adaptive_counters(metadata: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("adaptive_counters", "counters"):
        value = metadata.get(key)
        if isinstance(value, dict):
            return value
    return None


def _domain_r4_cell_count(
    country_code: str,
    layer_artifacts: dict[str, dict[str, Any]],
    adaptive_metadata: dict[str, Any] | None,
) -> int | None:
    if isinstance(adaptive_metadata, dict):
        for key in ("domain_r4_cell_count", "coverage_domain_r4_cell_count"):
            value = adaptive_metadata.get(key)
            if value is not None:
                return int(value)

    country_artifacts = layer_artifacts.get("country_mask")
    if not isinstance(country_artifacts, dict):
        return None
    cells = country_artifacts.get("cells")
    if not isinstance(cells, pd.DataFrame):
        return None
    if "h3" not in cells.columns:
        return None
    if "layer_value" in cells.columns:
        filtered = cells[cells["layer_value"].astype(str) == country_code]
    else:
        filtered = cells
    return int(filtered["h3"].astype(str).nunique())


def run_calibration(system: SystemConfig, layers: LayersConfig, country_code: str) -> Path:
    started = perf_counter()
    stage_durations: dict[str, float] = {}
    layer_durations: dict[str, float] = {}

    ts = datetime.now(timezone.utc)
    run_timestamp_utc = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_slug = ts.strftime("%Y%m%dT%H%M%S%fZ")
    country = country_code.strip()

    ingest_started = perf_counter()
    source_inputs = [(Path(source.path), source.source_name) for source in sorted(system.inputs, key=lambda x: x.path)]
    facilities, organizations, _ = ingest_and_normalize(
        source_inputs,
        canonical_h3_resolutions=sorted(set(system.canonical_h3_resolutions + [system.country_mask_resolution])),
    )
    stage_durations["ingest_normalize"] = perf_counter() - ingest_started

    filter_started = perf_counter()
    facilities = facilities[facilities["country_label"] == country].copy().reset_index(drop=True)
    organizations = (
        facilities[["org_id", "org_name"]]
        .drop_duplicates()
        .sort_values(by=["org_id"])
        .reset_index(drop=True)
    )
    stage_durations["filter_country"] = perf_counter() - filter_started

    layers_started = perf_counter()
    registry = build_layer_registry(layers)
    layer_artifacts: dict[str, dict[str, Any]] = {}
    for layer_cfg in layers.layers:
        layer_started = perf_counter()
        plugin = registry[layer_cfg.name]
        metadata, cells = plugin.compute(
            canonical_store={"facilities": facilities, "organizations": organizations},
            layer_store=layer_artifacts,
            params=layer_cfg.params,
        )
        if layer_cfg.name == "country_mask" and "layer_value" in cells.columns:
            cells = cells[cells["layer_value"].astype(str) == country].copy().reset_index(drop=True)
        plugin.validate({"metadata": metadata, "cells": cells})
        layer_artifacts[layer_cfg.name] = {"metadata": metadata, "cells": cells}
        layer_durations[layer_cfg.name] = perf_counter() - layer_started
    stage_durations["layers_compute"] = perf_counter() - layers_started

    invariant_started = perf_counter()
    invariant_passed = True
    invariant_error: str | None = None
    try:
        run_invariants(
            facilities=facilities,
            layer_artifacts=layer_artifacts,
            required_h3_resolutions=system.canonical_h3_resolutions,
        )
    except Exception as exc:
        invariant_passed = False
        invariant_error = str(exc)
    invariant_stage_duration = perf_counter() - invariant_started
    stage_durations["invariants"] = invariant_stage_duration
    stage_durations["total"] = perf_counter() - started

    adaptive_metadata = None
    adaptive_leaf_count = 0
    smoothing_iterations = 0
    adaptive_artifacts = layer_artifacts.get("facility_density_adaptive")
    if isinstance(adaptive_artifacts, dict):
        maybe_meta = adaptive_artifacts.get("metadata")
        maybe_cells = adaptive_artifacts.get("cells")
        if isinstance(maybe_meta, dict):
            adaptive_metadata = maybe_meta
        if isinstance(maybe_cells, pd.DataFrame):
            adaptive_leaf_count = int(len(maybe_cells))
    if isinstance(adaptive_metadata, dict):
        smoothing_iterations = int(
            adaptive_metadata.get("smoothing_iterations")
            or ((adaptive_metadata.get("adaptive_counters") or {}).get("smoothing_iterations", 0))
            or 0
        )

    report: dict[str, Any] = {
        "country_code": country,
        "run_timestamp_utc": run_timestamp_utc,
        "facility_count": int(len(facilities)),
        "runtime_seconds": round(stage_durations.get("total", 0.0), 6),
        "facilities": int(len(facilities)),
        "layer_durations_seconds": {k: round(v, 6) for k, v in sorted(layer_durations.items())},
        "stage_durations_seconds": {k: round(v, 6) for k, v in sorted(stage_durations.items())},
        "invariant_stage_duration_seconds": round(invariant_stage_duration, 6),
        "invariant_passed": invariant_passed,
        "adaptive_leaf_count": adaptive_leaf_count,
        "smoothing_iterations": smoothing_iterations,
        "adjacency_checks": 0,
    }
    if invariant_error:
        report["invariant_error"] = invariant_error
    domain_count = _domain_r4_cell_count(country, layer_artifacts, adaptive_metadata)
    report["domain_r4_cell_count"] = int(domain_count or 0)

    counters = _extract_adaptive_counters(adaptive_metadata or {})
    if counters is not None:
        report["adaptive_counters"] = counters

    report_path = Path("artifacts") / "calibration" / f"{ts_slug}-{country}" / "report.json"
    _write_json(report_path, report)
    return report_path


def main() -> None:
    system = load_system_config(Path("configs/system.yaml"))
    layers = load_layers_config(Path("configs/layers.yaml"))
    country = os.environ.get("COUNTRY", "GB")
    report_path = run_calibration(system=system, layers=layers, country_code=country)
    print(str(report_path))


if __name__ == "__main__":
    main()
