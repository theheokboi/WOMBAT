## Checklist
- [x] Confirm latest published run and target artifact directory
- [x] Export Taiwan and Argentina `r7` region coordinates as CSV artifacts
- [x] Verify saved CSV files and row counts

## 2026-03-08T07:16:43Z
- Status: complete
- Checklist item: Export Taiwan and Argentina `r7` region coordinates as CSV artifacts
- Update: Exported country-specific CSVs for the latest published `r7` regions under `artifacts/derived/`, using the current representative-point rule over the latest published `facility_density_r7_regions` clusters.
- Evidence: `artifacts/derived/2026-03-08-r7-regions-tw.csv`; `artifacts/derived/2026-03-08-r7-regions-ar.csv`
- Next: Handoff completed.

## 2026-03-08T07:16:43Z
- Status: complete
- Checklist item: Verify saved CSV files and row counts
- Update: Confirmed both exported files are readable and contain the expected number of region rows for the latest published run.
- Evidence: `2026-03-08-r7-regions-tw.csv rows=10`; `2026-03-08-r7-regions-ar.csv rows=42`
- Next: Handoff completed.
