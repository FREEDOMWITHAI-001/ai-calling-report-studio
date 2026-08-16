# Start the API and the UI.
#   .\run.ps1          -> API on :8000 + Vite dev server on :5173 (hot reload)
#   .\run.ps1 -Prod    -> build the UI once and serve everything from :8000
param([switch]$Prod)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = Join-Path $root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Virtualenv missing. Run .\setup.ps1 first." }

if ($Prod) {
    Write-Host "Building the UI..." -ForegroundColor Cyan
    Push-Location (Join-Path $root 'frontend')
    npm run build
    Pop-Location

    Write-Host "`nApp running at http://127.0.0.1:8000  (Ctrl+C to stop)" -ForegroundColor Green
    Push-Location (Join-Path $root 'backend')
    & $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    Pop-Location
    return
}

Write-Host "Starting API on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
$api = Start-Process -FilePath $py `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload' `
    -WorkingDirectory (Join-Path $root 'backend') -PassThru

Start-Sleep -Seconds 4
Write-Host "Starting UI on http://127.0.0.1:5173 ..." -ForegroundColor Cyan
Write-Host "`n  Open http://127.0.0.1:5173 in your browser.  Ctrl+C stops both.`n" -ForegroundColor Green

try {
    Push-Location (Join-Path $root 'frontend')
    npm run dev
} finally {
    Pop-Location
    if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force }
}
