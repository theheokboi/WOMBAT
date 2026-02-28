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
