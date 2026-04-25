# Tapeline — zero-dependency local runner
# Uses SQLite instead of Postgres, skips Redis (in-process pub/sub), no Docker required.
# Python 3.12+ and Node 20+ are the only prerequisites.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "=== Tapeline (no-Docker dev) ===" -ForegroundColor Cyan

# 1. Venv
if (-not (Test-Path "$root\backend\.venv")) {
    Write-Host "[1/5] Creating Python venv..."
    python -m venv "$root\backend\.venv"
    & "$root\backend\.venv\Scripts\pip.exe" install --upgrade pip | Out-Null
    Write-Host "      Installing backend deps (~1 min)..."
    & "$root\backend\.venv\Scripts\pip.exe" install -e "$root\backend[dev]"
} else {
    Write-Host "[1/5] venv exists"
}

# 2. .env with SQLite
if (-not (Test-Path "$root\.env")) {
    Write-Host "[2/5] Writing .env for SQLite..."
    @"
APP_NAME=Tapeline
APP_ENV=development
APP_URL=http://localhost:3000
API_URL=http://localhost:8000
DATABASE_URL=sqlite:///tapeline_dev.sqlite
POLYGON_API_KEY=
POLYGON_TIER=starter
CLERK_SECRET_KEY=
CLERK_PUBLISHABLE_KEY=
CLERK_WEBHOOK_SECRET=
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
RESEND_API_KEY=
SCORE_REFRESH_SECONDS=10
SNAPSHOT_REFRESH_SECONDS=10
"@ | Set-Content -Path "$root\.env" -Encoding utf8
} else {
    Write-Host "[2/5] .env exists"
}

# 3. Migrate
Write-Host "[3/5] Running DB migrations..." -ForegroundColor Yellow
Push-Location "$root\backend"
& ".venv\Scripts\python.exe" -m alembic upgrade head
Pop-Location

# 4. Launch API + worker
Write-Host "[4/5] Launching API + worker..." -ForegroundColor Yellow
$py = "$root\backend\.venv\Scripts\python.exe"

Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000" `
    -WorkingDirectory "$root\backend" -WindowStyle Normal

Start-Sleep -Seconds 3

Start-Process -FilePath $py -ArgumentList "-m", "app.workers.signal_publisher" `
    -WorkingDirectory "$root\backend" -WindowStyle Normal

# 5. Frontend
Write-Host "[5/5] Setting up frontend..." -ForegroundColor Yellow
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "      Installing frontend deps (~2 min, first run only)..."
    Push-Location "$root\frontend"
    npm install
    Pop-Location
}
if (-not (Test-Path "$root\frontend\.env.local")) {
    Copy-Item "$root\frontend\.env.local.example" "$root\frontend\.env.local"
}
Start-Process -FilePath "npm" -ArgumentList "run", "dev" `
    -WorkingDirectory "$root\frontend" -WindowStyle Normal

Write-Host ""
Write-Host "✔ Services launched. Waiting for frontend to build..." -ForegroundColor Green
Start-Sleep -Seconds 8
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "URLs:"
Write-Host "  Landing:   http://localhost:3000"
Write-Host "  Scanner:   http://localhost:3000/app/scanner  (updates every 10s)"
Write-Host "  API docs:  http://localhost:8000/docs"
Write-Host "  Health:    http://localhost:8000/api/health"
Write-Host ""
Write-Host "To stop: close the three service windows."
