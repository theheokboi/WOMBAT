# Script Catalog

## Maintained Workflow

- `export_facilities_sqlite.py`: canonical facilities export
- `export_static_demo_bundle.py`: browser-ready demo snapshot export
- `archive_progress_logs.py`: archive stale committed progress logs

## Experimental / Legacy Helpers

These scripts are kept for ad hoc use or historical workflows. They are not part of the default dev loop and should not be treated as maintained entrypoints unless explicitly promoted.

- `build_r7_route_ui_geojson.py`: compact route overlay generation from full route JSON
- `fetch_r7_region_routes.py`: fetch or stage derived route inputs
- `generate_arg_facility_density_map.py`: one-off Argentina facility density artifact generator
- `generate_multilevel_h3_from_shp.py`: one-off geometry-to-H3 visualization generator
