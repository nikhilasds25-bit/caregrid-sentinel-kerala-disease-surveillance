# CareGrid Sentinel — Analytical Dashboard Deployment

## Purpose

Deploy the exploratory retrospective analytical dashboard with a separately hosted FastAPI backend.

The analytical outputs are historical backtests, not prospective disease forecasts, confirmed outbreak alerts, or hospital-capacity predictions.

## 1. Backend deployment — Render

The repository includes `render.yaml`, defining the `caregrid-sentinel-api` Python web service.

Deploy the repository using Render's Blueprint deployment workflow.

Select the intended repository and branch. Review the service configuration before deploying.

### Build command

```bash
pip install -r requirements.txt && python scripts/prepare_analytical_data.py
```

The preparation script runs these existing generators in order:

1. `caregrid.run_chart_data`
2. `caregrid.run_anomaly_chart_data`
3. `caregrid.run_exceedance_analysis`
4. `caregrid.run_exceedance_chart_data`

The script uses existing tracked input artifacts. It does not retrain forecasting models.

Generated analytical CSV files are prepared during the build and are not required to be committed to Git.

### Start command

    uvicorn caregrid.api:app --app-dir src --host 0.0.0.0 --port $PORT

### Backend environment variable

Set:

    CORS_ORIGINS=https://YOUR-FRONTEND.vercel.app

Replace the example with the actual Vercel frontend origin.

For multiple allowed origins, use comma-separated URLs.

Do not include a trailing slash.

## 2. Frontend deployment — Vercel

Configure the React dashboard project with:

- Root directory: `dashboard`
- Build command: `npm run build`
- Output directory: `dist`

### Frontend environment variable

Set:

    VITE_API_BASE_URL=https://YOUR-BACKEND.onrender.com

Replace the example with the actual Render backend URL.

Redeploy the frontend after changing its environment variables.

## 3. Verification

After both services are deployed:

1. Confirm that the backend responds to its API endpoints.
2. Open the Vercel dashboard and select the analytical view.
3. Verify disease and district filters.
4. Verify that actual Confirmed district-month observations appear alongside retrospective predictions.
5. Check model comparison, EWMA/CUSUM, and Q90 exploratory views.
6. Confirm that browser developer tools show no CORS errors.

## 4. Local validation

From the repository root:

    .venv/Scripts/python.exe scripts/prepare_analytical_data.py
    PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q

From the `dashboard` directory:

    npm test
    npm run build

## 5. Data interpretation and limitations

- District-month actual observations are sourced separately from statewide curated monthly data.
- The analytical forecasts are retrospective backtests, not future predictions.
- The 2025 holdout must remain separate from development and tuning evidence.
- EWMA/CUSUM flags represent unusual activity, not confirmed outbreaks.
- Q90 exceedance assessments are exploratory and must not be interpreted as validated outbreak probabilities.
- Missing observations are not replaced with zero.
- Prediction-interval coverage may be inadequate.
- No validated hospital-capacity simulation is provided.
- Deployment success must be verified on the actual hosting platform; local tests alone do not establish production readiness.

## 6. Operational notes

Dataset generation occurs during the backend build rather than inside API requests.

The Render service must have sufficient resources to complete dependency installation and analytical dataset preparation.

If deployment fails, inspect the Render build logs before changing analytical code or committing generated datasets.
