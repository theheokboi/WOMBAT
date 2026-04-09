from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException


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


def load_layer_metadata(run_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for layer_dir in sorted((run_root / "layers").glob("*")):
        for version_dir in sorted(layer_dir.glob("*")):
            metadata_path = version_dir / "layer_metadata.json"
            if metadata_path.exists():
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
                items.append(payload)
    return items


def latest_layer_metadata_for(run_root: Path, layer_name: str) -> dict[str, Any] | None:
    candidates = [m for m in load_layer_metadata(run_root) if m.get("layer_name") == layer_name]
    if not candidates:
        return None
    return candidates[-1]


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
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


def adaptive_adjacency_health(adaptive_metadata: dict[str, Any] | None) -> dict[str, Any]:
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


def build_run_status_payload(
    store: DataStore,
    runtime_expectations: dict[str, Any],
    run_id: str,
    *,
    pointer: str | None,
    lane: str | None,
) -> dict[str, Any]:
    run_root = store.run_root(run_id)
    layer_metadata = load_layer_metadata(run_root)
    adaptive = next((m for m in layer_metadata if m.get("layer_name") == "facility_density_adaptive"), None)
    metrics = read_json_if_exists(run_root / "reports" / "metrics.json") or {}
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
            "adjacency_health": adaptive_adjacency_health(adaptive),
        },
        "latest_progress_event": latest_progress,
    }
