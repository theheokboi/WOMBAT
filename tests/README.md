# Test Tiers

- `make verify-dev` / `make verify-fast`: fastest local smoke gate
- `make verify-ui`: UI shell smoke only
- `make verify-full`: broader regression suite
- `make verify-experimental`: perf and property checks

## Intent

- `tests/unit/`: narrow behavior and contract checks
- `tests/integration/`: publish, API, and lightweight end-to-end smoke
- `tests/ui/`: static shell and route smoke
- `tests/perf/`: non-default performance checks
- `tests/property/`: non-default broader invariants

The default gate should stay cheap enough for routine iteration.
