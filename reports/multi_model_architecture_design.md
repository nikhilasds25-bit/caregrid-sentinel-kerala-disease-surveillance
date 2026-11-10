# CareGrid Sentinel — Multi-Model Architecture Design

**Status:** Design proposal only; no model, registry, API, or interface described here has been implemented.
**Purpose:** Define reusable task-specific contracts that can support heterogeneous models without implying every model is runnable or that unavailable data should be fabricated.

## Design principles

1. **Separate analytical tasks.** Forecasting, outbreak detection, climate analysis, and spatial intelligence have different targets, outputs, validation schemes, and metrics. Do not force them into one generic `predict()`/leaderboard contract.
2. **Readiness before execution.** A model must declare required data, granularity, classification, covariates, and evaluation history. It can return `unavailable` or `not_evaluable` with machine-readable reasons; there is no silent fallback to a different dataset/model.
3. **Preserve source meaning.** Inputs carry the exact source classification, source labels, reporting grain, provenance, and approved crosswalk version. No model adapter may silently combine Confirmed, Probable, suspected, daily, monthly, annual, or cumulative counts.
4. **No fabricated observations.** Missing dates/districts remain missing unless a task-specific, justified transformation is explicitly registered and evaluated. Annual district counts do not become monthly district observations.
5. **Uncertainty is a first-class output.** A point estimate alone is not sufficient for probabilistic models. Store predictive samples or distributions, quantiles, calibration evidence, and their provenance.
6. **Comparable evaluation only.** Model comparisons require the same target definition, data snapshot, geography, time origin/horizon, and evaluation folds. A metric from one task is not comparable to another task.
7. **Reproducible runs.** Each result is bound to immutable source hashes, configuration, code revision, dependency versions, feature definition, and split plan.

## Proposed package boundaries

Keep the existing API/data-access modules stable initially. Add these boundaries only when implementation begins:

```text
src/caregrid/analytics/
    contracts.py              # shared provenance, readiness, result metadata
    registry.py               # model/task descriptors and capability discovery
    readiness.py              # data capability checks, no fitting
    evaluation/
        splits.py              # chronological/rolling-origin plans
        forecasting.py
        outbreak.py
        climate.py
        spatial.py
    forecasting/
        interface.py
        models/                # statistical, Bayesian, GP, climate-conditioned
    outbreak/
        interface.py
        models/                # anomaly, EWMA/CUSUM, Bayesian, HMM
    climate/
        interface.py
        analysis/              # descriptive/lagged association; separate from forecasting
    spatial/
        interface.py
        models/                # hierarchical/spatial-temporal when geography is ready
```

This is a destination structure, not a request to create empty packages now. Keep model implementations out of `api.py`; API routes should orchestrate validated requests and serialize stored run results.

## Shared run and data contracts

Every task-specific input should reference a common immutable data envelope:

| Field | Meaning |
|---|---|
| `dataset_id`, `dataset_version`, `source_hashes` | Exact curated snapshot and all source documents used. |
| `target` | Disease, measure, unit, and exact target category; e.g., reported monthly confirmed cases. |
| `classification` and `crosswalk_version` | Source label and explicit approved mapping, or `null` when not justified. |
| `temporal_grain`, `period_start`, `period_end` | Day/month/year and observed range; never inferred from row order. |
| `geography_level`, `geography_ids`, `boundary_version` | State/district/site scope and stable identifiers. |
| `observed_keys`, `missing_keys`, `duplicate_keys` | Explicit coverage diagnostics; missing is not zero. |
| `covariates` | Variable definition, units, observed/forecast availability time, source, and aggregation method. |
| `exposure` | Optional population/person-time offset with its own source/version and alignment. |
| `as_of_time`, `forecast_origin` | Information cut-off. Features must be available as of the origin. |
| `provenance` | Source URL, retrieval time, parser/version, quality flags, revision status. |

Use typed task-specific schemas over this envelope rather than one permissive frame with optional fields for every task. A model may require fields the current dataset cannot provide; readiness must report that fact without mutating the data.

### Common readiness result

Suggested fields:

- `status`: `ready`, `partially_ready`, `unavailable`, or `not_evaluable`.
- `reasons[]`: stable codes such as `INCOMPATIBLE_CLASSIFICATION`, `INSUFFICIENT_HISTORY`, `MISSING_EXPOSURE`, `NO_DISTRICT_MONTH_PANEL`, `NO_FUTURE_WEATHER_AT_ORIGIN`, `NO_OUTBREAK_LABELS`, `NO_SPATIAL_GRAPH`, or `TOO_FEW_VALIDATION_ORIGINS`.
- `requirements[]`: observed versus required capabilities, with units/grain.
- `eligible_origins` and `eligible_horizons`, if applicable.
- `warnings[]`: source or statistical caveats that do not by themselves block execution.

The readiness policy must be model- and task-specific. Minimum sample sizes, lag spans, and calibration thresholds belong in reviewed configuration, not hidden global constants. A `not_evaluable` model is not a failed model and must not be assigned a fabricated score.

## Task-specific interfaces

### 1. Forecasting

**Input:** A univariate or multivariate target with an exact time key, source classification, forecast origin, horizon, optional exposure, and only covariates known or forecastable at that origin.

**Model protocol:**

- `describe_capabilities()`: target types, granularity, exogenous variables, count support, uncertainty format, and resource requirements.
- `assess_readiness(input, evaluation_plan)`: report eligibility and blockers without fitting.
- `fit(training_data, config)`: train strictly on data at/before each origin.
- `predict(forecast_request)`: return horizon-aligned predictive distribution, point summary, and provenance.

**Prediction result:**

- Target keys, origin, horizon, units, and data/crosswalk version.
- Point summaries and quantiles (for example 50/80/95% intervals).
- Posterior/predictive draws or a serializable distribution description when available.
- Non-negativity/count constraints where appropriate.
- Fit warnings and model/configuration identifier.

**Candidate families:** Naïve/seasonal naïve; SARIMAX; Bayesian Structural Time Series; Bayesian Poisson/Negative Binomial; Gaussian Process; Student-t Process; climate-conditioned variants. These are candidates, not current implementations.

**Evaluation:** Expanding/rolling-origin chronological backtests, with origin-specific training-only preprocessing. Report MAE/RMSE/MASE for point forecasts when defined; count deviance/log score where distributional assumptions are valid; interval coverage/width, weighted interval score, CRPS or log score, and calibration diagnostics for uncertainty. Record sample counts per fold. One holdout year must not be presented as reliable generalization.

### 2. Outbreak detection

**Input:** Dated observed counts, explicit case definition and reporting delay/revision policy, denominator/exposure if needed, baseline/seasonality assumptions, and a declared outbreak event/threshold definition. Daily IDSP and monthly DHS targets are separate input series.

**Detector protocol:**

- `describe_capabilities()`.
- `assess_readiness(input, evaluation_plan)`.
- `fit_baseline(training_data, config)`.
- `score_observation(observation, state)`: return exceedance/anomaly score or posterior outbreak probability, not a future case forecast.
- `update_state(...)`: explicit state/version for sequential methods; replay must reproduce results.

**Output:** Observation time, score, threshold or posterior `P(outbreak)`, uncertainty/latent-state probabilities, baseline window, alert decision rule/version, and source revision context. A thresholded alert must remain distinguishable from the underlying probability.

**Candidate families:** Statistical anomaly detection, EWMA, CUSUM, Bayesian probabilistic detection, Hidden Markov Models, latent outbreak-state models.

**Evaluation:** Event-level sensitivity/recall, precision, false alerts per unit time, lead time, missed-event rate, and probability calibration (Brier/log score). Freeze outbreak onset/end definitions before evaluation; do not evaluate against labels created from the detector output itself. Report detection delay and performance under realistic reporting gaps.

### 3. Climate analysis

This is an explanatory/descriptive task, not automatically a forecasting model.

**Input:** Disease observations and weather observations aligned at the same defensible geography and time grain, with source classifications and explicit lag windows. Each weather feature records whether it is observed retrospectively or available as a forecast at each prediction origin.

**Analysis protocol/output:** Estimate descriptive associations or lag-response distributions with uncertainty, model assumptions, missingness, sensitivity checks, and exact feature provenance. Do not claim causality from correlation. Inference and climate-conditioned prediction are separate outputs/interfaces.

**Evaluation:** For association, use posterior/interval diagnostics, sensitivity to lag and source definitions, and held-out replication where possible. To claim predictive improvement, compare climate and no-climate forecasting models on identical chronological folds using proper out-of-sample scores and calibration. Realized future weather is prohibited as a forecast-origin feature.

### 4. Spatial and spatial-temporal intelligence

**Input:** Stable district identifiers and boundary version, district-time disease observations, population/exposure denominators where rates are required, district-level climate/covariates, and an explicit adjacency/graph definition. Statewide counts cannot be replicated across districts to satisfy this contract.

**Model protocol/output:** Hierarchical district effects and spatial/temporal dependence are modeled explicitly. Return district-specific posterior predictive distributions or risk probabilities, uncertainty, graph/boundary provenance, and a flag for districts without observations. Mapping is downstream presentation, not an inference method.

**Candidate families:** Bayesian hierarchical models, spatial-temporal models, district-level outbreak-risk estimates.

**Evaluation:** Time-blocked and spatially aware holdouts (including leave-district-out when appropriate), log score/CRPS and interval calibration, spatial residual checks, and comparison to non-spatial baselines on identical targets. Report district coverage and population denominators; do not rank small-population raw counts as per-capita risk.

## Registry, comparison, and selection

The future registry should store descriptors, not instantiate every model at application startup. Each descriptor identifies:

- `model_id`, version, task, supported targets/grains, dependencies, and resource profile.
- Required data/covariates and uncertainty capabilities.
- Readiness evaluator and task-specific evaluator.
- Reproducibility configuration schema and explicit unavailable reasons.

Comparison workflow:

1. Freeze a target/crosswalk, source snapshot, and evaluation plan.
2. Ask each registered model for readiness; retain blocked models in the response with reasons.
3. Run only ready models, independently per valid fold and within a bounded compute policy.
4. Verify outputs share identical target keys, origin/horizon, units, and evaluation folds before ranking.
5. Rank only on predeclared task-specific primary metrics; show uncertainty/calibration and score sample sizes alongside rank.
6. Persist all results, including unsuccessful execution errors; never turn errors into a successful-looking empty result.

Model selection is a validation result, not a per-request runtime guess. It should include eligibility, metric thresholds, tie-breaking policy, and a fallback status. If no model is ready or validated, return `not_evaluable`; do not manufacture a prediction.

## Ensemble policy

Ensemble forecasting is allowed only when component predictions share the same target, source classification, units, origin, horizon, and folds. Learn weights only from training-side or nested rolling-origin out-of-fold predictions; do not tune weights on the final holdout. Preserve a mixture or otherwise calibrated predictive distribution, not just an average point prediction. Compare the ensemble against every component on the same held-out folds and uncertainty metrics. If it does not improve the preregistered criterion or calibration, do not select it.

Outbreak detector voting and combining climate/spatial analyses are separate designs; they must not be called a forecasting ensemble.

## Data readiness gates for this repository

At present, the shared readiness layer would need to report:

- 2021/2022 monthly records: `not_evaluable` for a confirmed-only target without an approved crosswalk.
- 2023–2024 confirmed-only statewide baseline: eligible only for a limited single 2024 holdout; not enough origins for robust rolling validation.
- 2025 confirmed monthly snapshot: source data available, but cross-document comparability review and a versioned candidate dataset are prerequisites.
- District-month models: `unavailable` because no validated district-month disease series is present.
- Climate-lag models: `not_evaluable` for defensible forecasting with current short statewide data, proxy weather, and no known future weather input.
- Daily outbreak models: require explicit handling of preliminary/revised reports, missing dates, unknown dashes, and outbreak labels/thresholds; cumulative values cannot serve as daily outcomes.
- Spatial models: `unavailable` until compatible district-time observations, stable boundary/adjacency data, and appropriate exposure denominators are available.

## Implementation sequence after data readiness

1. Define and version disease/source classification contracts; review whether the 2023–2025 explicit Confirmed series is comparable.
2. Curate a separate immutable candidate dataset with validation and provenance; do not rewrite existing inputs or artifacts.
3. Introduce task/result/readiness contracts and a deterministic evaluation-plan serializer.
4. Implement evaluation infrastructure and baselines before adding model families.
5. Add one model family at a time only when its input and repeated validation are ready.
6. Add distribution calibration, model selection, and then ensembles only after honest out-of-sample evidence.
7. Add outbreak and spatial task packages independently with their own labels, metrics, and readiness gates.

No Bayesian, statistical, GP, Student-t, outbreak, climate-predictive, or spatial-temporal model is implemented by this design document.
