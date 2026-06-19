# run-daily.ps1 — Task Scheduler entrypoint for the daily dump.
# Runs dumpbot.py from the wow-api repo and tees output to a dated log under automation/logs/.
# Register it to run daily "whether the user is logged on or not" BUT with access to an
# interactive desktop session (input automation needs one — see README).
#
#   powershell -ExecutionPolicy Bypass -File automation\run-daily.ps1

$ErrorActionPreference = "Stop"

$AutomationDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $AutomationDir
$LogDir = Join-Path $AutomationDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$Log = Join-Path $LogDir "dumpbot_$Stamp.log"

# Use the venv python if present, else whatever 'python' resolves to.
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

Push-Location $RepoRoot
try {
    & $Python (Join-Path $AutomationDir "dumpbot.py") 2>&1 | Tee-Object -FilePath $Log
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}

Write-Output "dumpbot exited $code; log: $Log"
exit $code
