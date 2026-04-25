# Tapeline — local dev runner
# Starts Postgres + Redis in docker, migrates DB, runs API + worker, runs frontend.
# Prerequisites: Docker Desktop, Python 3.12, Node 20+.

param(
    [switch]$SkipFrontend,
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "=== Tapeline dev runner ===" -ForegroundColor Cyan

# 1. Postgres + Redis via Docker
if (-not $SkipDocker) {
    Write-Host "[1/5] Starting Postgres + Redis..." -ForegroundColor Yellow
    try {
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Docker daemon not reachable" }
    } catch {
        Write-Host ""
        Write-Host "ERROR: Docker Desktop is not running." -ForegroundColor Red
        Write-Host "Start Docker Desktop from the Windows menu, wait for it to show 'Engine running',"
        Write-Host "then re-run: .\scripts\run_local.ps1"
        exit 1
    }
    docker compose -f "$root\infra\docker-compose.yml" up -d postgres redis
    Start-Sleep -Seconds 4
}

# 2. Backend venv
if (-not (Test-Path "$root\backend\.venv")) {
    Write-Host "[2/5] Creating Python venv..."
    python -m venv "$root\backend\.venv"
    & "$root\backend\.venv\Scripts\pip.exe" install --upgrade pip
    & "$root\backend\.venv\Scripts\pip.exe" install -e "$root\backend[dev]"
} else {
    Write-Host "[2/5] venv exists"
}

# 3. .env
if (-not (Test-Path "$root\.env")) {
    Write-Host "[3/5] Copying .env.example -> .env"
    Copy-Item "$root\.env.example" "$root\.env"
    # Override DB to match docker-compose
    (Get-Content "$root\.env") `
        -replace "^DATABASE_URL=.*", "DATABASE_URL=postgresql://tapeline:dev_only_change_me@localhost:5432/tapeline" `
        | Set-Content "$root\.env"
}

# 4. DB migrate
Write-Host "[4/5] Running DB migrations..." -ForegroundColor Yellow
Push-Location "$root\backend"
& ".venv\Scripts\python.exe" -m alembic upgrade head
Pop-Location

# 5. Launch API + worker + frontend
Write-Host "[5/5] Launching services..." -ForegroundColor Yellow

$py = "$root\backend\.venv\Scripts\python.exe"
Start-Process -FilePath $py -ArgumentList "-m uvicorn app.main:app --reload --port 8000" `
    -WorkingDirectory "$root\backend" -WindowStyle Normal
Start-Sleep -Seconds 2
Start-Process -FilePath $py -ArgumentList "-m app.workers.signal_publisher" `
    -WorkingDirectory "$root\backend" -WindowStyle Normal

if (-not $SkipFrontend) {
    if (-not (Test-Path "$root\frontend\node_modules")) {
        Write-Host "Installing frontend deps (first run, ~2 min)..." -ForegroundColor Yellow
        Push-Location "$root\frontend"
        npm install
        Pop-Location
    }
    if (-not (Test-Path "$root\frontend\.env.local")) {
        Copy-Item "$root\frontend\.env.local.example" "$root\frontend\.env.local"
    }
    Start-Process -FilePath "npm" -ArgumentList "run dev" `
        -WorkingDirectory "$root\frontend" -WindowStyle Normal
}

Write-Host ""
Write-Host "All services started. Opening browser..." -ForegroundColor Green
Start-Sleep -Seconds 6
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "URLs:"
Write-Host "  Landing:   http://localhost:3000"
Write-Host "  Scanner:   http://localhost:3000/app/scanner"
Write-Host "  API docs:  http://localhost:8000/docs"
Write-Host "  Health:    http://localhost:8000/api/health"
