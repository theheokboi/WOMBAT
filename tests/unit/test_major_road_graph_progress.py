from __future__ import annotations

from pathlib import Path

import pytest

import inframap.ingest.major_road_graph as major_road_graph


def _edge(edge_id: str, u: int, v: int, coords: list[list[float]]) -> dict[str, object]:
    return {
        "edge_id": edge_id,
        "u": u,
        "v": v,
        "road_class": "motorway",
        "oneway": None,
        "name": "m",
        "ref": None,
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def test_build_major_road_graph_variants_emits_progress_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class FakeCollector:
        def __init__(self) -> None:
            self.shared_node_refs = {2}

        def apply_file(self, _path: str, locations: bool = False, idx: str | None = None) -> None:  # noqa: ARG002
            return

    class FakeBuilder:
        def __init__(self, shared_node_refs: set[int]) -> None:  # noqa: ARG002
            self.nodes = {
                1: (121.0, 25.0),
                2: (121.1, 25.0),
                3: (121.2, 25.0),
            }
            self.edges = [
                _edge("e1", 1, 2, [[121.0, 25.0], [121.1, 25.0]]),
                _edge("e2", 2, 3, [[121.1, 25.0], [121.2, 25.0]]),
            ]

        def apply_file(self, _path: str, locations: bool = False, idx: str | None = None) -> None:  # noqa: ARG002
            return

    monkeypatch.setattr(major_road_graph, "_SplitNodeCollector", FakeCollector)
    monkeypatch.setattr(major_road_graph, "_MajorRoadGraphBuilder", FakeBuilder)

    events: list[tuple[str, str, dict[str, object]]] = []
    outputs = major_road_graph.build_major_road_graph_variants(
        pbf_path=tmp_path / "dummy.osm.pbf",
        output_dir=tmp_path / "out",
        variants=("raw", "adaptive"),
        adaptive_resolution=2,
        progress_callback=lambda event, stage, payload: events.append((event, stage, payload)),
    )

    assert set(outputs) == {"raw", "adaptive"}
    assert [(event, stage) for event, stage, _ in events] == [
        ("phase_start", "collect_shared_nodes"),
        ("phase_end", "collect_shared_nodes"),
        ("phase_start", "build_raw_graph"),
        ("phase_end", "build_raw_graph"),
        ("phase_start", "write_raw"),
        ("phase_end", "write_raw"),
        ("phase_start", "write_adaptive"),
        ("phase_end", "write_adaptive"),
        ("done", "complete"),
    ]
    for event, _, payload in events:
        if event != "phase_end":
            continue
        assert float(payload.get("elapsed_seconds", 0.0)) >= 0.0


def test_build_major_road_graph_variants_validates_adaptive_resolution_before_write(tmp_path: Path) -> None:
    events: list[tuple[str, str]] = []
    with pytest.raises(ValueError, match="adaptive_resolution is required"):
        major_road_graph.build_major_road_graph_variants(
            pbf_path=tmp_path / "dummy.osm.pbf",
            output_dir=tmp_path / "out",
            variants=("raw", "adaptive"),
            adaptive_resolution=None,
            progress_callback=lambda event, stage, _payload: events.append((event, stage)),
        )
    assert events == []
    assert not (tmp_path / "out").exists()
