<#
.SYNOPSIS
  Deploy the current main of the backend to Fly.io on demand, entirely through
  GitHub Actions (no local flyctl auth needed).

.DESCRIPTION
  Triggers the workflow_dispatch on .github/workflows/deploy-backend.yml, which
  runs the test gate then `flyctl deploy --remote-only` using the FLY_API_TOKEN
  repo secret. Requires the one-time `scripts/enable-ci-deploy.ps1` to have set
  that secret. Streams the run and exits non-zero if the deploy fails.

  This is the "deploy myself" path: it needs only `gh` (already authenticated
  for the repo), so it works even when local flyctl is logged out / expired.
#>
[CmdletBinding()]
param(
    [string]$Repo     = "cham-p24/tapeline",
    [string]$Workflow = "deploy-backend.yml",
    [string]$Ref      = "main"
)
$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "'gh' is not on PATH." }

# Guard: warn early if the deploy secret was never set (otherwise the run goes
# green but silently skips the deploy).
$hasSecret = (gh secret list --repo $Repo 2>$null | Select-String -SimpleMatch "FLY_API_TOKEN")
if (-not $hasSecret) {
    throw "FLY_API_TOKEN secret is not set on $Repo. Run scripts/enable-ci-deploy.ps1 once first."
}

Write-Host "==> Dispatching $Workflow on $Ref ..." -ForegroundColor Cyan
gh workflow run $Workflow --repo $Repo --ref $Ref

# The run takes a moment to register; poll for the newest dispatch run id.
$runId = $null
foreach ($i in 1..20) {
    Start-Sleep -Seconds 3
    $runId = (gh run list --repo $Repo --workflow $Workflow --event workflow_dispatch `
                --limit 1 --json databaseId --jq ".[0].databaseId" 2>$null)
    if ($runId) { break }
}
if (-not $runId) { throw "Could not find the dispatched run; check the Actions tab." }

Write-Host "==> Watching run $runId ..." -ForegroundColor Cyan
gh run watch $runId --repo $Repo --exit-status
$ok = ($LASTEXITCODE -eq 0)

Write-Host ""
if ($ok) {
    Write-Host "Deploy succeeded." -ForegroundColor Green
    Write-Host "Verify:  curl https://api.tapeline.io/api/version" -ForegroundColor Green
} else {
    Write-Host "Deploy FAILED — see: gh run view $runId --repo $Repo --log-failed" -ForegroundColor Red
    exit 1
}
