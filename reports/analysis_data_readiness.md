# Analysis data readiness — statewide monthly disease and weather

- Generated (UTC): 2026-10-28T05:01:25+00:00
- Disease source: `data/processed/kerala_disease_monthly_2021_2024.csv` (read-only; no source rows changed).
- Integrated dataset: `data/processed/kerala_disease_weather_monthly_2021_2024.csv`
- Weather quality report: `reports/weather_data_quality_report.md`

## Scope and source meaning

- Disease input has 96 statewide monthly rows across 48 observed months (2021-01 to 2024-12); it is not district-month disease data.
- The annual district dataset is not used in this monthly join. No district-month disease values are inferred from annual counts.
- Cases and deaths are retained from the statewide source; classifications remain distinct, including 2021 `reported_category_status_not_split`, 2022 `non_probable_category_probable_separate`, and 2023–2024 `Confirmed`.
- The 2021 dengue difference documented in the existing audit (3,251 statewide monthly versus 3,261 district confirmed annual total) remains unresolved and is not reconciled by this pipeline.
- Empty disease months are not changed to zero. Missing reporting months stop this pipeline.

### Disease coverage by source category

| Year | Disease | Source classification | Rows |
| --- | --- | --- | --- |
| 2021 | Dengue | reported_category_status_not_split | 12 |
| 2021 | Leptospirosis | reported_category_status_not_split | 12 |
| 2022 | Dengue | non_probable_category_probable_separate | 12 |
| 2022 | Leptospirosis | non_probable_category_probable_separate | 12 |
| 2023 | Dengue | Confirmed | 12 |
| 2023 | Leptospirosis | Confirmed | 12 |
| 2024 | Dengue | Confirmed | 12 |
| 2024 | Leptospirosis | Confirmed | 12 |

## Weather method

- Source: Open-Meteo Historical Weather API, using daily `precipitation_sum` (mm) and `temperature_2m_mean/min/max` (°C) in `Asia/Kolkata`.
- Fourteen representative locations, one approximate district-headquarters point per district, are documented in the acquisition script and raw response metadata.
- Monthly precipitation is the equal-weight mean of the fourteen location-level monthly totals. Temperature metrics are equal-weight means of each location's monthly daily-temperature metric.
- The resulting weather series is a **proxy**, not an official population-weighted statewide measure or a district-wide spatial average. API-selected historical model is not pinned.
- Raw responses and request/retrieval metadata are preserved under `data/raw/open_meteo_weather/`; reruns reuse these files unless `--refresh` is specified.

## Coverage and join validation

| Check | Result |
| --- | --- |
| Disease/weather month overlap | 48 joined months |
| Unmatched disease months | None |
| Unmatched weather months | None |
| Monthly weather location completeness | PASS (14/14 locations) |
| Duplicate integrated natural keys | 0 |
| Integrated records | 96 |

## Exploratory descriptive associations

The table reports Pearson correlations of monthly cases with same-month weather **only as descriptive associations**. Correlation does not establish that weather causes disease changes. Reporting classifications are not harmonized across years, observations are few, and this analysis does not adjust for seasonality, reporting changes, population, lags, or confounders. No model was trained.

| Disease | Source classification | Weather measure | Months (n) | Pearson r | Interpretation |
| --- | --- | --- | --- | --- | --- |
| Dengue | Confirmed | monthly precipitation (mm) | 24 | 0.578 | descriptive Pearson correlation only; not causal |
| Dengue | Confirmed | monthly mean temperature (°C) | 24 | -0.617 | descriptive Pearson correlation only; not causal |
| Dengue | non_probable_category_probable_separate | monthly precipitation (mm) | 12 | 0.603 | descriptive Pearson correlation only; not causal |
| Dengue | non_probable_category_probable_separate | monthly mean temperature (°C) | 12 | -0.898 | descriptive Pearson correlation only; not causal |
| Dengue | reported_category_status_not_split | monthly precipitation (mm) | 12 | 0.429 | descriptive Pearson correlation only; not causal |
| Dengue | reported_category_status_not_split | monthly mean temperature (°C) | 12 | -0.424 | descriptive Pearson correlation only; not causal |
| Leptospirosis | Confirmed | monthly precipitation (mm) | 24 | 0.422 | descriptive Pearson correlation only; not causal |
| Leptospirosis | Confirmed | monthly mean temperature (°C) | 24 | -0.666 | descriptive Pearson correlation only; not causal |
| Leptospirosis | non_probable_category_probable_separate | monthly precipitation (mm) | 12 | 0.681 | descriptive Pearson correlation only; not causal |
| Leptospirosis | non_probable_category_probable_separate | monthly mean temperature (°C) | 12 | -0.860 | descriptive Pearson correlation only; not causal |
| Leptospirosis | reported_category_status_not_split | monthly precipitation (mm) | 12 | 0.131 | descriptive Pearson correlation only; not causal |
| Leptospirosis | reported_category_status_not_split | monthly mean temperature (°C) | 12 | -0.707 | descriptive Pearson correlation only; not causal |

## Charts

- `reports/figures/statewide_monthly_disease_trends_2021_2024.png`
- `reports/figures/kerala_monthly_weather_proxy_2021_2024.png`
- `reports/figures/disease_weather_descriptive_associations_2021_2024.png`

## Readiness decision

The joined dataset is suitable for a **limited descriptive, statewide exploratory analysis** for the observed periods and preserved reporting categories. It is not suitable for causal claims, district-level conclusions, robust lag inference, forecasting, or hospital-capacity prediction. The short 48-month statewide series and year-specific classification semantics are substantial limitations.

## Recommended next step

Obtain and validate a multi-year official monthly district-level disease extract with source definitions and reporting metadata before any district-level climate analysis or model work. Keep the current statewide output as a provenance-preserving exploratory baseline only.

## District-month source status update — 2026-11-10

A follow-up investigation verified an official Kerala Health Department dashboard JSON source and created a separate 2023–2025 district-month candidate. This does not change the statewide descriptive results above or establish classification comparability. See [`reports/district_monthly_data_research.md`](district_monthly_data_research.md) and [`reports/historical_classification_comparison.md`](historical_classification_comparison.md) for the source, validation, and 2025 discrepancies. Climate inputs remain representative-point historical estimates, not forecast-origin-known district observations.
