# Coding Agent Assignment: H3 Infrastructure Map Bootstrap

## 1. Mission
1. Implement the project bootstrap from docs to working code, with a strict test-first approach.
2. Prioritize correctness, determinism, and clarity over performance.
3. Ensure the UI can display both facility points and H3 grid layers (metro + country).

## 2. Source of Truth
1. Product/contracts: `docs/PROJECT.md`
2. Implementation blueprint: `docs/IMPLEMENTATION_PLAN.md`
3. Agent workflow policy: `AGENTS.md`
4. Project overview: `README.md`
5. Input staging and schema: `data/facilities/README.md`

## 3. Current Input Data
1. Use `data/facilities/peeringdb.csv` and `data/facilities/atlas.csv` as initial sources.
2. Keep support for `data/facilities/facilities_template.csv` as a fixture and onboarding sample.

## 4. Non-Negotiable Constraints
1. Deterministic outputs for identical `inputs_hash` + `config_hash`.
2. Atomic publish semantics with a single latest pointer flip.
3. Immutable published run artifacts.
4. Explicit, versioned config only; no hidden auto-tuning.
5. Strict blocking tests for publish-critical paths.
6. Keep `README.md` and `AGENTS.md` updated if workflow/contracts change.

## 5. Implementation Scope (Execute in This Order)
1. Scaffold repo structure and Python package layout per implementation plan.
2. Implement config loading and run manifest generation (`run_id`, `inputs_hash`, `config_hash`, `code_hash`).
3. Implement ingestion/validation/normalization for CSV/TSV facility data.
4. Implement H3 indexing at configured resolutions and canonical parquet outputs.
5. Implement layer plugin framework and `metro_density_core` (M1).
6. Implement `country_mask` layer using Natural Earth + centroid rule.
7. Implement validation/invariant pipeline and fail-closed policy.
8. Implement publish pipeline (staging -> validate -> atomic latest pointer).
9. Implement FastAPI read-only endpoints defined in docs.
10. Implement minimal internal frontend map with toggles, tooltips, drill-down, and H3 rendering.
11. Add Makefile targets for local run, serve, and UI.

## 6. Testing Requirements
1. Build blocking suites: unit, property-based, golden regression, invariants, integration.
2. Build non-blocking suites: UI smoke and perf/monitoring.
3. Ensure tests cover deterministic rerun equivalence, metro contiguity behavior, country assignment rule, and publish atomicity.
4. Add small fixtures and stable expected outputs for goldens.

## 7. Progress Tracking Requirements
1. Maintain a checklist with `[ ]`, `[~]`, `[x]`.
2. Maintain progress log at `logs/progress/<YYYY-MM-DD>-bootstrap-implementation.md`.
3. Log status transitions with evidence (test command/output summary or changed file path).
4. Include explicit docs check note each cycle.

## 8. Definition of Done
1. End-to-end local run works from `data/facilities/` to published artifacts.
2. API endpoints return correct run/layer/facility/tile responses.
3. Frontend renders facilities and H3 grid layers correctly.
4. Blocking tests pass locally.
5. Docs are synchronized with implemented behavior.
6. Final handoff includes architecture summary, test results, known limitations, and next recommended milestone.
