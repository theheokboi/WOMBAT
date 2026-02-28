# Task F: Adaptive v3 README Docs

## Checklist
- [x] Confirm current adaptive layer contract and v3 behavior from repo config/tests.
- [x] Update `README.md` to describe adaptive `v3` behavior (coarse interior, detailed boundary/near-occupied, smoothing).
- [x] Add migration guidance from `v2` to `v3` in `README.md`.
- [x] Review docs scope (`AGENTS.md`) and confirm no change required.
- [x] Run mistake replay check against `logs/mistakes.md` before handoff.

## 2026-02-28T05:36:52Z
- Status: in progress
- Checklist item: Confirm current adaptive layer contract and v3 behavior from repo config/tests.
- Update: Started Task F and gathered baseline context from `README.md`, `configs/layers.yaml`, and adaptive/config tests to verify repository now targets adaptive `v3` params.
- Evidence: `rg -n "facility_density_adaptive|v3|empty_interior_max_resolution|max_neighbor_resolution_delta" README.md configs tests src -S`
- Next: Update `README.md` v2 references to v3 behavior and add migration note.

## 2026-02-28T05:38:41Z
- Status: in progress
- Checklist item: Update `README.md` to describe adaptive `v3` behavior (coarse interior, detailed boundary/near-occupied, smoothing).
- Update: Edited `README.md` to document v3 behavior in bootstrap summary, API note, run artifact path, and migration section.
- Evidence: `README.md`
- Next: Finalize migration bullets and record docs/mistake checks.

## 2026-02-28T05:39:27Z
- Status: complete
- Checklist item: Run mistake replay check against `logs/mistakes.md` before handoff.
- Update: Confirmed no repeat of logged mistakes (no external runtime dependency introduced; no adaptive algorithm implementation change). Docs check complete: `AGENTS.md` unchanged because task scope is README-only and no workflow/contract/tooling change beyond adaptive version documentation refresh.
- Evidence: `logs/mistakes.md`, `README.md`
- Next: Handoff with changed files summary.

## 2026-02-28T05:41:36Z
- Status: complete
- Checklist item: Add migration guidance from `v2` to `v3` in `README.md`.
- Update: Created required git checkpoint commit for this non-trivial docs task.
- Evidence: `git commit` -> `d688a17` (`docs: update README for adaptive v3 behavior and migration`)
- Next: Final handoff.
