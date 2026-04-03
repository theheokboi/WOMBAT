## 2026-04-03T00:00:00Z
- Status: in progress
- Checklist item: [ ] Confirm run command and published scope for the new datacenter source
- Update: Verified `make run-dev` uses the active `configs/system.yaml` inputs and the current country-mask scope when no `COUNTRIES` override is provided.
- Evidence: `Makefile`, `src/inframap/agent/cli.py`, `configs/layers.yaml`
- Next: Launch a new dev run and confirm the published pointer flips.

## 2026-04-03T00:00:00Z
- Status: complete
- Checklist item: [x] Confirm run command and published scope for the new datacenter source
- Update: Ran a fresh dev pipeline and published a new run that includes the datacenter source in canonical ingest.
- Evidence: `make run-dev` -> `run-99dc154d9882-7f9c4ec96c32-5a59a1dad66b`; `data/published/latest-dev` and `data/published/latest` both point to the same run; `reports/metrics.json` reports `facility_count_by_source = {'DataCenterMap': 12079, 'LandingPoints': 1377, 'PeeringDB': 5593}`.
- Next: None.
