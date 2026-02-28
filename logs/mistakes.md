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

## 2026-02-28T05:23:01Z
- Mistake: Parallel task merge initially left `run_invariants` inconsistent with adaptive v2 policy (`r0` empties rejected and adaptive overlap not checked).
- Root cause: Integration pass did not immediately reconcile generic invariants with new layer-specific contracts after accepting parallel subagent commits.
- Corrective action: Updated `src/inframap/validation/invariants.py` to allow adaptive `resolution` range `0..13`, enforce adaptive `h3`/resolution consistency, require occupied adaptive cells at `r9+`, and reject ancestor/descendant overlap.
- Prevention rule: After parallel merges that change layer contracts, run target suites (`tests/unit/test_invariants.py` and API integration) before full suite to catch cross-cutting gate drift early.
- Verification evidence: `pytest -q tests/unit/test_invariants.py` and `pytest -q tests/integration/test_api.py` passing.

## 2026-02-28T06:31:34Z
- Mistake: Attempted Python syntax compilation on a JavaScript file (`frontend/main.js`) during verification.
- Root cause: Mixed-language verification command was assembled too quickly without language-specific filtering.
- Corrective action: Re-ran `py_compile` using Python files only and kept frontend checks to UI smoke tests.
- Prevention rule: Restrict syntax-compile commands to language-appropriate file sets; never include frontend JS in Python compile commands.
- Verification evidence: `python -m py_compile src/inframap/agent/calibrate.py src/inframap/agent/runtime_estimator.py src/inframap/serve/app.py tests/integration/test_api.py tests/unit/test_runtime_estimator.py tests/integration/test_calibration_workflow.py` passed.

## 2026-02-28T06:58:47Z
- Mistake: Used unescaped backticks inside a shell heredoc while appending progress log evidence, causing unintended command substitution.
- Root cause: Quick log append used double-quoted shell command without considering markdown backtick expansion.
- Corrective action: Corrected the broken progress-log entry using  and switched to safer quoting for subsequent log appends.
- Prevention rule: When appending markdown containing backticks via shell, use single-quoted heredoc delimiters or apply_patch edits to avoid shell interpolation.
- Verification evidence:  now contains corrected evidence text and no shell artifacts.

## 2026-02-28T06:59:12Z
- Mistake: Used unescaped markdown backticks in shell log-append commands, triggering unintended command substitution.
- Root cause: Used double-quoted shell strings for markdown content that included backticks.
- Corrective action: Replaced shell append approach with a single-quoted heredoc and corrected the malformed progress-log evidence entry.
- Prevention rule: For markdown log appends, always use single-quoted heredocs or `apply_patch`; never embed backticks in double-quoted shell command strings.
- Verification evidence: `logs/mistakes.md` has this entry and `logs/progress/2026-02-28-ui-gb-only-display.md` contains clean evidence text.
