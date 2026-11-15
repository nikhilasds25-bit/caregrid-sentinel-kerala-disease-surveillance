# CareGrid Sentinel — Person 3 Handover

**Branch:** feature/outbreak-detection
**Latest commit:** 029a916
**Status:** Exploratory analysis and chart-data preparation completed locally. Dashboard integration pending team review.

## 1. Responsibilities

Person 3 is responsible for:
- Retrospective unusual-activity detection using EWMA and CUSUM.
- Exploratory historical threshold-exceedance probabilities.
- Forecast visualizations: actual vs predicted, uncertainty bands, and model comparisons.
- Dashboard integration following approval of the API contract.

## 2. Completed Work

### EWMA and CUSUM

Implemented in `src/caregrid/outbreak_detection.py`.

- Uses Confirmed district-month disease counts.
- Covers dengue and leptospirosis across 14 Kerala districts.
- Uses strictly earlier observations for seasonal baselines.
- Supports expanding and optional trailing baselines.
- Uses existing untuned detector parameters.
- Does not use independently validated outbreak labels.

Development analysis, January 2019–December 2024:

| Detector | Records | Flagged months |
|---|---:|---:|
| EWMA | 2016 | 514 |
| CUSUM | 2016 | 233 |

Flags represent exploratory retrospective unusual activity, not confirmed outbreaks.

### Threshold Exceedance

Implemented in `src/caregrid/exceedance.py`.

Methods:
- Historical all-months 90th percentile.
- Historical seasonal-window 90th percentile.

Thresholds use observations available by each forecast origin.

Results:
- 9,408 scored rows.
- 6,720 rows with usable thresholds.
- 2,688 rows with insufficient historical reference.

Predicted probabilities come from 200 approximate predictive draws per forecast.

They are uncalibrated and must not be interpreted as validated outbreak probabilities.

### Forecast Chart Data

Implemented in:
- `src/caregrid/chart_data.py`
- `src/caregrid/run_chart_data.py`

Generated:
- `outputs/chart_data/forecast_bands.csv`
- `outputs/chart_data/model_comparison.csv`
- `outputs/chart_data/chart_data_metadata.json`

Results:
- 14,112 forecast-band rows.
- 312 model-comparison rows.
- All 12 reference configurations matched published reference-table values within rounding tolerance.

The chart data preserves original and adjusted intervals, evidence roles, and uncertainty warnings.

### Retrospective Signal Chart Data

Runner: `src/caregrid/run_anomaly_chart_data.py`

Output: `outputs/anomaly_chart_data/`

Contains 4,032 EWMA/CUSUM records for development years 2019–2024.

### Exceedance Chart Data

Runner: `src/caregrid/run_exceedance_chart_data.py`

Output: `outputs/exceedance_chart_data/`

Preserves unavailable probabilities and separates the 2025 holdout from development results.

## 3. Testing

Latest complete Python test run:

**139 passed, 1 warning.**

The warning concerns Starlette/httpx deprecation.

No failed tests were reported.

## 4. Important Limitations

- No independent outbreak labels or approved operational thresholds.
- No operational outbreak detection or validated alert performance.
- No model declared operationally ready.
- Poisson prediction intervals substantially undercover observed counts.
- Dengue horizons 9–12 have substantial interval undercoverage.
- Predictive draws are approximate and do not model cross-district dependence.
- The forecasting outputs are retrospective backtests, not future forecasts.
- The 2025 holdout is descriptive only and must not be used for tuning.
- Insufficient evidence and unavailable values must remain explicitly identified.

## 5. Dashboard Integration

The existing dashboard uses React, TypeScript, Vite, and Recharts.

The existing backend uses FastAPI.

Person 3's proposed endpoints are documented in:

`reports/person3/PROPOSED_API_CONTRACT.md`

No shared dashboard or API modifications have been made for this integration.

## 6. Generated Files

The following generated outputs remain untracked pending team agreement:

- `outputs/anomaly_chart_data/`
- `outputs/chart_data/`
- `outputs/exceedance_chart_data/`
- `outputs/exceedance_thresholds/exceedance_scored_draws.csv`

The underlying generators are committed locally.

## 7. Pending Decisions from Person 1

1. Approve or revise the proposed API contract.
2. Decide whether generated CSV/JSON outputs should be committed or regenerated.
3. Confirm when to push this branch and create a PR.
4. Confirm validated outbreak definitions or available event labels.
5. Confirm the Vercel frontend/backend deployment architecture.
6. Confirm required source, model, uncertainty, and epidemiological reviews before dashboard integration.

## 8. Next Work

Following approval:

1. Implement read-only API endpoints and tests.
2. Integrate chart components into the dashboard.
3. Show unavailable and insufficient-evidence states explicitly.
4. Run Python tests and frontend tests/build.
5. Prepare and validate deployment configuration.

**No production forecasts or operational public-health alerts are currently provided.**
