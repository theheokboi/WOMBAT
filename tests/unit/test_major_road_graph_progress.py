from __future__ import annotations

from pathlib import Path

import h3
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
    mask_cell = str(h3.latlng_to_cell(25.0, 121.1, 5))
    outputs = major_road_graph.build_major_road_graph_variants(
        pbf_path=tmp_path / "dummy.osm.pbf",
        output_dir=tmp_path / "out",
        variants=("raw", "adaptive", "adaptive_portal", "adaptive_portal_run"),
        adaptive_resolution=2,
        adaptive_mask_cells={mask_cell},
        progress_callback=lambda event, stage, payload: events.append((event, stage, payload)),
    )

    assert set(outputs) == {"raw", "adaptive", "adaptive_portal", "adaptive_portal_run"}
    assert [(event, stage) for event, stage, _ in events if event in {"phase_start", "phase_end", "done"}] == [
        ("phase_start", "collect_shared_nodes"),
        ("phase_end", "collect_shared_nodes"),
        ("phase_start", "build_raw_graph"),
        ("phase_end", "build_raw_graph"),
        ("phase_start", "write_raw"),
        ("phase_end", "write_raw"),
        ("phase_start", "write_adaptive"),
        ("phase_end", "write_adaptive"),
        ("phase_start", "write_adaptive_portal"),
        ("phase_end", "write_adaptive_portal"),
        ("phase_start", "write_adaptive_portal_run"),
        ("phase_end", "write_adaptive_portal_run"),
        ("done", "complete"),
    ]
    for event, _, payload in events:
        if event != "phase_end":
            continue
        assert float(payload.get("elapsed_seconds", 0.0)) >= 0.0
    cell_progress_updates = [
        payload
        for event, stage, payload in events
        if event == "phase_update"
        and stage == "write_adaptive_portal_run"
        and str(payload.get("step", "")) == "contract_cells_progress"
    ]
    assert cell_progress_updates
    assert all(int(payload.get("processed_cells", 0) or 0) <= int(payload.get("total_cells", 0) or 0) for payload in cell_progress_updates)


def test_build_major_road_graph_variants_validates_adaptive_resolution_before_write(tmp_path: Path) -> None:
    events: list[tuple[str, str]] = []
    with pytest.raises(ValueError, match="adaptive_resolution is required"):
        major_road_graph.build_major_road_graph_variants(
            pbf_path=tmp_path / "dummy.osm.pbf",
            output_dir=tmp_path / "out",
            variants=("raw", "adaptive_portal"),
            adaptive_resolution=None,
            progress_callback=lambda event, stage, _payload: events.append((event, stage)),
        )
    assert events == []
    assert not (tmp_path / "out").exists()


def test_build_major_road_graph_variants_validates_adaptive_mask_before_write(tmp_path: Path) -> None:
    events: list[tuple[str, str]] = []
    with pytest.raises(ValueError, match="adaptive_mask_cells is required"):
        major_road_graph.build_major_road_graph_variants(
            pbf_path=tmp_path / "dummy.osm.pbf",
            output_dir=tmp_path / "out",
            variants=("raw", "adaptive_portal_run"),
            adaptive_mask_cells=None,
            progress_callback=lambda event, stage, _payload: events.append((event, stage)),
        )
    assert events == []
    assert not (tmp_path / "out").exists()
