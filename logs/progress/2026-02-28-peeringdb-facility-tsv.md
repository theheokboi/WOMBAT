# Task: Support peeringdb_facility.tsv ingestion

## Checklist
- [x] Confirm requirement and current breakage from docs/config/code
- [x] Add/adjust tests for peeringdb TSV normalization behavior
- [x] Implement minimal ingestion/config changes for `data/facilities/peeringdb_facility.tsv`
- [x] Run impacted blocking tests and `make run`
- [x] Update docs/config references and validate freshness
- [ ] Run mistake replay check against `logs/mistakes.md`
- [~] Create required git checkpoint commit

## 2026-02-28T04:32:30Z
- Status: in progress
- Checklist item: Confirm requirement and current breakage from docs/config/code
- Update: Confirmed current config references missing `data/facilities/atlas.csv` and canonical-column parser rejects raw PeeringDB facility TSV schema.
- Evidence: `configs/system.yaml`; `src/inframap/ingest/pipeline.py`; `make run` fails with FileNotFoundError for `atlas.csv`; `data/facilities/peeringdb_facility.tsv` header inspection.
- Next: Add a unit test that defines expected normalization behavior for PeeringDB facility TSV rows.

## 2026-02-28T04:33:44Z
- Status: in progress
- Checklist item: Add/adjust tests for peeringdb TSV normalization behavior
- Update: Added unit test covering normalization from PeeringDB facility TSV fields (`name`, `org_id`, `latitude`, `longitude`, `updated`) into canonical ingest fields.
- Evidence: `tests/unit/test_ingest_normalize.py` includes `test_ingest_normalizes_peeringdb_facility_tsv_schema`.
- Next: Implement ingest normalization adapter and switch configured input path to the TSV file.

## 2026-02-28T04:33:44Z
- Status: in progress
- Checklist item: Implement minimal ingestion/config changes for `data/facilities/peeringdb_facility.tsv`
- Update: Implemented PeeringDB TSV schema normalization in ingest pipeline and updated `configs/system.yaml` default inputs to `data/facilities/peeringdb_facility.tsv`.
- Evidence: `src/inframap/ingest/pipeline.py`; `configs/system.yaml`.
- Next: Run blocking verification and pipeline run.

## 2026-02-28T04:33:44Z
- Status: complete
- Checklist item: Run impacted blocking tests and `make run`
- Update: Verified updated ingest unit tests and full blocking suite; reran pipeline successfully.
- Evidence: `pytest -q tests/unit/test_ingest_normalize.py` -> 4 passed; `make test-blocking` -> 23 passed; `make run` -> `run-bf8e2b620e27-61111dbc9946-a70743ac6fea`.
- Next: Finalize docs freshness check and perform mistake replay check.

## 2026-02-28T04:33:44Z
- Status: complete
- Checklist item: Update docs/config references and validate freshness
- Update: Updated README and data input guidance to reflect PeeringDB facility TSV as default supported ingest source.
- Evidence: `README.md`; `data/facilities/README.md`.
- Next: Perform mistake replay check and create git checkpoint commit.

## 2026-02-28T04:34:01Z
- Status: complete
- Checklist item: Run mistake replay check against `logs/mistakes.md`
- Update: Reviewed ledger entry about external map-style dependency; confirmed this task did not introduce any new external rendering dependency or repeat that mistake.
- Evidence: `logs/mistakes.md` (entry `2026-02-28T00:46:44Z`); changes limited to ingest/config/tests/docs.
- Next: Create required git checkpoint commit and record hash.
