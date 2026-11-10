"""Combine audited monthly confirmed Kerala DHS counts for 2023 and 2024.

Inputs:
  data/interim/kerala_disease_monthly_confirmed_2023.csv
  data/processed/kerala_disease_monthly_2024.csv
Output:
  data/processed/kerala_disease_monthly_confirmed_2023_2024.csv

The 2023 values were transcribed from the official Kerala DHS monthly tables
and are retained in the interim CSV with report URL/page provenance. The 2024
input is created by extract_idsp_2024.py. This produces a descriptive baseline,
not a sufficiently long training series for reliable forecasting.
"""
from pathlib import Path
import sys
import pandas as pd

EXPECTED = {
    (2023, "Dengue"): (16766, 153),
    (2023, "Leptospirosis"): (2417, 133),
    (2024, "Dengue"): (20674, 128),
    (2024, "Leptospirosis"): (3552, 251),
}
REQUIRED = {"period", "year", "month_num", "month_name", "geography", "geography_level", "disease", "classification", "cases", "deaths", "source_url"}

def main() -> int:
    root = Path(__file__).resolve().parents[2]
    input_2023 = root / "data" / "interim" / "kerala_disease_monthly_confirmed_2023.csv"
    input_2024 = root / "data" / "processed" / "kerala_disease_monthly_2024.csv"
    output = root / "data" / "processed" / "kerala_disease_monthly_confirmed_2023_2024.csv"
    for p in (input_2023, input_2024):
        if not p.is_file():
            print(f"ERROR: Missing input: {p}", file=sys.stderr)
            return 2
    d23 = pd.read_csv(input_2023)
    d24 = pd.read_csv(input_2024)
    if REQUIRED - set(d23.columns) or REQUIRED - set(d24.columns):
        print("ERROR: Input CSV columns do not match the expected schema.", file=sys.stderr)
        return 2
    d23 = d23[d23["classification"].str.casefold() == "confirmed"].copy()
    d24 = d24[d24["classification"].str.casefold() == "confirmed"].copy()
    data = pd.concat([d23, d24], ignore_index=True)
    data["year"] = pd.to_numeric(data["year"], errors="raise").astype(int)
    data["month_num"] = pd.to_numeric(data["month_num"], errors="raise").astype(int)
    data["cases"] = pd.to_numeric(data["cases"], errors="raise").astype(int)
    data["deaths"] = pd.to_numeric(data["deaths"], errors="raise").astype(int)
    data = data.sort_values(["disease", "year", "month_num"]).reset_index(drop=True)
    if data.duplicated(["year", "month_num", "disease", "classification", "geography"]).any():
        print("ERROR: Duplicate monthly disease/geography records found.", file=sys.stderr)
        return 2
    for key, expected in EXPECTED.items():
        year, disease = key
        sub = data[(data.year == year) & (data.disease == disease)]
        got = (int(sub.cases.sum()), int(sub.deaths.sum()))
        status = "PASS" if got == expected and len(sub) == 12 else "FAIL"
        print(f"{year} {disease:<14} monthly total={got[0]:>6,}/{got[1]:<3,} expected={expected[0]:,}/{expected[1]:,} rows={len(sub):2} {status}")
        if status != "PASS":
            return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(output, index=False, encoding="utf-8")
    print(f"\nSUCCESS: wrote {len(data)} rows to {output}")
    print("Scope: Kerala statewide, monthly CONFIRMED dengue and leptospirosis, 2023–2024.")
    print("Probable counts are excluded for this comparison because the two annual reports' monthly tables are not equivalent for probable classifications.")
    print("Caution: 24 months per disease is still too short for a robust forecasting claim.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
