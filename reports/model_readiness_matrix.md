# Data-driven model readiness matrix

**Investigation date:** 2026-11-10
**Purpose:** Identify what the available disease and weather data can support next. This is a readiness assessment only: no forecasting, outbreak, climate, Bayesian, or spatial-temporal model was implemented or trained.

## Data basis and constraints

- The existing statewide historical monthly files cover 2021–2024, but 2021 and 2022 categories are not the same as the explicit 2023–2024 `Confirmed` labels.
- The new source-native dashboard candidate contains 36 months (2023–2025), 14 districts, two diseases, and separate `Confirmed`/`Suspected` rows. It is complete and internally reconciled, but case definitions are unverified and 2025 values differ from DHS monthly reports. Dashboard `Suspected` is not equated to DHS `Probable`.
- The dashboard source itself returns 2016–2025 data, but older periods have not received the same classification and source audit; 2016 Suspected entries are absent.
- Each candidate disease/category panel has 504 district-month records, but only 36 time points per district (three seasonal cycles). This is short for stable seasonality, calibrated uncertainty, and model selection.
- Weather is currently saved only for 2021–2024 at 14 representative points; a one-location API check suggests a longer archive may be acquirable, but it is not a validated 14-district climate panel. There are no validated outbreak labels or population denominators in the candidate.

## Model/data readiness

| Model or method | Analytical task | Minimum data and evaluation needs | Current readiness | Decision |
|---|---|---|---|---|
| Bayesian Poisson regression / hierarchical Poisson | Probabilistic count forecasting | Stable count definition, enough monthly history, seasonal effects, district structure, proper posterior diagnostics, chronological rolling origins; population offset if estimating rates | Candidate 2023–2025 panel supplies 504 rows per disease/category, but only 36 months and unresolved source semantics | **Conditional first experiment** after source clarification; start with counts, not rates, unless reliable denominators are obtained. |
| Bayesian Negative Binomial / hierarchical Negative Binomial | Probabilistic count forecasting | Same requirements as Poisson plus posterior-predictive overdispersion assessment and prior/convergence checks | Same candidate panel; overdispersion has not been tested or assumed | **Conditional first experiment**, paired with Poisson as a distributional comparison. Do not select solely on in-sample fit. |
| SARIMAX | Statistical time-series forecasting | Longer stable single series, seasonal period and exogenous variables available at origin; chronological rolling-origin evaluation | 36 dashboard months are only three annual cycles; existing 2021–2024 series has classification changes. A longer source-native history needs classification audit first. | **Conditional benchmark later**; seasonal-naive remains a benchmark, not a new model. |
| Gaussian Process | Nonlinear probabilistic forecasting or regression | Enough distinct time points, pre-specified kernel, appropriate count likelihood or justified transformation, calibrated predictive intervals | Only 36 time points per district in the versioned candidate; multi-district covariance and count likelihood are unspecified | **Research/second-stage** after count baselines; not an initial selection candidate. |
| Student-t Process | Robust probabilistic regression/forecasting | Same GP requirements plus justification for heavy-tailed process and enough data to identify tail behavior | No validated outlier/revision model and short per-district time series | **Research proposal**; defer until GP/count baselines and source revisions are understood. |
| Bayesian Structural Time Series | Forecasting / intervention analysis | Longer consistent target history, documented intervention dates, covariates with origin timestamps, and a suitable count observation model | No verified intervention series or long harmonized target; current weather is historical, not origin-known | **Not evaluable yet**; intervention claims would be unsupported. |
| Statistical anomaly detection (e.g. seasonal count limits, CUSUM/EWMA) | Outbreak detection, not ordinary forecasting | Stable baseline, seasonality, reporting-delay/revision model, alert thresholds, adjudicated event windows and non-event periods | Candidate provides monthly counts but only three years; no validated outbreak/event labels or reporting-delay history | **Not ready for performance claims**. A retrospective alert experiment needs separate event review and false-alarm calibration. |
| Hidden Markov Model | Latent-regime/outbreak-state detection | Long repeated sequence, identifiable states, enough transitions, interpretable state definition and independent evaluation labels | 36 monthly points per district are sparse for state identification; no outbreak labels | **Research proposal**; defer. |
| Climate-informed count model | Climate association or forecast, depending on task | Multi-year, geographically aligned weather and disease; lag definitions; forecast-vintage covariates for prediction; climate uncertainty | Saved weather overlap is 2021–2024 at representative points; 2025 14-point panel not saved; humidity availability is verified but not integrated | **Not ready for climate forecasting**. Retrospective association is a separate, limited task after data acquisition. |
| Spatial-temporal count model | District-level forecasting or spatial risk estimation | Audited district-month targets, stable boundaries/crosswalk, neighbor graph, population denominators if rates are required, spatial/temporal holdouts | Candidate supplies 14 districts × 36 months; boundary version/crosswalk, denominators, and longer history are unresolved | **Research proposal**; do not generate population-weighted estimates or interpret counts as rates. |

## First experimental comparison (future phase, not this phase)

Once dashboard definitions and the 2025 differences are clarified, a bounded first **forecasting** experiment could compare:

1. Existing seasonal-naive reference;
2. Bayesian Poisson count model;
3. Bayesian Negative Binomial count model;
4. SARIMAX only if a stable source-native series with enough seasonal cycles is approved.

Use the same source version, disease/category, geography, forecast origin, and horizon for all candidates. With 2023–2025 alone, evaluation is limited: holding out 2025 leaves just 24 training months and one test year. Treat it as a pilot, not reliable evidence of model superiority. An audited earlier dashboard series may provide additional history, but should not be appended until its categories and coverage are reviewed year by year.

No model should be forced to run when its requirements fail. Readiness must be recorded per model and task as `ready`, `conditional`, `not_ready`, `not_evaluable`, or `unavailable`, with specific missing-data reasons.

## Keep analytical tasks and metrics separate

Do not compare outbreak detectors, climate association methods, spatial estimates, and forecasts using a single score.

| Task | Suitable evaluation dimensions |
|---|---|
| Count forecasting | Rolling-origin MAE/MASE for point forecasts; count log score or deviance and CRPS/WIS for distributions; interval coverage and width; calibration by horizon. Avoid random train/test splits and undefined percentage errors at zero. |
| Outbreak detection | Sensitivity over adjudicated event windows, false alarms per district-month, positive predictive value, detection delay, and threshold/alert burden. Requires independent event definitions and review. |
| Climate association | Effect estimates with uncertainty, temporal/spatial holdout stability, lag sensitivity, residual diagnostics, and explicit confounding limitations. Association metrics are not forecast scores and do not establish causality. |
| Spatial-temporal intelligence | Held-out district/month predictive log score and calibration, geographic generalization, spatial residual dependence, and stability under boundary/crosswalk checks. Do not use random row splits that leak neighboring months or districts. |

## Data gates before implementation

1. Obtain authoritative definitions and revision/cut-off information for DHS and dashboard categories; resolve or explicitly bound 2025 discrepancies.
2. Decide whether the 2023–2025 dashboard candidate is approved for a source-native pilot; keep it separate from the 2021–2024 source series until then.
3. Audit earlier dashboard years before extending the target history; preserve absent periods/categories as missing, not zero.
4. For rates or population offsets, obtain reliable date-aligned district population denominators and document boundary changes.
5. For climate experiments, acquire and version all-location weather, validate it against suitable observations, and preserve forecast-origin vintages for forecast tasks.
6. Define distinct evaluation datasets, rolling origins, task-specific metrics, and outbreak event labels before training.

The recommended next implementation phase is data-contract and source-reconciliation work, followed by a limited Poisson-versus-Negative-Binomial comparison only after the gates above are met. No Bayesian or outbreak model is operational today.
