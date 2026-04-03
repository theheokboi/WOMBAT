## 2026-04-02T16:29:46Z
- Status: in progress
- Checklist item: [~] Document the local UI URL in the README
- Update: Confirmed the README only mentioned the dev commands, not the actual localhost URL for the UI or the backend health check path.
- Evidence: `README.md`; `src/inframap/serve/app.py`; `Makefile`
- Next: Add the explicit `http://localhost:8000/ui/` guidance and record the docs impact.

## 2026-04-02T16:29:46Z
- Status: complete
- Checklist item: [x] Document the local UI URL in the README
- Update: Added the `http://localhost:8000/ui/` URL, noted the `/` redirect, and added the `http://localhost:8000/v1/health` backend check to the README.
- Evidence: `README.md`
- Next: Handoff complete.

## 2026-04-02T16:29:46Z
- Status: complete
- Checklist item: [x] Docs check: no changes required
- Update: Only `README.md` needed an update for this user-facing clarification; `docs/PROJECT.md` and `AGENTS.md` already matched the current contract and workflow.
- Evidence: Existing docs remain accurate.
- Next: Handoff complete.

## 2026-04-02T16:29:46Z
- Status: complete
- Checklist item: [x] Mistake replay check
- Update: No new mistake pattern was introduced by this README-only edit.
- Evidence: `logs/mistakes.md`
- Next: Handoff complete.
