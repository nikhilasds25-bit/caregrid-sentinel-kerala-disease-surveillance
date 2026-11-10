# CareGrid Sentinel — Team Handoff

**Status:** research and engineering prototype; not a clinical or operational alerting system.

## 1. Product vision and objectives

CareGrid Sentinel is an adaptive disease-surveillance and outbreak-intelligence platform for Kerala. Its long-term goal is to compare statistical, machine-learning, and Bayesian approaches, measure their performance and predictive uncertainty, and select or combine models only when evidence supports doing so.

The current application is primarily a source-aware historical surveillance dashboard with a read-only FastAPI API, separate daily IDSP report snapshots, and offline retrospective forecasting experiments. The 2016–2025 dashboard-native disease and representative-location weather candidates support exploratory research. Historical disease-definition consistency has **not** been officially established.

The system intentionally distinguishes:

1. Forecasting future disease counts.
2. Detecting retrospective unusual activity relative to a baseline.
3. Estimating the probability that a defined epidemiological threshold is exceeded.

The latter two are not operational or validated. Do not treat experimental selections as live recommendations, merge unlike source categories, fill missing values with zero, or describe representative weather points as district-wide measurements.

## 2. Current architecture

```text
data/raw, data/processed, data/live_surveillance, data/candidates
                            |
                            v
                   src/caregrid/
          import/build/audit/read-only data services
              |                         |
              v                         v
    FastAPI read-only API       offline experiment runners
              |                         |
              v                         v
 React + TypeScript + Vite     reports/* reproducible outputs
```

- **Backend:** Python package under `src/caregrid/`. `api.py` exposes validated read-only historical, annual, weather, live-report snapshot, and prior forecasting-experiment endpoints. The API does not expose operational forecasts, outbreak alerts, clinical advice, or real hospital capacity.
- **Dashboard:** React, TypeScript, and Vite application under `dashboard/`. It calls the API through Vite's `/api` development proxy.
- **Data pipelines:** source-specific scripts preserve raw documents, retrieval metadata, candidate datasets, classifications, and audit outputs. `daily_surveillance.py` and `import_idsp_daily.py` remain separate from the monthly and annual historical data flows.
- **Previous forecasting experiment:** `forecasting.py` and `run_forecasting_experiment.py` implement the earlier, limited Confirmed-only 2023–2024 hindcast.
- **First multi-model experiment:** `multimodel/` contains candidate validation, model contracts, feature construction, and model implementations. `run_multimodel_experiment.py` builds rolling-origin experiment outputs.
- **Model Intelligence Engine:** `model_intelligence/` contains the registry, evaluation/alignment checks, selection policy, and separate task contracts. `run_model_intelligence.py` reads saved predictions and writes selection/evaluation artifacts. It does not retrain models.

## 3. Dataset sources and coverage

### Historical statewide and annual records

- The original 2021–2024 monthly disease history is a statewide series whose source classifications vary by year. It retains Confirmed/Probable labels as reported; labels alone do not prove consistent case definitions across years.
- Annual district disease records cover 2020–2024, 14 districts, Dengue and Leptospirosis, and source-native Confirmed/Probable categories. They are **annual**, not district-month data.
- DHS annual sources and comparisons are retained in `data/raw/`, `data/processed/`, `data/candidates/`, and `reports/`. Previously identified annual coverage gaps and source disagreements remain unresolved rather than imputed.

### Dashboard-native disease candidate

- Candidate: `data/candidates/kerala_district_monthly_disease_dashboard_2016_2025.csv`.
- Kerala Health Department disease dashboard JSON snapshot: `data/raw/kerala_health_disease_data_2026-11-10.json`.
- Candidate sidecar: `data/candidates/kerala_district_monthly_disease_dashboard_2016_2025.metadata.json`; it records source and candidate hashes, URL, snapshot/retrieval details, and related audit file hashes.
- Recorded SHA-256: source snapshot `ca401184db2f983030d3fd26eb94872aa3cc61f6be340067aef1e362bdd2101c`; candidate CSV `283c202f132261b77f86710c32649f6102ce258e0cc54eaadd83d4fd808c0f23`.
- Coverage is 2016–2025 monthly, 14 districts, Dengue and Leptospirosis, with source-native Confirmed and Suspected categories. The candidate contains 6,720 rows; 336 unavailable source-category rows are retained as unavailable, not zero.
- 2016 Suspected categories are unavailable. For the experiment, only Confirmed rows were used: 3,360 records (1,680 per disease), 120 periods per district/disease, no missing Confirmed case counts and 224 explicit zero counts.
- Dashboard Confirmed/Suspected is **not harmonized** to DHS Confirmed/Probable. Four district-to-state monthly case reconciliation mismatch cells are preserved in `data/candidates/kerala_district_monthly_disease_dashboard_2016_2025_reconciliation.csv`; two involve Confirmed records. District values were not replaced.
- DHS/dashboard discrepancies remain documented in `reports/source_discrepancy_analysis.md`.

### Weather candidate

- Candidate: `data/candidates/kerala_district_representative_weather_monthly_2016_2025.csv`.
- Sidecar: `data/candidates/kerala_district_representative_weather_monthly_2016_2025.metadata.json`.
- Raw Open-Meteo archive response: `data/raw/open_meteo_weather_2016_2025/district_locations_batch_2016_2025.json`.
- Candidate CSV SHA-256 is `85364a93b25a741b2eaf5080f958fee764ac557821e03fe1e663e7c73518e175`; the sidecar's response-body SHA-256 is `45f64f3278afb4b7f8eb4842deef58f8bb921c174352952fce519ef040107ecc`. The latter hashes the embedded HTTP response body, not the JSON envelope file bytes.
- Monthly weather covers 2016–2025 for 14 representative district locations (1,680 rows), including precipitation, mean/min/max temperature, relative humidity, and dew point. Precipitation is summed; other variables are averaged from available daily values. The response did not expose a specific model/reanalysis identifier.
- Each location is a representative grid point, **not an areal or measured district-wide average**. Incomplete values and observed-day counts are retained in the candidate; completeness is checked before the multi-model input join.
- Existing 2021–2024 weather products are preserved separately and were not replaced.

### Daily IDSP

- The daily DHS/IDSP pipeline retains dated report snapshots and original PDFs separately from monthly and cumulative values. It keeps suspected and confirmed series distinct, treats cumulative counts as running totals, and does not add cumulative values across report dates.
- The last documented daily source snapshot in the project documentation is the DHS report dated 1 November 2026. A report snapshot is not a real-time feed; preliminary values can change. Check `reports/daily_idsp_data_quality_report.md` and the snapshot source-status metadata for the exact packaged state.
- Do not infer district monthly counts from annual district totals or combine daily/cumulative data with monthly reports without a separately validated transformation.

## 4. Existing dashboard functionality

The React app currently provides:

- **Overview:** observed data coverage, trends, and statewide annual totals.
- **Disease surveillance:** monthly disease, year, and classification filters with cases/deaths and CSV export.
- **Live Kerala Health Monitor:** latest retrieved daily report snapshot, separate daily/month-to-date/cumulative counts and district rows, provenance and source status; it is not a real-time sensor.
- **District explorer:** annual district comparison, not a district-month map.
- **Climate insights:** historical statewide weather proxy alongside statewide disease observations; no causal claim.
- **Forecasts & risk:** the earlier, limited historical hindcast/readiness view. It is not wired to the new experimental multi-model outputs.
- **Capacity simulator:** hypothetical user-entered scenarios only; no hospital capacity feed is connected.
- **Sources & methodology:** data lineage, source definitions, coverage, and caveats.

No validated hospital bed/ICU capacity feed, district-boundary map, operational future forecasting service, or live outbreak-alert feature is present.

## 5. Implemented forecasting models

The separate first multi-model experiment uses 2016–2025 dashboard-native **Confirmed** counts:

1. Seasonal Naive: same calendar month in the prior year; empirical training residual intervals.
2. Regularized Poisson regression: district and month effects, linear trend, previous-month incidence.
3. Regularized NB2 regression: the same history features with overdispersion.
4. Climate-informed Poisson regression.
5. Climate-informed NB2 regression.

Climate variants add lagged rainfall, preceding-three-month rainfall sum, temperature mean/range, humidity, and dew point. Weather is frozen at each forecast origin. Models are evaluated in rolling chronological windows at horizons 1–12; the December 2024 origin forecasts the held-out 2025 period.

The NB2 model is a regularized pooled fixed-effect model. It is **not** a Bayesian hierarchical model. No Bayesian inference algorithm has been implemented. Existing experiment artifacts and configuration are under `reports/multimodel_experiment/`; the earlier forecasting outputs under `reports/forecasting_experiment/` are a separate experiment.

## 6. Model Intelligence and Evaluation Engine

The engine is under `src/caregrid/model_intelligence/`:

- `registry.py`: model/configuration registrations, tasks, supported inputs/diseases/horizons, uncertainty capability, readiness, and limitations.
- `evaluation.py`: required-schema checks, unique prediction-key validation, equivalent observation and actual-value checks, count metrics, predictive log score where available, predictive-interval coverage/width/proper scores, district and fold summaries.
- `selection.py`: rolling-origin-only experimental selection per disease and horizons 1, 3, 6, and 12; applies evidence, interval coverage, per-fold coverage and stability gates before a composite ranking. Close candidates or a lack of eligible candidates produce `insufficient_evidence`.
- `interfaces.py`: separate extension contracts for forecasting, retrospective unusual-activity detection, and outbreak threshold-exceedance probability.
- `run_model_intelligence.py`: reads the saved multi-model prediction CSV and writes `reports/model_intelligence/` plus summary reports. It does not fit models or change the experiment outputs.

The final 2025 holdout is descriptive only and is excluded from selection. Selections are experimental, non-clinical, and not wired into the live dashboard.

## 7. Current experimental results

The saved multi-model comparison contains 11,760 prediction rows (10,080 rolling-origin and 1,680 final-2025), 3,600 metrics rows, 70 model-fit configurations, and no fit/forecast failures. Six December origins (2018–2023) are used for development comparison; the final holdout is December 2024 → January–December 2025.

The current selection policy found five experimental selections out of eight disease/horizon combinations:

| Disease | Horizon | Experimental engine result |
|---|---:|---|
| Dengue | 1 month | Climate-informed NB2 |
| Dengue | 3 months | Climate-informed NB2 |
| Dengue | 6 months | Insufficient evidence |
| Dengue | 12 months | Insufficient evidence |
| Leptospirosis | 1 month | Climate-informed NB2 |
| Leptospirosis | 3 months | History-only NB2 |
| Leptospirosis | 6 months | History-only NB2 |
| Leptospirosis | 12 months | Insufficient evidence |

These are outputs of the documented experimental policy, not production recommendations. They depend on the saved prediction artifact and its validation design.

Across 120 rolling model/disease/horizon interval summaries, 80% intervals are flagged undercovered in 80 groups and 95% intervals in 75 groups; 8 groups show 80% overcoverage. The warnings include strong undercoverage for multiple longer-horizon Dengue and Poisson variants. Some intervals are very wide. This is diagnostic evidence, not proof of calibration. The final holdout has only 14 districts per disease/horizon and one forecast origin, insufficient to establish calibration.

See `reports/model_selection_validation.md`, `reports/model_intelligence/uncertainty_review.csv`, `reports/multimodel_experiment_report.md`, and the corresponding machine-readable experiment artifacts.

## 8. Known limitations

- Historical disease classification/reporting consistency across years remains unverified; source categories must not be silently harmonized.
- District-to-state discrepancies and DHS/dashboard numeric differences remain unresolved.
- Daily IDSP values are snapshot reports, with preliminary values and distinct daily, month-to-date, and cumulative semantics.
- Weather points are representative locations; availability does not make them district-wide measurements or establish causal effects.
- Six rolling origins and one final holdout provide limited temporal evidence. The 2025 final period does not establish prospective performance or uncertainty calibration.
- Existing marginal district predictive intervals do not yield a valid joint statewide interval by simply summing interval endpoints.
- The model selector is an experimental evidence filter, not an automated production routing policy.
- No independently verified outbreak labels or official thresholds are available for sensitivity, false-alert, probability calibration, or lead-time validation.
- The API is read-only and does not provide operational forecasts, alerts, clinical advice, or real hospital capacity.
- Git currently has no commits or remotes; all project files appear untracked. Teammates should establish an agreed version-control baseline before collaborative changes.
- Some existing sidecars preserve absolute paths from the original workstation. Use sibling relative paths in the package and verify content by recorded hashes rather than relying on those machine-specific paths.

## 9. Not yet implemented

- Bayesian Poisson or Bayesian hierarchical Negative Binomial inference and diagnostics.
- Gaussian Process, Student-t Process, Bayesian Structural Time Series, and ensemble algorithms.
- A production-ready model lifecycle, persisted model registry service, or live model selection.
- Model uncertainty recalibration and prospective calibration monitoring.
- Retrospective anomaly detection evaluated against independently reviewed event labels.
- Probability of outbreak-threshold exceedance with defined thresholds and validated event labels.
- Officially validated climate-informed causal or forecast improvements.
- Spatial-temporal disease models, district-level monthly DHS harmonization, and population-normalized rates using vetted denominators.
- Live dashboard integration of the new multi-model experiment or operational alerts.
- Verified hospital capacity integration.

## 10. Recommended next development phases

1. **Team/source review:** verify dashboard and DHS classifications, month semantics, reconciliation mismatches, and the known source discrepancies; document what remains unresolved.
2. **Reproducibility and baseline:** establish Git history/remotes with the team, pin dependency versions, verify clean-machine setup, and retain immutable experiment artifacts and hashes.
3. **Uncertainty research:** diagnose interval undercoverage and width by district, horizon, disease, and origin; evaluate calibration methods only inside nested chronological validation, preserving the final holdout.
4. **Bayesian pilot:** after review, implement one count model with regularizing priors, multiple chains, convergence and predictive checks, and matched rolling origins. Do not label it Bayesian-ready based on point estimates.
5. **Outbreak evidence:** obtain independently reviewed historical event labels and epidemiologist-approved threshold definitions before evaluating anomaly detection or outbreak probability.
6. **Climate assessment:** establish weather forecast-origin availability and a fair history-only versus climate comparison over more validation origins and, if possible, better spatial weather support.
7. **Integration gate:** only after independent review, define a versioned API contract and guarded dashboard presentation for exploratory results. Keep model outputs visibly distinct from observed surveillance.

## 11. Handoff references

- Setup and commands: `SETUP.md`
- Open team backlog: `TEAM_TASKS.md`
- Data and source caveats: `reports/historical_2016_2025_data_audit.md`, `reports/source_discrepancy_analysis.md`, `reports/extended_weather_data_readiness.md`, and `reports/daily_idsp_data_quality_report.md`
- Experiment outputs: `reports/multimodel_experiment/` and `reports/model_intelligence/`
