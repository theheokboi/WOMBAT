from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd


class LayerPlugin(Protocol):
    version: str

    def spec(self) -> dict[str, Any]:
        ...

    def compute(
        self, canonical_store: dict[str, pd.DataFrame], layer_store: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        ...

    def validate(self, artifacts: dict[str, Any]) -> None:
        ...


@dataclass(frozen=True)
class LayerArtifacts:
    metadata: dict[str, Any]
    cells: pd.DataFrame
