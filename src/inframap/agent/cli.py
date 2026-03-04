from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Event, Thread
from time import monotonic, sleep

from inframap.agent.runner import run_pipeline
from inframap.config import load_layers_config, load_system_config


def _parse_country_codes(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [token.strip().upper() for token in value.split(",")]
    countries: list[str] = []
    seen: set[str] = set()
    for token in items:
        if not token:
            continue
        if len(token) != 2 or not token.isalpha():
            raise ValueError(f"Invalid country code '{token}'. Expected comma-separated ISO-2 codes (e.g., AR,JP,US).")
        if token in seen:
            continue
        seen.add(token)
        countries.append(token)
    return countries or None


def _apply_country_selection(layers, countries: list[str] | None):
    if not countries:
        return layers
    updated_layers = []
    for layer in layers.layers:
        if layer.name != "country_mask":
            updated_layers.append(layer)
            continue
        params = dict(layer.params)
        params["polygon_dataset_dir"] = str(params.get("polygon_dataset_dir", "data/countries"))
        params["include_iso_a2"] = countries
        params.pop("polygon_dataset", None)
        updated_layers.append(layer.__class__(name=layer.name, plugin=layer.plugin, version=layer.version, params=params))
    return layers.__class__(layers_version=layers.layers_version, layers=updated_layers)


def _env_truthy(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"0", "false", "no", "off"}:
        return False
    if normalized in {"1", "true", "yes", "on"}:
        return True
    return default


def _format_progress_line(payload: dict) -> str:
    status = str(payload.get("status", "--"))
    stage = str(payload.get("stage", "--"))
    layer_name = payload.get("layer_name")
    note = payload.get("note")
    elapsed = payload.get("elapsed_s")
    elapsed_label = "--"
    if isinstance(elapsed, (int, float)):
        elapsed_label = f"{elapsed:.1f}s"
    layer_suffix = f" ({layer_name})" if layer_name else ""
    note_suffix = f" note={note}" if note else ""
    return f"[run-dev] {status} {stage}{layer_suffix} elapsed={elapsed_label}{note_suffix}"


def _start_progress_monitor(staging_root: Path, enabled: bool) -> tuple[Event, Thread | None]:
    stop_event = Event()
    if not enabled:
        return stop_event, None

    active_status_path = staging_root / "active_run.json"

    def monitor() -> None:
        last_line: str | None = None
        last_emit = 0.0
        while not stop_event.is_set():
            if active_status_path.exists():
                try:
                    payload = json.loads(active_status_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    sleep(0.5)
                    continue
                line = _format_progress_line(payload)
                now = monotonic()
                if line != last_line or (now - last_emit) >= 15.0:
                    print(line, flush=True)
                    last_line = line
                    last_emit = now
            sleep(0.5)

    thread = Thread(target=monitor, name="run-dev-progress-monitor", daemon=True)
    thread.start()
    return stop_event, thread


def main() -> None:
    system_path = Path(os.environ.get("SYSTEM_CONFIG_PATH", "configs/system.yaml"))
    layers_path = Path(os.environ.get("LAYERS_CONFIG_PATH", "configs/layers.yaml"))
    system = load_system_config(system_path)
    layers = load_layers_config(layers_path)
    countries_raw = os.environ.get("COUNTRIES") or os.environ.get("COUNTRY")
    countries = _parse_country_codes(countries_raw)
    layers = _apply_country_selection(layers, countries)
    progress_enabled = _env_truthy(os.environ.get("RUN_DEV_PROGRESS"), default=True)
    stop_event, monitor_thread = _start_progress_monitor(Path(system.paths.staging_root), enabled=progress_enabled)
    if progress_enabled:
        print("[run-dev] progress monitor enabled (set RUN_DEV_PROGRESS=0 to disable)", flush=True)
    try:
        run_id = run_pipeline(
            system,
            layers,
            latest_pointer="latest-dev",
            compatibility_alias="latest",
            enforce_blocking_checks=False,
            run_invariants_check=False,
        )
    finally:
        stop_event.set()
        if monitor_thread is not None:
            monitor_thread.join(timeout=1.0)
    if progress_enabled:
        print(f"[run-dev] complete run_id={run_id}", flush=True)
    print(run_id)


if __name__ == "__main__":
    main()
