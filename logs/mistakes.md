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

## 2026-02-28T04:52:14Z
- Mistake: Initial adaptive split implementation emitted duplicate H3 cells with conflicting counts.
- Root cause: Recursive grouping logic used unstable partition flow that did not guarantee one unique active assignment per facility at each split stage.
- Corrective action: Replaced recursion with iterative active-cell reassignment per facility row and final deterministic group-by aggregation.
- Prevention rule: For adaptive partition algorithms, model one current cell assignment per record and refine in-place; avoid recursive group trees unless uniqueness invariants are explicitly proven and tested.
- Verification evidence: `tests/integration/test_api.py` and `make test-blocking` pass; plugin validation no longer raises duplicate-cell error.
