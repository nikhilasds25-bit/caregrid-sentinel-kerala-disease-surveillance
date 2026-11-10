"""Build a provenance-preserving 2016-2025 district-month dashboard candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from caregrid.build_district_monthly_candidate import (
    DASHBOARD_DISTRICT_NAMES,
    METADATA_PATH as DASHBOARD_METADATA_PATH,
    RAW_DASHBOARD_DISTRICTS,
    SOURCE_PATH as DASHBOARD_SOURCE_PATH,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = (
    ROOT
    / "data"
    / "candidates"
    / "kerala_district_monthly_disease_dashboard_2016_2025.csv"
)
METADATA_OUTPUT_PATH = (
    ROOT
    / "data"
    / "candidates"
    / "kerala_district_monthly_disease_dashboard_2016_2025.metadata.json"
)
RECONCILIATION_PATH = (
    ROOT
    / "data"
    / "candidates"
    / "kerala_district_monthly_disease_dashboard_2016_2025_reconciliation.csv"
)
DISTRICT_ANNUAL_COMPARISON_PATH = (
    ROOT
    / "data"
    / "candidates"
    / "dhs_dashboard_district_annual_comparison_2020_2025.csv"
)
DHS_2021_2022_PATH = ROOT / "data" / "interim" / "kerala_disease_monthly_2021_2022.csv"
DHS_2023_PATH = ROOT / "data" / "interim" / "kerala_disease_monthly_confirmed_2023.csv"
DHS_2024_PATH = ROOT / "data" / "processed" / "kerala_disease_monthly_2024.csv"
DHS_2025_PATH = ROOT / "data" / "live_surveillance" / "latest.json"
DHS_DISTRICT_ANNUAL_2020_2024_PATH = (
    ROOT / "data" / "processed" / "kerala_district_annual_disease_2020_2024.csv"
)

YEARS = tuple(range(2016, 2026))
MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
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
CANDIDATE_COLUMNS = (
    "year",
    "month_num",
    "month_name",
    "period",
    "district",
    "source_district",
    "disease",
    "classification",
    "source_category_code",
    "cases",
    "deaths",
    "source_name",
    "source_url",
    "dashboard_url",
    "source_snapshot_date",
    "source_retrieved_at_utc",
    "source_response_date",
    "source_etag",
    "source_sha256",
    "temporal_granularity",
    "availability_status",
    "source_category_available",
    "cases_available",
    "deaths_available",
    "value_status",
)
RECONCILIATION_COLUMNS = (
    "year",
    "month_num",
    "month_name",
    "period",
    "disease",
    "classification",
    "source_category_code",
    "cases_district_sum",
    "cases_kerala_source",
    "cases_difference",
    "cases_reconciliation_status",
    "deaths_district_sum",
    "deaths_kerala_source",
    "deaths_difference",
    "deaths_reconciliation_status",
    "source_name",
    "source_url",
    "source_sha256",
)

DHS_CATEGORY_BY_DASHBOARD = {
    (2021, "Confirmed"): "reported_category_status_not_split",
    (2022, "Confirmed"): "non_probable_category_probable_separate",
    (2023, "Confirmed"): "Confirmed",
    (2024, "Confirmed"): "Confirmed",
    (2024, "Suspected"): "Probable",
    (2025, "Confirmed"): "Confirmed",
    (2025, "Suspected"): "Probable",
}
DHS_COMPARISON_NOTE = {
    2021: "Dashboard Confirmed compared numerically to an unsplit DHS category; semantics differ/unverified.",
    2022: "Dashboard Confirmed compared numerically to DHS non-probable category; source monthly table does not explicitly say Confirmed.",
    2023: "Dashboard Confirmed compared to the retained DHS Confirmed transcription; original PDF extraction was not independently readable.",
    2024: "DHS Confirmed matches dashboard Confirmed; Suspected/Probable is numeric-only and not an established semantic equivalence.",
    2025: "Suspected/Probable comparison is numeric-only; 2025 source values differ and definitions/revisions are unresolved.",
}


class ExtendedDiseaseDataError(ValueError):
    """Raised when source integrity or expected source structure is invalid."""


def _count(value: Any, context: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExtendedDiseaseDataError(f"{context} is not a numeric count")
    if not math.isfinite(value) or value < 0 or int(value) != value:
        raise ExtendedDiseaseDataError(f"{context} is not a non-negative integer count")
    return int(value)


def _required_metadata(metadata: Mapping[str, Any]) -> None:
    missing = [key for key in REQUIRED_METADATA if not metadata.get(key)]
    if missing:
        raise ExtendedDiseaseDataError(
            "source metadata is missing required fields: " + ", ".join(missing)
        )
    if not re.fullmatch(r"[0-9a-f]{64}", str(metadata["sha256"])):
        raise ExtendedDiseaseDataError("source sha256 must be a 64-character hex digest")


def build_extended_candidate(
    payload: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return a dense district panel and a separate state-total reconciliation."""
    _required_metadata(metadata)
    if "source_payload_sha256" in metadata and not re.fullmatch(
        r"[0-9a-f]{64}", str(metadata["source_payload_sha256"])
    ):
        raise ExtendedDiseaseDataError(
            "source_payload_sha256 must be a 64-character hex digest"
        )
    if set(payload) != {str(year) for year in YEARS}:
        raise ExtendedDiseaseDataError("source years must be exactly 2016 through 2025")

    records: list[dict[str, Any]] = []
    reconciliation: list[dict[str, Any]] = []
    for year in YEARS:
        year_data = payload[str(year)]
        if not isinstance(year_data, Mapping):
            raise ExtendedDiseaseDataError(f"{year} data must be an object")
        districts = set(year_data) - {"KERALA"}
        if districts != RAW_DASHBOARD_DISTRICTS:
            raise ExtendedDiseaseDataError(
                f"{year} district keys do not match the 14-district source schema"
            )
        state = year_data.get("KERALA")
        if not isinstance(state, Mapping):
            raise ExtendedDiseaseDataError(f"{year} is missing the KERALA aggregate")

        for month_num, month in enumerate(MONTHS, start=1):
            period = f"{year}-{month_num:02d}"
            state_month = state.get(month)
            for category_code, disease, classification in CATEGORIES:
                district_metric_values: dict[str, list[int | None]] = {"C": [], "D": []}
                category_seen: list[bool] = []
                for source_district in sorted(RAW_DASHBOARD_DISTRICTS):
                    district_month = year_data[source_district].get(month)
                    category = (
                        district_month.get(category_code)
                        if isinstance(district_month, Mapping)
                        else None
                    )
                    category_available = isinstance(category, Mapping)
                    category_seen.append(category_available)
                    cases = _count(
                        category.get("C") if category_available else None,
                        f"{period}/{source_district}/{category_code}/C",
                    )
                    deaths = _count(
                        category.get("D") if category_available else None,
                        f"{period}/{source_district}/{category_code}/D",
                    )
                    district_metric_values["C"].append(cases)
                    district_metric_values["D"].append(deaths)
                    if not category_available:
                        availability = "unavailable_source_category_absent"
                    elif cases is None or deaths is None:
                        availability = "source_category_present_metric_missing"
                    else:
                        availability = "available"
                    if availability != "available":
                        value_status = availability
                    elif cases == 0 and deaths == 0:
                        value_status = "available_explicit_zero_cases_and_deaths"
                    elif cases == 0 or deaths == 0:
                        value_status = "available_with_one_explicit_zero_metric"
                    else:
                        value_status = "available_nonzero_cases_and_deaths"
                    records.append({
                        "year": year,
                        "month_num": month_num,
                        "month_name": month,
                        "period": period,
                        "district": DASHBOARD_DISTRICT_NAMES[source_district],
                        "source_district": source_district,
                        "disease": disease,
                        "classification": classification,
                        "source_category_code": category_code,
                        "cases": cases,
                        "deaths": deaths,
                        "source_name": "Kerala Health Department disease prevalence dashboard",
                        "source_url": metadata["source_url"],
                        "dashboard_url": metadata["dashboard_url"],
                        "source_snapshot_date": metadata["response_date"],
                        "source_retrieved_at_utc": metadata["retrieved_at_utc"],
                        "source_response_date": metadata["response_date"],
                        "source_etag": metadata["etag"],
                        "source_sha256": metadata["sha256"],
                        "temporal_granularity": "monthly",
                        "availability_status": availability,
                        "source_category_available": category_available,
                        "cases_available": cases is not None,
                        "deaths_available": deaths is not None,
                        "value_status": value_status,
                    })

                state_category = (
                    state_month.get(category_code)
                    if isinstance(state_month, Mapping)
                    else None
                )
                state_available = isinstance(state_category, Mapping)
                metric_results: dict[str, tuple[int | None, int | None, int | None, str]] = {}
                for metric, output_name in (("C", "cases"), ("D", "deaths")):
                    state_value = _count(
                        state_category.get(metric) if state_available else None,
                        f"{period}/KERALA/{category_code}/{metric}",
                    )
                    values = district_metric_values[metric]
                    district_sum = (
                        sum(value for value in values if value is not None)
                        if category_seen and all(category_seen) and all(
                            value is not None for value in values
                        )
                        else None
                    )
                    if district_sum is None or state_value is None:
                        status = "unavailable_source_category_or_metric"
                    elif district_sum == state_value:
                        status = "match"
                    else:
                        status = "mismatch"
                    difference = (
                        district_sum - state_value
                        if district_sum is not None and state_value is not None
                        else None
                    )
                    metric_results[output_name] = (
                        district_sum,
                        state_value,
                        difference,
                        status,
                    )
                reconciliation.append({
                    "year": year,
                    "month_num": month_num,
                    "month_name": month,
                    "period": period,
                    "disease": disease,
                    "classification": classification,
                    "source_category_code": category_code,
                    "cases_district_sum": metric_results["cases"][0],
                    "cases_kerala_source": metric_results["cases"][1],
                    "cases_difference": metric_results["cases"][2],
                    "cases_reconciliation_status": metric_results["cases"][3],
                    "deaths_district_sum": metric_results["deaths"][0],
                    "deaths_kerala_source": metric_results["deaths"][1],
                    "deaths_difference": metric_results["deaths"][2],
                    "deaths_reconciliation_status": metric_results["deaths"][3],
                    "source_name": "Kerala Health Department disease prevalence dashboard",
                    "source_url": metadata["source_url"],
                    "source_sha256": metadata["sha256"],
                })

    candidate = pd.DataFrame.from_records(records, columns=CANDIDATE_COLUMNS)
    reconciliation_frame = pd.DataFrame.from_records(
        reconciliation, columns=RECONCILIATION_COLUMNS
    )
    natural_key = ["period", "district", "disease", "classification"]
    if candidate.duplicated(natural_key).any():
        raise ExtendedDiseaseDataError("candidate has duplicate disease-month-district keys")
    expected_rows = len(YEARS) * 12 * len(RAW_DASHBOARD_DISTRICTS) * len(CATEGORIES)
    if len(candidate) != expected_rows:
        raise ExtendedDiseaseDataError(
            f"candidate row count {len(candidate)} does not equal expected {expected_rows}"
        )
    return candidate, reconciliation_frame


def _load_dhs_records() -> pd.DataFrame:
    frames = [
        pd.read_csv(DHS_2021_2022_PATH),
        pd.read_csv(DHS_2023_PATH),
        pd.read_csv(DHS_2024_PATH),
    ]
    annual_2025 = json.loads(DHS_2025_PATH.read_text(encoding="utf-8"))
    frames.append(pd.DataFrame(annual_2025["monthly_records"]))
    data = pd.concat(frames, ignore_index=True, sort=False)
    return data[data["disease"].isin(["Dengue", "Leptospirosis"])].copy()


def build_source_comparison(
    payload: Mapping[str, Any],
    dhs_records: pd.DataFrame,
) -> pd.DataFrame:
    """Compare monthly statewide values while retaining category-semantic caveats."""
    lookup = {
        (int(row.year), int(row.month_num), row.disease, row.classification): row
        for row in dhs_records.itertuples(index=False)
        if pd.notna(row.year)
        and pd.notna(row.month_num)
        and row.disease in {"Dengue", "Leptospirosis"}
    }
    rows: list[dict[str, Any]] = []
    for year in range(2021, 2026):
        state = payload[str(year)]["KERALA"]
        for month_num, month in enumerate(MONTHS, start=1):
            for category_code, disease, classification in CATEGORIES:
                dhs_classification = DHS_CATEGORY_BY_DASHBOARD.get((year, classification))
                if dhs_classification is None:
                    status = "no_dhs_monthly_category_counterpart"
                    dhs_row = None
                else:
                    dhs_row = lookup.get(
                        (year, month_num, disease, dhs_classification)
                    )
                    status = (
                        "compared_label_semantics_unverified"
                        if dhs_row is not None
                        else "dhs_monthly_record_unavailable"
                    )
                dashboard_values = (
                    state.get(month, {}).get(category_code, {})
                    if isinstance(state.get(month, {}), Mapping)
                    else {}
                )
                dashboard_cases = _count(
                    dashboard_values.get("C"),
                    f"{year}-{month_num:02d}/KERALA/{category_code}/C",
                )
                dashboard_deaths = _count(
                    dashboard_values.get("D"),
                    f"{year}-{month_num:02d}/KERALA/{category_code}/D",
                )
                dhs_cases = int(dhs_row.cases) if dhs_row is not None else None
                dhs_deaths = int(dhs_row.deaths) if dhs_row is not None else None
                rows.append({
                    "year": year,
                    "month_num": month_num,
                    "month_name": month,
                    "period": f"{year}-{month_num:02d}",
                    "disease": disease,
                    "dashboard_classification": classification,
                    "dashboard_category_code": category_code,
                    "dashboard_cases": dashboard_cases,
                    "dashboard_deaths": dashboard_deaths,
                    "dhs_classification": dhs_classification,
                    "dhs_cases": dhs_cases,
                    "dhs_deaths": dhs_deaths,
                    "cases_difference_dashboard_minus_dhs": (
                        dashboard_cases - dhs_cases
                        if dashboard_cases is not None and dhs_cases is not None
                        else None
                    ),
                    "deaths_difference_dashboard_minus_dhs": (
                        dashboard_deaths - dhs_deaths
                        if dashboard_deaths is not None and dhs_deaths is not None
                        else None
                    ),
                    "comparison_status": status,
                    "interpretation_note": DHS_COMPARISON_NOTE.get(
                        year, "No direct DHS monthly comparison is available."
                    ),
                })
    return pd.DataFrame.from_records(rows)


def build_district_annual_comparison(
    candidate: pd.DataFrame,
    dhs_annual: pd.DataFrame,
) -> pd.DataFrame:
    """Compare dashboard month sums with DHS annual district records, no recoding."""
    dhs_lookup = {
        (int(row.year), row.district, row.disease, row.classification): row
        for row in dhs_annual.itertuples(index=False)
        if pd.notna(row.year)
        and row.disease in {"Dengue", "Leptospirosis"}
    }
    rows: list[dict[str, Any]] = []
    dashboard = candidate[candidate["year"].between(2020, 2025)]
    for (year, district, disease, classification), group in dashboard.groupby(
        ["year", "district", "disease", "classification"], sort=True
    ):
        dhs_classification = "Confirmed" if classification == "Confirmed" else "Probable"
        dhs_row = dhs_lookup.get(
            (int(year), district, disease, dhs_classification)
        )
        cases = (
            int(group["cases"].sum())
            if group["cases"].notna().all()
            else None
        )
        deaths = (
            int(group["deaths"].sum())
            if group["deaths"].notna().all()
            else None
        )
        dhs_cases = int(dhs_row.cases) if dhs_row is not None else None
        dhs_deaths = int(dhs_row.deaths) if dhs_row is not None else None
        rows.append({
            "year": int(year),
            "district": district,
            "disease": disease,
            "dashboard_classification": classification,
            "dashboard_category_code": group["source_category_code"].iloc[0],
            "dashboard_month_count": int(group["period"].nunique()),
            "dashboard_monthly_cases_sum": cases,
            "dashboard_monthly_deaths_sum": deaths,
            "dhs_classification": dhs_classification,
            "dhs_annual_cases": dhs_cases,
            "dhs_annual_deaths": dhs_deaths,
            "cases_difference_dashboard_minus_dhs": (
                cases - dhs_cases if cases is not None and dhs_cases is not None else None
            ),
            "deaths_difference_dashboard_minus_dhs": (
                deaths - dhs_deaths
                if deaths is not None and dhs_deaths is not None
                else None
            ),
            "comparison_status": (
                "compared_label_semantics_unverified"
                if dhs_row is not None
                else "no_dhs_district_annual_counterpart"
            ),
            "interpretation_note": (
                "Dashboard Suspected versus DHS Probable is numeric-only; "
                "a semantic equivalence is not established."
                if classification == "Suspected"
                else "Matching Confirmed labels do not establish unchanged case definitions."
            ),
        })
    return pd.DataFrame.from_records(rows)


def _load_dhs_district_annual() -> pd.DataFrame:
    historical = pd.read_csv(DHS_DISTRICT_ANNUAL_2020_2024_PATH)
    latest = json.loads(DHS_2025_PATH.read_text(encoding="utf-8"))
    annual_2025 = pd.DataFrame(latest["district_annual_records"])
    combined = pd.concat([historical, annual_2025], ignore_index=True, sort=False)
    return combined[combined["disease"].isin(["Dengue", "Leptospirosis"])].copy()


def load_extended_candidate(
    source_path: Path = DASHBOARD_SOURCE_PATH,
    metadata_path: Path = DASHBOARD_METADATA_PATH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_bytes = source_path.read_bytes()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    actual_hash = hashlib.sha256(source_bytes).hexdigest()
    if actual_hash != metadata.get("sha256"):
        raise ExtendedDiseaseDataError(
            f"dashboard snapshot hash mismatch: metadata={metadata.get('sha256')}, "
            f"actual={actual_hash}"
        )
    payload = json.loads(source_bytes)
    metadata["source_payload_sha256"] = actual_hash
    return payload, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DASHBOARD_SOURCE_PATH)
    parser.add_argument("--metadata", type=Path, default=DASHBOARD_METADATA_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--output-metadata", type=Path, default=METADATA_OUTPUT_PATH)
    parser.add_argument("--reconciliation", type=Path, default=RECONCILIATION_PATH)
    parser.add_argument("--comparison", type=Path, default=ROOT / "data/candidates/dhs_dashboard_monthly_comparison_2021_2025.csv")
    parser.add_argument(
        "--district-annual-comparison",
        type=Path,
        default=DISTRICT_ANNUAL_COMPARISON_PATH,
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    destinations = [
        args.output,
        args.output_metadata,
        args.reconciliation,
        args.comparison,
        args.district_annual_comparison,
    ]
    existing = [str(path) for path in destinations if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(
            "Refusing to overwrite existing outputs: " + ", ".join(existing)
            + "; pass --overwrite only after reviewing them."
        )

    payload, metadata = load_extended_candidate(args.source, args.metadata)
    candidate, reconciliation = build_extended_candidate(payload, metadata)
    comparison = build_source_comparison(payload, _load_dhs_records())
    annual_comparison = build_district_annual_comparison(
        candidate, _load_dhs_district_annual()
    )
    output_frames = (
        (candidate, args.output),
        (reconciliation, args.reconciliation),
        (comparison, args.comparison),
        (annual_comparison, args.district_annual_comparison),
    )
    output_hashes = {}
    for frame, path in output_frames:
        path.parent.mkdir(parents=True, exist_ok=True)
        csv_bytes = frame.to_csv(index=False).encode("utf-8")
        path.write_bytes(csv_bytes)
        output_hashes[str(path)] = hashlib.sha256(csv_bytes).hexdigest()
        print(f"Wrote {len(frame)} rows to {path}")
    output_metadata = {
        "schema_version": 1,
        "source_name": "Kerala Health Department disease prevalence dashboard",
        "source_url": metadata["source_url"],
        "dashboard_url": metadata["dashboard_url"],
        "source_snapshot_path": str(args.source),
        "source_snapshot_date": metadata["response_date"],
        "source_retrieved_at_utc": metadata["retrieved_at_utc"],
        "source_etag": metadata["etag"],
        "source_sha256": metadata["sha256"],
        "candidate_path": str(args.output),
        "candidate_sha256": output_hashes[str(args.output)],
        "candidate_rows": len(candidate),
        "candidate_unique_periods": int(candidate["period"].nunique()),
        "candidate_districts": sorted(candidate["district"].unique().tolist()),
        "candidate_classifications": ["Confirmed", "Suspected"],
        "missing_source_category_rows": int(
            candidate["availability_status"]
            .eq("unavailable_source_category_absent")
            .sum()
        ),
        "reconciliation_path": str(args.reconciliation),
        "reconciliation_sha256": output_hashes[str(args.reconciliation)],
        "monthly_dhs_comparison_path": str(args.comparison),
        "monthly_dhs_comparison_sha256": output_hashes[str(args.comparison)],
        "district_annual_comparison_path": str(args.district_annual_comparison),
        "district_annual_comparison_sha256": output_hashes[
            str(args.district_annual_comparison)
        ],
    }
    args.output_metadata.parent.mkdir(parents=True, exist_ok=True)
    args.output_metadata.write_text(
        json.dumps(output_metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote source and dataset provenance to {args.output_metadata}")
    mismatch_count = int(
        reconciliation["cases_reconciliation_status"].eq("mismatch").sum()
        + reconciliation["deaths_reconciliation_status"].eq("mismatch").sum()
    )
    print(f"Dashboard district-to-state monthly metric mismatches: {mismatch_count}")


if __name__ == "__main__":
    main()
