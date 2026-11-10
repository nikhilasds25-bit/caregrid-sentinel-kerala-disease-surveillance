"""Extract Kerala's 2024 monthly dengue/leptospirosis counts from the IDSP PDF.

Expected project layout:
  CareGrid-Sentinel/
    data/raw/IDSP-Annual-Data-2024.pdf
    data/interim/
    data/processed/

The script keeps confirmed and probable counts separate and validates monthly
sums against the annual totals published in the same report before writing CSV.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import pdfplumber

MONTHS = [
    ("Jan", 1), ("Feb", 2), ("Mar", 3), ("Apr", 4),
    ("May", 5), ("Jun", 6), ("Jul", 7), ("Aug", 8),
    ("Sep", 9), ("Oct", 10), ("Nov", 11), ("Dec", 12),
]
MONTH_NUMBERS = dict(MONTHS)

# Page 17 of the report: positions in each row are case/death pairs.
# The annual totals are cross-checked against the year summary on page 2.
TARGETS = {
    "Prob Dengue": {
        "disease": "Dengue",
        "classification": "Probable",
        "cases_idx": 2,
        "deaths_idx": 3,
        "expected_cases": 53536,
        "expected_deaths": 13,
    },
    "Con Dengue": {
        "disease": "Dengue",
        "classification": "Confirmed",
        "cases_idx": 4,
        "deaths_idx": 5,
        "expected_cases": 20674,
        "expected_deaths": 128,
    },
    "Prob Lepto": {
        "disease": "Leptospirosis",
        "classification": "Probable",
        "cases_idx": 6,
        "deaths_idx": 7,
        "expected_cases": 2428,
        "expected_deaths": 143,
    },
    "Con Lepto": {
        "disease": "Leptospirosis",
        "classification": "Confirmed",
        "cases_idx": 8,
        "deaths_idx": 9,
        "expected_cases": 3552,
        "expected_deaths": 251,
    },
}

SOURCE_URL = "https://dhs.kerala.gov.in/wp-content/uploads/2025/06/IDSP-Annual-Data-2024.pdf"


def parse_month_rows(page_text: str) -> dict[str, list[int]]:
    """Return 12 monthly rows and the Total row, each with 16 numeric values."""
    rows: dict[str, list[int]] = {}
    allowed_names = [name for name, _ in MONTHS] + ["Total"]
    line_re = re.compile(r"^\s*(" + "|".join(allowed_names) + r")\s+(.+?)\s*$")

    for line in page_text.splitlines():
        match = line_re.match(line)
        if not match:
            continue
        values = [int(x) for x in re.findall(r"\d+", match.group(2))]
        if len(values) == 16:
            rows[match.group(1)] = values
            # Page 17 has multiple monthly tables. Stop after the first Total row
            # so rows from later tables cannot overwrite the dengue/leptospirosis data.
            if match.group(1) == "Total":
                break

    missing = [name for name, _ in MONTHS if name not in rows]
    if missing:
        raise ValueError(
            "Could not parse all monthly rows from PDF page 17. Missing: "
            + ", ".join(missing)
            + ". Check the extracted text before proceeding."
        )
    if "Total" not in rows:
        raise ValueError("Could not parse the Total row from PDF page 17.")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf",
        type=Path,
        help="Path to the source PDF (defaults to data/raw/IDSP-Annual-Data-2024.pdf).",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Project root (normally inferred from this script's location).",
    )
    args = parser.parse_args()

    root = args.project_root.resolve() if args.project_root else Path(__file__).resolve().parents[2]
    pdf_path = args.pdf.resolve() if args.pdf else root / "data" / "raw" / "IDSP-Annual-Data-2024.pdf"
    interim_dir = root / "data" / "interim"
    processed_dir = root / "data" / "processed"
    interim_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.is_file():
        print(f"ERROR: Source PDF not found: {pdf_path}", file=sys.stderr)
        print("Copy IDSP-Annual-Data-2024.pdf into data/raw, or pass --pdf <full path>.", file=sys.stderr)
        return 2

    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) < 17:
            print(f"ERROR: Expected at least 17 PDF pages; found {len(pdf.pages)}.", file=sys.stderr)
            return 2
        extracted = {
            2: pdf.pages[1].extract_text() or "",
            17: pdf.pages[16].extract_text() or "",
            18: pdf.pages[17].extract_text() or "" if len(pdf.pages) >= 18 else "",
        }

    raw_output = interim_dir / "idsp_2024_source_pages.txt"
    with raw_output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"Source file: {pdf_path.name}\nSource URL: {SOURCE_URL}\n")
        handle.write("Note: PDF pages below are extracted text for audit; the PDF remains the authoritative source.\n\n")
        for page_num, page_text in extracted.items():
            handle.write(f"{'=' * 18} PDF PAGE {page_num} {'=' * 18}\n")
            handle.write(page_text)
            handle.write("\n\n")

    rows = parse_month_rows(extracted[17])
    month_rows = {name: rows[name] for name, _ in MONTHS}
    total_row = rows["Total"]

    output_rows: list[dict[str, object]] = []
    print("Validation against annual report totals (PDF page 2):")
    print("Source label       Month sum (cases/deaths)    Reported total    Status")
    print("-" * 78)

    for source_label, info in TARGETS.items():
        case_idx = int(info["cases_idx"])
        death_idx = int(info["deaths_idx"])
        cases_sum = sum(values[case_idx] for values in month_rows.values())
        deaths_sum = sum(values[death_idx] for values in month_rows.values())
        expected = (int(info["expected_cases"]), int(info["expected_deaths"]))
        total_row_values = (total_row[case_idx], total_row[death_idx])
        observed = (cases_sum, deaths_sum)
        status = "PASS" if observed == expected == total_row_values else "FAIL"
        print(f"{source_label:<18} {cases_sum:>8,}/{deaths_sum:<7,} {str(expected):>15}    {status}")
        if status != "PASS":
            print("ERROR: Totals do not reconcile; CSV was not written.", file=sys.stderr)
            print(f"Observed monthly sums={observed}; report total row={total_row_values}; expected={expected}", file=sys.stderr)
            return 3

        for month_name, month_num in MONTHS:
            values = month_rows[month_name]
            output_rows.append({
                "period": f"2024-{month_num:02d}",
                "year": 2024,
                "month_num": month_num,
                "month_name": month_name,
                "geography": "Kerala",
                "geography_level": "Statewide",
                "disease": info["disease"],
                "classification": info["classification"],
                "cases": values[case_idx],
                "deaths": values[death_idx],
                "source_label": source_label,
                "source_file": pdf_path.name,
                "source_page": 17,
                "validation_page": 2,
                "source_url": SOURCE_URL,
            })

    csv_path = processed_dir / "kerala_disease_monthly_2024.csv"
    fieldnames = list(output_rows[0].keys())
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\nSUCCESS: wrote {len(output_rows)} rows to {csv_path}")
    print(f"Audit text saved to {raw_output}")
    print("Scope: Kerala statewide, 2024 monthly confirmed/probable dengue and leptospirosis.")
    print("Confirmed and probable values are deliberately kept separate.")
    print("This 1-year dataset is a data-pipeline check, not enough by itself for forecasting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
