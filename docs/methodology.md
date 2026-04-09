# Methodology

This project implements a geometry-first, reproducible pipeline for infrastructure mapping using the H3 hierarchical hexagonal grid. The method integrates several geocoded infrastructure datasets, constrains analysis to authoritative country polygons, converts point observations into a mixed-resolution spatial partition, and publishes immutable run artifacts that can be served through an API or exported as static assets. This document is written to stand on its own and is intended for direct sharing with collaborators who do not have access to the source code.

## 1. Overview of the Method

The workflow has five major stages:

1. Collect and normalize geocoded infrastructure point datasets.
2. Construct a country coverage mask from polygon geometry.
3. Generate an adaptive H3 representation of infrastructure density within that mask.
4. Derive region-like connected components from the finest relevant adaptive cells.
5. Publish the resulting artifacts with run-level reproducibility metadata.

The central design principle is that geometry is authoritative. Spatial membership is determined from coordinates and country polygons, not from free-text place labels. A facility is included in a country-scoped run because its coordinates fall inside the geometry-backed coverage domain, not because its row contains a matching country string.

## 2. Datasets

### 2.1 Infrastructure point datasets

The current system uses three geocoded point datasets:

- PeeringDB facility data
- standardized submarine cable landing-point data
- geocoded datacenter data

In the current workspace, these datasets contain 6,322 PeeringDB facility rows, 1,377 landing-point rows, and 12,079 datacenter rows. Each row is treated as a point observation with latitude and longitude in WGS84 coordinates.

The three sources are conceptually complementary:

- PeeringDB contributes carrier-neutral and interconnection facility locations.
- Landing-point data contributes coastal infrastructure relevant to international connectivity.
- Datacenter data contributes commercial compute and colocation locations.

Although these datasets include textual metadata such as city, state, and country names, those fields are treated only as descriptive labels. They are not used as the authoritative basis for spatial inclusion.

### 2.2 Country geometry datasets

Country scope is defined by country polygon files stored as GeoJSON. A run may target one or more countries. For each selected country, the method loads the corresponding polygon geometry and converts it into an H3-based country mask. In the default checked-in configuration, the active country set includes Argentina, Great Britain, Japan, Taiwan, and South Africa, although the pipeline can be rerun for different country selections.

### 2.3 Auxiliary datasets

The repository also includes auxiliary reference datasets for serving and visualization, such as populated places and OpenStreetMap-derived transport overlays. These are useful for contextual maps and qualitative inspection, but they are not the primary data source for the adaptive facility-density algorithm.

## 3. Software and Computational Environment

The method is implemented in Python and uses a small set of standard geospatial and data-processing libraries:

- `pandas` for tabular transformation and aggregation
- `h3` for hierarchical hexagonal indexing and neighborhood traversal
- `shapely` for polygon processing and intersection tests
- `pyarrow` for Parquet storage
- `FastAPI` for serving published artifacts through a local API

The project is operated in a development-first workflow. The intended execution loop is:

- run the pipeline
- serve the latest published outputs locally
- inspect the browser UI if needed
- run a lightweight verification tier

This matters for the methodology because the system is designed for rapid spatial iteration rather than a heavyweight production deployment workflow.

## 4. Canonical Data Construction

The first substantive stage is canonicalization of the infrastructure inputs.

### 4.1 Input harmonization

The pipeline accepts comma-separated or tab-separated files. It supports both a generic canonical schema and source-specific schemas for the three maintained input datasets. Rather than forcing all data providers to emit identical source files, the method uses explicit normalization rules for each known dataset.

Conceptually, each raw row is rewritten into a canonical facility record with these fields:

- organization identity
- facility or node name
- latitude and longitude
- optional textual location labels
- source provenance
- as-of date

This normalization step makes heterogeneous datasets comparable without discarding their provenance.

### 4.2 Validation

Rows are rejected if they:

- lack required values
- contain invalid numeric fields
- fall outside the valid latitude-longitude range

This produces a fail-closed ingest stage. Invalid records are counted and reported, but they are not allowed to silently enter downstream layers.

### 4.3 Stable identifiers and provenance retention

Each accepted row receives deterministic identifiers:

- an organization identifier
- a facility identifier
- a record hash

These identifiers are derived from normalized content, so repeated runs over unchanged inputs produce the same identities. Provenance is retained directly in each row, including source name, original facility name, as-of date, and textual location labels.

### 4.4 H3 enrichment and deduplication

After normalization, each facility point is converted into H3 cells at a predefined set of resolutions. This gives the pipeline a stable spatial index that can support both fixed-resolution and adaptive-resolution processing.

Duplicate facilities are resolved deterministically. Records are sorted in a stable order and deduplicated by facility identity so that repeated runs over the same inputs yield the same canonical output tables.

The result of this stage is a canonical facilities table and a companion organizations table.

## 5. Reproducibility Backbone

Every run records four mandatory reproducibility fields:

- `run_id`
- `inputs_hash`
- `config_hash`
- `code_hash`

These fields are used to guarantee that the published outputs can be tied to a specific combination of:

- input data contents
- configuration state
- source-code state

The run identifier is derived deterministically from these hashes. As a result, if the inputs, configuration, and code are unchanged, the run identity remains stable. If any of them change, the run identity changes as well.

Published run directories are immutable once promoted. Instead of mutating previous outputs, the system publishes a new run and updates a lightweight pointer to indicate which run is currently active.

## 6. Country Mask Construction

Before infrastructure density is estimated, the method constructs a country coverage mask.

### 6.1 Purpose

The country mask defines the valid spatial domain for analysis. It answers the question: which H3 cells belong to the country scope of the current run?

This is important because the adaptive density algorithm should not create coverage outside the intended country geometry, and it should not decide spatial membership from textual attributes in facility rows.

### 6.2 Construction logic

Country polygons are converted into H3 coverage cells. The implementation supports both:

- a fixed-resolution approach, where coverage is evaluated at one chosen H3 level
- a quadtree-like classify-and-split approach, where ambiguous cells can be refined recursively

In the default configuration, the country mask is generated at a fixed H3 resolution. The output is a table of country-associated H3 cells with country identifiers and display metadata.

### 6.3 Role in downstream processing

The country mask is the coverage authority for the adaptive layer. Downstream algorithms are required to derive their spatial domain from this mask rather than recomputing country membership independently.

## 7. Core Algorithm: Adaptive H3 Facility Density

The central algorithm produces a mixed-resolution H3 representation of infrastructure density within the country mask.

### 7.1 Motivation

A single fixed H3 resolution creates an undesirable tradeoff:

- coarse resolutions obscure dense urban clusters
- fine resolutions over-fragment sparse areas and inflate output size

The adaptive method addresses this by refining dense or topologically sensitive areas while keeping sparse interiors coarse.

### 7.2 Inputs

The adaptive algorithm consumes two authoritative inputs:

- the canonical facilities table
- the country mask layer

The country mask determines where output is allowed to exist. The facilities determine where refinement is justified.

### 7.3 Output

The output is a leaf set of H3 cells with mixed resolutions. Each output row contains:

- the H3 cell ID
- its resolution
- a layer value, interpreted here as facility count in that leaf
- layer identity metadata
- an as-of date

The output is mixed-resolution but non-overlapping. In other words, the final leaf set is a partition: no cell in the output is allowed to coexist with one of its descendants.

## 8. Adaptive Algorithm in Detail

### 8.1 Stage 1: Normalize the coverage domain

The country mask may already contain cells at different resolutions. The algorithm first converts that mask into a uniform base-resolution domain:

- cells coarser than the base resolution are expanded downward
- cells finer than the base resolution are rolled up to their base parent
- cells already at the base resolution are preserved

This yields a single working domain over which facility counts can be computed consistently.

### 8.2 Stage 2: Precompute facility counts across resolutions

Each facility is assigned to H3 cells at every working resolution from the base resolution to the maximum adaptive resolution. Only facilities whose base-resolution cell lies inside the coverage domain are retained for the current country run.

For each resolution, the algorithm builds a count table mapping H3 cells to facility counts. This allows the recursion step to inspect local occupancy at multiple scales without recomputing point-to-cell assignments repeatedly.

### 8.3 Stage 3: Recursive partitioning

The initial adaptive output is constructed recursively from coarse cells toward finer cells.

#### Occupied cells

If a cell contains one or more facilities, the algorithm decides whether to stop or split based on two ideas:

- a floor resolution below which occupied cells should generally not remain coarse
- a density threshold that determines whether a cell is too crowded and should be split further

Dense occupied cells keep refining until either their local facility count falls below the target count per leaf or the configured maximum resolution is reached.

Sparse occupied cells stop earlier. In the refined `v4` policy, sparse occupied branches are allowed to stop at a resolution slightly coarser than the original occupied floor when that branch is isolated and no neighboring condition forces further refinement. This produces more compact outputs in sparse regions without sacrificing the refinement of dense clusters.

#### Empty cells

If a cell contains no facilities, it may still need to split for structural reasons. The algorithm refines empty cells when any of the following are true:

- the hierarchy requires refinement to connect coarse coverage to the active base resolution
- the cell is below the minimum output resolution
- the cell lies near a country boundary
- the cell lies near occupied cells and therefore affects topology

Empty interior cells that are far from boundaries and occupied branches are capped at a coarse maximum resolution.

### 8.4 Stage 4: Neighbor smoothing

Recursive splitting alone can create abrupt jumps where a very coarse cell borders a much finer cell. These jumps can make the output harder to interpret visually and structurally.

To address this, the algorithm enforces a maximum allowed resolution difference between neighboring leaves. It inspects adjacency relationships on the H3 grid and identifies violating pairs. When a violation is found, the coarser side is refined, and the check is repeated.

This smoothing pass is not cosmetic. It is treated as a hard structural postcondition. If the algorithm cannot eliminate excessive neighbor resolution jumps, the run is considered invalid.

### 8.5 Stage 5: Post-compaction

After smoothing, the algorithm attempts to merge eligible sibling leaves back into their parent when doing so does not break any structural guarantee.

This compaction stage is conservative:

- it must preserve domain validity
- it must preserve the neighbor-resolution constraint
- it must respect boundary-sensitive and near-occupied topology rules

In the `v4` policy, compaction is restricted to empty sibling groups. Occupied singleton compaction is disabled to avoid collapsing sparse occupied structures below their intended adaptive resolution.

### 8.6 Stage 6: Final geometry filter

As a final safeguard, the algorithm reloads the country polygons and drops any emitted H3 cell that has zero overlap with the country geometry. This ensures that the final adaptive output remains faithful to the country mask even after recursive splitting, smoothing, and compaction.

## 9. Derived Regionalization

The method includes a derived layer that operates on the adaptive output at H3 resolution 7.

This layer:

- extracts the resolution-7 cells from the adaptive result
- finds connected components on the H3 grid
- assigns each component a deterministic cluster identifier
- chooses a representative cluster location

This step is better understood as region extraction than as a new density model. It groups adjacent adaptive cells into region-like units that can support route overlays, summary views, or regional reporting.

## 10. Publication and Serving

After all layers are computed, the run artifacts are written to a staging area and then published atomically. Publication consists of:

- moving the staged run into an immutable run directory
- updating a development pointer to the latest run
- maintaining a compatibility alias for consumers expecting a generic latest pointer

The published artifacts can then be accessed in three ways:

- as Parquet layer outputs inside the run directory
- through a local read-only API
- through export scripts that create a SQLite copy of facilities or a static demo bundle for browser-only use

## 11. Validation Strategy

The method is supported by a layered testing strategy.

### 11.1 Unit and contract tests

Unit tests verify:

- schema adapters for each input dataset
- invalid-record rejection
- deterministic deduplication
- manifest determinism
- country-mask behavior
- adaptive algorithm behavior, including the `v4` sparse-branch changes
- structural invariants such as non-overlap and valid neighbor smoothing

### 11.2 Integration tests

Integration tests verify:

- atomic publication semantics
- API smoke behavior
- run metadata availability

### 11.3 Property and performance tests

Non-default property and performance tests provide additional monitoring for determinism, contiguity, and runtime behavior.

### 11.4 Structural invariants

The adaptive output must satisfy several invariants:

- no duplicate H3 cells
- no ancestor-descendant overlap in the final leaf set
- valid H3 resolution encoding
- non-negative facility counts
- bounded resolution difference between neighboring leaves

These invariants are critical to downstream interpretation and are treated as part of the algorithmic contract.

## 12. Recommended Paper Structure

For a formal methodology section, the material in this document can be presented in the following order:

1. Data sources
2. Canonicalization and preprocessing
3. Country-mask construction
4. Adaptive H3 partition algorithm
5. Derived regionalization layer
6. Reproducibility and publication
7. Validation and test strategy

If the paper needs a shorter version, Sections 2 through 8 can be condensed into three subsections:

- Datasets and preprocessing
- Adaptive spatial partitioning algorithm
- Reproducibility and validation

## 13. Short Academic Summary

In one sentence, the method can be summarized as follows:

The project constructs a reproducible, country-constrained, mixed-resolution H3 representation of digital infrastructure by normalizing multiple geocoded point datasets, deriving a geometry-backed coverage mask, recursively refining occupied and topologically sensitive regions, smoothing neighbor resolution jumps, conservatively compacting empty structure, and publishing immutable run artifacts with explicit reproducibility hashes.
