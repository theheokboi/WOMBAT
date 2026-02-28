from __future__ import annotations

from statistics import median
from typing import Final

_FEATURE_KEYS: Final[tuple[str, ...]] = (
    "facilities",
    "domain_r4_cell_count",
    "adaptive_leaf_count",
    "smoothing_iterations",
    "adjacency_checks",
)

_RUNTIME_KEYS: Final[tuple[str, ...]] = (
    "runtime_seconds",
    "elapsed_seconds",
    "total_runtime_seconds",
    "seconds",
)

# Stable hand-tuned weights so each feature contributes at a similar order of magnitude.
_WEIGHTS: Final[dict[str, float]] = {
    "facilities": 1.0,
    "domain_r4_cell_count": 8.0,
    "adaptive_leaf_count": 4.0,
    "smoothing_iterations": 200.0,
    "adjacency_checks": 0.05,
}

_FALLBACK_SECONDS_PER_POINT: Final[float] = 0.02


def _as_non_negative_float(payload: dict, key: str) -> float:
    value = float(payload.get(key, 0.0))
    return value if value > 0.0 else 0.0


def _complexity_score(payload: dict) -> float:
    return sum(_as_non_negative_float(payload, key) * _WEIGHTS[key] for key in _FEATURE_KEYS)


def _extract_runtime_seconds(payload: dict) -> float | None:
    for key in _RUNTIME_KEYS:
        if key in payload:
            value = float(payload[key])
            if value > 0.0:
                return value
    return None


def _round_seconds(value: float) -> int:
    return max(1, int(round(value)))


def estimate_world_runtime(calibration_reports: list[dict], world_driver_snapshot: dict) -> dict:
    world_score = _complexity_score(world_driver_snapshot)

    seconds_per_point_samples: list[float] = []
    for report in calibration_reports:
        runtime_seconds = _extract_runtime_seconds(report)
        score = _complexity_score(report)
        if runtime_seconds is None or score <= 0.0:
            continue
        seconds_per_point_samples.append(runtime_seconds / score)

    sample_count = len(seconds_per_point_samples)
    if sample_count == 0:
        center_seconds = max(1.0, world_score * _FALLBACK_SECONDS_PER_POINT)
    else:
        center_seconds = max(1.0, median(seconds_per_point_samples) * world_score)

    if sample_count == 1:
        band = 0.40
    elif sample_count >= 3:
        band = 0.20
    else:
        band = 0.30

    typical_min = _round_seconds(center_seconds * (1.0 - band))
    typical_max = _round_seconds(center_seconds * (1.0 + band))
    if typical_max < typical_min:
        typical_max = typical_min

    slow_path_max = _round_seconds(center_seconds * (1.0 + (2.0 * band)))
    if slow_path_max < typical_max:
        slow_path_max = typical_max

    return {
        "sample_count": sample_count,
        "estimated_seconds_typical_min": typical_min,
        "estimated_seconds_typical_max": typical_max,
        "estimated_seconds_slow_path_max": slow_path_max,
        "uncertainty_band": round(band, 2),
        "method_summary": (
            "feature-weighted runtime scaling via median seconds-per-complexity-point; "
            f"band=+/-{int(band * 100)}%"
        ),
    }
