# District-month multi-model readiness: verified 2016–2025 data

**Assessment date:** 2026-11-10
**Scope:** Feasibility based on the new dashboard-native disease and representative-location weather candidates. No forecasting, outbreak, Bayesian, or climate model was implemented or trained.

## Verified data available

- Disease candidate: 2016-01–2025-12, 14 districts, 2 diseases, 2 dashboard categories. It contains 6,720 panel rows; 6,384 are available counts. The 336 unavailable rows are 2016 Suspected values and remain null.
- At each district, each disease has 120 monthly Confirmed counts (10 years); each disease has 108 monthly Suspected counts (9 years, 2017–2025). Thus there are 1,680 available district-month observations per disease/category for Confirmed and 1,512 for Suspected.
- Weather candidate: all 1,680 district-month locations across the same 120 months, with six complete features. A location is a representative point, not district-wide measured weather.
- The disease candidate has four source-internal district/state case reconciliation exceptions and annual/monthly DHS differences. The dashboard provides no documented case definitions or revision history. The data are structurally long enough for an exploratory comparison, but the target meaning is not approved as cross-year harmonized.

See the [historical disease audit](historical_2016_2025_data_audit.md), [source discrepancy analysis](source_discrepancy_analysis.md), and [weather readiness report](extended_weather_data_readiness.md).

## Model readiness matrix

| Method | Analytical task | Readiness from current data | Decision / gates |
|---|---|---|---|
| Seasonal Naïve | Forecasting benchmark | **First experiment candidate, conditional.** 108–120 months per district/category permit seasonal lag-12 baselines and rolling-origin backtests. | Use one dashboard source/category at a time; exclude unavailable 2016 Suspected rather than imputing. Flag the four state-reconciliation exceptions and do not claim epidemiological harmonization. Lock source snapshot and use multiple temporal origins. |
| Poisson regression | Count forecasting | **Structurally feasible, conditional.** Available district-month case counts provide a panel for seasonality and district effects. | First parametric count comparison after source definitions and discrepancy policy are reviewed. Model counts, not incidence rates, unless reliable date-aligned district population offsets are obtained. Check overdispersion and temporal residuals. |
| Negative Binomial regression | Count forecasting | **Structurally feasible, conditional.** It can address overdispersion if supported by diagnostics. | Compare with Poisson under identical splits and proper count/distributional scoring; do not assume negative-binomial dispersion in advance. |
| Hierarchical Bayesian Negative Binomial | Partially pooled district count forecasting | **Exploratory only, later.** Fourteen districts and a 9–10-year panel provide groups and repeated time observations, but data semantics and revisions remain unresolved. | Needs explicit priors, prior predictive checks, MCMC convergence/effective sample diagnostics, posterior predictive checks, and sensitivity analyses. Does not remove source-definition bias. |
| Bayesian Structural Time Series | Forecasting/intervention analysis | **Not first-ready.** One hundred-plus months are available, but no audited intervention timeline, stable target definition, or forecast-origin covariate archive is established. | Define intervention dates and observation/reporting process; avoid causal/intervention claims without design and controls. Weather archive alone is not origin-known weather. |
| Gaussian Process | Nonlinear probabilistic regression/forecasting | **Research/second-stage.** Long monthly input is now available, but the target is a count and the spatial/time covariance design is unspecified. | Requires a count likelihood or defended transform, kernel pre-specification, calibrated out-of-time uncertainty, and comparison against simpler count baselines. |
| Student-t Process | Robust probabilistic regression/forecasting | **Research proposal.** Heavy-tail behavior has not been demonstrated, and native count support is not automatic. | Defer until the count series and outliers/revisions are audited and a suitable likelihood is defined. |
| Hidden Markov Model | Latent-regime/outbreak-state detection | **Not ready for outbreak conclusions.** 108–120 months per district is limited for stable state/transition identification; no adjudicated outbreak labels exist. | Define clinically meaningful states and independently reviewed event windows; test state identifiability and label stability before interpreting regimes as outbreaks. |
| EWMA/CUSUM | Sequential anomaly/outbreak detection | **Retrospective charting only, not evaluated.** Counts and history exist, but surveillance revisions, reporting delays, baseline stability, and event labels are not established. | Establish alert thresholds on training history, then assess independent event sensitivity, false alarms/district-month, positive predictive value, and detection delay. No operational alert claim. |
| Climate-informed model | Climate association or forecast | **Retrospective exploration feasible; forecasting conditional/unready.** Complete 2016–2025 historical weather is aligned by district/month but is representative-point archive data with no explicit model identifier. | Retrospective associations are not causal. For forecast use, acquire archived weather forecasts available at each origin and preserve issue times/lead times; using realized target-period weather leaks future information. Validate spatial exposure. |

## Which can be tested first?

After a data-governance gate, a bounded first **forecasting** experiment can compare:

1. Seasonal Naïve (benchmark);
2. Poisson regression;
3. Negative Binomial regression.

Keep disease, district, source category, and snapshot fixed; never combine dashboard Suspected with DHS Probable or assume identical annual reporting practice. The first experiment should be a dashboard-only, retrospective result with source caveats, not a production or outbreak claim. A hierarchical Bayesian Negative Binomial model is a reasonable follow-up if the simpler count experiment reveals pooling needs and the data-definition gate passes.

Gaussian/Student-t processes, BSTS, and HMMs are not justified as first competitors. EWMA/CUSUM can be used to design an event-review protocol, but cannot yet be scored for outbreak performance.

## Evaluation must follow the task

| Task | Evaluation |
|---|---|
| Forecasting counts | Rolling-origin MAE/MASE for point forecasts; log score/deviance and CRPS/WIS for distributions; interval coverage/width and calibration by horizon. No random row split. |
| Outbreak detection | Sensitivity over independently adjudicated event windows, false alarms per district-month, positive predictive value, detection delay, and alert burden. |
| Climate association | Effect estimates/uncertainty, lag sensitivity, temporal holdout stability, residual checks, and explicit confounding limitations. Association is not a forecast score or causal result. |
| Spatial-temporal analysis | Geographic/time holdouts, calibration and predictive score, spatial residual dependence, and boundary/crosswalk sensitivity. A representative point is not a district exposure surface. |

Do not select models across different analytical tasks with a single metric.

## Required next research phase

1. Obtain written definitions and revision/cut-off documentation for the dashboard's Confirmed/Suspected categories and DHS Confirmed/Probable categories.
2. Resolve or formally bound the four dashboard district/state mismatches and the 2021/2022/2025 DHS discrepancies; verify the missing 2025 DHS Alappuzha annual source.
3. Review the dashboard years before 2017 and any category or reporting-method transitions; do not backfill absent 2016 Suspected values.
4. Decide whether this exact dashboard snapshot is approved for a dashboard-only retrospective benchmark; keep later snapshots versioned.
5. If estimating rates, obtain authoritative population denominators and district boundary vintages. For climate forecasting, acquire forecast-vintage weather rather than using realized historical weather.
6. Only then implement the offline Seasonal Naïve / Poisson / Negative Binomial comparison with rolling origins. Outbreak detection requires separate event adjudication and false-alarm evaluation before any alerting implementation.

No forecasting or outbreak models have been trained or deployed in this phase.
