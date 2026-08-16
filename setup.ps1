# One-time setup: Python venv + backend deps + frontend deps.
# Usage:  .\setup.ps1
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

Write-Host "== Checking prerequisites ==" -ForegroundColor Cyan
foreach ($cmd in 'python', 'node', 'npm') {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $found) { throw "$cmd is not on PATH. Install it and re-run." }
    Write-Host ("  {0,-6} {1}" -f $cmd, $found.Source)
}

Write-Host "`n== Backend: virtualenv + dependencies ==" -ForegroundColor Cyan
$venv = Join-Path $root 'backend\.venv'
if (-not (Test-Path $venv)) { python -m venv $venv }
$py = Join-Path $venv 'Scripts\python.exe'
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r (Join-Path $root 'backend\requirements.txt') --quiet
Write-Host "  backend dependencies installed"

$envFile = Join-Path $root 'backend\.env'
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $root 'backend\.env.example') $envFile
    Write-Host "  created backend\.env - edit it to point at your database (SQLite is used if DATABASE_URL is removed)"
}

Write-Host "`n== Frontend: npm install ==" -ForegroundColor Cyan
Push-Location (Join-Path $root 'frontend')
npm install --no-audit --no-fund
Pop-Location

Write-Host "`n== Creating database tables ==" -ForegroundColor Cyan
Push-Location (Join-Path $root 'backend')
& $py -c "from app.db import init_db; init_db(); print('  tables ready')"
Pop-Location

Write-Host "`nSetup complete. Start the app with:  .\run.ps1" -ForegroundColor Green
