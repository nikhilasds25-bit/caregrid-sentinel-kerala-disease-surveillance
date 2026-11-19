# CareGrid Sentinel
### Climate-Aware Disease Surveillance, Forecasting and Hospital Capacity Stress Simulation for Kerala

**An integrated public-health analytics and decision-support prototype for Kerala.**

CareGrid Sentinel brings together disease surveillance data, historical climate indicators, retrospective forecasting experiments, exploratory unusual-activity analysis and hypothetical hospital capacity simulation through an interactive web application.

---

## Project Information

| Detail | Information |
|---|---|
| Project | CareGrid Sentinel |
| Institution | Digital University Kerala |
| Programme | Master of Science in Data Science |
| Group | Group D |
| Academic Year | 2026–2027 |
| Faculty Guide | Dr Anoop Ayappan |
| Frontend | React, TypeScript, Vite |
| Backend | Python, FastAPI |
| Data Analysis | Pandas, NumPy, scikit-learn |
| Deployment | Vercel and Render |

### Project Team

- Nikhil A S
- Arun P S
- Anu Gopal V

---

## 1. Project Overview

Public-health information is published through different government reports and formats, with varying reporting frequencies, geographical coverage and disease classifications. This makes it difficult to examine disease trends consistently, compare districts and study disease patterns alongside environmental conditions.

CareGrid Sentinel addresses this problem by developing a source-aware analytical workspace for Kerala, with an initial focus on **Dengue and Leptospirosis**.

The platform integrates:

- Historical statewide disease surveillance.
- Annual district-level disease comparisons.
- Daily DHS/IDSP report snapshots.
- Historical precipitation and temperature indicators.
- Retrospective disease-count forecasting experiments.
- Exploratory unusual-activity signals using EWMA and CUSUM.
- Historical Q90 threshold-exceedance analysis.
- Hypothetical hospital capacity and length-of-stay simulation.

The system is designed for public-health surveillance analysts, researchers, district and state health planners, and hospital-preparedness teams.

**Important:** CareGrid Sentinel is an academic public-health analytics prototype. It is not a clinical diagnostic system, an official outbreak alert service, a real-time surveillance system or a live hospital occupancy platform.

---

## 2. Key Features

### 2.1 Disease Surveillance

Provides historical disease trends and reported cases and deaths for Dengue and Leptospirosis.

The application maintains separate reporting categories and source-specific classifications rather than automatically combining categories from different reporting years.

### 2.2 District-Level Exploration

Provides annual comparisons across Kerala's 14 districts using available district-level disease records.

The annual district dataset is maintained separately from the monthly statewide dataset. Annual observations are not artificially converted into district-month observations.

### 2.3 Live Kerala Health Monitor

Integrates retrieved daily DHS/IDSP report snapshots.

The module preserves:
- Report publication dates.
- Retrieval timestamps.
- District-level reported values where available.
- Suspected and confirmed case categories.
- Source information and report status.

Daily reports are snapshots of official publications, not a continuous real-time feed. Preliminary values may change following laboratory testing and official review.

### 2.4 Climate Insights

Integrates historical weather information from the Open-Meteo Historical Weather API.

The variables include:
- Precipitation.
- Mean temperature.
- Minimum temperature.
- Maximum temperature.
- Relative humidity.
- Dew point.

Weather measurements are derived from representative district-location estimates. They are contextual proxies, not exact district-wide or population-weighted measurements.

### 2.5 Retrospective Forecasting

The project implements an offline disease-count forecasting experiment using:

- Seasonal Naive.
- Regularized Poisson Regression.
- Regularized Negative Binomial (NB2) Regression.
- Climate-informed Poisson Regression.
- Climate-informed NB2 Regression.
- A separate direct Negative Binomial model implementation.

The experiment uses chronological validation rather than random train-test splitting.

Forecasting outputs are retrospective research results. They are not operational future predictions.

### 2.6 Model Intelligence and Evaluation

A separate evaluation engine assesses saved forecasting predictions and their uncertainty.

It includes:
- Model registration and readiness assessment.
- Prediction and actual-value consistency checks.
- MAE and RMSE evaluation.
- Predictive log scores where available.
- Prediction interval coverage and width.
- Rolling-origin evaluation.
- Evidence-based experimental model selection.

The selection engine can return `insufficient_evidence` rather than forcing a model choice.

### 2.7 Unusual-Activity Analysis

Implements two retrospective statistical methods:

- **EWMA – Exponentially Weighted Moving Average**
- **CUSUM – Cumulative Sum**

These methods identify unusual deviations from historical seasonal reference patterns.

They are exploratory statistical signals, not validated outbreak alerts.

### 2.8 Q90 Threshold Analysis

Implements historical 90th-percentile threshold analysis using:

- Q90 across all historical months.
- Seasonal-window Q90.

Approximate model-based threshold-exceedance probabilities are also explored.

These estimates are not calibrated outbreak probabilities and do not represent official epidemiological thresholds.

### 2.9 Hospital Capacity Simulator

Provides a user-driven simulation for hypothetical hospital demand.

Inputs include:
- Disease cases.
- Assumed hospitalization rate.
- Total available beds.
- Initially occupied beds.
- Average length of stay.

Outputs include estimated admissions, projected occupancy, peak load, remaining beds and potential bed shortages.

All capacity values are assumptions entered by the user. No verified hospital occupancy or bed-availability feed is connected.

---

## 3. Data Sources

The project uses publicly available government surveillance resources and historical weather information.

| Source | Data Used |
|---|---|
| Kerala Health Department | Disease prevalence and district-wise disease records |
| Directorate of Health Services, Kerala | Communicable disease reports |
| Integrated Disease Surveillance Programme (IDSP) | Daily disease surveillance reports |
| Open-Meteo Historical Weather API | Historical precipitation and temperature information |

### Official Source Links

- Kerala Health Department: https://health.kerala.gov.in/
- Kerala Department Data: https://health.kerala.gov.in/department-data
- Kerala Disease Prevalence: https://health.kerala.gov.in/static_disease_prevalence
- Directorate of Health Services: https://dhs.kerala.gov.in/en/data-on-communicable-diseases/
- IDSP: https://idsp.mohfw.gov.in/
- Open-Meteo Historical Weather API: https://open-meteo.com/en/docs/historical-weather-api

---

## 4. Dataset Coverage

The project maintains separate datasets for different reporting frequencies and geographical levels.

| Dataset | Coverage | Details |
|---|---|---|
| Statewide monthly disease records | 2021–2024 | 48 monthly periods |
| Annual district disease records | 2020–2024 | 280 records across 14 districts |
| Extended dashboard disease candidate | 2016–2025 | 6,720 candidate rows |
| Confirmed district-month modelling panel | 2016–2025 | 3,360 observations |
| Daily DHS/IDSP reports | 25 July–1 November 2026 | 97 successfully parsed report dates |
| Historical statewide weather proxy | 2021–2024 | 48 monthly records |
| Extended district-location weather candidate | 2016–2025 | 1,680 weather records |

### Data Quality Principles

CareGrid Sentinel follows explicit data-quality rules:

1. Missing values are not automatically converted into zero.
2. Confirmed, Probable and Suspected categories are preserved separately where definitions are not established as equivalent.
3. Annual district records are not treated as monthly district observations.
4. Original source information and retrieval metadata are retained.
5. Cross-source differences are documented instead of being silently overwritten.
6. Representative weather estimates are clearly identified as proxies.

The extended modelling panel includes 224 explicit zero-case records and retains four source reconciliation mismatch cells, two of which involve Confirmed observations.

---

## 5. Forecasting Methodology

### 5.1 Models

**Seasonal Naive**

Uses the corresponding observation from the previous seasonal cycle as a benchmark for monthly disease-count forecasting.

**Poisson Regression**

Uses a regularized log-link count model to estimate expected disease counts.

**Negative Binomial NB2 Regression**

Allows overdispersion using the variance relationship:

Var(Y | X) = μ + αμ²

This provides an alternative to the restrictive Poisson variance assumption.

**Climate-Informed Variants**

Additional weather features are included to examine whether historical climate indicators provide incremental predictive information.

The implemented NB2 regression is a regularized fixed-effects model. It is not a Bayesian hierarchical model.

### 5.2 Validation Strategy

The retrospective experiment uses:
- Six chronological rolling origins from December 2018 to December 2023.
- A separate December 2024 origin for the 2025 holdout.
- Forecast horizons of 1 to 12 months.

The final 2025 holdout is not used for model fitting or model selection.

### 5.3 Model Intelligence

The separate Model Intelligence and Evaluation Engine examines saved predictions across equivalent validation observations.

Experimental model selection results:

| Disease | 1 Month | 3 Months | 6 Months | 12 Months |
|---|---|---|---|---|
| Dengue | Climate NB2 | Climate NB2 | Insufficient evidence | Insufficient evidence |
| Leptospirosis | Climate NB2 | History-only NB2 | History-only NB2 | Insufficient evidence |

These selections are exploratory research outputs, not production model recommendations.

### 5.4 Uncertainty Assessment

The saved experiment contains:
- 11,760 prediction rows.
- 3,600 metric rows.
- 70 model-fit configurations.
- Zero failed model windows.

The uncertainty review identified undercoverage in many rolling validation groups:

- 80% intervals: undercoverage in 80 of 120 groups.
- 95% intervals: undercoverage in 75 of 120 groups.
- Eight groups showed 80% overcoverage for the 80% intervals.

Therefore, reliable predictive interval calibration has not been established.

Bayesian Negative Binomial, Bayesian Poisson, Gaussian/Student-t Processes, Bayesian Structural Time Series, Hidden Markov Models and ensemble methods remain possible future extensions rather than completed models.

---

## 6. System Architecture

The project follows a modular full-stack architecture.

```text
             PUBLIC DATA SOURCES
                     |
       +-------------+-------------+
       |             |             |
   Disease Data   DHS / IDSP    Climate Data
       |             |             |
       +-------------+-------------+
                     |
                     v
          DATA PROCESSING LAYER
             Python / Pandas
                     |
          Cleaning and Validation
                     |
          Curated Datasets
                     |
          +----------+----------+
          |                     |
          v                     v
     ANALYTICAL ENGINE      DATA SERVICES
     Forecasting            Data Access
     Poisson / NB2          Validation
     Seasonal Naive         Provenance
     EWMA / CUSUM
     Q90 Analysis
     Capacity Simulation
          |                     |
          +----------+----------+
                     |
                     v
             FASTAPI BACKEND
              Read-only API
                     |
                     v
           REACT + TYPESCRIPT UI
                     |
                     v
           INTERACTIVE DASHBOARD
```

### Technology Stack

| Layer | Technologies |
|---|---|
| Programming | Python |
| Data Processing | Pandas, NumPy |
| Statistical Modelling | scikit-learn, SciPy |
| Backend | FastAPI, Uvicorn |
| Frontend | React, TypeScript |
| Build Tool | Vite |
| Charts | Recharts |
| Testing | Pytest, Vitest |
| Backend Deployment | Render |
| Frontend Deployment | Vercel |
| Version Control | Git, GitHub |

---

## 7. Repository Structure

```text
caregrid-sentinel-kerala-disease-surveillance/
│
├── dashboard/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── AnalyticalDashboard.tsx
│   │   ├── ForecastingExperiment.tsx
│   │   ├── LiveSurveillance.tsx
│   │   ├── UnusualActivity.tsx
│   │   ├── ThresholdExceedance.tsx
│   │   ├── ModelComparison.tsx
│   │   ├── capacitySimulation.ts
│   │   └── components.tsx
│   ├── package.json
│   └── package-lock.json
│
├── data/
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   ├── candidates/
│   └── live_surveillance/
│
├── outputs/
│   ├── exceedance_thresholds/
│   └── predictive_draws/
│
├── reports/
│   ├── forecasting_experiment/
│   ├── multimodel_experiment/
│   ├── model_intelligence/
│   ├── model_selection/
│   ├── interval_calibration/
│   └── data_quality_audit.md
│
├── scripts/
│   ├── prepare_analytical_data.py
│   ├── register_idsp_daily_task.ps1
│   └── run_idsp_daily.ps1
│
├── src/
│   └── caregrid/
│       ├── api.py
│       ├── analytical_api.py
│       ├── surveillance.py
│       ├── daily_surveillance.py
│       ├── forecasting.py
│       ├── outbreak_detection.py
│       ├── exceedance.py
│       ├── multimodel/
│       ├── model_intelligence/
│       └── run_multimodel_experiment.py
│
├── tests/
├── requirements.txt
├── render.yaml
├── SETUP.md
├── HANDOFF.md
└── README.md
```

Generated analytical chart files under `outputs/chart_data/`, `outputs/anomaly_chart_data/` and `outputs/exceedance_chart_data/` are created by the analytical data preparation script.

---

## 8. Installation and Local Setup

### Prerequisites

- Python 3.11 or later.
- Node.js and npm.
- Git.
- Windows PowerShell is used in the documented setup instructions.

### Step 1: Clone the repository

```powershell
git clone https://github.com/nikhilasds25-bit/caregrid-sentinel-kerala-disease-surveillance.git

cd caregrid-sentinel-kerala-disease-surveillance
```

### Step 2: Create Python environment

```powershell
py -3 -m venv .venv

.\.venv\Scripts\python.exe -m pip install --upgrade pip

.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

### Step 3: Generate analytical dashboard datasets

Run this once before starting the local application so the exploratory analytical API has its required generated CSV files.

```powershell
.\.venv\Scripts\python.exe .\scripts\prepare_analytical_data.py
```

This prepares the retrospective forecast, model-comparison, EWMA/CUSUM and Q90 chart datasets.

### Step 4: Start FastAPI backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn caregrid.api:app --app-dir .\src --reload --host 127.0.0.1 --port 8000
```

Backend:

http://127.0.0.1:8000

API documentation:

http://127.0.0.1:8000/docs

### Step 5: Start React frontend

Open another terminal:

```powershell
cd dashboard

npm ci

npm run dev
```

Open the local URL printed by Vite, normally:

http://127.0.0.1:5173

The Vite development server proxies API requests to FastAPI on port 8000.

---

## 9. Reproducing Data Pipelines and Experiments

### Historical Weather Integration

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\integrate_historical_weather.py
```

Use `--refresh` to explicitly request fresh API responses.

### Daily IDSP Report Import

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\import_idsp_daily.py
```

This retrieves official report snapshots on demand. It does not assume continuous monitoring or scheduled polling.

### Extended Multi-Model Experiment

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\run_multimodel_experiment.py --output-dir .\reports\multimodel_experiment_reproduction
```

The experiment generates retrospective predictions, evaluation metrics, residuals, validation information and model configuration outputs.

### Model Intelligence Evaluation

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\run_model_intelligence.py
```

This evaluates saved predictions and generates model-selection and uncertainty reports. It does not retrain the forecasting models.

**Note:** Experiment runners can generate or replace report files. Use a separate working copy when reproducing experiments if you need to preserve the committed reference outputs.

---

## 10. Testing

### Backend Tests

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### Frontend Tests

Run from the dashboard folder:

```powershell
npm test
```

### Production Build

```powershell
npm run build
```

The frontend build performs TypeScript compilation and Vite production bundling.

---

## 11. API Overview

The backend exposes read-only REST API endpoints.

### Main API

| Endpoint | Purpose |
|---|---|
| `/api/health` | Backend and dataset status |
| `/api/overview` | Dashboard overview |
| `/api/disease/monthly` | Monthly disease observations |
| `/api/districts` | Annual district comparisons |
| `/api/climate` | Historical climate context |
| `/api/methodology` | Sources and methodology |
| `/api/forecasting/experiment` | Retrospective baseline experiment |
| `/api/live-surveillance/` | Daily and annual surveillance data |

### Exploratory Analytical API

The versioned analytical API uses the `/api/v1/` prefix.

| Endpoint | Purpose |
|---|---|
| `/api/v1/forecasts` | Historical retrospective predictions |
| `/api/v1/model-comparisons` | Model comparison records |
| `/api/v1/detection/signals` | EWMA/CUSUM signals |
| `/api/v1/exceedance/assessments` | Q90 threshold assessments |
| `/api/v1/surveillance/observations` | Source-specific surveillance observations |

All analytical endpoints are intended for retrospective exploration, not operational health alerts.

---

## 12. Deployment

The project uses separate backend and frontend hosting.

**Backend:** Render  
Configuration: `render.yaml`

**Frontend:** Vercel  
Application source: `dashboard/`

Recorded deployment URLs:

- Frontend: https://caregrid-sentinel.vercel.app/
- Backend: https://caregrid-sentinel-api-4lh3.onrender.com/
- Backend API documentation: https://caregrid-sentinel-api-4lh3.onrender.com/docs

For separate frontend/backend deployments:

- Configure the Vercel environment variable `VITE_API_BASE_URL` with the backend API origin.
- Configure the Render environment variable `CORS_ORIGINS` with the frontend origin.

Deployment availability may change, so verify the hosted services before relying on them.

---

## 13. Limitations and Responsible Use

CareGrid Sentinel is a research prototype, and its outputs must be interpreted carefully.

1. Disease classifications and reporting definitions vary across sources and years.
2. Four source reconciliation mismatch cells remain documented, including two involving Confirmed observations.
3. The district annual dataset cannot replace a district-month disease dataset.
4. Weather indicators are representative-location proxies and are not population-weighted district measurements.
5. Forecasting outputs are retrospective, and the predictive intervals show undercoverage in many evaluation groups.
6. Climate indicators do not consistently improve forecasting accuracy.
7. EWMA, CUSUM and Q90 have not been validated as operational outbreak detection systems.
8. No Bayesian hierarchical forecasting model has been implemented.
9. No independently verified outbreak labels or official epidemiological thresholds are available for validating outbreak detection performance.
10. Hospital capacity values are user-entered assumptions; no actual hospital data feed is connected.

CareGrid Sentinel does not provide individual diagnosis, treatment recommendations, official outbreak alerts or real hospital resource allocation.

---

## 14. Future Enhancements

- Improve the consistency and traceability of official disease data.
- Extend validated district-month surveillance coverage.
- Review and resolve remaining source reconciliation differences.
- Improve count-model validation and predictive interval calibration.
- Expand climate analysis only where spatial and temporal alignment is defensible.
- Evaluate unusual-activity signals against independently verified outbreak events.
- Explore Bayesian count models when a suitable inference environment and diagnostics are available.
- Integrate verified hospital admission, discharge and bed-capacity information through appropriate data-sharing permissions.
- Improve monitoring, access control and governance for any future operational deployment.

---

## 15. References

1. Kerala Health Department — https://health.kerala.gov.in/
2. Directorate of Health Services, Kerala — https://dhs.kerala.gov.in/
3. Integrated Disease Surveillance Programme — https://idsp.mohfw.gov.in/
4. Open-Meteo Historical Weather API — https://open-meteo.com/en/docs/historical-weather-api
5. Hyndman, R. J. and Athanasopoulos, G. (2021). *Forecasting: Principles and Practice*, 3rd Edition. OTexts.

---

## 16. Project Team

**Group D — MSc Data Science**

Digital University Kerala

- Nikhil A S
- Arun P S
- Anu Gopal V

**Faculty Guide:** Dr.Anoop Ayappan

**Academic Year:** 2026–2027

---

*CareGrid Sentinel — Data-driven insights. Prepared communities.*E is unavailable because the training set contains no two observations separated by 12 months. Climate-enhanced performance was not evaluated: there is insufficient training history for defensible lag selection, and actual weather during the 2024 holdout would not be available at a 2023 forecast origin.
