"""Audit the curated annual district-level disease dataset without modifying it."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

YEARS = tuple(range(2020, 2025))
DISTRICTS = (
    "Thiruvananthapuram",
    "Kollam",
    "Pathanamthitta",
    "Alappuzha",
    "Kottayam",
    "Idukki",
    "Ernakulam",
    "Thrissur",
    "Palakkad",
    "Malappuram",
    "Kozhikode",
    "Wayanad",
    "Kannur",
    "Kasaragod",
)
DISEASES = ("Dengue", "Leptospirosis")
CLASSIFICATIONS = ("Confirmed", "Probable")
KEY_COLUMNS = ("year", "district", "disease", "classification")
TOTAL_COLUMNS = ("year", "disease", "classification")
NUMERIC_COLUMNS = ("cases", "deaths")
REQUIRED_COLUMNS = (
    "year",
    "district",
    "district_code",
    "disease",
    "classification",
    "cases",
    "deaths",
    "source_case_label",
    "source_death_label",
    "case_source_sheet",
    "death_source_sheet",
    "classification_note",
    "source_header_note",
    "temporal_granularity",
    "case_source_title",
    "case_source_url",
    "death_source_title",
    "death_source_url",
)
OUTPUT_PREFIX = "district_data_quality"


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    values = frame.fillna("").astype(str)
    headers = list(values.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(value.replace("|", "\\|").replace("\n", " ") for value in row) + " |"
        for row in values.itertuples(index=False, name=None)
    )
    return "\n".join(lines)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8")


def _build_flags(data: pd.DataFrame, numeric: dict[str, pd.Series]) -> pd.DataFrame:
    flags: list[pd.DataFrame] = []
    details = data.reset_index(drop=True).copy()
    details.insert(0, "source_row", details.index + 2)
    flag_columns = ["source_row", *KEY_COLUMNS, *NUMERIC_COLUMNS, "issue", "detail"]

    def add(mask: pd.Series, issue: str, detail: str) -> None:
        if not mask.any():
            return
        selected = details.loc[mask, ["source_row", *KEY_COLUMNS, *NUMERIC_COLUMNS]].copy()
        selected["issue"] = issue
        selected["detail"] = detail
        flags.append(selected[flag_columns])

    duplicate = data.duplicated(list(KEY_COLUMNS), keep=False)
    add(duplicate, "duplicate_key", "Duplicate year/district/disease/classification key.")
    for column in NUMERIC_COLUMNS:
        converted = numeric[column]
        nonnumeric = data[column].notna() & converted.isna()
        add(
            nonnumeric,
            f"nonnumeric_{column}",
            f"{column} is populated but cannot be parsed as a number.",
        )
        add(
            converted < 0,
            f"negative_{column}",
            f"{column} is negative; source value retained for review.",
        )
    comparable = numeric["cases"].notna() & numeric["deaths"].notna()
    add(
        comparable & (numeric["deaths"] > numeric["cases"]),
        "deaths_exceed_cases",
        "Reported deaths exceed reported cases; flagged for review, not changed.",
    )
    return pd.concat(flags, ignore_index=True) if flags else pd.DataFrame(columns=flag_columns)


def _expected_combinations() -> pd.DataFrame:
    return pd.MultiIndex.from_product(
        [YEARS, DISTRICTS, DISEASES, CLASSIFICATIONS],
        names=KEY_COLUMNS,
    ).to_frame(index=False)


def run_audit(input_csv: Path, reports_dir: Path) -> Path:
    if not input_csv.is_file():
        raise FileNotFoundError(f"Dataset not found: {input_csv}")
    try:
        data = pd.read_csv(input_csv)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise ValueError(f"Could not read dataset CSV {input_csv}: {exc}") from exc

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing_columns:
        raise ValueError(
            "Dataset is missing required columns: "
            + ", ".join(missing_columns)
            + f". Found: {', '.join(map(str, data.columns))}"
        )

    reports_dir.mkdir(parents=True, exist_ok=True)
    numeric = {
        column: pd.to_numeric(data[column], errors="coerce")
        for column in NUMERIC_COLUMNS
    }
    missing_values = data.isna().sum().rename("missing_count").rename_axis("column").reset_index()

    district_coverage = []
    for year in YEARS:
        observed = set(data.loc[data["year"] == year, "district"].dropna())
        district_coverage.append({
            "year": year,
            "district_count": len(observed),
            "missing_districts": "; ".join(sorted(set(DISTRICTS) - observed)),
            "unexpected_districts": "; ".join(sorted(observed - set(DISTRICTS))),
        })
    district_coverage_frame = pd.DataFrame(district_coverage)

    expected = _expected_combinations()
    observed = data.groupby(list(KEY_COLUMNS), dropna=False).size().rename("record_count").reset_index()
    missing_combinations = expected.merge(
        observed,
        how="left",
        on=list(KEY_COLUMNS),
        validate="one_to_one",
    )
    missing_combinations = missing_combinations.loc[
        missing_combinations["record_count"].isna()
    ].copy()
    missing_combinations["record_count"] = missing_combinations["record_count"].astype("Int64")

    working = data[list(KEY_COLUMNS)].copy()
    for column in NUMERIC_COLUMNS:
        working[column] = numeric[column]
        working[f"{column}_numeric_records"] = numeric[column].notna().astype(int)
    totals = (
        working.groupby(list(TOTAL_COLUMNS), dropna=False)
        .agg(
            record_count=("year", "size"),
            cases=("cases", lambda values: values.sum(min_count=1)),
            deaths=("deaths", lambda values: values.sum(min_count=1)),
            cases_numeric_records=("cases_numeric_records", "sum"),
            deaths_numeric_records=("deaths_numeric_records", "sum"),
        )
        .reset_index()
        .sort_values(list(TOTAL_COLUMNS), kind="stable")
    )

    flags = _build_flags(data, numeric)
    source_columns = [
        "year",
        "disease",
        "classification",
        "source_case_label",
        "source_death_label",
        "case_source_sheet",
        "death_source_sheet",
        "classification_note",
        "source_header_note",
        "temporal_granularity",
        "case_source_title",
        "case_source_url",
        "death_source_title",
        "death_source_url",
    ]
    source_metadata = data[source_columns].drop_duplicates().sort_values(
        ["year", "disease", "classification"], kind="stable"
    )

    outputs = {
        "missing_values": (missing_values, "missing_values.csv"),
        "district_year_coverage": (district_coverage_frame, "district_year_coverage.csv"),
        "missing_expected_combinations": (
            missing_combinations,
            "missing_expected_combinations.csv",
        ),
        "totals_by_year_disease_classification": (
            totals,
            "totals_by_year_disease_classification.csv",
        ),
        "record_flags": (flags, "record_flags.csv"),
        "source_metadata": (source_metadata, "source_metadata.csv"),
    }
    output_paths: dict[str, Path] = {}
    for name, (frame, suffix) in outputs.items():
        path = reports_dir / f"{OUTPUT_PREFIX}_{suffix}"
        _write_csv(frame, path)
        output_paths[name] = path

    duplicate_count = int(data.duplicated(list(KEY_COLUMNS), keep=False).sum())
    nonnumeric_counts = {
        column: int((data[column].notna() & numeric[column].isna()).sum())
        for column in NUMERIC_COLUMNS
    }
    negative_counts = {
        column: int((numeric[column] < 0).sum())
        for column in NUMERIC_COLUMNS
    }
    deaths_exceed_cases = int(
        (
            numeric["cases"].notna()
            & numeric["deaths"].notna()
            & (numeric["deaths"] > numeric["cases"])
        ).sum()
    )
    missing_years = sorted(set(YEARS) - set(data["year"].dropna()))
    unexpected_years = sorted(set(data["year"].dropna()) - set(YEARS))
    observed_diseases = set(data["disease"].dropna())
    observed_classifications = set(data["classification"].dropna())
    missing_diseases = sorted(set(DISEASES) - observed_diseases)
    missing_classifications = sorted(set(CLASSIFICATIONS) - observed_classifications)
    unexpected_diseases = sorted(observed_diseases - set(DISEASES))
    unexpected_classifications = sorted(observed_classifications - set(CLASSIFICATIONS))
    row_mismatch = data.duplicated(list(KEY_COLUMNS), keep=False).any() or not missing_combinations.empty

    checks = [
        ("CSV readable; required schema present", True, f"{input_csv}"),
        ("Dataset shape and column names recorded", True, f"{len(data)} rows × {len(data.columns)} columns"),
        ("No missing values", int(data.isna().sum().sum()) == 0, f"{int(data.isna().sum().sum())} missing cells"),
        ("No duplicate natural keys", duplicate_count == 0, f"{duplicate_count} duplicate-key rows"),
        (
            "Coverage of years 2020–2024",
            not missing_years and not unexpected_years,
            f"missing={missing_years}; unexpected={unexpected_years}",
        ),
        (
            "All 14 districts represented each year",
            (district_coverage_frame["district_count"] == len(DISTRICTS)).all()
            and (district_coverage_frame["missing_districts"] == "").all()
            and (district_coverage_frame["unexpected_districts"] == "").all(),
            f"district counts by year={dict(zip(district_coverage_frame.year, district_coverage_frame.district_count))}",
        ),
        (
            "Disease coverage",
            not missing_diseases and not unexpected_diseases,
            f"observed={sorted(observed_diseases)}; missing={missing_diseases}; unexpected={unexpected_diseases}",
        ),
        (
            "Classification coverage; categories retained separately",
            not missing_classifications and not unexpected_classifications,
            f"observed={sorted(observed_classifications)}; missing={missing_classifications}; unexpected={unexpected_classifications}",
        ),
        ("No missing expected combinations or duplicate keys", not row_mismatch, f"{len(missing_combinations)} missing combinations; {duplicate_count} duplicate-key rows"),
        ("No non-numeric case/death values", not any(nonnumeric_counts.values()), f"cases={nonnumeric_counts['cases']}; deaths={nonnumeric_counts['deaths']}"),
        ("No negative case/death values", not any(negative_counts.values()), f"cases={negative_counts['cases']}; deaths={negative_counts['deaths']}"),
        ("No deaths greater than cases", deaths_exceed_cases == 0, f"{deaths_exceed_cases} records flagged"),
    ]

    recorded_header_notes = source_metadata.loc[
        source_metadata["source_header_note"].notna()
        & source_metadata["source_header_note"].astype(str).str.strip().ne(""),
        ["year", "death_source_sheet", "source_header_note"],
    ].drop_duplicates()
    classification_notes = sorted({
        note.strip()
        for note in source_metadata["classification_note"].dropna().astype(str)
        if note.strip()
    })
    metadata_lines = [
        f"- Case source: `{title}` — {url}"
        for title, url in data[["case_source_title", "case_source_url"]].drop_duplicates().itertuples(index=False, name=None)
    ]
    metadata_lines.extend(
        f"- Death source: `{title}` — {url}"
        for title, url in data[["death_source_title", "death_source_url"]].drop_duplicates().itertuples(index=False, name=None)
    )
    header_note_text = (
        "\n".join(
            f"- {row.year}: `{row.death_source_sheet}` — {row.source_header_note}"
            for row in recorded_header_notes.itertuples(index=False)
        )
        if not recorded_header_notes.empty
        else "- No non-empty `source_header_note` values are recorded in the dataset."
    )

    report_path = reports_dir / "data_quality_audit_latest.md"
    report_lines = [
        "# District disease dataset: data-quality audit",
        "",
        f"- Run timestamp (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Input: `{input_csv}`",
        "- Source CSV is read-only for this audit; no source values are changed.",
        "",
        "## Scope and interpretation",
        "",
        "This dataset contains annual district-level records, not monthly district-level observations. "
        "It does not support district-month climate-lag forecasting. Confirmed and Probable are "
        "preserved as separate source categories. Do not assume their definitions or reporting "
        "practices are identical across reporting years.",
        "",
        "Known cross-source discrepancy: the 2021 district-wise Dengue Confirmed total was "
        "previously found to be 3,261, while the statewide monthly dataset totals 3,251 "
        "(difference +10). These values are not reconciled; review the source records and "
        "definitions before drawing conclusions.",
        "",
        "## Dataset structure",
        "",
        f"- Shape: **{data.shape[0]} rows × {data.shape[1]} columns**",
        f"- Column names (source order): `{', '.join(map(str, data.columns))}`",
        f"- Years observed: `{sorted(data['year'].dropna().unique().tolist())}`",
        f"- Diseases observed: `{sorted(observed_diseases)}`",
        f"- Classifications observed: `{sorted(observed_classifications)}`",
        "",
        "## Check results",
        "",
        _markdown_table(pd.DataFrame(checks, columns=["Check", "Result", "Details"]).assign(
            Result=lambda frame: frame["Result"].map({True: "PASS", False: "WARN"})
        )),
        "",
        "A WARN indicates a condition requiring inspection; records are never silently modified.",
        "",
        "## Missing values by column",
        "",
        _markdown_table(missing_values),
        "",
        "The 224 blank `source_header_note` cells are sparse optional metadata: an empty value "
        "means no header discrepancy was recorded for that source row, not that a disease "
        "measurement is absent. The missing-value count is still reported as stored.",
        "",
        "## District coverage by year",
        "",
        _markdown_table(district_coverage_frame),
        "",
        "## Totals by year, disease, and classification",
        "",
        "Case/death totals sum parseable numeric values only. `*_numeric_records` and "
        "`record_count` make incomplete numeric groups visible; invalid source values remain "
        "in the source file and are listed in the record-flags table.",
        "",
        _markdown_table(totals),
        "",
        "## Record-level flags",
        "",
        f"Flagged records: **{len(flags)}**. Deaths exceeding cases are review flags, not corrections.",
        "",
        f"See `{output_paths['record_flags'].name}` for the complete flagged-record table.",
        "",
        "## Source metadata and header discrepancies",
        "",
        *metadata_lines,
        "",
        "Header notes recorded in the dataset:",
        "",
        header_note_text,
        "",
        "Classification/source notes:",
        "",
        *([f"- {note}" for note in classification_notes] or ["- No classification notes are recorded."]),
        "",
        f"Full row-level source metadata is saved in `{output_paths['source_metadata'].name}`.",
        "",
        "## Derived tables",
        "",
        *[f"- `{path.name}`" for path in output_paths.values()],
        "",
        "Missing expected combinations are defined over 2020–2024 × the 14 named Kerala "
        "districts × Dengue/Leptospirosis × Confirmed/Probable.",
        "",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Dataset: {input_csv}")
    print(f"Shape: {data.shape[0]} rows x {data.shape[1]} columns")
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'WARN'}: {name} — {detail}")
    print(f"Report: {report_path}")
    for path in output_paths.values():
        print(f"Summary: {path}")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-csv",
        type=Path,
        help="Dataset path (defaults to data/processed/kerala_district_annual_disease_2020_2024.csv).",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Project root (normally inferred from this script's location).",
    )
    args = parser.parse_args()
    root = args.project_root.resolve() if args.project_root else Path(__file__).resolve().parents[2]
    input_csv = args.input_csv.resolve() if args.input_csv else (
        root / "data" / "processed" / "kerala_district_annual_disease_2020_2024.csv"
    )
    reports_dir = root / "reports"
    try:
        run_audit(input_csv, reports_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
