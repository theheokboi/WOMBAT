from pathlib import Path

import pandas as pd

from inframap.agent.runner import run_pipeline
from inframap.config import load_layers_config, load_system_config


def test_end_to_end_run_publishes_artifacts(tmp_path: Path) -> None:
    system = load_system_config(Path("configs/system.yaml"))
    layers = load_layers_config(Path("configs/layers.yaml"))

    # Override paths for isolated integration test run.
    system = system.__class__(
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

    run_id = run_pipeline(system, layers)

    run_root = tmp_path / "runs" / run_id
    assert (run_root / "canonical" / "facilities.parquet").exists()
    assert (run_root / "layers" / "metro_density_core" / "m1" / "cells.parquet").exists()
    assert (run_root / "layers" / "country_mask" / "v1" / "cells.parquet").exists()
    assert (tmp_path / "published" / "latest").read_text(encoding="utf-8").strip() == run_id

    facilities = pd.read_parquet(run_root / "canonical" / "facilities.parquet")
    assert len(facilities) > 0
