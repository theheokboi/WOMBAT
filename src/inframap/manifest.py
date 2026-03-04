from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import subprocess

from inframap.config import LayersConfig, SystemConfig, serialize_config


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    inputs_hash: str
    config_hash: str
    code_hash: str


REQUIRED_INPUT_COLUMNS = {
    "ORGANIZATION",
    "NODE_NAME",
    "LATITUDE",
    "LONGITUDE",
    "SOURCE",
    "ASOF_DATE",
}


def hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_inputs_hash(system: SystemConfig, layers: LayersConfig) -> str:
    digest = sha256()
    for source in sorted(system.inputs, key=lambda x: x.path):
        file_path = Path(source.path)
        digest.update(source.path.encode("utf-8"))
        digest.update(hash_file(file_path).encode("utf-8"))
    layer_input_paths = set()
    for layer in layers.layers:
        dataset_path = layer.params.get("polygon_dataset")
        if isinstance(dataset_path, str):
            layer_input_paths.add(dataset_path)
        dataset_dir = layer.params.get("polygon_dataset_dir")
        include_iso = layer.params.get("include_iso_a2")
        if isinstance(dataset_dir, str) and isinstance(include_iso, list):
            for iso in sorted({str(code).upper() for code in include_iso}):
                layer_input_paths.add(str(Path(dataset_dir) / f"{iso}.geojson"))
    for dataset_path in sorted(layer_input_paths):
        file_path = Path(dataset_path)
        if not file_path.exists():
            continue
        digest.update(dataset_path.encode("utf-8"))
        digest.update(hash_file(file_path).encode("utf-8"))
    return digest.hexdigest()


def compute_config_hash(system: SystemConfig, layers: LayersConfig) -> str:
    return sha256(serialize_config(system, layers)).hexdigest()


def compute_code_hash(code_dir: Path) -> str:
    content_digest = sha256()
    for path in sorted(code_dir.rglob("*.py")):
        content_digest.update(str(path).encode("utf-8"))
        content_digest.update(hash_file(path).encode("utf-8"))
    content_hash = content_digest.hexdigest()

    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        if head:
            return sha256(f"{head}:{content_hash}".encode("utf-8")).hexdigest()
    except Exception:
        pass

    return content_hash


def build_run_manifest(system: SystemConfig, layers: LayersConfig, code_dir: Path) -> RunManifest:
    inputs_hash = compute_inputs_hash(system, layers)
    config_hash = compute_config_hash(system, layers)
    code_hash = compute_code_hash(code_dir)
    run_id = f"run-{inputs_hash[:12]}-{config_hash[:12]}-{code_hash[:12]}"
    return RunManifest(
        run_id=run_id,
        inputs_hash=inputs_hash,
        config_hash=config_hash,
        code_hash=code_hash,
    )


def manifest_to_dict(manifest: RunManifest) -> dict[str, str]:
    return {k: str(v) for k, v in asdict(manifest).items()}
