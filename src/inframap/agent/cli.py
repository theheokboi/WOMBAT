from __future__ import annotations

import os
from pathlib import Path

from inframap.agent.runner import run_pipeline
from inframap.config import load_layers_config, load_system_config


def main() -> None:
    system_path = Path(os.environ.get("SYSTEM_CONFIG_PATH", "configs/system.yaml"))
    layers_path = Path(os.environ.get("LAYERS_CONFIG_PATH", "configs/layers.yaml"))
    system = load_system_config(system_path)
    layers = load_layers_config(layers_path)
    run_id = run_pipeline(
        system,
        layers,
        latest_pointer="latest-dev",
        compatibility_alias="latest",
        enforce_blocking_checks=False,
        run_invariants_check=False,
    )
    print(run_id)


if __name__ == "__main__":
    main()
