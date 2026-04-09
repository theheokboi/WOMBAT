# Architecture

This note is the short mental model for routine development. Contract details still live in [docs/PROJECT.md](/Users/hyes92121/Desktop/h3-experiment/docs/PROJECT.md).

## Run Flow

1. `make run-dev` loads [configs/system.yaml](/Users/hyes92121/Desktop/h3-experiment/configs/system.yaml) and [configs/layers.yaml](/Users/hyes92121/Desktop/h3-experiment/configs/layers.yaml).
2. The CLI applies any runtime country selection override to `country_mask`.
3. The pipeline ingests source files, normalizes canonical facilities and organizations, and writes canonical outputs.
4. Layers run in YAML order and write run-scoped artifacts plus layer metadata.
5. The staged run is atomically published and `latest-dev` is flipped to the new immutable run.

Primary entrypoints:

- [src/inframap/agent/cli.py](/Users/hyes92121/Desktop/h3-experiment/src/inframap/agent/cli.py)
- [src/inframap/agent/runner.py](/Users/hyes92121/Desktop/h3-experiment/src/inframap/agent/runner.py)
- [src/inframap/publish/pipeline.py](/Users/hyes92121/Desktop/h3-experiment/src/inframap/publish/pipeline.py)

## Layer Dependency Chain

The default pipeline is:

`metro_density_core`
`country_mask`
`facility_density_adaptive`
`facility_density_r7_regions`

The important dependency chain is narrower:

- `country_mask` defines the coverage domain.
- `facility_density_adaptive` uses that domain plus canonical facilities to build the mixed-resolution cell output.
- `facility_density_r7_regions` derives connected r7 regions from the adaptive output.

Layer registration is driven by [src/inframap/layers/registry.py](/Users/hyes92121/Desktop/h3-experiment/src/inframap/layers/registry.py).

## Adaptive Layer Stages

The adaptive layer in [src/inframap/layers/facility_density_adaptive.py](/Users/hyes92121/Desktop/h3-experiment/src/inframap/layers/facility_density_adaptive.py) works in four stages:

1. Build the coverage domain from `country_mask`.
2. Recursively split cells under the active facility-density policy.
3. Smooth neighbor resolution jumps to satisfy `max_neighbor_resolution_delta`.
4. Compact eligible sibling groups and then filter the final output against country geometry.

Important implication:

- Geometry is authoritative.
- `country_mask` is the coverage authority.
- Adaptive output is constrained by both policy-driven density rules and geometry-backed boundary rules.
- Version-specific facility-density behavior notes live under [docs/algorithms/facility-density/README.md](/Users/hyes92121/Desktop/h3-experiment/docs/algorithms/facility-density/README.md).

Versioned algorithm notes for the facility-density behavior live under [docs/algorithms/facility-density/README.md](/Users/hyes92121/Desktop/h3-experiment/docs/algorithms/facility-density/README.md).

## Where To Look First

- Contracts: [docs/PROJECT.md](/Users/hyes92121/Desktop/h3-experiment/docs/PROJECT.md)
- Default commands: [README.md](/Users/hyes92121/Desktop/h3-experiment/README.md)
- Advanced workflows: [docs/advanced-workflows.md](/Users/hyes92121/Desktop/h3-experiment/docs/advanced-workflows.md)
- Config loading: [src/inframap/config.py](/Users/hyes92121/Desktop/h3-experiment/src/inframap/config.py)
- Tests by scope: [tests/README.md](/Users/hyes92121/Desktop/h3-experiment/tests/README.md)
