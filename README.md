# CareGrid Sentinel — district-level annual data (2020–2024)

## What is included
- `data/processed/kerala_district_annual_disease_2020_2024.csv`: normalized long-format panel with annual cases and deaths for dengue and leptospirosis, split by the source's `Confirmed` and `Probable` labels.
- `reports/kerala_district_annual_validation_2020_2024.csv`: district-sum totals by year, disease, and classification.
- `reports/statewide_monthly_vs_district_annual_crosscheck_2021_2024.csv`: cross-source numeric comparison against the previously curated statewide monthly series.
- `reports/data_quality_audit.md`: summary of workbook structure, data caveats, and intended use.
- `data/raw/districtwise_disease_cases_2020_2024.xlsx`: original uploaded disease-cases workbook (copied without edits).
- `data/raw/districtwise_disease_deaths_2020_2024.xlsx`: original uploaded disease-deaths workbook (copied without edits).

## Coverage
- Years: 2020–2024
- Districts: 14 per year
- Diseases: Dengue, Leptospirosis
- Classifications: Confirmed, Probable
- Rows in tidy CSV: 280 = 5 years × 14 districts × 2 diseases × 2 classifications
- Temporal granularity: annual, not monthly

## District-code normalization
TVM = Thiruvananthapuram; KLM = Kollam; PTA = Pathanamthitta; ALP = Alappuzha; KTM = Kottayam; IDK = Idukki; EKM = Ernakulam; TSR/TCR = Thrissur; PKD = Palakkad; MLP = Malappuram; KKD = Kozhikode; WYD = Wayanad; KNR = Kannur; KSD = Kasaragod.
The 2023 source workbooks use `TCR` for Thrissur in some sheets; it is normalized to `TSR` in the tidy dataset.

## Data-quality notes
1. The source tables report annual district-level counts; they do not provide district-by-month disease counts.
2. In the deaths workbook, the sheet name `CD DEATH_2024` is the year identifier, but its title cell incorrectly says `Number of Death 2021`. This mismatch is recorded in `source_header_note`; the 2024 sheet has been assigned to year 2024 based on its tab name.
3. Source terminology is preserved in `source_case_label` and `source_death_label`. Even when the category text matches, do not assume case definitions/reporting practices are perfectly comparable across years without checking the official reports.
4. These are raw counts. For fair district comparisons, consider population denominators (rates per 100,000) if reliable annual population estimates are available.
5. Cross-source audit found that the 2021 dengue confirmed sum in the district workbook is 3,261, versus 3,251 in the statewide monthly series. The 2021 monthly series does not split disease counts by status, so this discrepancy needs source review; do not silently reconcile it.
6. Five annual observations per district are not enough on their own for a robust climate-lag forecasting model. This panel supports annual district comparisons/hotspot exploration, while monthly district-level surveillance data still needs to be obtained.
7. The uploaded workbook includes other diseases, but only dengue and leptospirosis rows were curated for this first CareGrid data product.

## Public source page
Both workbooks were downloaded from the Kerala Health Department's Department Data page:
https://health.kerala.gov.in/department-data

The CSV carries source title and URL columns so lineage stays attached to each row.

## Historical weather integration (statewide exploratory only)

Run the reproducible Open-Meteo acquisition, validation, and descriptive analysis pipeline with the existing environment:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\integrate_historical_weather.py
```

By default, the script reuses preserved API response files in `data/raw/open_meteo_weather/`. Pass `--refresh` to explicitly request fresh responses. It uses daily precipitation and temperature for one documented representative location in each of Kerala's 14 districts. Their equal-weight monthly mean is a **statewide proxy**, not an official population-weighted statewide weather measurement.

The script joins weather only to `data/processed/kerala_disease_monthly_2021_2024.csv`; it does not use or alter the annual district dataset. The source's year-specific classification labels remain separate, missing disease months are never filled, and the 2021 dengue total discrepancy remains unresolved.

Successful runs create:

- `data/processed/kerala_weather_monthly_district_proxy_2021_2024.csv`
- `data/processed/kerala_disease_weather_monthly_2021_2024.csv`
- `reports/weather_data_quality_report.md`
- `reports/analysis_data_readiness.md`
- Three descriptive figures under `reports/figures/`

Raw API responses include request parameters, retrieval timestamps, selected response headers, and the original response body. The correlations and charts are exploratory and do not establish causality or justify forecasts. The monthly series is short and statewide; district-month disease records are still required for district-level climate analysis.

## CareGrid Sentinel application

The project includes a React + TypeScript + Vite dashboard in `dashboard/` and a read-only FastAPI data API in `src/caregrid/api.py`. The forecasting experiment is a separate, reproducible retrospective baseline hindcast. It does not publish operational future forecasts, live alerts, district maps, or actual hospital capacity data.

### Live Kerala Health Monitor

The monitor now separates the latest retrieved **daily DHS IDSP report** from the **2025 annual report** and the **2021–2024 historical datasets**. The report snapshot is not a real-time feed. The verified daily source index is [Kerala DHS IDSP](https://dhs.kerala.gov.in/en/idsp-2/); the latest successfully retrieved report is dated **1 November 2026** and its official post was published on **2 November 2026**:

- [Official report post](https://dhs.kerala.gov.in/en/2026/11/02/01-11-2026/)
- [Original DHS PDF](https://dhs.kerala.gov.in/wp-content/uploads/2026/11/DR-CD-01.11.2026sd.pdf)
- The original PDF is preserved in `data/raw/idsp_daily/`; the parsed, versioned snapshot and source status are stored separately under `data/live_surveillance/daily_idsp/`.
- The report includes statewide daily, present-month and cumulative-2026 counts, plus a district-wise daily table for all 14 Kerala districts. Suspected and confirmed cases/deaths remain separate. The district death field is unclassified by suspected/confirmed status.
- DHS marks these values preliminary and subject to change after laboratory tests and death audits. Cumulative values are running totals and are never added across report dates.
- For the 1 November report, cumulative dengue is 35,419 suspected cases / 35 suspected deaths and 13,244 confirmed cases / 44 confirmed deaths. Cumulative leptospirosis is 1,455 suspected cases / 92 suspected deaths and 2,465 confirmed cases / 123 confirmed deaths.

Refresh this feed on demand with the reproducible importer:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\import_idsp_daily.py
```

The importer discovers dated report posts from the official index, extracts the actual PDF link from each post, applies request timeouts/size limits, preserves source metadata and the original PDF/hash, validates report and district dates/codes/counts, then atomically publishes a snapshot. A failed refresh retains the last valid snapshot and records the failed attempt. No scheduled polling or public API is assumed.

Daily endpoints are available under `/api/live-surveillance/daily/`: `latest`, `cumulative`, `diseases/daily`, `diseases/month-to-date`, `districts`, `latest-date`, `source-status`, `last-update`, `source`, and `trends`. The existing `/api/live-surveillance/*` annual-report endpoints remain separate. See `reports/daily_idsp_data_quality_report.md` for source provenance, validation, exact coverage and limitations.

The optional 2026 backfill command processes actual dated posts on the official index, preserves every successfully downloaded PDF (including documents that cannot be parsed) with its SHA-256, and writes `data/live_surveillance/daily_idsp/backfill_2026_status.json`:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\import_idsp_daily.py --backfill-2026
```

The report's printed `-` is preserved as an uninterpreted source marker with a null numeric value; blank cells are marked not reported, and explicit `0` remains zero. Missing calendar dates are not interpolated. The rolling 7-day and 30-day summaries are withheld unless both equivalent windows have every report date and a numeric value for the metric. See the backfill manifest for actual discovered dates, unresolved PDFs, and dates not listed on the captured index page.

To optionally register a once-daily Windows Task Scheduler check (default 07:00 local time):

```powershell
.\scripts\register_idsp_daily_task.ps1 -At "07:00"
```

The task runs only while the current user is logged on. Task Scheduler ignores overlapping instances, and the runner also uses an exclusive lock. Append-only logs are written to `data/live_surveillance/daily_idsp/logs/scheduled_import.log`; the application does not depend on the task or a continuously running process. Run the runner manually with `.\scripts\run_idsp_daily.ps1`, or omit the setup entirely and refresh on demand.

The **2025 DHS annual report** remains available for historical comparison. It is not current daily surveillance; 13 of 14 districts appear in that annual report and Alappuzha is not imputed. Its district counts remain annual only, and source classifications are not merged. See `reports/live_kerala_surveillance_data_quality.md`.

No verified official bed-occupancy, ICU, available-bed, oxygen-capacity or hospital-wise patient-load feed was identified in the DHS pages inspected or connected to this application. The existing capacity simulator remains hypothetical only.

Refresh the report snapshot from the exact DHS PDF URL that was verified:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\import_official_surveillance_report.py --download
```

Or import a locally saved copy of the official PDF:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\import_official_surveillance_report.py --pdf .\data\raw\DHS-CD-Data-2025-Approved.pdf --last-modified "Wed, 23 Sep 2026 13:51:49 GMT"
```

The importer validates the report structure, labels, periods, counts, district mapping, duplicate keys, and monthly-to-annual totals before publishing an atomic snapshot. A failed refresh records an error and retains the last valid snapshot. Source/methodology details and the actual report are available from the dashboard. See `reports/live_kerala_surveillance_data_quality.md` for the verified access method, actual coverage, reconciliation differences, and freshness rules.

### Install and run locally (PowerShell)

From the project root, install the API requirements into the existing virtual environment, then launch FastAPI:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn caregrid.api:app --app-dir .\src --reload
```

In another terminal, install the dashboard dependencies once and start Vite:

```powershell
Set-Location .\dashboard
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://127.0.0.1:5173`). The Vite development server proxies `/api` requests to FastAPI on port 8000. To serve the built dashboard and API from FastAPI, run `npm run build` in `dashboard/` and then start the API; the API serves `dashboard/dist` when that build exists.

### Application pages

- **Overview:** available observed coverage, monthly reported trends, and annual statewide totals without combining source classifications.
- **Disease surveillance:** filters for disease, year and source classification; reported cases/deaths and CSV export with provenance fields.
- **Live Kerala Health Monitor:** latest retrieved daily 2026 DHS IDSP report, separate suspected/confirmed daily, month-to-date and cumulative counts, daily district rows, source freshness and provisional warnings, followed by a distinct 2025 annual comparison. A single daily snapshot is not interpreted as a trend or outbreak.
- **District explorer:** annual district comparison table/chart. No district boundaries were found, so no map is drawn.
- **Climate insights:** validated monthly precipitation/temperature alongside statewide disease observations. Weather is an equally weighted proxy from 14 representative locations, not a population-weighted statewide measure.
- **Forecasts & risk:** experimental 2024 historical holdout comparison for explicitly Confirmed 2023–2024 monthly disease counts only. There are not enough comparable years for dependable forecasting; no future predictions, risk scores, or alerts are generated.
- **Hospital capacity simulator:** user-entered hypothetical values only; no real facility status or capacity is connected.
- **Sources & methodology:** provenance, report links, coverage, category definitions, and the unresolved 2021 dengue discrepancy.

### Tests and production build

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Set-Location .\dashboard
npm test -- --reporter=dot
npm run build
```

### Reproduce the baseline forecasting experiment

Run from the repository root with the existing Python environment:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\run_forecasting_experiment.py
```

The script writes the readiness audit and experiment report under `reports/`, metrics/predictions/residuals/configuration under `reports/forecasting_experiment/`, and actual-versus-predicted, residual, and baseline-error plots under `reports/figures/`. The API endpoint `GET /api/forecasting/experiment` serves the experiment only while its disease and weather source hashes match the current inputs. `forecasting_available` remains false for future operational forecasts.

The readiness audit found 12 monthly observations each for the unharmonized 2021 and 2022 categories and 24 Confirmed observations per disease across 2023–2024. The requested 2021–2023 training window cannot be treated as one compatible series. A limited 12-month 2023 training / 12-month 2024 holdout is possible for Confirmed data, but provides only one test year; a repeated 12-month rolling-origin validation is not possible. Seasonal MASE is unavailable because the training set contains no two observations separated by 12 months. Climate-enhanced performance was not evaluated: there is insufficient training history for defensible lag selection, and actual weather during the 2024 holdout would not be available at a 2023 forecast origin.
