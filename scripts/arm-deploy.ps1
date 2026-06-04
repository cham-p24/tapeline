#!/usr/bin/env pwsh
#requires -Version 7
<#
.SYNOPSIS
  One-time operator setup — arm hands-off backend auto-deploy.

.DESCRIPTION
  Mints a Fly.io *deploy* token (scoped to deploying tapeline-backend and
  nothing else) and stores it as the FLY_API_TOKEN GitHub Actions secret.

  That secret is the ONLY thing gating .github/workflows/deploy-backend.yml.
  The moment it exists, every merge to main:
    1. test-gates the backend (ruff + mypy + pytest), then
    2. auto-deploys to Fly (remote build + `alembic upgrade head`), then
    3. runs a post-deploy smoke check against prod.
  No manual `fly deploy` ever again, and a dirty local checkout can no longer
  reach prod — which is what caused the v128/v129 clobber of the public API.

  This lives in the repo (not run by the AI assistant) on purpose: minting and
  planting a production deploy credential is an operator action by design.

.PREREQUISITES
  - flyctl logged in :  fly auth login
  - gh logged in     :  gh auth login        (needs repo admin to set secrets)

.EXAMPLE
  pwsh scripts/arm-deploy.ps1
#>
[CmdletBinding()]
param(
  [string]$App  = "tapeline-backend",
  [string]$Repo = "cham-p24/tapeline"
)
$ErrorActionPreference = "Stop"

Write-Host "-> Minting a Fly deploy token for '$App'..." -ForegroundColor Cyan
$raw = (fly tokens create deploy -a $App 2>&1 | Out-String)
$token = ($raw -split "`r?`n" | Where-Object { $_ -match '^FlyV1\b' } | Select-Object -First 1)
if ($token) { $token = $token.Trim() }
if (-not $token) {
  Write-Error "Could not parse a FlyV1 deploy token from flyctl output. Are you logged in (fly auth login)?`nRaw output:`n$raw"
  exit 1
}

Write-Host "-> Storing it as the FLY_API_TOKEN secret on '$Repo'..." -ForegroundColor Cyan
gh secret set FLY_API_TOKEN --repo $Repo --body $token
if ($LASTEXITCODE -ne 0) {
  Write-Error "gh secret set failed. Need repo admin + a logged-in gh (gh auth login)."
  exit 1
}

Write-Host ""
Write-Host "OK - armed. The backend now auto-deploys + smoke-tests on every merge to main." -ForegroundColor Green
Write-Host "Ship the current backlog (clamp + ticker/news guards) right now with:" -ForegroundColor Green
Write-Host "  gh workflow run deploy-backend.yml --repo $Repo" -ForegroundColor Green
