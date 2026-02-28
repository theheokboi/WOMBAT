# Task: Remove facility style selector and keep raw facilities only

## Checklist
- [x] Confirm selector wiring and affected UI elements
- [x] Remove facility style selector from UI markup
- [x] Simplify frontend logic to render raw facilities only
- [x] Update tests for removed selector
- [x] Run impacted verification
- [x] Docs/mistake replay check
- [~] Create git checkpoint commit with evidence

## 2026-02-28T04:57:19Z
- Status: in progress
- Checklist item: Confirm selector wiring and affected UI elements
- Update: Confirmed `facility-style` select exists in `frontend/index.html` and controls `currentFacilityData()` in `frontend/main.js`.
- Evidence: `frontend/index.html`; `frontend/main.js`.
- Next: Remove selector and related branching to always render raw data.

## 2026-02-28T04:57:41Z
- Status: complete
- Checklist item: Remove facility style selector from UI markup
- Update: Removed facility-style label/select block from the control panel.
- Evidence: `frontend/index.html`.
- Next: Simplify JS to render raw facilities only.

## 2026-02-28T04:57:41Z
- Status: complete
- Checklist item: Simplify frontend logic to render raw facilities only
- Update: Removed facility-style mode branching and associated transform helpers; facility layer now always renders raw facilities payload.
- Evidence: `frontend/main.js`.
- Next: Update UI smoke assertions and run tests.

## 2026-02-28T04:57:41Z
- Status: complete
- Checklist item: Update tests for removed selector
- Update: Added assertion that `facility-style` is absent in UI smoke.
- Evidence: `tests/ui/test_ui_smoke.py`.
- Next: Run non-blocking verification.

## 2026-02-28T04:57:41Z
- Status: complete
- Checklist item: Run impacted verification
- Update: Ran non-blocking suite including UI smoke.
- Evidence: `make test-nonblocking` -> 2 passed.
- Next: Final docs/mistake replay check and commit.

## 2026-02-28T04:57:41Z
- Status: complete
- Checklist item: Docs/mistake replay check
- Update: Docs check: no changes required because this is a UI control removal with no contract/workflow changes. Mistake replay check: no reintroduction of external style dependency or adaptive partition logic changes.
- Evidence: `README.md`/`AGENTS.md` unchanged by design; reviewed `logs/mistakes.md` entries `2026-02-28T00:46:44Z` and `2026-02-28T04:52:14Z`.
- Next: Create git checkpoint commit and record hash evidence.
