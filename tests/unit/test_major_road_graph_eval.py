from __future__ import annotations

import json
from pathlib import Path

from inframap.ingest.major_road_graph_eval import evaluate_graph_variant_pair


def _edge_feature(u: int, v: int, coords: list[list[float]]) -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {
            "u": u,
            "v": v,
            "road_class": "motorway",
            "edge_id": f"e-{u}-{v}",
        },
    }


def _write_edges(path: Path, features: list[dict[str, object]]) -> None:
    payload = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_evaluate_graph_variant_pair_reports_no_shortcuts_when_chain_contraction_preserves_paths(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.geojson"
    collapsed_path = tmp_path / "collapsed.geojson"

    _write_edges(
        raw_path,
        [
            _edge_feature(1, 2, [[0.0, 0.0], [1.0, 0.0]]),
            _edge_feature(2, 3, [[1.0, 0.0], [2.0, 0.0]]),
            _edge_feature(3, 4, [[2.0, 0.0], [3.0, 0.0]]),
            _edge_feature(3, 5, [[2.0, 0.0], [2.0, 1.0]]),
        ],
    )
    _write_edges(
        collapsed_path,
        [
            _edge_feature(1, 3, [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]),
            _edge_feature(3, 4, [[2.0, 0.0], [3.0, 0.0]]),
            _edge_feature(3, 5, [[2.0, 0.0], [2.0, 1.0]]),
        ],
    )

    report = evaluate_graph_variant_pair(raw_path, collapsed_path, max_pairs=16, ratio_tolerance=0.02)

    assert report["raw"]["edge_count"] == 4
    assert report["collapsed"]["edge_count"] == 3
    assert report["comparison"]["edge_reduction_ratio"] == 0.25
    assert report["comparison"]["sample_pairs_evaluated"] > 0
    assert report["comparison"]["shortcut_pairs"] == 0
    assert report["comparison"]["detour_pairs"] == 0
    assert report["comparison"]["reachability_preserved_for_sample_pairs"] is True


def test_evaluate_graph_variant_pair_flags_shortcuts_when_collapsed_graph_cuts_path_length(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.geojson"
    collapsed_path = tmp_path / "collapsed.geojson"

    _write_edges(
        raw_path,
        [
            _edge_feature(1, 2, [[0.0, 0.0], [1.0, 0.0]]),
            _edge_feature(2, 3, [[1.0, 0.0], [2.0, 0.0]]),
        ],
    )
    _write_edges(
        collapsed_path,
        [
            _edge_feature(1, 3, [[0.0, 0.0], [0.5, 0.0]]),
        ],
    )

    report = evaluate_graph_variant_pair(raw_path, collapsed_path, max_pairs=8, ratio_tolerance=0.02)

    assert report["comparison"]["sample_pairs_evaluated"] == 1
    assert report["comparison"]["shortcut_pairs"] == 1
    assert report["comparison"]["detour_pairs"] == 0
    assert report["comparison"]["path_length_ratio_min"] < 1.0
