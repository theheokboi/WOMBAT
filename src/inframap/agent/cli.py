from __future__ import annotations

from pathlib import Path

from inframap.agent.runner import run_pipeline
from inframap.config import load_layers_config, load_system_config


def main() -> None:
    system = load_system_config(Path("configs/system.yaml"))
    layers = load_layers_config(Path("configs/layers.yaml"))
    run_id = run_pipeline(system, layers)
    print(run_id)


if __name__ == "__main__":
    main()
