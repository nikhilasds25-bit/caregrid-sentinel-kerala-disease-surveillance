# Forecasting experiment report

- Experiment executed (UTC): 2026-11-02T17:31:07+00:00
- Status: **experimental baseline hindcast only; no operational or future forecasts**

## Forecasting question and target

Can simple chronological baselines reproduce monthly statewide reported cases for Dengue and Leptospirosis in 2024, using only each disease's explicitly `Confirmed` 2023 observations?
The target is monthly reported case count (cases), not individual risk, district-month cases, or daily IDSP counts.

## Data and readiness

Input: `data/processed/kerala_disease_monthly_2021_2024.csv`; columns used: `period`, `year`, `disease`, `classification`, `classification_note`, `cases`, `source_label`, `source_file`, `source_page`, `source_url`.
Only the 2023–2024 `Confirmed` rows were used in evaluation. The 2021 not-split and 2022 non-probable categories were not combined with Confirmed. The annual 2020–2024 district data, 2025 annual import, and daily 2026 IDSP data were excluded.
Both evaluated series contain 24 valid, unique, consecutive observations: 12 training months (2023) and 12 holdout months (2024). Source documents change from the 2023 source PDF to the 2024 annual IDSP PDF; source labels remain explicitly Confirmed, but the transition is a limitation.
See `reports/forecasting_readiness_audit.md` and `readiness_audit.json` for candidate coverage, missing/duplicate months, zeros, classification notes, source changes, and IQR flags.

## Baselines and validation

- Naïve: repeat December 2023's observed value for all 2024 months.
- Seasonal naïve: repeat each corresponding 2023 calendar-month value into 2024.
- Chronological split: train January–December 2023; test January–December 2024. No random split or future-fitted preprocessing is used.
- The requested January 2021–December 2023 train interval is not compatible with a single target because classifications change in 2021, 2022, and 2023.
- Only 24 adjacent, explicitly Confirmed observations are available (2023-2024). A 12-month initial training period and 12-month horizon yields only one origin, not repeated rolling-origin validation.

MAE is mean absolute error in reported cases. RMSE is the square root of mean squared error in reported cases and penalizes large misses more. MASE is scaled absolute error; this report uses a 12-month seasonal training scale. It is undefined when training lacks 12-month-separated pairs or the scale is zero. Here the training window contains only one seasonal cycle, so MASE is reported as unavailable rather than replaced with a different scale.

## Results

| Disease | Classification | Model | Test months | MAE (cases) | RMSE (cases) | Seasonal MASE |
|---|---|---|---:|---:|---:|---:|
| Dengue | Confirmed | naive | 12 | 867.333 | 987.826 | Not estimable |
| Dengue | Confirmed | seasonal_naive | 12 | 727.833 | 805.005 | Not estimable |
| Leptospirosis | Confirmed | naive | 12 | 105.167 | 119.130 | Not estimable |
| Leptospirosis | Confirmed | seasonal_naive | 12 | 94.583 | 112.413 | Not estimable |

Metrics are based on one 12-month test year and should not be interpreted as evidence that either baseline is reliable for future years.

## Climate feature investigation

The weather proxy aligns with 24 confirmed disease-months, but no climate-augmented model was fitted or scored. The compatible training window has only 12 months, insufficient for defensible climate-lag selection or multivariable estimation. Observed 2024 weather is also not a feature available at a 2023 forecast origin; using it for the 2024 horizon would leak future information. No lag was selected using the holdout, and no causal inference is made.

## Interpretation, limitations, and decision

This run supplies a reproducible 2024 baseline comparison and actual-versus-predicted values, not a validated production forecasting model. Performance is sensitive to one holdout year, the training sample is one seasonal cycle, and source-document comparability across 2023–2024 should be reviewed. The historical weather proxy is not a forecast feed.

**Decision: future forecasting is not yet scientifically justified for operational use.** The 2024 results may be inspected as a limited retrospective experiment; no future predictions, risk scores, outbreak alerts, or hospital-capacity outputs are published.

Outputs are stored in `reports/forecasting_experiment/`; charts are stored in `reports/figures/forecasting_*.png`.
