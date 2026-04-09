# Script Catalog

## Core Workflow

- `export_facilities_sqlite.py`: canonical facilities export
- `export_static_demo_bundle.py`: browser-ready demo snapshot export
- `archive_progress_logs.py`: archive stale committed progress logs

## Graph Workflows

- `build_major_roads_graph.py`: graph artifact generation
- `evaluate_major_roads_graph.py`: raw vs collapsed graph evaluation
- `build_r7_route_ui_geojson.py`: compact route overlay generation
- `fetch_r7_region_routes.py`: fetch or stage derived route inputs

## Experimental Or Legacy Helpers

The remaining generators are not part of the default dev loop and should be treated as ad hoc utilities unless promoted into the main workflow.
