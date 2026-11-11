# Model comparison report (Person 2)

Scope: district-month forecasts, 12-month horizon, December origins 2018-2023
(6 rolling origins, 14 districts, 12 horizons = 1,008 rows per model per disease).
The 2025 holdout is NOT used anywhere in this report. No model is declared best.
Source: reports/model_selection/model_selection_rolling_origin_2018_2023.csv

## Pooled results (rolling origins 2018-2023)

### Dengue (sorted by MAE)

| Model | Features | MAE | Coverage 80% | Coverage 95% | Width 80% |
|---|---|---|---|---|---|
| seasonal_naive | history | 39.0 | 0.786 | 0.918 | 75.2 |
| direct_negative_binomial | history | 39.8 | 0.678 | 0.827 | 75.7 |
| negative_binomial_regression | history | 40.9 | 0.601 | 0.776 | 67.0 |
| negative_binomial_regression | history + climate | 47.6 | 0.554 | 0.730 | 82.7 |
| poisson_regression | history + climate | 51.7 | 0.284 | 0.364 | 14.1 |
| poisson_regression | history | 52.4 | 0.279 | 0.378 | 14.5 |

### Leptospirosis (sorted by MAE)

| Model | Features | MAE | Coverage 80% | Coverage 95% | Width 80% |
|---|---|---|---|---|---|
| poisson_regression | history | 8.43 | 0.476 | 0.614 | 7.2 |
| direct_negative_binomial | history | 8.54 | 0.836 | 0.940 | 25.2 |
| negative_binomial_regression | history + climate | 8.61 | 0.624 | 0.759 | 14.1 |
| seasonal_naive | history | 8.89 | 0.758 | 0.934 | 18.5 |
| poisson_regression | history + climate | 9.34 | 0.375 | 0.467 | 4.4 |
| negative_binomial_regression | history | 9.78 | 0.781 | 0.928 | 25.9 |

## How to read this

- Dengue: Seasonal Naive has the lowest MAE and the best coverage. The direct model
  is second on MAE. Climate variants did not improve on history-only models here.
- Leptospirosis: the top four MAEs are within 0.5 of each other, which is too close
  to rank with 6 forecast years. Poisson ranks first on MAE but its 80% intervals
  cover only 0.476 of outcomes, so its uncertainty cannot be trusted.
- Poisson is under-covered in both diseases. Use it for point forecasts at most.
- MAE and coverage must be read together. Wide intervals can buy coverage.

## Direct (non-recursive) NB2 vs recursive NB2, dengue, history-only

At horizon 1 the two models are identical (MAE 13.36, coverage 0.83), as expected.

| Horizon | Coverage direct | Coverage recursive | Width direct | Width recursive |
|---|---|---|---|---|
| 4 | 0.89 | 0.69 | 36.9 | 23.6 |
| 5 | 0.76 | 0.63 | 89.4 | 78.0 |
| 6 | 0.71 | 0.55 | 213.9 | 176.1 |
| 7 | 0.74 | 0.58 | 197.4 | 184.9 |
| 8 | 0.70 | 0.56 | 109.9 | 95.9 |
| 9 | 0.50 | 0.48 | 59.7 | 58.4 |
| 10 | 0.49 | 0.42 | 45.1 | 44.1 |
| 11 | 0.48 | 0.39 | 36.1 | 33.4 |
| 12 | 0.45 | 0.52 | 30.3 | 30.1 |

MAE differences between the two are small (for example 42.14 vs 40.60 at horizon 12)
and not reliable with 6 forecast years. Leptospirosis was not examined by horizon.

## Caveats

- The direct model changes both the recursion and the lag structure (at horizon 12 it
  is effectively a year-ago lag), so this comparison does not prove that recursion
  causes the under-coverage. Support is partial: horizons 4-8 improved, 9-12 did not.
- Only 6 forecast years, all December origins. Horizon and calendar month are confounded
  (horizon 6 is always June, horizon 12 is always December).
- These pooled MAEs use a different pooling from the earlier headline numbers
  (dengue NB2 40.597, leptospirosis Seasonal Naive 9.643). Do not compare them directly.
- Not done: SARIMAX, Bayesian models, direct model with climate.
