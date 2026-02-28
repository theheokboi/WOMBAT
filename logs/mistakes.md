# Mistake Ledger

Append-only log of agent mistakes and prevention rules.

## Entry Template
## <UTC timestamp>
- Mistake:
- Root cause:
- Corrective action:
- Prevention rule:
- Verification evidence:

## 2026-02-28T00:46:44Z
- Mistake: Frontend relied on an externally hosted map style URL, which can produce a blank map when the style is unreachable.
- Root cause: Initial UI bootstrap optimized for quick demo style integration instead of local deterministic rendering baseline.
- Corrective action: Replaced external style URL with local inline MapLibre style and added root redirect for discoverability.
- Prevention rule: Do not make rendering-critical frontend initialization depend on external runtime assets unless a local fallback is implemented and tested.
- Verification evidence: frontend/main.js updated; tests/integration/test_api.py and tests/ui/test_ui_smoke.py passed.
