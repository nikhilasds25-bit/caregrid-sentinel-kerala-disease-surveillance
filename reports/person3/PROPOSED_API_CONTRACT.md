# CareGrid Sentinel — Person 3 API Contract Proposal

**Status:** DRAFT — Awaiting Person 1 approval  
**Scope:** Exploratory retrospective forecasting, unusual-activity detection, and threshold-exceedance analysis.

## 1. General Requirements

- All endpoints are read-only.
- Results are exploratory and not operational public-health alerts.
- Distinguish historical observations, retrospective predictions, and future forecasts.
- The current analysis contains backtests, not future forecasts.
- Keep the 2025 holdout separate from development results.
- Do not replace missing values with zero.
- Include data availability, evidence status, and limitations.
- No model is designated operationally ready.


## Standard API Response Structure

All five versioned endpoints use this JSON envelope:

    {
      "data": [],
      "meta": {
        "schema_version": "1.0",
        "generated_at": "ISO-8601 timestamp",
        "status": "exploratory",
        "filters": {}
      }
    }

Requirements:
- Observations and forecasts remain separate.
- Forecasts identify backtest or prospective prediction type.
- Prediction intervals disclose nominal and empirical coverage and calibration status.
- Detection signals include method, statistic, control limit, baseline period and parameters.
- Exceedance assessments include probability_calibration_status.
- Missing values remain null, never zero.
- Insufficient evidence is explicitly identified.
- The meaning of generated_at must be documented.

## 2. Proposed Endpoints

### GET /api/v1/surveillance/observations

**Purpose:** Provide actual reported disease observations, separate from forecasts.

Filters:
- disease
- district
- reporting period range
- classification

Response:
- data: array of observation records
- meta: schema version, generation timestamp, status, and applied filters

Each record includes:
- disease
- district
- reporting_period
- observed_count
- classification
- source information
- data availability status

Only actual reported observations are returned. Predictions must never appear as observed cases.

### GET /api/v1/forecasts

**Purpose:** Display actual versus predicted disease cases.

Filters:
- disease
- district
- model_name
- feature_set
- origin_period
- validation_phase

Response:
- status
- evidence_role
- filters
- records
- limitations

Each record includes:
- disease, district
- origin_period, target_period, horizon
- actual, predictive_mean
- original 80% and 95% prediction intervals
- calibrated intervals where available
- display interval bounds and their sources
- uncertainty caution flags

Source: outputs/chart_data/forecast_bands.csv

### GET /api/v1/model-comparisons

**Purpose:** Compare model performance without declaring a winning model.

Filters:
- disease
- evidence_role
- horizon_scope

Response:
- status
- filters
- records
- limitations

Metrics:
- MAE and RMSE
- Original and display interval coverage
- Prediction interval widths
- Calibration availability
- Model and uncertainty caution flags

Source: outputs/chart_data/model_comparison.csv

### GET /api/v1/detection/signals

**Purpose:** Display retrospective EWMA/CUSUM signals.

Filters:
- disease
- district
- detector_id
- period range

Response:
- status
- evidence_role
- filters
- records
- limitations

Each record includes:
- detector_id
- disease, district, period
- observed_count
- baseline
- anomaly_score
- unusual_activity_flag

Source: outputs/anomaly_chart_data/anomaly_signals.csv

These flags identify exploratory statistical deviations, not confirmed outbreaks.

### GET /api/v1/exceedance/assessments

**Purpose:** Display exploratory historical threshold-exceedance probabilities.

Filters:
- disease
- district
- model_name
- method
- validation_phase
- origin_period

Response:
- status
- evidence_role
- filters
- records
- limitations

Each record includes:
- disease, district
- origin_period, target_period
- model_name
- threshold_definition_id
- threshold
- observed_exceedance
- predicted_probability
- calibration_status
- status

Source: outputs/exceedance_chart_data/exceedance_chart_data.csv

Probabilities are uncalibrated and do not represent validated outbreak probabilities.

## 3. Error Handling

- HTTP 422: Invalid filter values.
- HTTP 503: Required dataset missing or structurally invalid.
- HTTP 200 with empty records: Valid filters but no matching observations.
- Missing values remain null in JSON responses.
- Insufficient evidence is explicitly identified.
- Never substitute fabricated or zero-filled data.

## 4. Data and Reproducibility

- Generated datasets remain separate from curated surveillance data.
- Record input/output hashes and methodology versions.
- Confirm whether generated CSV/JSON files should be committed or regenerated.
- Do not expose experimental model selections as operational defaults.
- Preserve data-source status and uncertainty limitations.

## 5. Deployment Considerations

- Frontend: React, TypeScript, Vite.
- Backend: FastAPI.
- Proposed deployment target: Vercel.
- Deployment architecture requires team approval.
- Confirm how generated datasets will be available in production.
- Avoid performing model training or expensive simulations during API requests.

## 6. Pending Person 1 Decisions

1. Approve or revise endpoint names and response structures.
2. Confirm which generated artifacts should be version-controlled.
3. Confirm branch and PR integration sequence.
4. Confirm whether validated outbreak thresholds or labels are available.
5. Confirm frontend/backend hosting arrangements for Vercel.
6. Confirm required source, model, uncertainty, and epidemiological review gates before dashboard integration.

**This document is a proposal, not an implemented API contract.**
