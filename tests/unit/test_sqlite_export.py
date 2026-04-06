from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from inframap.ingest.pipeline import ingest_and_normalize, write_facilities_sqlite_output


def test_write_facilities_sqlite_output_writes_expected_schema(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/facilities_small.csv")
    facilities, _, invalid_count = ingest_and_normalize(
        [(fixture, "fixture")],
        canonical_h3_resolutions=[5, 7],
    )
    assert invalid_count == 0

    output_path = tmp_path / "facilities.sqlite"
    write_facilities_sqlite_output(output_path, facilities)

    assert output_path.exists()
    with sqlite3.connect(output_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(facilities)").fetchall()]
        rows = conn.execute(
            "SELECT facility_id, org_name, source_name, city, state, country FROM facilities ORDER BY facility_id"
        ).fetchall()

    assert columns == [
        "facility_id",
        "org_id",
        "org_name",
        "source_name",
        "source_facility_name",
        "lat",
        "lon",
        "city",
        "state",
        "country",
        "asof_date",
    ]
    assert len(rows) == 3


def test_export_facilities_sqlite_script_uses_configured_inputs(tmp_path: Path) -> None:
    facilities_path = tmp_path / "peeringdb_facility.tsv"
    facilities_path.write_text(
        "id\tname\torg_id\tcity\tstate\tcountry\tlatitude\tlongitude\tupdated\n"
        "19\tCoreSite LA1\t34\tLos Angeles\tCA\tUS\t34.047942\t-118.255564\t2025-09-26 22:42:05.000000 +00:00\n",
        encoding="utf-8",
    )

    landing_points_path = tmp_path / "std_landing_points.tsv"
    landing_points_path.write_text(
        "city_name\tstate_province\tcountry\tlatitude\tlongitude\tstandard_city\tstandard_state\tstandard_country\tstandard_latitude\tstandard_longitude\tasof_date\n"
        "Changi South\t\tSingapore\t1.3890448\t103.987015\tSingapore\t\tSG\t1.2930335\t103.85582\t2022-09-14\n",
        encoding="utf-8",
    )

    datacenters_path = tmp_path / "datacenters_geocoded.tsv"
    datacenters_path.write_text(
        "id\tsource_country_key\tsource_region_key\tdatacenter_name\taddress\tsource_path\tlatitude\tlongitude\textracted_at\n"
        "11\tindia\tbangalore\tMicronova Data Center\t#17, Bull Temple Road\thttps://www.datacentermap.com/india/bangalore/micronova-infotex/\t12.9474019\t77.5679723\t2026-03-09 11:32:36.204592 +00:00\n",
        encoding="utf-8",
    )

    system_config_path = tmp_path / "system.yaml"
    system_config_path.write_text(
        "\n".join(
            [
                "config_version: 1",
                "allowed_h3_resolutions: [2, 4, 5, 6, 7, 8, 9]",
                "canonical_h3_resolutions: [4, 5, 7]",
                "country_mask_resolution: 2",
                "zoom_to_h3_resolution: {0: 4}",
                "ui:",
                "  center: [-98.5795, 39.8283]",
                "  zoom: 2",
                "  drilldown_resolution: 7",
                "inputs:",
                f"  - path: {facilities_path}",
                "    source_name: PeeringDB",
                f"  - path: {landing_points_path}",
                "    source_name: LandingPoints",
                f"  - path: {datacenters_path}",
                "    source_name: DataCenterMap",
                "paths:",
                "  runs_root: data/runs",
                "  staging_root: data/staging",
                "  published_root: data/published",
            ]
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "facilities.sqlite"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_facilities_sqlite.py",
            "--system-config",
            str(system_config_path),
            "--output",
            str(output_path),
        ],
        cwd=Path.cwd(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert output_path.exists()
    assert result.stdout.strip() == str(output_path)
    with sqlite3.connect(output_path) as conn:
        counts = conn.execute(
            "SELECT source_name, COUNT(*) FROM facilities GROUP BY source_name ORDER BY source_name"
        ).fetchall()

    assert counts == [
        ("DataCenterMap", 1),
        ("LandingPoints", 1),
        ("PeeringDB", 1),
    ]
