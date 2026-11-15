# Uncertainty report (Person 2)

Scope: 80% and 95% prediction intervals, district-month forecasts, 12-month horizon.
Nothing in this report is called "calibrated": no model reached the 0.80 target at all horizons.

## Diagnostics on the original forecasts

- Poisson is badly under-covered at every horizon (for example 13% against a nominal 80%).
- Dengue NB2 80% coverage was below target in all six origin years (0.40 to 0.77).
  Leptospirosis was nearer target (0.74 to 0.85).
- Dengue NB2 bias (predicted/actual by forecast year) ranged from 0.26 (2023 outbreak year)
  to 3.10 (2020, COVID low year). Only 6 forecast years.
- Very wide dengue intervals in June follow large forecasts, because NB2 variance grows with
  the mean. This is not a bug.
- Hypotheses, not confirmed causes: recursive forecasting compounding, month effects,
  annual level shifts.

## Post-hoc conformal calibration

Method: score = distance outside the interval divided by its width. For origin December Y,
only scores from earlier rolling origins are used. Calibrated per disease, model, feature set
and horizon, pooling 14 districts. Fewer than 28 prior scores = left uncalibrated.
Code: src/caregrid/multimodel/calibration.py. Results: reports/interval_calibration/.
It can widen or narrow intervals. It cannot fix a biased mean.

Leakage check (read from the saved file): prior scores per origin were 0, 14, 28, 42, 56, 70
for Dec 2018 to Dec 2023, and 84 for the 2025 holdout (origin Dec 2024), so the holdout used
only the 2018-2023 origins. Dec 2018 and Dec 2019 intervals were unchanged.

### Dengue NB2 history-only, rolling origins (n=56 per horizon), 80% coverage

| Horizon | Before | After |
|---|---|---|
| 1 | 0.80 | 0.80 |
| 2 | 0.75 | 0.70 |
| 3 | 0.62 | 0.55 |
| 4 | 0.73 | 0.82 |
| 5 | 0.71 | 0.84 |
| 6 | 0.55 | 0.84 |
| 7 | 0.61 | 0.80 |
| 8 | 0.59 | 0.70 |
| 9 | 0.50 | 0.62 |
| 10 | 0.48 | 0.71 |
| 11 | 0.50 | 0.68 |
| 12 | 0.54 | 0.70 |

Calibration helped most at horizons 5-7. It lowered coverage at horizons 2-3 and left
horizons 8-12 below 0.80.

### Dengue Seasonal Naive, same rows, 80% coverage after calibration

Horizons 1-5: 0.77, 0.79, 0.88, 0.89, 0.84. Horizons 6-12: 0.62, 0.57, 0.66, 0.71,
0.71, 0.64, 0.62. Not calibrated at horizons 6-12.

### Averages over horizons, rolling origins (80% coverage before -> after)

- Dengue NB2 history-only 0.62 -> 0.73; with climate 0.59 -> 0.77.
- Dengue Seasonal Naive 0.71 -> 0.73.
- Dengue Poisson history-only 0.29 -> 0.70, but width rose from 14.6 to 98.4.
- Leptospirosis NB2 history-only 0.78 -> 0.81 (width 25.6 -> 29.2). Not checked by horizon.

### 2025 holdout (descriptive only, 14 districts, effectively 1-2 independent observations)

- Dengue NB2: coverage near 0.95 on average after calibration,
@'
# Uncertainty report (Person 2)

Scope: 80% and 95% prediction intervals, district-month forecasts, 12-month horizon.
Nothing in this report is called "calibrated": no model reached the 0.80 target at all horizons.

## Diagnostics on the original forecasts

- Poisson is badly under-covered at every horizon (for example 13% against a nominal 80%).
- Dengue NB2 80% coverage was below target in all six origin years (0.40 to 0.77).
  Leptospirosis was nearer target (0.74 to 0.85).
- Dengue NB2 bias (predicted/actual by forecast year) ranged from 0.26 (2023 outbreak year)
  to 3.10 (2020, COVID low year). Only 6 forecast years.
- Very wide dengue intervals in June follow large forecasts, because NB2 variance grows with
  the mean. This is not a bug.
- Hypotheses, not confirmed causes: recursive forecasting compounding, month effects,
  annual level shifts.

## Post-hoc conformal calibration

Method: score = distance outside the interval divided by its width. For origin December Y,
only scores from earlier rolling origins are used. Calibrated per disease, model, feature set
and horizon, pooling 14 districts. Fewer than 28 prior scores = left uncalibrated.
Code: src/caregrid/multimodel/calibration.py. Results: reports/interval_calibration/.
It can widen or narrow intervals. It cannot fix a biased mean.

Leakage check (read from the saved file): prior scores per origin were 0, 14, 28, 42, 56, 70
for Dec 2018 to Dec 2023, and 84 for the 2025 holdout (origin Dec 2024), so the holdout used
only the 2018-2023 origins. Dec 2018 and Dec 2019 intervals were unchanged.

### Dengue NB2 history-only, rolling origins (n=56 per horizon), 80% coverage

| Horizon | Before | After |
|---|---|---|
| 1 | 0.80 | 0.80 |
| 2 | 0.75 | 0.70 |
| 3 | 0.62 | 0.55 |
| 4 | 0.73 | 0.82 |
| 5 | 0.71 | 0.84 |
| 6 | 0.55 | 0.84 |
| 7 | 0.61 | 0.80 |
| 8 | 0.59 | 0.70 |
| 9 | 0.50 | 0.62 |
| 10 | 0.48 | 0.71 |
| 11 | 0.50 | 0.68 |
| 12 | 0.54 | 0.70 |

Calibration helped most at horizons 5-7. It lowered coverage at horizons 2-3 and left
horizons 8-12 below 0.80.

### Dengue Seasonal Naive, same rows, 80% coverage after calibration

Horizons 1-5: 0.77, 0.79, 0.88, 0.89, 0.84. Horizons 6-12: 0.62, 0.57, 0.66, 0.71,
0.71, 0.64, 0.62. Not calibrated at horizons 6-12.

### Averages over horizons, rolling origins (80% coverage before -> after)

- Dengue NB2 history-only 0.62 -> 0.73; with climate 0.59 -> 0.77.
- Dengue Seasonal Naive 0.71 -> 0.73.
- Dengue Poisson history-only 0.29 -> 0.70, but width rose from 14.6 to 98.4.
- Leptospirosis NB2 history-only 0.78 -> 0.81 (width 25.6 -> 29.2). Not checked by horizon.

### 2025 holdout (descriptive only, 14 districts, effectively 1-2 independent observations)

- Dengue NB2: coverage near 0.95 on average after calibration, but widths grew 2-3 times
  (horizon 12: 104 -> 315). That is wider, not better.
- Dengue Seasonal Naive: coverage fell at horizons 1-4 after calibration. Conformal
  calibration assumes past errors resemble future errors, and a level shift breaks this.

## Direct (non-recursive) NB2

Coverage rose toward 0.80 at dengue horizons 4-8 (0.70-0.89 vs 0.55-0.69 for recursive NB2)
with wider intervals, and did not fix horizons 9-12 (0.45-0.50). See the model comparison
report. Pooled dengue coverage: 0.678 direct vs 0.601 recursive NB2.

## Predictive draws

outputs/predictive_draws/: 200 draws per forecast row for NB2 history-only and direct NB2,
dispersion recovered from saved variance. Median gap to saved 80% bounds 0.104,
95th percentile 0.37, so draws are approximate. They are marginal per district-month and
carry no correlation across districts or horizons. Do not use them to simulate
state-wide totals as if districts were independent without saying so.

## Limits

- 6 forecast years, December origins only, horizon confounded with calendar month.
- Calibration before/after figures were read from calibration_summary.csv; the code that
  makes the summary was not re-audited line by line.
- Coverage is not accuracy. No model ranking comes from this report.
