# Advanced Workflows

These commands are supported, but they are not part of the default `run-dev` / `serve-dev` / `ui-dev` / `verify-dev` loop.

## Static Demo Bundle

```bash
PYTHONPATH=src python scripts/export_static_demo_bundle.py --run-id "$(cat data/published/latest-dev)"
```

This writes browser-ready snapshots into `frontend/demo-data/` for backend-free hosting.

## Facilities SQLite Export

```bash
make export-facilities-sqlite
# or
PYTHONPATH=src python scripts/export_facilities_sqlite.py --output artifacts/exports/facilities.sqlite
```

The export contains one flat `facilities` table using canonical normalization with in-row source provenance.

## Major-Road Graph Workflows

Build graph artifacts:

```bash
python scripts/build_major_roads_graph.py --country TW
```

Useful variants:

- `raw`
- `collapsed`
- `adaptive`
- `adaptive_portal`
- `adaptive_portal_run`

Run-scoped adaptive portal output:

```bash
python scripts/build_major_roads_graph.py --country TW --graph-variant adaptive_portal_run --run-id <run-id>
```

Evaluate raw vs collapsed graph artifacts:

```bash
python scripts/evaluate_major_roads_graph.py --country TW --out artifacts/eval/TW-major-roads-eval.json
```

## Progress Log Retention

Archive stale committed progress logs:

```bash
make archive-progress-logs
```
