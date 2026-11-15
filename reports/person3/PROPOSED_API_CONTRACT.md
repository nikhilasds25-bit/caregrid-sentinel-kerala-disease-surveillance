# CareGrid Sentinel — Analytical API Contract

**Status:** Implemented in PR #3; integration and deployment validation pending.

**Scope:** Read-only access to retrospective forecasting, model comparison, unusual-activity detection, threshold exceedance, and reported disease observations.

## 1. General Requirements

- All endpoints are read-only and exploratory.
- Historical observations and model-generated predictions remain separate.
- Retrospective predictions must not be presented as future forecasts.
- EWMA/CUSUM signals are not confirmed outbreak alerts.
- Q90 thresholds are statistical, not epidemiologically validated.
- Exceedance probabilities are not validated outbreak probabilities.
- Missing values remain null rather than being replaced with zero.
- No forecasting model is designated operationally ready.
- The 2025 holdout must remain separate from development and model-selection results.

## 2. Standard Response Structure

All five endpoints return:

```json
{
  "data": [],
  "meta": {
    "schema_version": "1.0",
    "generated_at": "ISO-8601 timestamp",
    "status": "exploratory",
    "filters": {},
    "limitations": []
  }
}
```

`generated_at` indicates when the API response was created, not when the underlying analytical results were generated.

The observations endpoint additionally provides `geographic_granularity` in metadata.

## 3. Implemented Endpoints

### GET /api/v1/surveillance/observations

Returns reported observations, not model-generated predictions.

Supported filters:
- `disease`
- `district`
- `classification`
- `granularity`: monthly or annual
- `year`: 2020–2024

Monthly observations are statewide and cover available months in 2021–2024.

Annual observations provide district-level records for 2020–2024.

District filtering is unavailable for monthly observations and returns HTTP 422.

Records include `observed_count`, `reporting_period`, `temporal_granularity`, and `observation_type`.

Source classifications are preserved.

### GET /api/v1/forecasts

Returns exploratory retrospective forecasting results.

Supported filters:
- `disease`
- `district`
- `model_name`
- `validation_phase`

Source: `outputs/chart_data/forecast_bands.csv`

Records include model identifiers, feature sets, forecast origins, target periods, horizons, predicted means, original and calibrated prediction intervals, display intervals, interval sources, and uncertainty caution flags.

Each response record has `prediction_type` set to `backtest`.

The source CSV's `actual` column is excluded from API responses.

### GET /api/v1/model-comparisons

Returns retrospective model evaluation results without identifying an operationally approved model.

Supported filters:
- `disease`
- `evidence_role`
- `horizon_scope`

Source: `outputs/chart_data/model_comparison.csv`

Metrics include:
- MAE and RMSE
- Original and display prediction-interval coverage
- Prediction-interval widths
- Calibration share
- Forecast counts
- Model and uncertainty caution flags

### GET /api/v1/detection/signals

Returns exploratory retrospective unusual-activity signals.

Supported filters:
- `disease`
- `district`
- `detector_id`

Source: `outputs/anomaly_chart_data/anomaly_signals.csv`

Records include:
- Detector identifier
- Disease and district
- Reporting period
- Observed count
- Baseline
- Anomaly score
- Unusual-activity flag
- Evidence role and signal status/type

The current dataset does not expose detector control limits or parameter configurations.

Signals do not establish confirmed disease outbreaks.

### GET /api/v1/exceedance/assessments

Returns exploratory historical statistical threshold-exceedance assessments.

Supported filters:
- `disease`
- `district`
- `model_name`

Source: `outputs/exceedance_chart_data/exceedance_chart_data.csv`

Records include:
- Disease, district, and model
- Validation phase and forecast origin
- Target period and horizon
- Predictive mean
- Exceedance method and threshold definition
- Reference period and reference sample size
- Statistical threshold
- Predicted exceedance probability
- Observed exceedance indicator
- Calibration status
- Evidence role and exploratory label

The source CSV's `actual` column is excluded from API responses.

These probabilities have not been validated as calibrated outbreak probabilities.

## 4. Error Handling

- HTTP 422: Invalid supported filter values or incompatible observation granularity.
- HTTP 503: Required dataset unavailable or unreadable.
- HTTP 200 with empty `data`: Valid request with no matching records.
- Missing values should remain JSON null.

Not all filter values currently have explicit validation. Further validation and response-schema enforcement remain integration tasks.

## 5. Data Provenance and Reproducibility

Analytical outputs are generated from versioned project inputs.

Prepared datasets are read from disk at request time. Model training and expensive simulations are not executed by API endpoints.

Generation scripts and analytical methodology are maintained in PR #2.

The production deployment must make the required analytical CSV files available through reproducible preparation or an approved artifact-distribution method.

Large intermediate simulation outputs should not be committed solely to support API requests.

Input/output hashes and methodology metadata should accompany generated results where available.

## 6. Deployment Architecture

Agreed deployment approach:
- Frontend: React/TypeScript/Vite on Vercel.
- Backend: FastAPI on Render or Railway.
- Frontend backend URL: `VITE_API_BASE_URL`.
- Approved browser origins: `CORS_ORIGINS`.

The deployment owner is responsible for production services, environment configuration, and final integration.

## 7. Remaining Integration Work

1. Merge PR #2 into the forecasting branch.
2. Merge the combined forecasting branch through PR #1.
3. Update PR #3 with the merged analytical generation code.
4. Prepare analytical datasets reproducibly for backend deployment.
5. Verify source availability, filtering, data provenance, and response schemas.
6. Complete frontend/backend integration testing.
7. Review and merge PR #3 into `main` after approval.

## 8. Scientific Limitations

The current forecasting analyses are retrospective.

District-level analytical predictions must not be confused with separate statewide surveillance observations.

Unusual-activity signals and Q90 exceedance assessments are exploratory statistical indicators.

The system does not currently establish validated prospective outbreak-warning performance, calibrated outbreak probabilities, actual hospital occupancy, or operational hospital-capacity recommendations.
