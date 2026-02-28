from pathlib import Path
from hashlib import sha256

from inframap.agent.runner import run_pipeline
from inframap.config import load_layers_config, load_system_config


def _hash(path: Path) -> str:
    digest = sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_rerun_determinism(tmp_path: Path) -> None:
    system = load_system_config(Path("configs/system.yaml"))
    layers = load_layers_config(Path("configs/layers.yaml"))

    def make_system(subdir: str):
        return system.__class__(
            config_version=system.config_version,
            allowed_h3_resolutions=system.allowed_h3_resolutions,
            canonical_h3_resolutions=system.canonical_h3_resolutions,
            country_mask_resolution=system.country_mask_resolution,
            zoom_to_h3_resolution=system.zoom_to_h3_resolution,
            ui=system.ui,
            inputs=list(system.inputs),
            paths=system.paths.__class__(
                runs_root=str(tmp_path / subdir / "runs"),
                staging_root=str(tmp_path / subdir / "staging"),
                published_root=str(tmp_path / subdir / "published"),
            ),
        )

    run_a = run_pipeline(make_system("a"), layers)
    run_b = run_pipeline(make_system("b"), layers)

    facilities_a = tmp_path / "a" / "runs" / run_a / "canonical" / "facilities.parquet"
    facilities_b = tmp_path / "b" / "runs" / run_b / "canonical" / "facilities.parquet"
    metro_a = tmp_path / "a" / "runs" / run_a / "layers" / "metro_density_core" / "m1" / "cells.parquet"
    metro_b = tmp_path / "b" / "runs" / run_b / "layers" / "metro_density_core" / "m1" / "cells.parquet"

    assert _hash(facilities_a) == _hash(facilities_b)
    assert _hash(metro_a) == _hash(metro_b)
