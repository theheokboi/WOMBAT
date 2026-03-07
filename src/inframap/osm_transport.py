from __future__ import annotations

# Single source for mainline classes used across ingest and serve.
MAINLINE_ROAD_CLASSES: tuple[str, ...] = ("motorway", "trunk", "secondary")
MAINLINE_ROAD_CLASS_SET = frozenset(MAINLINE_ROAD_CLASSES)
