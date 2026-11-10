param(
    [string]$At = "07:00",
    [string]$TaskName = "CareGrid Sentinel - Daily DHS IDSP Import"
)

$ErrorActionPreference = "Stop"
$runnerPath = Join-Path $PSScriptRoot "run_idsp_daily.ps1"
$powerShellPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path -LiteralPath $runnerPath -PathType Leaf)) {
    throw "Daily IDSP runner was not found: $runnerPath"
}
if (-not (Test-Path -LiteralPath $powerShellPath -PathType Leaf)) {
    throw "Windows PowerShell was not found: $powerShellPath"
}

try {
    $runTime = [datetime]::ParseExact(
        $At,
        "HH:mm",
        [System.Globalization.CultureInfo]::InvariantCulture
    )
}
catch {
    throw "The -At value must use 24-hour HH:mm format, for example 07:00."
}

$action = New-ScheduledTaskAction `
    -Execute $powerShellPath `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$runnerPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At $runTime
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Description "Checks the official Kerala DHS IDSP index once daily and preserves successful report snapshots." `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Output "Registered '$TaskName' to run daily at $($runTime.ToString('HH:mm'))."
Write-Output "The task runs only while the current user is logged on. Logs: data\live_surveillance\daily_idsp\logs\scheduled_import.log"
