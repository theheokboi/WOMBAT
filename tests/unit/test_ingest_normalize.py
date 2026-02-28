from pathlib import Path

from inframap.ingest.pipeline import ingest_and_normalize


def test_ingest_csv_and_tsv_and_required_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "a.csv"
    csv_path.write_text(
        "ORGANIZATION,NODE_NAME,LATITUDE,LONGITUDE,SOURCE,ASOF_DATE\n"
        "Org A,Node A,41.0,-87.0,fixture,2026-02-28\n",
        encoding="utf-8",
    )
    tsv_path = tmp_path / "b.tsv"
    tsv_path.write_text(
        "ORGANIZATION\tNODE_NAME\tLATITUDE\tLONGITUDE\tSOURCE\tASOF_DATE\n"
        "Org B\tNode B\t40.0\t-88.0\tfixture\t2026-02-28\n",
        encoding="utf-8",
    )

    facilities, organizations, invalid_count = ingest_and_normalize(
        [(csv_path, "fixture"), (tsv_path, "fixture")],
        canonical_h3_resolutions=[5, 7],
    )

    assert invalid_count == 0
    assert len(facilities) == 2
    assert len(organizations) == 2
    assert {"facility_id", "org_id", "record_hash", "h3_r5", "h3_r7"}.issubset(set(facilities.columns))


def test_ingest_drops_invalid_coordinates(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "ORGANIZATION,NODE_NAME,LATITUDE,LONGITUDE,SOURCE,ASOF_DATE\n"
        "Org A,Node A,91.0,-87.0,fixture,2026-02-28\n"
        "Org B,Node B,41.0,-200.0,fixture,2026-02-28\n"
        "Org C,Node C,41.0,-87.0,fixture,2026-02-28\n",
        encoding="utf-8",
    )

    facilities, organizations, invalid_count = ingest_and_normalize(
        [(path, "fixture")], canonical_h3_resolutions=[5]
    )
    assert invalid_count == 2
    assert len(facilities) == 1
    assert len(organizations) == 1


def test_ingest_deduplicates_same_facility_id(tmp_path: Path) -> None:
    path = tmp_path / "dupe.csv"
    path.write_text(
        "ORGANIZATION,NODE_NAME,LATITUDE,LONGITUDE,SOURCE,ASOF_DATE\n"
        "Org A,Node A,41.0,-87.0,fixture,2026-02-28\n"
        "Org A,Node A,41.0,-87.0,fixture,2026-02-28\n",
        encoding="utf-8",
    )
    facilities, _, invalid_count = ingest_and_normalize(
        [(path, "fixture")], canonical_h3_resolutions=[5]
    )
    assert invalid_count == 0
    assert len(facilities) == 1


def test_ingest_normalizes_peeringdb_facility_tsv_schema(tmp_path: Path) -> None:
    path = tmp_path / "peeringdb_facility.tsv"
    path.write_text(
        "id\tname\torg_id\tcity\tstate\tcountry\tlatitude\tlongitude\tupdated\n"
        "19\tCoreSite LA1\t34\tLos Angeles\tCA\tUS\t34.047942\t-118.255564\t2025-09-26 22:42:05.000000 +00:00\n",
        encoding="utf-8",
    )

    facilities, organizations, invalid_count = ingest_and_normalize(
        [(path, "PeeringDB")], canonical_h3_resolutions=[5]
    )

    assert invalid_count == 0
    assert len(facilities) == 1
    assert len(organizations) == 1
    assert facilities.iloc[0]["source_name"] == "PeeringDB"
    assert facilities.iloc[0]["source_facility_name"] == "CoreSite LA1"
    assert facilities.iloc[0]["org_name"] == "org_34"
    assert facilities.iloc[0]["asof_date"] == "2025-09-26"
