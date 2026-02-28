from pathlib import Path

import pandas as pd

from inframap.ingest.pipeline import ingest_and_normalize, write_canonical_outputs


def test_writes_canonical_parquet_outputs(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/facilities_small.csv")
    facilities, organizations, invalid_count = ingest_and_normalize(
        [(fixture, "fixture")], canonical_h3_resolutions=[5, 7]
    )
    assert invalid_count == 0

    out_dir = tmp_path / "canonical"
    write_canonical_outputs(out_dir, facilities, organizations)

    facilities_path = out_dir / "facilities.parquet"
    organizations_path = out_dir / "organizations.parquet"
    assert facilities_path.exists()
    assert organizations_path.exists()

    loaded = pd.read_parquet(facilities_path)
    assert len(loaded) == 3
    assert loaded["h3_r5"].notnull().all()
    assert loaded["h3_r7"].notnull().all()
