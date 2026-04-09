# Advanced Workflows

These commands are supported, but they are not part of the default `run-dev` / `serve-dev` / `ui-dev` / `verify-dev` loop.

This doc is for maintained workflows only. Ad hoc and legacy helper scripts stay cataloged in [scripts/README.md](/Users/hyes92121/Desktop/h3-experiment/scripts/README.md) and should not be promoted here unless they become part of the supported workflow surface.

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

## Progress Log Retention

Archive stale committed progress logs:

```bash
make archive-progress-logs
```
