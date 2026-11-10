$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
$importerPath = Join-Path $repositoryRoot "src\caregrid\import_idsp_daily.py"
$logDirectory = Join-Path $repositoryRoot "data\live_surveillance\daily_idsp\logs"
$logPath = Join-Path $logDirectory "scheduled_import.log"
$lockPath = Join-Path $logDirectory "scheduled_import.lock"

if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    throw "Project Python environment was not found: $pythonExecutable"
}
if (-not (Test-Path -LiteralPath $importerPath -PathType Leaf)) {
    throw "Daily IDSP importer was not found: $importerPath"
}
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

$lockStream = $null
try {
    $lockStream = [System.IO.File]::Open(
        $lockPath,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
}
catch [System.IO.IOException] {
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "$(Get-Date -Format o) Duplicate run skipped; another import holds the lock."
    exit 0
}

try {
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "$(Get-Date -Format o) Starting official DHS IDSP refresh."
    & $pythonExecutable $importerPath 2>&1 | ForEach-Object {
        Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "$(Get-Date -Format o) $_"
    }
    $importExitCode = $LASTEXITCODE

    if ($importExitCode -eq 0) {
        Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "$(Get-Date -Format o) Import completed successfully."
    }
    else {
        Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "$(Get-Date -Format o) Import failed with exit code $importExitCode."
    }
    exit $importExitCode
}
catch {
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "$(Get-Date -Format o) Import runner failed: $_"
    exit 1
}
finally {
    if ($null -ne $lockStream) {
        $lockStream.Dispose()
    }
}
