from __future__ import annotations

from inframap.layers.facility_density_policies.base import FacilityDensityAdaptivePolicy
from inframap.layers.facility_density_policies.v3 import FacilityDensityAdaptiveV3Policy, _AdaptiveCoverageIndex


def build_adaptive_policy(version: str) -> FacilityDensityAdaptivePolicy:
    policies = {
        "v3": FacilityDensityAdaptiveV3Policy,
    }
    try:
        policy_cls = policies[version]
    except KeyError as exc:
        raise ValueError(f"Unsupported facility_density_adaptive version: {version}") from exc
    return policy_cls(version=version)


__all__ = [
    "FacilityDensityAdaptivePolicy",
    "FacilityDensityAdaptiveV3Policy",
    "_AdaptiveCoverageIndex",
    "build_adaptive_policy",
]
