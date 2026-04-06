#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from inframap.config import load_system_config
from inframap.ingest.pipeline import ingest_and_normalize, write_facilities_sqlite_output


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYSTEM_CONFIG = REPO_ROOT / "configs" / "system.yaml"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "exports" / "facilities.sqlite"


def _resolve_input_path(config_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    config_relative = (config_path.parent / path).resolve()
    if config_relative.exists():
        return config_relative
    repo_relative = (REPO_ROOT / path).resolve()
    return repo_relative


def export_facilities_sqlite(system_config_path: Path, output_path: Path) -> Path:
    system = load_system_config(system_config_path)
    inputs = [
        (_resolve_input_path(system_config_path, source.path), source.source_name)
        for source in system.inputs
    ]
    facilities, _, _ = ingest_and_normalize(
        inputs,
        canonical_h3_resolutions=system.canonical_h3_resolutions,
    )
    write_facilities_sqlite_output(output_path, facilities)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export configured facility inputs into a single SQLite facilities table."
    )
    parser.add_argument(
        "--system-config",
        default=str(DEFAULT_SYSTEM_CONFIG),
        help="Path to the system config that declares input sources.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output SQLite database path.",
    )
    args = parser.parse_args()
    output_path = export_facilities_sqlite(
        system_config_path=Path(args.system_config).resolve(),
        output_path=Path(args.output).resolve(),
    )
    print(output_path)


if __name__ == "__main__":
    main()
