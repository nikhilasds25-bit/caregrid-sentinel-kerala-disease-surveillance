# CareGrid Model Intelligence and Evaluation Engine

## Purpose and current boundary

The engine is a reusable offline layer for registering model capability, validating comparable prediction sets, calculating task-specific metrics, and making explicitly gated experimental selections. It consumes saved predictions and does not train models. The existing forecasting experiment, source datasets, daily IDSP pipeline, and live dashboard are outside its write path.

## Registry

Each registration records stable model ID, name/version, analytical task, supported diseases, required features, training requirements, supported horizon, prediction-output contract, uncertainty availability, readiness, failure status, and limitations. Each implemented feature configuration is a distinct registry entry so climate and history-only results cannot be confused. Registry serialization is in `reports/model_intelligence/model_registry.json`.

| Model / configuration | Analytical task | Readiness | Uncertainty |
|---|---|---|---|
| seasonal_naive::disease_history | count_forecasting | evaluated_exploratory | empirical_prediction_intervals; log score unavailable |
| poisson_regression::disease_history | count_forecasting | evaluated_exploratory | Poisson_distributional_prediction_intervals |
| negative_binomial_regression::disease_history | count_forecasting | evaluated_exploratory | negative_binomial_distributional_prediction_intervals |
| poisson_regression::disease_history_and_climate | count_forecasting | evaluated_exploratory | Poisson_distributional_prediction_intervals |
| negative_binomial_regression::disease_history_and_climate | count_forecasting | evaluated_exploratory | negative_binomial_distributional_prediction_intervals |
| bayesian_poisson::planned | count_forecasting | planned_not_implemented | not_available |
| gaussian_process::planned | count_forecasting | planned_not_implemented | not_available |
| student_t_process::planned | count_forecasting | planned_not_implemented | not_available |
| bayesian_structural_time_series::planned | count_forecasting | planned_not_implemented | not_available |
| hidden_markov_model::planned | retrospective_unusual_activity_detection | planned_not_implemented | not_available |
| ensemble_forecast::planned | count_forecasting | planned_not_implemented | not_available |
| bayesian_negative_binomial::planned | count_forecasting | unavailable_inference_dependency | not_available |
| outbreak_probability::planned | probabilistic_outbreak_threshold_exceedance | blocked_missing_thresholds_and_event_labels | not_available |

Current evaluated forecast configurations: 5; Bayesian Negative Binomial is registered as unavailable because no PyMC/Stan runtime is installed; outbreak probability is blocked pending thresholds and labels. Algorithm extension points marked planned: 6. Planned registrations do not indicate that a model has been implemented or evaluated.

## Common evaluation contract

`evaluation.py` verifies required prediction fields, non-negative counts, interval ordering, unique keys, and equivalent observation keys and actuals across every model/feature candidate. Metrics are emitted overall, by district, by horizon, and by rolling-origin window:

- MAE, RMSE, and mean Poisson deviance for count errors.
- Predictive log score when a distributional score exists; missing scores remain unavailable.
- 80%/95% predictive interval coverage, mean width, and proper interval score.
- Per-fold MAE, coverage, interval score, and stability inputs.

The 2025 final period is available for descriptive holdout reporting only. It is not used in candidate scoring or model selection.

## Selection behavior

`selection.py` applies explicit sample-size, origin-count, interval-coverage, per-origin stability, and forecast-error stability gates, then ranks eligible candidates on accuracy (40%), interval score (40%), and fold MAE variability (20%). A close composite tie returns `insufficient_evidence`; a candidate with unreliable intervals cannot win merely through lower MAE. Policy values and per-candidate rejection reasons are persisted with the selection results. No result should be treated as a live model route without independent review.

## Extension interfaces and analytical task boundaries

`interfaces.py` defines separate contracts and output types:

1. `ForecastingModel` predicts future counts and is evaluated with forecast error, count scoring, and predictive-interval metrics.
2. `UnusualActivityDetector` identifies retrospective deviations from a defined baseline and requires independently reviewed unusual-activity labels for sensitivity, specificity, precision-recall, and false-alert-rate evaluation.
3. `OutbreakProbabilityEstimator` estimates probability of exceeding a versioned epidemiological threshold and requires both a specified threshold and verified outbreak labels; it is evaluated with Brier score, log loss, and reliability/calibration metrics.

These are not interchangeable. The engine does not create alerts or infer official thresholds. Bayesian Negative Binomial is explicitly marked unavailable because the inference runtime is missing; Bayesian Poisson, Gaussian Process, Student-t Process, Bayesian Structural Time Series, Hidden Markov, and ensemble registrations are extension points only. No such algorithms are implemented here.

## Known limitations

- Current validation has six rolling origins and a single 2025 final origin; coverage is not established prospectively.
- Candidate counts derive from Kerala Health Department dashboard classifications whose historical semantic consistency remains unresolved.
- District weather features are from representative locations, not district-wide averages.
- Existing model intervals are evaluated as predictive intervals. No parameter confidence intervals are in this evaluation.
- The engine's model ranking is experimental, non-clinical, and not wired to the dashboard.
