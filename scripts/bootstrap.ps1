# Tapeline — first-time dev bootstrap
# Run from C:\Project 1\ in PowerShell

Write-Host "=== Tapeline dev bootstrap ===" -ForegroundColor Cyan

# 1. Backend venv
if (-not (Test-Path "backend\.venv")) {
    Write-Host "[1/4] Creating Python venv..."
    python -m venv backend\.venv
}
Write-Host "[2/4] Installing backend deps..."
& "backend\.venv\Scripts\pip.exe" install --upgrade pip
& "backend\.venv\Scripts\pip.exe" install -e "backend[dev]"

# 2. Copy env template if not present
if (-not (Test-Path ".env")) {
    Write-Host "[3/4] Copying .env.example -> .env (fill in real values!)"
    Copy-Item ".env.example" ".env"
} else {
    Write-Host "[3/4] .env already exists, skipping"
}

# 3. Frontend init reminder
Write-Host "[4/4] Frontend: run the init command in frontend\README.md" -ForegroundColor Yellow
Write-Host ""
Write-Host "Done. Next steps:" -ForegroundColor Green
Write-Host "  1. Edit .env with Polygon, Clerk, Stripe, Resend keys"
Write-Host "  2. cd infra; docker compose up -d  (local Postgres + Redis)"
Write-Host "  3. cd frontend; npx create-next-app@latest . ..."
Write-Host "  4. Read docs\LEGAL_CHECKLIST.md BEFORE first paying customer"
