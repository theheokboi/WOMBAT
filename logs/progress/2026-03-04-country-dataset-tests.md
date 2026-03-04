# Task: migrate tests from legacy world dataset path to per-country datasets

Checklist:
- [x] Confirm requirement in docs/PROJECT.md
- [~] Locate and update unit/golden/integration/perf tests found by rg
- [ ] Run impacted tests and capture failures
- [ ] Docs check and mistake replay check

## 2026-03-04T22:11:41Z
- Status: in progress
- Checklist item: Confirm requirement in docs/PROJECT.md
- Update: Reviewed project contract and verified country-level polygon membership requirements; no strict path requirement blocks test fixture migration.
- Evidence: docs/PROJECT.md (country membership and config appendix sections)
- Next: Edit tests discovered by rg to use per-country data under data/countries.

## 2026-03-04T22:13:30Z
- Status: in progress
- Checklist item: Locate and update unit/golden/integration/perf tests found by rg
- Update: Replaced legacy dataset path references in unit/golden/perf tests with data/countries/US.geojson and switched integration GB fixture source to data/countries/GB.geojson; preserved warning test behavior by overriding legacy_world_dataset_path in test setup.
- Evidence: tests/unit/test_country_mask.py, tests/golden/test_golden_regression.py, tests/perf/test_adaptive_runtime.py, tests/integration/test_api.py
- Next: Run targeted tests and regenerate golden hash expectation if the country mask digest changed.

## 2026-03-04T22:15:20Z
- Status: in progress
- Checklist item: Run impacted tests and capture failures
- Update: Initial targeted test run failed because data/countries schema uses GID_0/COUNTRY properties instead of iso_a2/name expected by CountryMaskLayer test inputs.
- Evidence: pytest failures in tests/unit/test_country_mask.py and tests/perf/test_adaptive_runtime.py (KeyError: iso_a2)
- Next: Normalize per-country fixtures to expected property keys inside tests and rerun targeted suites.
