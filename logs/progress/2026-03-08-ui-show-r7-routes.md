## 2026-03-08T07:47:15Z
- Status: in progress
- Checklist item: [~] Show saved AR/TW r7 route geometries on the UI
- Update: Confirmed the UI currently renders run-scoped cell layers only and the server does not yet expose the saved route JSON artifacts.
- Evidence: `frontend/main.js`; `frontend/index.html`; `src/inframap/serve/app.py`; `artifacts/derived/2026-03-08-r7-regions-tw-routes.json`; `artifacts/derived/2026-03-08-r7-regions-ar-routes.json`
- Next: Add a read-only API for saved route artifacts, wire a new UI overlay toggle, and verify via tests and screenshot.
