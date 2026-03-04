# Next Steps (Handoff)

1. Improve world-scale country rendering performance.
- Evaluate server-side simplification/tiling for `/v1/layers/country_mask/cells` to avoid large full-GeoJSON payloads.

2. Add explicit country inclusion/exclusion policy docs.
- Document handling of territories, disputed areas, and default include/exclude sets (currently excludes `AQ`).

3. Add integration test coverage for antimeridian rendering edge cases.
- Assert no cross-world line artifacts for H3 cell polygons near the dateline.

4. Add UI legend for country color semantics.
- Explain that colors are deterministic graph-color classes, not categorical geopolitical groupings.

5. Add API metadata endpoint details in docs.
- Document `country_color_palette` and `country_color_map` expectations in layer metadata docs.

6. Consider zoom-adaptive country layer display.
- Use lower-opacity/fewer outlines at global view and richer outlines at regional zooms.

7. Optional: publish a stable handoff snapshot commit.
- Include updated docs, logs, and screenshot artifacts for reproducible transfer.
