from __future__ import annotations

from pathlib import Path
import os


def _flip_pointer(published_root: Path, pointer_name: str, run_id: str) -> None:
    pointer_tmp = published_root / f"{pointer_name}.tmp"
    pointer = published_root / pointer_name
    pointer_tmp.write_text(run_id + "\n", encoding="utf-8")
    os.replace(pointer_tmp, pointer)


def atomic_publish(
    run_id: str,
    staging_root: Path,
    runs_root: Path,
    published_root: Path,
    blocking_checks_passed: bool,
    latest_pointer: str = "latest-dev",
    compatibility_alias: str | None = "latest",
) -> None:
    _ = blocking_checks_passed

    staged = staging_root / run_id
    if not staged.exists():
        raise FileNotFoundError(f"Staged run not found: {staged}")

    runs_root.mkdir(parents=True, exist_ok=True)
    published_root.mkdir(parents=True, exist_ok=True)

    final_run = runs_root / run_id
    if final_run.exists():
        raise FileExistsError(f"Published run already exists (immutable): {final_run}")

    os.replace(staged, final_run)

    _flip_pointer(published_root, latest_pointer, run_id)
    if compatibility_alias and compatibility_alias != latest_pointer:
        _flip_pointer(published_root, compatibility_alias, run_id)
