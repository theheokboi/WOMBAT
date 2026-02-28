# Facilities Input Drop Zone

Place raw facility input files here for local ingestion experiments.

## Accepted format (minimum)

CSV or TSV with these columns:

- `ORGANIZATION` (required)
- `NODE_NAME` (required)
- `LATITUDE` (required, WGS84)
- `LONGITUDE` (required, WGS84)
- `CITY` (optional)
- `STATE` (optional)
- `COUNTRY` (optional)
- `SOURCE` (required)
- `ASOF_DATE` (required, `YYYY-MM-DD`)

## Notes

- Geometry is authoritative; city/state/country are metadata labels only.
- Latitude must be within `[-90, 90]`; longitude within `[-180, 180]`.
- Keep one logical snapshot per file when possible.

## Suggested naming

`<source>_<YYYY-MM-DD>.csv`

Example: `peeringdb_2026-02-28.csv`
