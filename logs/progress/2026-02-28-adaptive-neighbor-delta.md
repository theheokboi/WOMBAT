# Task Checklist
- [x] Confirm requirement and current contract for adaptive neighbor smoothing delta.
- [x] Add/adjust unit tests to capture adjacency-delta guarantee regression.
- [x] Implement minimal layer change to guarantee adjacent leaf resolution delta <= configured max.
- [x] Run focused tests for modified behavior.
- [ ] Docs check (`README.md` and `AGENTS.md`) and mistake replay check.
- [ ] Create required git checkpoint commit and record hash.

## 2026-02-28T07:23:53Z
- Status: in progress
- Checklist item: Confirm requirement and current contract for adaptive neighbor smoothing delta.
- Update: Started task scoped to `src/inframap/layers/facility_density_adaptive.py`, `tests/unit/test_facility_density_adaptive.py`, and `tests/unit/test_invariants.py`; inspected current smoothing logic and tests.
- Evidence: Read target files and ran `pytest -q tests/unit/test_facility_density_adaptive.py tests/unit/test_invariants.py` (12 passed).
- Next: Confirm contract source and reproduce an adjacency-delta counterexample.

## 2026-02-28T07:25:26Z
- Status: in progress
- Checklist item: Run focused tests for modified behavior.
- Update: Reproduced deterministic adjacency-delta counterexample, implemented minimal smoothing fix to force-refine coarse empty leaves only when required by configured neighbor delta, and added two regression tests for the dense local case.
- Evidence: `pytest -q tests/unit/test_facility_density_adaptive.py tests/unit/test_invariants.py` (14 passed).
- Next: Perform docs check, mistake replay check, and create scoped git checkpoint commit.

## 2026-02-28T07:25:47Z
- Status: in progress
- Checklist item: Docs check (`README.md` and `AGENTS.md`) and mistake replay check.
- Update: Reviewed `README.md` and `AGENTS.md`; no workflow/API/contract command changes were introduced by this fix, so docs updates are not required. Per mistake replay check, verified this change does not repeat logged mistakes (no shell backtick interpolation for logs; validated adaptive invariant behavior with focused tests).
- Evidence: Docs check: no changes required (behavior change is internal smoothing refinement to satisfy existing configured max-neighbor-delta contract). Tests: `pytest -q tests/unit/test_facility_density_adaptive.py tests/unit/test_invariants.py` (14 passed).
- Next: Create git checkpoint commit and record hash.
