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

## 2026-03-05T20:53:29Z
- Mistake: Applied a broad country-code replacement across tests, which temporarily produced invalid expectations (for example duplicated TW tokens in CLI parsing expectations) and required cleanup.
- Root cause: Used a coarse scripted search/replace before narrowing replacements to per-test semantics and invariant expectations.
- Corrective action: Reworked affected test assertions manually to preserve intended behavior while enforcing TW-only country scope, then re-ran focused suites and `make verify-dev`.
- Prevention rule: Avoid global semantic replacements in tests for logic-bearing values; run scoped replacements and immediately validate each touched test file.
- Verification evidence: `pytest -q tests/unit/test_agent_cli.py tests/unit/test_ingest_normalize.py tests/unit/test_country_mask.py tests/unit/test_facility_density_adaptive.py tests/unit/test_invariants.py tests/golden/test_golden_regression.py` and `make verify-dev` pass.

## 2026-03-06T08:03:53Z
- Mistake: Used an unquoted heredoc while appending markdown to progress log, which caused backtick command substitution and malformed log text.
- Root cause: I wrote markdown with inline code fences in a shell context that still allowed interpolation.
- Corrective action: Preserved the original entry, then appended corrected progress-log entries using single-quoted heredocs and explicit verification.
- Prevention rule: For log markdown appends, always use single-quoted heredoc delimiters () when content may include backticks.
- Verification evidence: logs/progress/2026-03-06-tw-osm-roads-railways-prune.md now includes corrected follow-up entries with intact inline code.

## 2026-03-06T08:22:37Z
- Mistake: Appended progress-log markdown using a double-quoted shell command containing backticks, which triggered unintended command substitution and malformed evidence text.
- Root cause: I used an unsafe shell append pattern for markdown content with inline code formatting.
- Corrective action: Preserved the malformed entry and appended a corrected follow-up entry using a single-quoted heredoc.
- Prevention rule: For progress-log markdown appends, always use single-quoted heredocs and avoid backticks in double-quoted shell strings.
- Verification evidence: logs/progress/2026-03-06-ui-osm-overlay-rail-motorway-trunk.md includes a corrective append entry after the malformed line.

## 2026-03-06T08:27:41Z
- Mistake: Attempted to parse API JSON with a piped heredoc command pattern that fed JSON into the Python interpreter source stream, causing a SyntaxError.
- Root cause: Mixed  patterns incorrectly; heredoc supplies code and ignores piped stdin semantics.
- Corrective action: Switched to  for stdin JSON parsing and reran payload verification.
- Prevention rule: When validating JSON from a pipe, use /; do not combine  with piped payload input.
- Verification evidence: successful payload check printed feature_count/available_countries/classes from  on port 8001.

## 2026-03-06T08:28:20Z
- Mistake: Previous mistake-ledger entry was malformed by shell interpolation and dropped key command text.
- Root cause: Continued use of shell-quoted markdown appends while including inline command formatting.
- Corrective action: Added this corrective append with explicit plain-text command names (curl pipe to python -c), and switched to apply_patch for future ledger edits.
- Prevention rule: For logs containing command snippets, prefer apply_patch edits over shell appends to eliminate interpolation risks.
- Verification evidence: this corrective entry preserves complete command context without missing tokens.

## 2026-03-06T20:59:53Z
- Mistake: Appended progress-log markdown with an unquoted shell heredoc containing inline code markers, which triggered command substitution and produced malformed evidence text.
- Root cause: I used an unsafe shell append pattern for markdown that contained backticks.
- Corrective action: Preserved the original append for auditability, then added a corrective append-only progress entry and switched log edits back to apply_patch.
- Prevention rule: Use apply_patch for progress and mistake logs whenever markdown includes inline code or special shell characters.
- Verification evidence: logs/progress/2026-03-06-ui-osm-transport-source-toggle.md now includes a corrective entry at 2026-03-06T20:59:53Z with intact evidence text.

## 2026-03-06T21:05:52Z
- Mistake: Ran Python bytecode compilation against a JavaScript file (`frontend/main.js`) during verification.
- Root cause: Verification command was assembled quickly and mixed file types.
- Corrective action: Re-ran `py_compile` with Python files only and continued JS validation via UI smoke tests.
- Prevention rule: Restrict `python -m py_compile` targets to `.py` files; validate frontend JS through dedicated frontend/UI checks.
- Verification evidence: `python -m py_compile src/inframap/ingest/major_road_graph.py scripts/build_major_roads_graph.py src/inframap/serve/app.py tests/unit/test_serve_osm_transport.py`; `pytest -q tests/ui/test_ui_smoke.py`.

## 2026-03-06T21:11:50Z
- Mistake: Attempted to parse piped JSON using a heredoc Python invocation, causing the JSON payload to be interpreted as Python source and fail with `SyntaxError`.
- Root cause: Mixed incompatible shell patterns (`pipe` + `python - <<'PY'`) under quick verification.
- Corrective action: Re-ran JSON validation with `python -c` reading from `sys.stdin`.
- Prevention rule: For piped JSON checks, use `python -c` or `jq`; do not combine piped payloads with heredoc Python source mode.
- Verification evidence: `curl -s 'http://127.0.0.1:8001/v1/osm/transport?...' | python -c "import json,sys; ..."` completed successfully.

## 2026-03-07T07:23:00Z
- Mistake: Appended markdown progress-log content using shell commands that allowed backtick interpolation, repeatedly corrupting progress entries.
- Root cause: Used unsafe double-quoted heredoc/command patterns instead of interpolation-safe edits while including inline code markup.
- Corrective action: Added append-only corrective entries in the affected progress log and switched log editing to `apply_patch` for this task.
- Prevention rule: For progress/mistake logs containing markdown with backticks, use `apply_patch` or single-quoted heredocs only; avoid double-quoted shell append commands.
- Verification evidence: `logs/progress/2026-03-07-adaptive-portal-graph.md` includes explicit correction entries and restored checklist snapshot.

## 2026-03-07T08:37:55Z
- Mistake: Appended markdown progress-log content via shell commands that still produced malformed entries due interpolation behavior.
- Root cause: Continued using shell append flow for markdown-heavy log updates after prior interpolation incidents.
- Corrective action: Switched this task's remaining log edits and ledger update back to apply_patch and recorded corrective append-only progress entries.
- Prevention rule: Do not use shell append commands for progress logs that include markdown formatting; use apply_patch for all such updates.
- Verification evidence: This ledger entry was added with apply_patch, and subsequent progress-log checklist updates were appended as plain text without shell-substituted fragments.

## 2026-03-07T08:56:02Z
- Mistake: Tried to append progress-log markdown using a double-quoted shell string that contained inline backticks, causing `zsh` command substitution errors.
- Root cause: I used an unsafe shell append pattern instead of interpolation-safe editing for markdown content.
- Corrective action: Re-ran the append with a single-quoted heredoc and placeholder timestamp replacement.
- Prevention rule: For markdown logs with inline code, use `apply_patch` first; if shell append is required, use single-quoted heredoc delimiters only.
- Verification evidence: `logs/progress/2026-03-07-add-primary-roads.md` now contains the corrected append entries without malformed command text.

## 2026-03-08T04:40:00Z
- Mistake: Initial empty near-occupied compaction patch removed the near-occupied veto but missed the separate empty-interior compaction cap, so the Taiwan run output did not change.
- Root cause: I focused on the `is_near_occupied` guard and overlooked that `can_compact_parent()` also capped compaction at `empty_interior_max_resolution`, which blocked the real `r5`/`r6` Taiwan case.
- Corrective action: Updated `can_compact_parent()` so enabled near-occupied compaction can merge above the normal empty-interior cap up to `facility_floor_resolution - 1`, then reran targeted tests and the Taiwan probe check.
- Prevention rule: For policy changes with multiple gating conditions, verify the full decision predicate against a real example before assuming the first edited branch is sufficient.
- Verification evidence: `python -m pytest tests/unit/test_facility_density_adaptive.py tests/unit/test_config_manifest.py tests/unit/test_invariants.py tests/golden/test_golden_regression.py::test_golden_facility_density_adaptive_v3_fixture_is_deterministic_with_valid_partition tests/integration/test_api.py`; Taiwan probe `854ba04bfffffff` now appears while child `864ba0487ffffff` no longer does.

## 2026-03-08T07:27:00Z
- Mistake: My first CSV rewrite overwrote the original two-letter `country` code column with the reverse-geocoded country name, which dropped existing data instead of preserving it.
- Root cause: I updated the row's `country` key directly before confirming whether the geocoded value should replace or coexist with the original schema field.
- Corrective action: Added a separate `country_code` column, restored `AR`/`TW` there, and kept reverse-geocoded country names in `country`.
- Prevention rule: Before writing enrichment data back to CSV, explicitly distinguish between source columns being preserved and derived columns being appended or replaced.
- Verification evidence: `artifacts/derived/2026-03-08-r7-regions-ar.csv` and `artifacts/derived/2026-03-08-r7-regions-tw.csv` now begin with `run_id,country_code,country,...,city,region`.
