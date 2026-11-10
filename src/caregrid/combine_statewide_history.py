from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EARLY = ROOT / "data" / "interim" / "kerala_disease_monthly_2021_2022.csv"
RECENT = ROOT / "data" / "interim" / "kerala_disease_monthly_confirmed_2023_2024.csv"
OUTPUT = ROOT / "data" / "processed" / "kerala_disease_monthly_2021_2024.csv"

EXPECTED = {
    (2021, "Dengue"): (3251, 27),
    (2021, "Leptospirosis"): (1745, 97),
    (2022, "Dengue"): (4468, 58),
    (2022, "Leptospirosis"): (2482, 121),
    (2023, "Dengue"): (16766, 153),
    (2023, "Leptospirosis"): (2417, 133),
    (2024, "Dengue"): (20674, 128),
    (2024, "Leptospirosis"): (3552, 251),
}


def main():
    for path in (EARLY, RECENT):
        if not path.exists():
            raise FileNotFoundError(f"Required input is missing: {path}")
    early = pd.read_csv(EARLY)
    recent = pd.read_csv(RECENT)
    if "classification_note" not in early.columns:
        raise ValueError("Early historical CSV is missing classification_note")
    if "classification_note" not in recent.columns:
        recent["classification_note"] = "The DHS report explicitly labels this monthly category as confirmed."
    df = pd.concat([early, recent], ignore_index=True)
    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)
    df["month_num"] = pd.to_numeric(df["month_num"], errors="raise").astype(int)
    df["cases"] = pd.to_numeric(df["cases"], errors="raise").astype(int)
    df["deaths"] = pd.to_numeric(df["deaths"], errors="raise").astype(int)
    df = df.sort_values(["year", "month_num", "disease"]).reset_index(drop=True)

    if len(df) != 96:
        raise ValueError(f"Expected 96 rows (48 months x 2 diseases), found {len(df)}")
    if df.duplicated(["period", "geography", "disease"]).any():
        raise ValueError("Duplicate period/geography/disease key detected")
    if not df.groupby(["year", "disease"]).size().eq(12).all():
        raise ValueError("Every year/disease group must contain exactly 12 monthly rows")

    print("CareGrid Sentinel — annual totals validation")
    for (year, disease), (expected_cases, expected_deaths) in EXPECTED.items():
        subset = df[(df["year"] == year) & (df["disease"] == disease)]
        actual = (int(subset["cases"].sum()), int(subset["deaths"].sum()))
        ok = actual == (expected_cases, expected_deaths) and len(subset) == 12
        print(f"{year} {disease:<14} monthly={actual[0]:>6,}/{actual[1]:<3,} expected={expected_cases:>6,}/{expected_deaths:<3,} rows={len(subset):2d} {'PASS' if ok else 'FAIL'}")
        if not ok:
            raise ValueError(f"Validation failed for {year} {disease}: {actual}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False, encoding="utf-8")
    print(f"\nSUCCESS: wrote {len(df)} rows to {OUTPUT}")
    print("Coverage: Kerala statewide, monthly dengue and leptospirosis, 2021–2024.")
    print("Important: classification metadata differs by year; read classification_note before modelling.")
    print("This remains a short statewide series and does not justify robust forecasting claims by itself.")

if __name__ == "__main__":
    main()
