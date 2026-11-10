# CareGrid Sentinel — IDSP 2024 extraction starter

## What this adds
- `data/raw/IDSP-Annual-Data-2024.pdf`: the original Kerala IDSP report.
- `src/caregrid/extract_idsp_2024.py`: reproducible extractor for the monthly target-series table.
- `data/processed/kerala_disease_monthly_2024.csv`: 48 long-format rows (12 months × 4 target series).
- `data/interim/idsp_2024_source_pages.txt`: extracted source-page text for audit.

## Run on Windows PowerShell
From the `CareGrid-Sentinel` project root:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\extract_idsp_2024.py
```

The script reads `data/raw/IDSP-Annual-Data-2024.pdf`, extracts the monthwise data from PDF page 17, and writes the CSV and audit text into `data/processed/` and `data/interim/`. It checks case and death totals against the monthwise totals and annual summary in the same report before writing the CSV.

## Data fields
- `period`: month in `YYYY-MM` form.
- `geography`: Kerala, statewide (not district-level).
- `disease`: Dengue or Leptospirosis.
- `classification`: Confirmed or Probable, retained separately as reported.
- `cases`, `deaths`: reported monthly counts.
- `source_page`, `validation_page`, `source_url`: provenance fields.

## Validated 2024 totals
- Probable dengue: 53,536 cases; 13 deaths.
- Confirmed dengue: 20,674 cases; 128 deaths.
- Probable leptospirosis: 2,428 cases; 143 deaths.
- Confirmed leptospirosis: 3,552 cases; 251 deaths.

## Important limitation
This is a data-pipeline smoke test and a single year of statewide monthly observations. By itself it is not enough for a reliable forecasting model and it cannot support district-level forecasts. The next data task is to obtain and validate multiple historical years, ideally at district-month resolution, before training or evaluating a forecasting model.
