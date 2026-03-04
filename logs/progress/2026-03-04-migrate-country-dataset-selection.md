# Task Checklist
- [~] Migrate country mask config/code to per-country dataset selection mode
- [ ] Update tests/fixtures to remove legacy world file dependency
- [ ] Run impacted test suites and fix regressions
- [ ] Update docs/config examples if needed
- [ ] Record mistake replay/docs check and finalize

## 2026-03-04T22:11:17Z
- Status: in progress
- Checklist item: Migrate country mask config/code to per-country dataset selection mode
- Update: Started migration off deleted legacy world GeoJSON to per-country file selection under data/countries.
- Evidence: /Users/hyes92121/Desktop/h3-experiment/data/reference/natural_earth_admin0_subset.geojson (deleted), /Users/hyes92121/Desktop/h3-experiment/data/countries/*.geojson
- Next: Implement config and country mask loader changes, then update tests.

## 2026-03-04T22:12:10Z
- Status: in progress
- Checklist item: Migrate country mask config/code to per-country dataset selection mode
- Update: Confirmed legacy world dataset path is removed and country files now live under data/countries as per-country GeoJSONs without iso_a2 attributes.
- Evidence: ls data/reference (missing), ls data/countries (AR/GB/JP/TW/US), property probe script output.
- Next: Implement dual-source loader preferring polygon_dataset_dir + include_iso_a2 and preserve deterministic ordering + metadata provenance.

## 2026-03-04T22:18:00Z
- Status: in progress
- Checklist item: Migrate country mask config/code to per-country dataset selection mode
- Update: Beginning code edits for country_mask parameter migration and input-hash provenance handling.
- Evidence: Planned edits in src/inframap/layers/country_mask.py and src/inframap/manifest.py.
- Next: Patch loader logic to support polygon_dataset_dir + include_iso_a2 with deterministic ordering and explicit metadata.
