from __future__ import annotations

from typing import Any, Protocol

import pandas as pd


class FacilityDensityAdaptivePolicy(Protocol):
    version: str

    def spec(self) -> dict[str, Any]:
        ...

    def compute(
        self, canonical_store: dict[str, pd.DataFrame], layer_store: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        ...

