# Kerala monthly district disease data: source investigation

> **Status update (2026-11-10):** This report records an earlier access attempt on 2026-10-24. A later investigation verified the dashboard page and its linked public JSON endpoint, captured a hash-bound source snapshot, and built a separate 2023–2025 candidate. The earlier “unknown/not verified” findings below describe that first attempt only and are superseded for current source availability by [district monthly data research](district_monthly_data_research.md). The candidate remains provisional and is not merged with DHS or the existing historical data.

**Investigation date:** 2026-10-24
**Project:** CareGrid Sentinel
**Initial decision (2026-10-24):** No district-month source was obtained or verified during that investigation.

## Executive summary

The two requested Kerala Health Department pages could not be loaded from this environment. The supplied dashboard URL and Department Data URL failed in the integrated browser (`ERR_FAILED (-2)`), `web_fetch` returned a transport-level DNS/connection/TLS failure, and direct HTTPS requests timed out. Therefore, I could not inspect the dashboard interface, its filters, export controls, page source, or network requests.

It is **not established** whether the dashboard offers monthly district exports or a documented/public data endpoint. No endpoint was guessed or probed, and no access controls were bypassed. No data was downloaded from the dashboard.

The existing project contains annual district-level records for 2020–2024 and monthly **statewide** records for 2021–2024. The statewide files cannot be transformed into district observations. No monthly district-level observations were fabricated, interpolated, or inferred.

## Official pages attempted

| Supplied official URL | Attempt and observed result |
| --- | --- |
| [Kerala Health Department disease prevalence dashboard](https://health.kerala.gov.in/static_disease_prevalence) | Integrated browser returned `ERR_FAILED (-2)`; `web_fetch` failed with transport-level DNS/connection/TLS error; direct HTTPS request timed out after 15 seconds. |
| [Kerala Health Department Department Data](https://health.kerala.gov.in/department-data) | Integrated browser returned `ERR_FAILED (-2)`; `web_fetch` failed with transport-level DNS/connection/TLS error; direct HTTPS request timed out after 15 seconds. |

These errors describe this investigation environment only. They do not establish that the official site or its data is unavailable generally.

## What could and could not be established

| Question | Finding |
| --- | --- |
| Can monthly district observations be exported from the dashboard? | **Unknown.** The dashboard could not be loaded, so export controls were not inspected. |
| Is there a documented or publicly accessible data endpoint? | **Unknown.** No endpoint was discoverable from the inaccessible page; none was guessed. |
| Which diseases, districts, years, metrics, or classifications does the dashboard expose? | **Unknown for the dashboard.** Its filters and metadata could not be inspected. |
| Does the dashboard provide cases and deaths separately? | **Unknown for the dashboard.** |
| Is the dashboard data truly monthly at district level? | **Not verified.** No dashboard response or export was obtained to establish its grain. |
| Can dashboard totals be reconciled with official reports? | **Not assessable without its data and definitions.** Existing project notes document official-report comparisons for statewide data; these are not a validation of dashboard district-month data. |
| What restrictions or missing periods apply? | **Unknown for the dashboard.** The page could not be inspected. |

Do not interpret an unknown as evidence that a particular feature is absent or present.

## Local data inspected

### Annual district dataset

`data/processed/kerala_district_annual_disease_2020_2024.csv` has 280 rows and 18 columns. It contains annual records for 14 districts, Dengue and Leptospirosis, with `Confirmed` and `Probable` retained separately. Its fields include year, district and district code, disease, classification, cases, deaths, source labels, workbook-sheet metadata, source titles/URLs, and `temporal_granularity=annual`.

The existing audit in `reports/data_quality_audit_latest.md` records complete 2020–2024 district coverage and explicitly states that the file contains annual district-level records, not monthly district-level observations. It also records the 2024 death-workbook title discrepancy and the 2021 dengue cross-source difference (district Confirmed total 3,261 versus statewide monthly total 3,251). Neither discrepancy is resolved here.

### Monthly statewide files

Local inspection found these processed monthly products:

| File | Rows / scope | Coverage and categories |
| --- | --- | --- |
| `data/processed/kerala_disease_monthly_2021_2024.csv` | 96 rows; `geography=Kerala`, `geography_level=Statewide` | 2021–2024, 12 months/year, Dengue and Leptospirosis. Classification labels vary by year: `reported_category_status_not_split`, `non_probable_category_probable_separate`, and `Confirmed`. |
| `data/processed/kerala_disease_monthly_confirmed_2023_2024.csv` | 48 rows; statewide | 2023–2024, two diseases, `Confirmed`. |
| `data/processed/kerala_disease_monthly_2024.csv` | 48 rows; statewide | 2024, two diseases, `Confirmed` and `Probable`. |

The project’s `data/interim/historical_monthly_sources.md` describes the previously curated official DHS annual reports and the classification caveats for statewide monthly figures. The existing combine/extract scripts document statewide total checks against those reports. This investigation did not independently re-fetch or rerun those source-report checks, and they do not establish district-month availability.

## Readiness decision

| Intended use | Suitable with data currently verified in the project? | Reason |
| --- | --- | --- |
| Monthly district-level descriptive analysis | **No** | District observations currently have annual granularity. Monthly observations are statewide only. |
| Join disease observations to district-level weather | **No** | There is no verified monthly district disease key to align with district-month weather. Statewide totals cannot be assigned to districts. |
| Test weather lags | **No** | District-month disease observations are missing; the dashboard source and definitions remain unverified. |
| Build and evaluate a forecasting model for district-month burden | **No** | Required target granularity is absent. The available statewide history is only 48 monthly observations per disease across four years, with year-dependent classification labels; this is not a validated basis for a district-level forecasting claim. |

Any future forecasting evaluation should use chronological holdout or rolling-origin validation, not a random train/test split. Model training was not started.

## Exact next step

1. Open the supplied [disease prevalence dashboard](https://health.kerala.gov.in/static_disease_prevalence) and [Department Data page](https://health.kerala.gov.in/department-data) in a browser/network where those official pages load.
2. On the dashboard, inspect the visible filters and determine whether it offers **month/year, district, disease, case/death metric, and classification**. Do not assume these controls exist.
3. If the official interface offers a CSV/XLSX export, export the original, unmodified data for the full available date range. If it only exports a selected view, retain each original export and its selected filters; do not manually fill unreported district-months with zero.
4. Record the exact page URL, download/export date, visible filter selections, source labels/definitions, and any coverage or status notes. Save the original export under `data/raw` with a descriptive filename and provide it for schema inspection.
5. If no export is available, ask the Kerala Health Department for the official district-by-month case and death extract, including classifications, reporting dates, district identifiers, and definitions. Do not substitute an undocumented endpoint.

Once an original official export or department-provided extract is available, the next implementation should begin by inspecting its real headers and granularity. Then build an importer and validation against that source, preserving its raw file and flagging missing district-month combinations for investigation. Do not integrate district-level weather or claim district-month lag readiness before those checks pass.

## Files changed

Only this investigation report was added. No source data, existing scripts, annual dataset, statewide monthly dataset, or unrelated project files were modified. No downloader/importer was created because a legitimate reproducible dashboard source format or endpoint could not be confirmed.
