# Exploratory multi-model forecasting experiment

## Scope and validation

This is an offline retrospective experiment using Dashboard Confirmed district-month observations only. It is not a production forecasting or outbreak-warning system. Historical semantic consistency is not officially established; dashboard Confirmed is not equated with DHS Confirmed or Probable.

The models are Seasonal Naive, regularized Poisson regression, and regularized NB2 regression, each disease-history-only; Poisson and NB2 are also evaluated with a separate climate feature set. Forecasts are recursively generated at horizons 1–12. Development rolling origins are December 2018 through December 2023, each evaluated over the following 12 months. The untouched final evaluation is the single December 2024 origin forecasting January–December 2025. No random split is used. Hyperparameters were fixed in advance for this experiment; the rolling origins are comparative validation, not hyperparameter tuning.

Metrics include MAE, RMSE, mean Poisson deviance, predictive log score where a probability distribution is available, 80%/95% interval coverage and mean interval width. Metrics are also exported by district and horizon. Seasonal Naive uses pooled training-only seasonal residual intervals; its predictive log score is unavailable. The final period supplies only 14 district observations at each horizon per disease/model, so calibration estimates are imprecise.

## Results (lower MAE is better)

### Dengue
- Final 2025, horizon 1: lowest MAE was `negative_binomial_regression` (disease_history_and_climate), MAE 11.74, RMSE 15.84; 80%/95% interval coverage 85.7%/100.0% (n=14).
- Final 2025, horizon 3: lowest MAE was `negative_binomial_regression` (disease_history), MAE 9.15, RMSE 11.57; 80%/95% interval coverage 92.9%/100.0% (n=14).
- Final 2025, horizon 6: lowest MAE was `seasonal_naive` (disease_history), MAE 125.21, RMSE 166.04; 80%/95% interval coverage 35.7%/78.6% (n=14).
- Final 2025, horizon 12: lowest MAE was `negative_binomial_regression` (disease_history), MAE 29.27, RMSE 35.42; 80%/95% interval coverage 78.6%/92.9% (n=14).
- Rolling-origin horizon-12 lowest MAE: `negative_binomial_regression` (disease_history), MAE 40.60 across 84 district-month predictions.
### Leptospirosis
- Final 2025, horizon 1: lowest MAE was `negative_binomial_regression` (disease_history_and_climate), MAE 3.86, RMSE 6.14; 80%/95% interval coverage 100.0%/100.0% (n=14).
- Final 2025, horizon 3: lowest MAE was `negative_binomial_regression` (disease_history), MAE 3.57, RMSE 5.29; 80%/95% interval coverage 85.7%/100.0% (n=14).
- Final 2025, horizon 6: lowest MAE was `seasonal_naive` (disease_history), MAE 8.93, RMSE 10.67; 80%/95% interval coverage 92.9%/100.0% (n=14).
- Final 2025, horizon 12: lowest MAE was `seasonal_naive` (disease_history), MAE 5.79, RMSE 7.17; 80%/95% interval coverage 92.9%/100.0% (n=14).
- Rolling-origin horizon-12 lowest MAE: `seasonal_naive` (disease_history), MAE 9.64 across 84 district-month predictions.

### Climate increment

- Dengue, negative_binomial_regression: climate-minus-history MAE by horizon 1m -0.69, 3m -1.14, 6m +33.23, 12m +3.25 cases (negative favors climate).
- Dengue, poisson_regression: climate-minus-history MAE by horizon 1m -0.55, 3m +3.89, 6m -11.60, 12m +0.50 cases (negative favors climate).
- Leptospirosis, negative_binomial_regression: climate-minus-history MAE by horizon 1m -0.02, 3m +1.29, 6m -0.52, 12m -0.12 cases (negative favors climate).
- Leptospirosis, poisson_regression: climate-minus-history MAE by horizon 1m +0.15, 3m -0.01, 6m -0.94, 12m +2.71 cases (negative favors climate).

Climate benefit is determined empirically from matched rolling-origin MAE in `metrics.csv`; the feature family is not presumed useful. These results do not establish causal climate effects.

## Predictive uncertainty

Poisson and NB2 intervals are distributional intervals from their fitted count likelihoods; Seasonal Naive intervals are empirical residual intervals. Their realized coverage and width are reported in `metrics.csv`. Coverage is a retrospective summary, not proof of calibrated uncertainty. Reported disease-month results do not include a jointly calibrated statewide interval.

The final-period figure showing sums of district interval endpoints is descriptive only: summing marginal endpoints does not produce a valid joint statewide prediction interval.

## Bayesian model feasibility

Hierarchical Bayesian Negative Binomial was not implemented. The environment has no PyMC/Stan inference runtime, so posterior convergence, effective sample size, divergence, and predictive checks cannot be established. The implemented pooled NB2 is a fixed-effect frequentist model and is not a Bayesian substitute. See `model_readiness.json`.

## Outbreak intelligence

The experiment forecasts future counts only. Unusual-activity detection and outbreak-probability estimation remain separate tasks. No independently verified outbreak labels or official thresholds are available here; therefore no outbreak sensitivity, specificity, probability calibration, or lead-time claim is made.

No model-window failures were recorded.

## Reproducibility

Machine-readable predictions, residuals, metrics, model configurations, model readiness, validation windows, plots, and input hashes are under `reports/multimodel_experiment/`. `data_readiness.json` records validated panel properties. Source discrepancies and district/state reconciliation flags remain intact and are never silently substituted or corrected.
