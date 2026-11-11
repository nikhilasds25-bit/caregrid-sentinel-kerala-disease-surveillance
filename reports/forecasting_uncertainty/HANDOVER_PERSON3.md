# Handover to Person 3: forecasting and uncertainty (Person 2)

Branch: feature/forecasting-uncertainty (not pushed, main untouched).
Tests: 116 passed.

## What is in the repo

| Item | Location |
|---|---|
| Interval calibration code, tests, runner | src/caregrid/multimodel/calibration.py, tests/test_calibration.py, src/caregrid/run_interval_calibration.py |
| Calibrated forecasts and summary | reports/interval_calibration/ |
| Direct (non-recursive) NB2 model, tests | src/caregrid/multimodel/direct_model.py, tests/test_direct_model.py |
| Direct model registered in runner | src/caregrid/run_multimodel_experiment.py (4 lines added) |
| Direct model forecasts and metrics | reports/direct_model_experiment/ |
| Model-selection table (2018-2023 origins only) | reports/model_selection/ |
| Approximate predictive draws (NB2 and direct NB2) | outputs/predictive_draws/ |
| Model comparison report | reports/forecasting_uncertainty/MODEL_COMPARISON_REPORT.md |
| Uncertainty report | reports/forecasting_uncertainty/UNCERTAINTY_REPORT.md |

Original results in reports/multimodel_experiment/ were never overwritten.
The direct model was run in a disposable Temp copy, with 0 failures. Old model
forecasts were checked against the original run: history-only models identical,
climate models differ by at most 0.39 cases.

## Findings (hypotheses, not proven causes)

1. Poisson intervals are far too narrow in both diseases. Do not use them for uncertainty.
2. Dengue NB2 coverage is below the 80% target at most horizons.
3. Conformal calibration (earlier origins only) widened intervals and raised coverage
   at dengue horizons 5-7, but horizons 9-12 stayed below 0.80. It can also reduce
   coverage, and it cannot fix a biased mean. Nothing here is "calibrated".
4. Leakage check passed: the 2025 rows were calibrated from the 2018-2023 origins only
   (84 prior scores). Dec 2018 and Dec 2019 were left uncalibrated (fewer than 28 scores).
5. The direct model gave coverage closer to 0.80 than recursive NB2 at dengue horizons 4-8,
   partly because its intervals are wider. It does not fix horizons 9-12. It also changes
   the lag structure, so recursion is not proven to be the cause.
6. Model-selection table (MAE, 2018-2023 origins, pooled): no best model is declared.
   Read MAE together with coverage. These pooled MAEs use a different pooling from the
   earlier headline numbers (40.597 and 9.643), so do not compare them directly.

## Limits

- Only 6 forecast years, all from December origins, so horizon and calendar month are confounded.
- The 2025 holdout (14 districts, one year) is closer to 1-2 independent observations. Descriptive only.
- Predictive draws are approximate (200 draws; median gap to saved 80% bounds 0.104,
  95th percentile 0.37). They are marginal per district-month, with no correlation across
  districts or horizons.

## Not done

- SARIMAX and Bayesian models (would need new installs).
- Direct model with climate (rejected in code for now).
- Direct model checks for leptospirosis by horizon (results exist, not examined).
- Row-by-row check that the draws reproduce the saved intervals.
- The README line in make_predictive_draws.py still says "Not committed to git (size)".
  The saved README was corrected; re-running the script would recreate the old line.

## Open questions

- Should the branch be pushed now, or after review?
