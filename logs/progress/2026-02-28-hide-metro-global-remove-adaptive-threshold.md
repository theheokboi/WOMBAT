# Task: Hide metro/global layers and remove adaptive threshold UI control

## Checklist
- [x] Confirm current UI wiring for metro/global/adaptive-threshold controls
- [x] Update frontend UI to hide Metro H3 and Global H3 layers
- [x] Remove adaptive threshold control and force published adaptive rendering
- [x] Update UI smoke tests for new expected controls
- [x] Run verification for impacted tests
- [x] Docs check (`README.md`, `AGENTS.md`) and mistake replay check
- [~] Create git checkpoint commit and record evidence

## 2026-02-28T04:55:38Z
- Status: in progress
- Checklist item: Confirm current UI wiring for metro/global/adaptive-threshold controls
- Update: Confirmed these controls are defined in `frontend/index.html` and wired in `frontend/main.js`; smoke tests currently assert global controls and adaptive threshold control IDs.
- Evidence: `frontend/index.html`; `frontend/main.js`; `tests/ui/test_ui_smoke.py`.
- Next: Patch frontend to remove those controls and related rendering logic.

## 2026-02-28T04:55:56Z
- Status: complete
- Checklist item: Update frontend UI to hide Metro H3 and Global H3 layers
- Update: Removed Metro H3 and Global H3 checkboxes from panel and removed related legend entries.
- Evidence: `frontend/index.html`.
- Next: Remove adaptive threshold controls and simplify adaptive rendering to published defaults.

## 2026-02-28T04:55:56Z
- Status: complete
- Checklist item: Remove adaptive threshold control and force published adaptive rendering
- Update: Removed adaptive threshold slider/info controls and deleted JS logic for threshold preview fetches; adaptive layer now uses default published cells payload only.
- Evidence: `frontend/index.html`; `frontend/main.js`.
- Next: Update UI smoke checks and run impacted verification.

## 2026-02-28T04:55:56Z
- Status: complete
- Checklist item: Update UI smoke tests for new expected controls
- Update: Updated smoke test assertions to match revised control panel and explicitly assert removed controls are absent.
- Evidence: `tests/ui/test_ui_smoke.py`.
- Next: Run non-blocking verification.

## 2026-02-28T04:55:56Z
- Status: complete
- Checklist item: Run verification for impacted tests
- Update: Executed non-blocking suites including UI smoke.
- Evidence: `make test-nonblocking` -> 2 passed.
- Next: Record docs check and mistake replay check, then commit.

## 2026-02-28T04:55:56Z
- Status: complete
- Checklist item: Docs check (`README.md`, `AGENTS.md`) and mistake replay check
- Update: Docs check: no changes required; this task only adjusts visible UI controls without workflow/API contract changes. Mistake replay check: confirmed no reintroduction of external style dependency risk and no adaptive duplicate-cell logic changes.
- Evidence: `README.md` unchanged with valid current behavior; `AGENTS.md` unchanged; `logs/mistakes.md` reviewed entries `2026-02-28T00:46:44Z` and `2026-02-28T04:52:14Z`.
- Next: Create git checkpoint commit and record hash evidence.
