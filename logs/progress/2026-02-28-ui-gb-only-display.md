# Task: Force UI display scope to GB only

## Checklist
- [x] Confirm current UI is not GB-only
- [x] Implement GB-only filtering/rendering in frontend
- [x] Update UI smoke tests for GB-only scope copy/assertions
- [x] Run impacted verification commands
- [ ] Commit scoped UI changes
- [ ] Docs freshness and mistake replay check

## 2026-02-28T06:58:06Z
- Status: in progress
- Checklist item: Confirm current UI is not GB-only
- Update: Verified UI loaded unfiltered facilities/country/adaptive datasets and did not enforce GB-only rendering.
- Evidence: `frontend/main.js` API loads and rendering paths before filtering.
- Next: Implement client-side GB filtering for country mask, facilities, and adaptive cells.

## 2026-02-28T06:58:06Z
- Status: in progress
- Checklist item: Implement GB-only filtering/rendering in frontend
- Update: Applied GB-only frontend filtering based on `country_mask` layer_value=`GB`, with facility/adaptive fallback via H3 ancestry checks; updated UI copy/status labels to GB-only scope.
- Evidence: `frontend/main.js`, `frontend/index.html`.
- Next: Align smoke tests to explicit GB-only scope text.

## 2026-02-28T06:58:06Z
- Status: in progress
- Checklist item: Update UI smoke tests for GB-only scope copy/assertions
- Update: Updated smoke assertions to require GB-only heading/scope and GB-calibrated world estimate copy.
- Evidence: `tests/ui/test_ui_smoke.py`.
- Next: Run `node --check frontend/main.js` and `pytest -q tests/ui/test_ui_smoke.py`.

## 2026-02-28T06:58:30Z
- Status: complete
- Checklist item: Run impacted verification commands
- Update: Verified frontend JS syntax and UI smoke behavior after GB-only scope updates.
- Evidence: `node --check frontend/main.js`; `pytest -q tests/ui/test_ui_smoke.py` reported `1 passed in 0.59s`.
- Next: Commit scoped changes and record commit hash.
