## 2026-04-03T00:00:00Z
- Status: in progress
- Checklist item: [ ] Confirm existing canonical ingest contract and source schema handling
- Update: Reviewed `docs/PROJECT.md`, current ingest adapters, and the new `data/datacenters/datacenters_geocoded.tsv` header to determine how to add the source without changing the canonical facility shape.
- Evidence: `docs/PROJECT.md`, `src/inframap/ingest/pipeline.py`, `data/datacenters/datacenters_geocoded.tsv`
- Next: Add the datacenter schema adapter, register the new input source, and add a unit test.

## 2026-04-03T00:00:00Z
- Status: in progress
- Checklist item: [~] Implement datacenter source ingestion and docs updates
- Update: Added a dedicated datacenter TSV adapter in ingest, registered the new source in `configs/system.yaml`, and updated `README.md`, `docs/PROJECT.md`, and `AGENTS.md` to document the new canonical input source.
- Evidence: `src/inframap/ingest/pipeline.py`, `configs/system.yaml`, `README.md`, `docs/PROJECT.md`, `AGENTS.md`
- Next: Add/adjust tests, then run targeted verification.

## 2026-04-03T00:00:00Z
- Status: complete
- Checklist item: [x] Implement datacenter source ingestion and docs updates
- Update: Added the new `DataCenterMap` ingest adapter, wired `data/datacenters/datacenters_geocoded.tsv` into system config, and documented the source in the project docs.
- Evidence: `pytest tests/unit/test_ingest_normalize.py tests/unit/test_canonical_outputs.py` -> 7 passed; `python -c "... ingest_and_normalize([(Path('data/datacenters/datacenters_geocoded.tsv'), 'DataCenterMap')], [5,7]) ..."` -> `12079 1 0`
- Next: None.
