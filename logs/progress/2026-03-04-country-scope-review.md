## 2026-03-04T19:36:21Z
- Status: in progress
- Checklist item: Inspect frontend/API country scoping and layer toggles for GB dependencies
- Update: Task started with repo exploration and initial GB logic grep.
- Evidence: `rg -n "GB"`
- Next: Identify files/lines that hardcode GB and describe refactor steps.

## 2026-03-04T19:36:53Z
- Status: in progress
- Checklist item: Inspect frontend/API country scoping and layer toggles for GB dependencies
- Update: Documented exact frontend/backend files where GB is hardcoded and drafted runtime-selection refactor outline.
- Evidence: `grep`/`nl` references in `frontend/main.js`, `frontend/index.html`, and `src/inframap/serve/app.py`
- Next: Finalize integration summary with file/line citations and propose actionable refactor list.
