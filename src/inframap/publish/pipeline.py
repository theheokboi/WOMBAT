from __future__ import annotations

from pathlib import Path
import os


def atomic_publish(
    run_id: str,
    staging_root: Path,
    runs_root: Path,
    published_root: Path,
    blocking_checks_passed: bool,
) -> None:
    if not blocking_checks_passed:
        raise RuntimeError("Blocking checks failed; refusing publish")

    staged = staging_root / run_id
    if not staged.exists():
        raise FileNotFoundError(f"Staged run not found: {staged}")

    runs_root.mkdir(parents=True, exist_ok=True)
    published_root.mkdir(parents=True, exist_ok=True)

    final_run = runs_root / run_id
    if final_run.exists():
        raise FileExistsError(f"Published run already exists (immutable): {final_run}")

    os.replace(staged, final_run)

    latest_tmp = published_root / "latest.tmp"
    latest = published_root / "latest"
    latest_tmp.write_text(run_id + "\n", encoding="utf-8")
    os.replace(latest_tmp, latest)
