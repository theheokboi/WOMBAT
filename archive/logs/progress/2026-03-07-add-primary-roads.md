# Add Primary Roads To Adaptive Portal

Checklist
- [~] Confirm requirement in docs/PROJECT.md
- [ ] Add/update tests for changed behavior
- [ ] Implement minimal code changes
- [ ] Run local verification for impacted paths
- [ ] Update docs/config examples if needed
- [ ] Mistake replay check logged

## 2026-03-07T08:49:33Z
- Status: in progress
- Checklist item: Confirm requirement in docs/PROJECT.md
- Update: Started task to add primary roads to major-road graph/API path for adaptive portal variants.
- Evidence: User request in chat; initial code scan identified motorway/trunk filters in ingest and serve.
- Next: Validate contract language in docs/PROJECT.md and patch tests/code.

## 2026-03-07T08:50:36Z
- Status: in progress
- Checklist item: Confirm requirement in docs/PROJECT.md
- Update: Verified current contract explicitly states adaptive_portal variants are mainline-only motorway/trunk; this change needs doc update to include primary.
- Evidence: docs/PROJECT.md lines around adaptive_portal and adaptive_portal_run variant semantics.
- Next: Apply code and test updates for primary inclusion.

## 2026-03-07T08:51:17Z
- Status: in progress
- Checklist item: Add/update tests for changed behavior
- Update: Identified impacted tests in ingest mainline filtering, serve shapefile class filtering, and UI smoke legend assertions.
- Evidence: tests/unit/test_major_road_graph_contraction.py, tests/unit/test_serve_osm_transport.py, tests/ui/test_ui_smoke.py
- Next: Patch tests first, then implement minimal code updates to satisfy them.

## 2026-03-07T08:52:51Z
- Status: in progress
- Checklist item: Implement minimal code changes
- Update: Expanded mainline class filters to include `primary` for adaptive portal graph outputs and shapefile transport ingestion; added frontend style + legend entry for primary roads.
- Evidence: src/inframap/ingest/major_road_graph.py, src/inframap/serve/app.py, frontend/main.js, frontend/index.html, frontend/styles.css
- Next: Run focused pytest for changed unit/UI tests.

## 2026-03-07T08:52:51Z
- Status: in progress
- Checklist item: Run local verification for impacted paths
- Update: Ran targeted pytest subset for changed behaviors and all selected tests passed.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py::test_filter_mainline_edges_keeps_only_motorway_trunk_and_primary tests/unit/test_serve_osm_transport.py::test_osm_transport_overlay_filters_mainline_classes_and_includes_railway tests/unit/test_serve_osm_transport.py::test_osm_transport_overlay_skips_missing_files_and_lists_available_countries tests/ui/test_ui_smoke.py::test_ui_static_smoke` -> `4 passed in 0.88s`.
- Next: Update docs wording for adaptive_portal semantics and legend class list.

## 2026-03-07T08:53:06Z
- Status: in progress
- Checklist item: Update docs/config examples if needed
- Update: Updated transport graph semantics in docs to include `primary` as a mainline class for adaptive portal variants and added README legend wording for primary.
- Evidence: docs/PROJECT.md, README.md
- Next: Run mistake replay check and finalize checklist completion snapshot.

## 2026-03-07T08:53:06Z
- Status: complete
- Checklist item: Mistake replay check logged
- Update: Replayed recent mistake ledger entries and confirmed this task used interpolation-safe `apply_patch` log updates and targeted pytest verification.
- Evidence: `rg -n "^## " logs/mistakes.md | tail -n 5`; `mistake-replay: reviewed latest entries for interpolation/heredoc and verification command pitfalls`
- Next: Handoff summary with files changed and verification results.

## 2026-03-07T08:53:06Z
- Status: complete
- Checklist item: Checklist snapshot
- Update: `[x] Confirm requirement in docs/PROJECT.md`, `[x] Add/update tests for changed behavior`, `[x] Implement minimal code changes`, `[x] Run local verification for impacted paths`, `[x] Update docs/config examples if needed`, `[x] Mistake replay check logged`.
- Evidence: See entries above in this log.
- Next: None.

## 2026-03-07T08:55:28Z
- Status: in progress
- Checklist item: Implement minimal code changes
- Update: Fixed ingest parse-stage class set to include `primary` in `MAJOR_HIGHWAY_CLASSES` so rebuilt graph artifacts can actually contain primary edges.
- Evidence: src/inframap/ingest/major_road_graph.py (`MAJOR_HIGHWAY_CLASSES = {"motorway", "trunk", "primary", ...}`).
- Next: Re-run full focused verification suite.

## 2026-03-07T08:55:28Z
- Status: complete
- Checklist item: Run local verification for impacted paths
- Update: Re-ran full focused suite used for this graph/API/UI area.
- Evidence: `pytest -q tests/unit/test_major_road_graph_contraction.py tests/unit/test_serve_osm_transport.py tests/unit/test_major_road_graph_eval.py tests/unit/test_major_road_graph_progress.py tests/ui/test_ui_smoke.py` -> `39 passed in 0.88s`.
- Next: Finalize docs/mistake replay confirmation and handoff commands.

## 2026-03-07T08:55:28Z
- Status: complete
- Checklist item: Mistake replay check logged
- Update: Confirmed latest mistake ledger entries were replayed before handoff; no new rule additions required for this change.
- Evidence: `rg -n "^## " logs/mistakes.md | tail -n 5`.
- Next: Provide user-facing summary and exact rebuild/view steps.

## 2026-03-07T08:55:28Z
- Status: complete
- Checklist item: Update docs/config examples if needed
- Update: Docs already updated for `primary` in adaptive portal semantics; AGENTS workflow doc unchanged because no workflow/tooling contract changed.
- Evidence: docs/PROJECT.md, README.md; Docs check: no AGENTS.md changes required.
- Next: None.
