## 2026-03-08T08:45:00Z
- Status: in progress
- Checklist item: [~] Update frontend default layer toggles to facilities on, country off, adaptive off, r7 regions on, and r7 routes on
- Update: Confirmed the current toggle defaults in `frontend/index.html` and the existing UI smoke coverage in `tests/ui/test_ui_smoke.py`.
- Evidence: `frontend/index.html`; `tests/ui/test_ui_smoke.py`
- Next: Update the checkbox defaults, add smoke assertions for checked state, and run targeted verification.

## 2026-03-08T08:47:00Z
- Status: in progress
- Checklist item: [~] Update frontend default layer toggles to facilities on, country off, adaptive off, r7 regions on, and r7 routes on
- Update: Changed the frontend checkbox defaults and added UI smoke assertions that pin the expected checked and unchecked toggle markup.
- Evidence: `frontend/index.html`; `tests/ui/test_ui_smoke.py`
- Next: Run targeted UI verification, record docs impact, and complete handoff checks.

## 2026-03-08T08:49:00Z
- Status: complete
- Checklist item: [x] Update frontend default layer toggles to facilities on, country off, adaptive off, r7 regions on, and r7 routes on
- Update: Verified the updated defaults with targeted UI smoke and JavaScript syntax checks. Docs check: no changes required because this changes only initial UI control state, not a documented workflow or contract. Mistake replay check complete; no new prevention updates were needed for this small UI-only change.
- Evidence: `python -m pytest -q tests/ui/test_ui_smoke.py`; `node --check frontend/main.js`
- Next: Handoff complete.
