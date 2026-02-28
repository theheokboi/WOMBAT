from __future__ import annotations

from inframap.agent.runtime_estimator import estimate_world_runtime


def _report(
    *,
    facilities: int,
    domain_r4_cell_count: int,
    adaptive_leaf_count: int,
    smoothing_iterations: int,
    adjacency_checks: int,
    runtime_seconds: int,
) -> dict:
    return {
        "facilities": facilities,
        "domain_r4_cell_count": domain_r4_cell_count,
        "adaptive_leaf_count": adaptive_leaf_count,
        "smoothing_iterations": smoothing_iterations,
        "adjacency_checks": adjacency_checks,
        "runtime_seconds": runtime_seconds,
    }


def _world_snapshot() -> dict:
    return {
        "facilities": 180,
        "domain_r4_cell_count": 90,
        "adaptive_leaf_count": 240,
        "smoothing_iterations": 3,
        "adjacency_checks": 1600,
    }


def test_one_sample_output_validity_and_wide_band() -> None:
    result = estimate_world_runtime(
        calibration_reports=[
            _report(
                facilities=120,
                domain_r4_cell_count=60,
                adaptive_leaf_count=180,
                smoothing_iterations=2,
                adjacency_checks=1200,
                runtime_seconds=300,
            )
        ],
        world_driver_snapshot=_world_snapshot(),
    )

    assert result["sample_count"] == 1
    assert result["uncertainty_band"] == 0.40
    assert isinstance(result["estimated_seconds_typical_min"], int)
    assert isinstance(result["estimated_seconds_typical_max"], int)
    assert result["estimated_seconds_typical_min"] > 0
    assert result["estimated_seconds_typical_max"] >= result["estimated_seconds_typical_min"]
    assert result["estimated_seconds_slow_path_max"] >= result["estimated_seconds_typical_max"]


def test_three_samples_use_reduced_band() -> None:
    result = estimate_world_runtime(
        calibration_reports=[
            _report(
                facilities=100,
                domain_r4_cell_count=50,
                adaptive_leaf_count=140,
                smoothing_iterations=2,
                adjacency_checks=900,
                runtime_seconds=210,
            ),
            _report(
                facilities=110,
                domain_r4_cell_count=55,
                adaptive_leaf_count=155,
                smoothing_iterations=2,
                adjacency_checks=980,
                runtime_seconds=230,
            ),
            _report(
                facilities=130,
                domain_r4_cell_count=65,
                adaptive_leaf_count=175,
                smoothing_iterations=2,
                adjacency_checks=1080,
                runtime_seconds=260,
            ),
        ],
        world_driver_snapshot=_world_snapshot(),
    )

    assert result["sample_count"] == 3
    assert result["uncertainty_band"] == 0.20
    assert "+/-20%" in result["method_summary"]


def test_repeated_calls_are_deterministically_equal() -> None:
    reports = [
        _report(
            facilities=100,
            domain_r4_cell_count=50,
            adaptive_leaf_count=140,
            smoothing_iterations=2,
            adjacency_checks=900,
            runtime_seconds=210,
        ),
        _report(
            facilities=110,
            domain_r4_cell_count=55,
            adaptive_leaf_count=155,
            smoothing_iterations=2,
            adjacency_checks=980,
            runtime_seconds=230,
        ),
        _report(
            facilities=130,
            domain_r4_cell_count=65,
            adaptive_leaf_count=175,
            smoothing_iterations=2,
            adjacency_checks=1080,
            runtime_seconds=260,
        ),
    ]
    world = _world_snapshot()

    first = estimate_world_runtime(reports, world)
    second = estimate_world_runtime(reports, world)

    assert first == second
