# CareGrid Sentinel — Historical Data Readiness Report

> **Subsequent source-verification update (2026-11-10):** The audit below predates the follow-up dashboard investigation. An official Kerala Health Department JSON source now provides a complete 2023–2025 district-month candidate, separately stored and validated. This does not resolve disease-definition comparability or the 2025 DHS/dashboard mismatches, and it does not change the original 2021–2024 historical files. See [classification comparison](historical_classification_comparison.md) and [district-month data research](district_monthly_data_research.md) for current findings.

**Investigation date:** 2026-11-10
**Scope:** Local disease, weather, official annual-report, and daily IDSP products; historical source availability; spatial readiness. No data was changed, synthesized, downloaded, or reclassified.

## Executive findings

- The curated statewide monthly dataset covers January 2021–December 2024 with 96 rows. It contains two diseases, one reported category per disease/year, and deliberately preserves different 2021/2022 classification meanings.
- An official 2025 DHS annual report with monthly tables is already imported as a separate validated surveillance snapshot. It contains all 12 months of Dengue and Leptospirosis `Confirmed` and `Probable` records. These records are consumed through the separate official-surveillance API/page, not the core `data/processed` monthly forecasting input.
- The literal category label `Confirmed` occurs in the 2023, 2024, and 2025 source series. That is a useful candidate for a separate 2023–2025 monthly series, but matching labels and validation totals do **not** prove that diagnostic definitions or reporting practices are comparable across documents. Consequently, 2025 should not yet be silently appended to the existing model input or called a semantically verified extension.
- Daily 2026 IDSP records are a different reporting product. Daily, present-month, cumulative, suspected, confirmed, district daily, and source-dash values remain separate. They are not monthly historical observations.
- There is no verified district-by-month disease panel. Annual district counts and representative-point weather cannot substitute for one.

## Local dataset inventory

Dimensions and null/duplicate counts below were checked directly from the files. Missing cells in the annual district CSV are optional `source_header_note` metadata, not missing case/death observations.

| File | Dimensions | Coverage / grain | Geography and categories | Nulls / exact duplicates | Use and limits |
|---|---:|---|---|---:|---|
| `data/processed/kerala_disease_monthly_2021_2024.csv` | 96 × 16 | 2021-01–2024-12; 48 distinct months | Kerala statewide; Dengue/Leptospirosis; 12 rows per disease/year | 0 / 0 | Main historical monthly source for API, climate joins, and the baseline hindcast. Category meaning varies by year. |
| `data/processed/kerala_disease_monthly_2024.csv` | 48 rows | 2024-01–2024-12 | Two diseases × Confirmed/Probable | No duplicate keys identified in project reports | One-year extraction/source comparison; not additional years of history. |
| `data/processed/kerala_disease_monthly_confirmed_2023_2024.csv` | 48 rows | 2023-01–2024-12 | Statewide, two diseases, Confirmed only | 0 duplicate natural keys | Candidate explicit-Confirmed series across two source documents; semantic comparability still requires source review. |
| `data/interim/kerala_disease_monthly_2021_2022.csv` | 48 rows | 2021-01–2022-12 | Two diseases, source-specific labels | No duplicate keys identified in project reports | Intermediate transcription; classifications are not equivalent to later Confirmed labels. |
| `data/interim/kerala_disease_monthly_confirmed_2023.csv` | 24 rows | 2023-01–2023-12 | Two diseases, Confirmed | No duplicate keys identified in project reports | Source-validated intermediate series. |
| `data/processed/kerala_district_annual_disease_2020_2024.csv` | 280 × 18 | 2020–2024; annual | 14 districts, two diseases, Confirmed and Probable | 224 null metadata cells in `source_header_note`; 0 duplicate rows | Useful for annual district comparisons only. Not a district-month panel. |
| `data/processed/kerala_weather_monthly_district_proxy_2021_2024.csv` | 48 × 9 | 2021-01–2024-12; monthly | Statewide proxy aggregated from 14 representative district locations | 0 / 0 | Precipitation and temperature only; equal-weight locations, not population-weighted. |
| `data/processed/kerala_disease_weather_monthly_2021_2024.csv` | 96 × 24 | 2021-01–2024-12; monthly | Disease records joined to the statewide weather proxy | 0 / 0 | Preserves source classifications; not a district-level climate dataset. |
| `data/live_surveillance/latest.json` | 324 monthly statewide rows in snapshot | 2025-01–2025-12; monthly tables in annual report | 27 disease/category series; Dengue and Leptospirosis include Confirmed and Probable separately | Snapshot validation passed; 12 months for every published series | Separate 2025 official-report snapshot and Live Monitor source, not part of the core monthly historical CSV or existing baseline experiment. |
| `data/live_surveillance/latest.json` annual tables | 32 statewide annual rows; 416 district annual rows | Reporting year 2025; annual | District tables cover 13 named districts; Alappuzha has no district page | Snapshot validation passed with documented district/state differences | Annual only; no district-month values. |
| `data/live_surveillance/daily_idsp/latest.json` plus versioned snapshots | 97 successfully imported distinct dates in the captured 2026 backfill | 2026-07-25–2026-11-01; report-date grain | Statewide disease/subtype table and daily district tables where present; suspected/confirmed separated | Three discovered reports were not imported because they were image-only | Daily provisional surveillance, not a continuous complete calendar series and not a monthly historical dataset. |

### Raw sources and provenance

- `data/raw/districtwise_disease_cases_2020_2024.xlsx` and `data/raw/districtwise_disease_deaths_2020_2024.xlsx`: five annual sheets apiece (2020–2024); official Kerala Health Department workbooks. A recorded 2024 death-sheet title mismatch is retained in source metadata.
- `data/raw/DHS-CD-Data-2025-Approved.pdf`: official DHS 2025 approved report, source of the separate annual/monthly snapshot. The source index did not state a formal publication date in the stored audit; retrieval and HTTP/PDF metadata are separately recorded.
- `data/raw/idsp_daily/`: preserved source PDFs for daily report imports/backfill, including reports that could not be parsed.
- `data/raw/open_meteo_weather/`: 14 preserved request/response records. The embedded Open-Meteo responses contain daily data from 2021-01-01 through 2024-12-31 (1,461 dates per location) for precipitation sum and mean/minimum/maximum temperature. The source code does not request humidity.
- Historical monthly source URLs and table pages are recorded in `data/interim/historical_monthly_sources.md`; per-row source fields are retained in the monthly CSVs.

The source provenance is carried as report names, source labels, URLs, workbook sheets/pages, retrieval timestamps, hashes, parser/schema versions, and validation flags where available. Imported values remain source-reported counts; they are not population-adjusted incidence rates.

## Reporting categories and comparability

| Reporting period | Monthly category in current data | Source interpretation |
|---|---|---|
| 2021 | `reported_category_status_not_split` | The statewide monthly/annual tables do not publish separate Probable rows for these diseases. It is not safe to equate this category to later Confirmed. |
| 2022 | `non_probable_category_probable_separate` | The source reports separate Probable totals in its annual summary; the monthly rows correspond to the other category, but the monthly table does not explicitly name it Confirmed. |
| 2023 | `Confirmed` | Monthly tables explicitly label confirmed Dengue and Leptospirosis. |
| 2024 | `Confirmed` | The annual DHS report explicitly labels confirmed monthly series; it is a different source document from 2023. |
| 2025 | `Confirmed` and `Probable` | The approved DHS report's monthly source labels include `Con Dengue`, `Prob Dengue`, `Con Lepto`, and `Prob Lepto`; the importer preserves raw labels and maps the reported categories separately. |
| 2026 IDSP daily | `Suspected` and `Confirmed` fields | Report-date counts and cumulative values from preliminary daily IDSP reports. These are separate fields and units from the annual DHS monthly report series. |

### Can 2025 extend the Confirmed monthly series?

**Data availability: yes. Semantic compatibility: not yet established.**

The local 2025 report contains 12 monthly Confirmed values for each target disease, so a candidate explicit-Confirmed sequence would have 36 months per disease for 2023–2025 if added to the existing 2023–2024 Confirmed-only observations. However:

- The 2023, 2024, and 2025 records come from three different official documents.
- A common printed label is not sufficient evidence that surveillance definitions, laboratory confirmation practices, reporting completeness, or revisions are unchanged.
- The 2025 imported report's snapshot validation proves structural/source consistency (including monthly totals and retained source categories), not cross-year epidemiological equivalence.
- The 2025 snapshot is already separately exposed by the annual-report monitor; it is not included in the hash-bound baseline experiment inputs.

Recommendation: review each report's definitions and any revision notes; document an explicit source crosswalk; compare monthly and annual totals/source changes; then curate a **new versioned candidate** preserving original source labels and provenance. Until then, keep it out of the existing confirmed training/evaluation input and report results separately.

## Missing periods and daily IDSP interpretation

- The current curated statewide monthly file has every month from 2021-01 through 2024-12. Its 2021 and 2022 rows are complete but classification-incompatible with an explicit Confirmed-only series.
- The official 2025 report has all 12 monthly values for each published disease/category series. Those values are in the separate snapshot, not the core historical monthly CSV.
- No verified monthly disease series exists here for 2020 or 2026. The annual 2020–2024 district data do not fill those monthly gaps.
- The captured IDSP index/backfill discovered 100 dated 2026 posts from 2026-07-25 through 2026-11-01. Ninety-seven distinct dates were imported; 2026-08-30, 2026-10-27, and 2026-10-29 remain unimported because the reports were image-only. Reports before July 25 were not in the captured index; that absence does not prove a report was never published.
- A missing IDSP report date is missing reporting, not a zero-case day. The report's dash is retained as `source_dash_uninterpreted` with numeric null; blank cells are `not_reported`; only printed zeroes are numeric zero.
- For each IDSP report, `daily`, `present_month`, and `cumulative_2026` are distinct source columns. Cumulative totals are running values and must never be summed across report dates. District deaths are unclassified by case category and remain unassigned.
- IDSP reports are preliminary and subject to change after laboratory/death review. Their daily Confirmed counts must not be added to annual-report monthly Confirmed values or used as a substitute for missing monthly totals.

## District and climate readiness

### Disease geography

- The historical district CSV contains 14 districts × 5 years × 2 diseases × 2 classifications = 280 annual rows.
- The 2025 DHS annual report includes 416 district annual rows for 13 named districts; Alappuzha is absent and is not imputed. Its district totals also do not fully reconcile to statewide annual totals; recorded differences are exposed, not corrected.
- The 2026 IDSP backfill has daily district tables for 14 official district codes on the 97 successfully parsed dates. This is report-date grain and has date gaps; it does not supply a long, validated district-month series.
- The official Health Department district disease dashboard is documented as a potential source, but it could not be accessed in this environment during the prior/current source investigation. Its export controls, definitions, endpoint, and historical coverage remain **unknown**; no endpoint was guessed and no dashboard data were downloaded.
- Therefore, there is no verified continuous district-month Dengue/Leptospirosis dataset available for model development now.

### Weather

- The available daily weather observations are from 14 approximate district-headquarters locations, not official district stations or population-weighted centroids.
- The current processed weather file averages those locations equally into a statewide monthly proxy for 2021–2024.
- It includes precipitation and temperature (mean/min/max); relative humidity is not requested or available in this pipeline.
- There is no joined district-month disease/weather panel. A statewide disease total must not be copied across districts or joined to annual district totals as if the spatial/temporal grain matched.
- Historical observed weather is not future-known weather at a forecast origin. Climate forecast models would need weather forecasts or an explicitly retrospective association design, not realized holdout weather as a predictor.

## Further official historical monthly reports

The locally documented annual DHS monthly report sources establish monthly statewide disease tables for 2021, 2022, 2023, 2024, and 2025. The 2025 approved report has already been retrieved locally and validated. This is an opportunity to extend a carefully crosswalked **statewide** candidate series by one year.

The DHS communicable-disease index and the Health Department dashboard were not reliably rendered by the available web/network tools during this audit; the official pages returned generic contact content or transport failures. No additional pre-2021 or 2026 monthly report series was verified. Older official monthly PDFs may exist in archives, but their existence, continuity, disease definitions, and accessible tables remain unconfirmed. Verify each candidate from its original official report before adding it. Do not infer publication or absence from a failed page fetch.

## Readiness decision

| Intended analysis | Current status | Reason |
|---|---|---|
| Descriptive statewide monthly counts, 2021–2024 | Available with caveats | Complete month keys; 2021/2022 classifications remain separate. |
| Explicit-Confirmed statewide candidate, 2023–2024 | Available for limited retrospective baseline | 24 monthly observations per disease across two source documents; only one 12-month holdout is currently available. |
| Explicit-Confirmed statewide candidate through 2025 | Source data available; cross-year use pending | 12 monthly values per disease are present, but cross-document definition/reporting comparability has not been established. |
| 2020–2025 district annual comparison | Available with caveats | 2020–2024 has 14 districts; 2025 source has only 13 district pages and reconciliation differences. |
| District-month descriptive forecasting | Not ready | No validated long-run district-month target data. |
| Climate-lag modelling | Not ready for defensible forecasting | No district-month disease alignment; short statewide series; no humidity; weather is proxy and future weather is unavailable. |
| Bayesian outbreak model | Not ready for defensible evaluation | No stable harmonized target, adequate comparable history, validated outbreak labels/thresholds, or multiple evaluation windows. |

No values were reclassified, merged, imputed, or converted from annual to monthly. All reported distinctions and source caveats should remain part of any future dataset contract.
