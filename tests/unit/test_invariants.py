import h3
import pandas as pd
import pytest

from inframap.validation.invariants import run_invariants


def test_invariants_pass_for_valid_data() -> None:
    facilities = pd.DataFrame(
        [
            {"facility_id": "f1", "lat": 41.0, "lon": -87.0, "h3_r5": "852664c7fffffff"},
            {"facility_id": "f2", "lat": 40.0, "lon": -88.0, "h3_r5": "85266437fffffff"},
        ]
    )
    layer_artifacts = {
        "metro_density_core": {
            "metadata": {"layer_name": "metro_density_core", "layer_version": "m1", "seed_cell": "852664c7fffffff"},
            "cells": pd.DataFrame(
                [{"h3": "852664c7fffffff", "resolution": 5, "layer_value": 2, "layer_id": "metro_density_core:m1"}]
            ),
        }
    }
    run_invariants(facilities, layer_artifacts, required_h3_resolutions=[5])


def test_invariants_fail_on_duplicate_facility_id() -> None:
    facilities = pd.DataFrame(
        [
            {"facility_id": "f1", "lat": 41.0, "lon": -87.0, "h3_r5": "852664c7fffffff"},
            {"facility_id": "f1", "lat": 40.0, "lon": -88.0, "h3_r5": "85266437fffffff"},
        ]
    )
    with pytest.raises(ValueError, match="facility_id"):
        run_invariants(facilities, {}, required_h3_resolutions=[5])


def test_invariants_pass_for_adaptive_mixed_resolution_partition_without_overlap() -> None:
    base = h3.latlng_to_cell(41.0, -87.0, 9)
    child = sorted(h3.cell_to_children(base, 10))[0]
    sibling = sorted(h3.cell_to_children(base, 10))[1]

    facilities = pd.DataFrame(
        [
            {"facility_id": "f1", "lat": 41.0, "lon": -87.0, "h3_r5": "852664c7fffffff"},
            {"facility_id": "f2", "lat": 42.0, "lon": -88.0, "h3_r5": "85266437fffffff"},
        ]
    )
    layer_artifacts = {
        "facility_density_adaptive": {
            "metadata": {
                "layer_name": "facility_density_adaptive",
                "layer_version": "v2",
                "policy_name": "facility_hierarchical_partition_v2",
                "coverage_domain": "country_mask_r4",
            },
            "cells": pd.DataFrame(
                [
                    {
                        "h3": child,
                        "resolution": 10,
                        "layer_value": 1,
                        "layer_id": "facility_density_adaptive:v2",
                    },
                    {
                        "h3": sibling,
                        "resolution": 10,
                        "layer_value": 1,
                        "layer_id": "facility_density_adaptive:v2",
                    },
                ]
            ),
        }
    }
    run_invariants(facilities, layer_artifacts, required_h3_resolutions=[5])


def test_invariants_fail_on_adaptive_ancestor_descendant_overlap() -> None:
    parent = h3.latlng_to_cell(41.0, -87.0, 9)
    child = sorted(h3.cell_to_children(parent, 10))[0]

    facilities = pd.DataFrame(
        [
            {"facility_id": "f1", "lat": 41.0, "lon": -87.0, "h3_r5": "852664c7fffffff"},
            {"facility_id": "f2", "lat": 42.0, "lon": -88.0, "h3_r5": "85266437fffffff"},
        ]
    )
    layer_artifacts = {
        "facility_density_adaptive": {
            "metadata": {
                "layer_name": "facility_density_adaptive",
                "layer_version": "v2",
                "policy_name": "facility_hierarchical_partition_v2",
                "coverage_domain": "country_mask_r4",
            },
            "cells": pd.DataFrame(
                [
                    {
                        "h3": parent,
                        "resolution": 9,
                        "layer_value": 1,
                        "layer_id": "facility_density_adaptive:v2",
                    },
                    {
                        "h3": child,
                        "resolution": 10,
                        "layer_value": 1,
                        "layer_id": "facility_density_adaptive:v2",
                    },
                ]
            ),
        }
    }
    with pytest.raises(ValueError, match="ancestor|descendant|overlap|partition"):
        run_invariants(facilities, layer_artifacts, required_h3_resolutions=[5])
