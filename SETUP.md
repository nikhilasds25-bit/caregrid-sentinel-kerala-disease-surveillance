# CareGrid Sentinel — Windows Setup

These instructions use Windows PowerShell and assume Python 3.11+ and Node.js/npm are installed. The current development environment used Python 3.13 and Node/npm; exact installed versions can be recorded with `python --version` and `node --version`. The setup has not been tested on a separate clean computer.

## 1. Extract and enter the project

Extract `CareGrid-Sentinel-Team-Handoff.zip` into a working folder, then:

```powershell
Set-Location 'C:\path\to\CareGrid-Sentinel'
```

Replace the example path with the actual extraction path.

## 2. Create and install the Python environment

From the project root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
```

If PowerShell blocks activation, either follow your organization's policy for local scripts or invoke the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

## 3. Start FastAPI

From the project root, in a dedicated PowerShell terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn caregrid.api:app --app-dir .\src --reload --host 127.0.0.1 --port 8000
```

The API is available at `http://127.0.0.1:8000`; interactive OpenAPI documentation is at `http://127.0.0.1:8000/docs`. Keep this terminal running while using the dashboard.

## 4. Install and start the React/Vite dashboard

In a second PowerShell terminal:

```powershell
Set-Location 'C:\path\to\CareGrid-Sentinel\dashboard'
npm ci
npm run dev
```

Open the local URL printed by Vite (normally `http://127.0.0.1:5173`). The Vite development server proxies `/api` requests to FastAPI on port 8000.

## 5. Run backend tests

From the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 6. Run frontend tests

From the dashboard folder:

```powershell
Set-Location 'C:\path\to\CareGrid-Sentinel\dashboard'
npm test
```

## 7. Build the production dashboard

From the dashboard folder:

```powershell
npm run build
```

This creates `dashboard/dist/`. When that build exists, FastAPI can serve the static frontend as well as the API:

```powershell
Set-Location 'C:\path\to\CareGrid-Sentinel'
.\.venv\Scripts\python.exe -m uvicorn caregrid.api:app --app-dir .\src --host 127.0.0.1 --port 8000
```

## 8. Reproduce the existing experiments safely

**Experiment runners write reports and outputs under `reports/`.** In particular, running them in the handoff extraction can replace included result files. Preserve the packaged baseline by reproducing from a disposable copy. The following example makes a new copy in the current user's temporary directory, excluding Git internals, environments, build products, and caches:

```powershell
$PackageRoot = (Get-Location).Path
$ReproRoot = Join-Path $env:TEMP ("CareGrid-Sentinel-repro-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $ReproRoot | Out-Null
robocopy $PackageRoot $ReproRoot /E /XD .git .venv .pytest_cache __pycache__ node_modules dist /XF *.pyc tsconfig.tsbuildinfo CareGrid-Sentinel-Team-Handoff.zip
if ($LASTEXITCODE -ge 8) { throw "Copy failed with robocopy exit code $LASTEXITCODE" }
Set-Location $ReproRoot
```

Install Python dependencies in this copy if not already available:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

Run the earlier, limited 2023–2024 baseline experiment:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\run_forecasting_experiment.py
```

Run the 2016–2025 multi-model comparison and write its experiment artifacts to a separate folder. Its two summary Markdown reports are still written beneath `reports/` in this disposable copy:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\run_multimodel_experiment.py --output-dir .\reports\multimodel_experiment_reproduction
```

Run the Model Intelligence evaluation on the saved predictions in the disposable copy:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\run_model_intelligence.py
```

The multi-model and Model Intelligence reports contain the exact input hashes and validation results. No experiment was rerun while preparing this handoff. The first-time installation does not include PyMC/Stan; Bayesian models are not implemented. The archived-weather model identifier was not explicitly exposed by the source response. Some source PDFs/data may require separate interpretation even though source snapshots are included.

## 9. Data and environment notes

- No `.env` file or secret is required for local API/dashboard use.
- Historical data and saved outputs are included so the application and offline evaluations can operate without fetching a current source response.
- Running import/build scripts that retrieve data may require network access and can create or replace their documented outputs. Review each script's options and provenance before refreshing any source.
- The daily IDSP importer is an on-demand source refresh, not a prerequisite for running saved data or the test suites.
- Dependencies are specified in `requirements.txt` and `dashboard/package-lock.json`; the project does not currently pin all Python packages to exact versions.
- The handoff ZIP has not been validated on another computer. A separate clean-machine test is still required.
