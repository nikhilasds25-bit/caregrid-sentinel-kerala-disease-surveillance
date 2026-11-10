# CareGrid Sentinel — Historical Monthly Disease Data (2021–2024)

This package extends the validated statewide monthly dengue/leptospirosis data to four years.

## Files
- `data/interim/kerala_disease_monthly_2021_2022.csv` — monthly records transcribed from official DHS annual reports, including source-classification notes.
- `data/interim/kerala_disease_monthly_confirmed_2023_2024.csv` — previously validated 2023–2024 confirmed-category series.
- `data/processed/kerala_disease_monthly_2021_2024.csv` — combined 96-row dataset (48 months x 2 diseases).
- `src/caregrid/combine_statewide_history.py` — rebuilds and validates the combined dataset.
- `data/interim/historical_monthly_sources.md` — source links, table locations, classification caveats and methodology notes.

## Install in your existing project
Extract this ZIP into `C:\Users\Nikhil\Desktop\CareGrid-Sentinel` (merge folders). Keep your `.venv` and `.git` directories.

## Run the validation/build script
From a PowerShell terminal in the project root:

```powershell
.\\.venv\\Scripts\\python.exe .\\src\\caregrid\\combine_statewide_history.py
```

Expected result: eight `PASS` lines and output at `data\\processed\\kerala_disease_monthly_2021_2024.csv`.

## Important caveats
- Earlier reports do not use identical explicit classification labels across all four years. Always inspect `classification` and `classification_note`.
- The dataset is statewide monthly, not district-monthly.
- Four years is still too little for strong claims about forecasting. Acquire multi-year district-level monthly records before serious modelling.
