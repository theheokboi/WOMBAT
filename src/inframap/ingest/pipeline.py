from __future__ import annotations

import csv
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable

import h3
import pandas as pd

from inframap.manifest import REQUIRED_INPUT_COLUMNS


OPTIONAL_COLUMNS = ["CITY", "STATE", "COUNTRY"]


@dataclass(frozen=True)
class IngestedRecord:
    organization: str
    node_name: str
    latitude: float
    longitude: float
    city: str | None
    state: str | None
    country: str | None
    source: str
    asof_date: str


def _detect_delimiter(path: Path) -> str:
    if path.suffix.lower() == ".tsv":
        return "\t"
    return ","


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "" or stripped.upper() == "NULL":
        return None
    return stripped


def _validate_required_columns(columns: Iterable[str]) -> None:
    missing = REQUIRED_INPUT_COLUMNS - set(columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")


def _extract_asof_date(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    return cleaned[:10]


def _looks_like_peeringdb_facility_schema(columns: Iterable[str]) -> bool:
    cols = set(columns)
    required = {"name", "org_id", "latitude", "longitude", "updated"}
    return required.issubset(cols)


def _looks_like_landing_points_schema(columns: Iterable[str]) -> bool:
    cols = set(columns)
    required = {"city_name", "country", "latitude", "longitude", "asof_date"}
    return required.issubset(cols)


def _normalize_peeringdb_facility_row(
    row: dict[str, str | None], source_name: str
) -> dict[str, str | None]:
    org_id = _clean(row.get("org_id"))
    organization = _clean(row.get("org_name"))
    if not organization and org_id:
        organization = f"org_{org_id}"

    asof_date = _extract_asof_date(row.get("updated"))
    if not asof_date:
        asof_date = _extract_asof_date(row.get("created"))

    normalized: dict[str, str | None] = {
        "ORGANIZATION": organization,
        "NODE_NAME": _clean(row.get("name")),
        "LATITUDE": _clean(row.get("latitude")),
        "LONGITUDE": _clean(row.get("longitude")),
        "CITY": _clean(row.get("city")),
        "STATE": _clean(row.get("state")),
        "COUNTRY": _clean(row.get("country")),
        "SOURCE": _clean(row.get("source")) or source_name,
        "ASOF_DATE": asof_date,
    }
    return normalized


def _normalize_landing_point_row(
    row: dict[str, str | None], source_name: str
) -> dict[str, str | None]:
    node_name = _clean(row.get("city_name")) or _clean(row.get("standard_city")) or "landing_point"
    normalized: dict[str, str | None] = {
        "ORGANIZATION": "landing_points",
        "NODE_NAME": node_name,
        "LATITUDE": _clean(row.get("latitude")),
        "LONGITUDE": _clean(row.get("longitude")),
        "CITY": _clean(row.get("city_name")),
        "STATE": _clean(row.get("state_province")),
        "COUNTRY": _clean(row.get("country")),
        "SOURCE": _clean(row.get("source")) or source_name,
        "ASOF_DATE": _extract_asof_date(row.get("asof_date")),
    }
    return normalized


def _parse_file(path: Path, source_name: str) -> list[dict[str, str | None]]:
    delimiter = _detect_delimiter(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Input file has no header: {path}")
        use_peeringdb_adapter = False
        use_landing_points_adapter = False
        if REQUIRED_INPUT_COLUMNS.issubset(set(reader.fieldnames)):
            _validate_required_columns(reader.fieldnames)
        elif _looks_like_peeringdb_facility_schema(reader.fieldnames):
            use_peeringdb_adapter = True
        elif _looks_like_landing_points_schema(reader.fieldnames):
            use_landing_points_adapter = True
        else:
            _validate_required_columns(reader.fieldnames)
        rows: list[dict[str, str | None]] = []
        for row in reader:
            row = dict(row)
            if use_peeringdb_adapter:
                rows.append(_normalize_peeringdb_facility_row(row, source_name))
                continue
            if use_landing_points_adapter:
                rows.append(_normalize_landing_point_row(row, source_name))
                continue
            if not _clean(row.get("SOURCE")):
                row["SOURCE"] = source_name
            rows.append(row)
        return rows


def _try_parse_record(raw: dict[str, str | None]) -> IngestedRecord | None:
    try:
        organization = _clean(raw.get("ORGANIZATION"))
        node_name = _clean(raw.get("NODE_NAME"))
        source = _clean(raw.get("SOURCE"))
        asof_date = _clean(raw.get("ASOF_DATE"))
        if not organization or not node_name or not source or not asof_date:
            return None

        lat_text = _clean(raw.get("LATITUDE"))
        lon_text = _clean(raw.get("LONGITUDE"))
        if not lat_text or not lon_text:
            return None

        latitude = float(lat_text)
        longitude = float(lon_text)
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            return None

        return IngestedRecord(
            organization=organization,
            node_name=node_name,
            latitude=latitude,
            longitude=longitude,
            city=_clean(raw.get("CITY")),
            state=_clean(raw.get("STATE")),
            country=_clean(raw.get("COUNTRY")),
            source=source,
            asof_date=asof_date,
        )
    except (TypeError, ValueError):
        return None


def _stable_hash(parts: list[str]) -> str:
    joined = "|".join(parts)
    return sha256(joined.encode("utf-8")).hexdigest()


def ingest_and_normalize(
    inputs: list[tuple[Path, str]], canonical_h3_resolutions: list[int]
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    records: list[IngestedRecord] = []
    invalid_count = 0
    for path, source_name in sorted(inputs, key=lambda x: str(x[0])):
        for row in _parse_file(path, source_name):
            parsed = _try_parse_record(row)
            if parsed is None:
                invalid_count += 1
                continue
            records.append(parsed)

    rows: list[dict[str, object]] = []
    for record in records:
        org_norm = record.organization.strip().lower()
        org_id = _stable_hash(["org", org_norm])[:16]
        facility_id = _stable_hash(
            [
                "facility",
                record.source,
                record.node_name,
                f"{record.latitude:.8f}",
                f"{record.longitude:.8f}",
                record.asof_date,
            ]
        )[:24]

        record_hash = _stable_hash(
            [
                record.organization,
                record.node_name,
                f"{record.latitude:.8f}",
                f"{record.longitude:.8f}",
                record.city or "",
                record.state or "",
                record.country or "",
                record.source,
                record.asof_date,
            ]
        )

        row: dict[str, object] = {
            "facility_id": facility_id,
            "org_id": org_id,
            "org_name": record.organization,
            "source_facility_name": record.node_name,
            "lat": record.latitude,
            "lon": record.longitude,
            "city_label": record.city,
            "state_label": record.state,
            "country_label": record.country,
            "source_name": record.source,
            "asof_date": record.asof_date,
            "ingest_timestamp": "deterministic",
            "record_hash": record_hash,
            "location_confidence": "exact_point",
            "notes": None,
        }
        for resolution in canonical_h3_resolutions:
            row[f"h3_r{resolution}"] = h3.latlng_to_cell(record.latitude, record.longitude, resolution)
        rows.append(row)

    facilities = (
        pd.DataFrame(rows)
        .sort_values(by=["facility_id", "record_hash"])
        .drop_duplicates(subset=["facility_id"], keep="first")
        .reset_index(drop=True)
    )
    org_rows = (
        facilities[["org_id", "org_name"]]
        .drop_duplicates()
        .sort_values(by=["org_id"])
        .reset_index(drop=True)
    )
    return facilities, org_rows, invalid_count


def write_canonical_outputs(
    out_dir: Path, facilities: pd.DataFrame, organizations: pd.DataFrame
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    facilities.to_parquet(out_dir / "facilities.parquet", index=False)
    organizations.to_parquet(out_dir / "organizations.parquet", index=False)
