"""Build a source-native 2023-2025 district-month candidate from the Kerala dashboard."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from caregrid.import_official_surveillance_report import DISTRICT_SOURCE_NAMES

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "data" / "raw" / "kerala_health_disease_data_2026-11-10.json"
METADATA_PATH = ROOT / "data" / "raw" / "kerala_health_disease_data_2026-11-10.metadata.json"
OUTPUT_PATH = (
    ROOT
    / "data"
    / "candidates"
    / "kerala_district_monthly_disease_dashboard_2023_2025.csv"
)

YEARS = ("2023", "2024", "2025")
MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
RAW_DASHBOARD_DISTRICTS = frozenset({
    "TRIVANDRUM",
    "KOLLAM",
    "PATHANAMTHITTA",
    "IDUKKI",
    "KOTTAYAM",
    "ALAPPUZHA",
    "ERANAKULAM",
    "THRISSUR",
    "PALAKKAD",
    "MALAPPURAM",
    "KOZHIKKODE",
    "WAYANAD",
    "KANNUR",
    "KASARKODE",
})
DASHBOARD_DISTRICT_NAMES = {
    **DISTRICT_SOURCE_NAMES,
    "ERANAKULAM": "Ernakulam",
    "KASARKODE": "Kasaragod",
}
CATEGORIES = (
    ("DENGUE|Con", "Dengue", "Confirmed"),
    ("DENGUE|Sus", "Dengue", "Suspected"),
    ("LEPTO|Con", "Leptospirosis", "Confirmed"),
    ("LEPTO|Sus", "Leptospirosis", "Suspected"),
)
REQUIRED_METADATA = (
    "source_url",
    "dashboard_url",
    "retrieved_at_utc",
    "response_date",
    "etag",
    "sha256",
)
COLUMNS = (
    "period",
    "year",
    "month_num",
    "district",
    "source_district",
    "disease",
    "classification",
    "source_category_code",
    "cases",
    "deaths",
    "source_case_metric_key",
    "source_death_metric_key",
    "temporal_granularity",
    "source_url",
    "dashboard_url",
    "source_sha256",
    "source_retrieved_at_utc",
    "source_response_date",
    "source_etag",
)


class CandidateDataError(ValueError):
    """Raised when the source snapshot cannot support a complete candidate panel."""


def _require_count(value: Any, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CandidateDataError(f"{context} must be a numeric count")
    if not math.isfinite(value) or value < 0 or int(value) != value:
        raise CandidateDataError(f"{context} must be a non-negative integer count")
    return int(value)


def build_candidate_frame(
    payload: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> pd.DataFrame:
    """Validate and shape the dashboard's monthly district counts without recoding."""
    missing_metadata = [key for key in REQUIRED_METADATA if not metadata.get(key)]
    if missing_metadata:
        raise CandidateDataError(
            "source metadata is missing required fields: " + ", ".join(missing_metadata)
        )
    if not re.fullmatch(r"[0-9a-f]{64}", str(metadata["sha256"])):
        raise CandidateDataError("source metadata sha256 must be a 64-character hex digest")

    records: list[dict[str, Any]] = []
    for year in YEARS:
        year_data = payload.get(year)
        if not isinstance(year_data, Mapping):
            raise CandidateDataError(f"source is missing year {year}")

        districts = set(year_data) - {"KERALA"}
        if districts != RAW_DASHBOARD_DISTRICTS:
            missing = sorted(RAW_DASHBOARD_DISTRICTS - districts)
            extra = sorted(districts - RAW_DASHBOARD_DISTRICTS)
            raise CandidateDataError(
                f"{year} district coverage differs from the 14-district source schema; "
                f"missing={missing}, extra={extra}"
            )

        for district_key in RAW_DASHBOARD_DISTRICTS:
            district_data = year_data[district_key]
            if not isinstance(district_data, Mapping):
                raise CandidateDataError(f"{year}/{district_key} must contain monthly data")
            missing_months = [month for month in MONTHS if month not in district_data]
            if missing_months:
                raise CandidateDataError(
                    f"{year}/{district_key} is missing monthly coverage: "
                    + ", ".join(missing_months)
                )

        state_data = year_data.get("KERALA")
        if not isinstance(state_data, Mapping):
            raise CandidateDataError(f"{year} is missing the KERALA aggregate")

        for month_num, month in enumerate(MONTHS, start=1):
            for category_code, disease, classification in CATEGORIES:
                district_counts = {"C": 0, "D": 0}
                for district_key in sorted(RAW_DASHBOARD_DISTRICTS):
                    month_data = year_data[district_key][month]
                    category_data = month_data.get(category_code)
                    if not isinstance(category_data, Mapping):
                        raise CandidateDataError(
                            f"{year}/{month}/{district_key} is missing {category_code}"
                        )
                    counts = {
                        metric: _require_count(
                            category_data.get(metric),
                            context=f"{year}/{month}/{district_key}/{category_code}/{metric}",
                        )
                        for metric in ("C", "D")
                    }
                    district_counts["C"] += counts["C"]
                    district_counts["D"] += counts["D"]
                    records.append({
                        "period": f"{year}-{month_num:02d}",
                        "year": int(year),
                        "month_num": month_num,
                        "district": DASHBOARD_DISTRICT_NAMES[district_key],
                        "source_district": district_key,
                        "disease": disease,
                        "classification": classification,
                        "source_category_code": category_code,
                        "cases": counts["C"],
                        "deaths": counts["D"],
                        "source_case_metric_key": "C",
                        "source_death_metric_key": "D",
                        "temporal_granularity": "monthly",
                        "source_url": metadata["source_url"],
                        "dashboard_url": metadata["dashboard_url"],
                        "source_sha256": metadata["sha256"],
                        "source_retrieved_at_utc": metadata["retrieved_at_utc"],
                        "source_response_date": metadata["response_date"],
                        "source_etag": metadata["etag"],
                    })

                aggregate_data = state_data.get(month)
                if not isinstance(aggregate_data, Mapping):
                    raise CandidateDataError(f"{year}/KERALA is missing month {month}")
                aggregate_category = aggregate_data.get(category_code)
                if not isinstance(aggregate_category, Mapping):
                    raise CandidateDataError(
                        f"{year}/{month}/KERALA is missing {category_code}"
                    )
                for metric in ("C", "D"):
                    aggregate_count = _require_count(
                        aggregate_category.get(metric),
                        context=f"{year}/{month}/KERALA/{category_code}/{metric}",
                    )
                    if district_counts[metric] != aggregate_count:
                        raise CandidateDataError(
                            f"{year}-{month} {category_code} {metric} district sum "
                            f"{district_counts[metric]} does not match KERALA aggregate "
                            f"{aggregate_count}"
                        )

    frame = pd.DataFrame.from_records(records, columns=COLUMNS)
    key_columns = ["period", "district", "disease", "classification"]
    if frame.duplicated(key_columns).any():
        raise CandidateDataError("candidate contains duplicate disease-month-district keys")
    return frame


def load_candidate_frame(
    source_path: Path = SOURCE_PATH,
    metadata_path: Path = METADATA_PATH,
) -> pd.DataFrame:
    source_bytes = source_path.read_bytes()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    actual_hash = hashlib.sha256(source_bytes).hexdigest()
    if actual_hash != metadata.get("sha256"):
        raise CandidateDataError(
            f"source snapshot hash mismatch: metadata={metadata.get('sha256')}, "
            f"actual={actual_hash}"
        )
    payload = json.loads(source_bytes)
    return build_candidate_frame(payload, metadata)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--metadata", type=Path, default=METADATA_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing candidate output after validating the source",
    )
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite:
        raise SystemExit(
            f"Refusing to overwrite existing candidate {args.output}; pass --overwrite "
            "only after reviewing it."
        )
    frame = load_candidate_frame(args.source, args.metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    print(
        f"Wrote {len(frame)} validated source-native records for "
        f"{frame['period'].nunique()} months and {frame['district'].nunique()} districts "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()
