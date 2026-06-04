<#
.SYNOPSIS
  One-time: wire a Fly.io deploy token into GitHub Actions so backend deploys
  become fully hands-off. Run this ONCE; never needed again.

.DESCRIPTION
  After this runs, .github/workflows/deploy-backend.yml deploys automatically on
  every push to main that touches backend/ — and can be triggered on demand from
  anywhere with scripts/deploy-backend.ps1 (no local flyctl auth required ever
  again, because the deploy runs inside GitHub Actions using the secret).

  Why a human has to run this once: minting a Fly token requires an interactive
  `fly auth login` (browser), which an assistant cannot and must not perform.
  The token is piped straight from Fly into the GitHub secret — it is never
  printed, written to disk, or stored in a variable that lingers.

.NOTES
  Prereqs: flyctl + gh installed and on PATH. ~60 seconds.
#>
[CmdletBinding()]
param(
    [string]$App  = "tapeline-backend",
    [string]$Repo = "cham-p24/tapeline",
    # Long expiry so the CI secret doesn't silently expire (the failure mode that
    # prompted this script). Rotate by re-running.
    [string]$Expiry = "8760h"   # 1 year
)
$ErrorActionPreference = "Stop"

function Require-Cmd($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "'$name' is not on PATH. Install it first, then re-run."
    }
}
Require-Cmd flyctl
Require-Cmd gh

Write-Host "==> Checking Fly auth..." -ForegroundColor Cyan
try { flyctl auth whoami | Out-Null } catch {
    Write-Host "    Not logged in. Opening browser for 'fly auth login'..." -ForegroundColor Yellow
    flyctl auth login
}
$who = (flyctl auth whoami 2>$null)
Write-Host "    Fly: $who"

Write-Host "==> Checking GitHub auth..." -ForegroundColor Cyan
gh auth status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { throw "gh is not authenticated. Run 'gh auth login' then re-run." }

Write-Host "==> Minting a Fly deploy token and storing it as GitHub secret FLY_API_TOKEN..." -ForegroundColor Cyan
Write-Host "    (the token is piped Fly -> GitHub; it is never displayed)"
# Capture, trim to the single FlyV1 line, pipe straight into the secret via stdin
# (never on the command line, so it can't leak into the process table).
$token = (flyctl tokens create deploy -a $App --expiry $Expiry | Out-String).Trim()
if ([string]::IsNullOrWhiteSpace($token)) { throw "Failed to create a Fly deploy token." }
$token | gh secret set FLY_API_TOKEN --repo $Repo
Remove-Variable token -ErrorAction SilentlyContinue
[System.GC]::Collect()

Write-Host "==> Verifying..." -ForegroundColor Cyan
$set = (gh secret list --repo $Repo | Select-String -SimpleMatch "FLY_API_TOKEN")
if (-not $set) { throw "Secret was not set; check 'gh secret list --repo $Repo'." }

Write-Host ""
Write-Host "Done. FLY_API_TOKEN is set on $Repo." -ForegroundColor Green
Write-Host "Backend pushes to main now deploy automatically." -ForegroundColor Green
Write-Host "Deploy current main on demand any time with:  pwsh scripts/deploy-backend.ps1" -ForegroundColor Green
