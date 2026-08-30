<#
.SYNOPSIS
  Turn on the Meta Conversions API: set the secrets, then prove events arrive.

.DESCRIPTION
  The browser pixel (id 28351455154543230) is already live and verified. This
  script switches on the SERVER-SIDE half - the one that matters most here,
  because the money event lands via a Stripe webhook 14 days after the click
  with no browser involved, and because this audience blocks trackers heavily.
  (Measured: fbevents.js came back with transferSize 0 in the founder's own
  Chrome, and 107,766 bytes in a clean browser. Same page, same deploy.)

  The token never leaves this machine. It is read with -AsSecureString so it
  is not echoed to the terminal, never written to a file, and never printed -
  including in the verification step, which sends it as a query parameter to
  Meta directly.

.PARAMETER TestEventCode
  Optional. From Events Manager -> Test Events. When supplied, the
  verification event is flagged as a test so it appears in the Test Events tab
  and is EXCLUDED from ad optimisation. Recommended for the first run.
  Do NOT set META_CAPI_TEST_EVENT_CODE as a Fly secret - that would quietly
  stop every real event counting. This is a one-off check only.

.PARAMETER SkipVerify
  Set the secrets but do not send the verification event.

.EXAMPLE
  .\scripts\meta-capi-golive.ps1 -TestEventCode TEST12345

.NOTES
  Prerequisites: flyctl on PATH and logged in (`fly auth whoami`).
  After this succeeds the backend fires CompleteRegistration on signup,
  StartTrial when the card-required trial begins, and Purchase on first
  charge. See docs/META_GO_LIVE.md.
#>
[CmdletBinding()]
param(
  [string]$TestEventCode,
  [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"

$PixelId = "28351455154543230"
$App     = "tapeline-backend"
$GraphV  = "v21.0"

Write-Host ""
Write-Host "Meta Conversions API - go live" -ForegroundColor Cyan
Write-Host "  pixel   $PixelId"
Write-Host "  fly app $App"
Write-Host ""

# -- preflight ----------------------------------------------------------------
# Resolve flyctl. It is NOT enough to check PATH: the official Windows installer
# drops it in ~\.fly\bin and does not always add that to PATH, which is exactly
# how this failed the first time it was run for real ("fly : The term 'fly' is
# not recognized"). Check PATH first, then the known install location.
#
# Written as an if/elseif chain on purpose. This previously used `??`, which is
# PowerShell 7+ only and is a parse error under Windows PowerShell 5.1 - the
# shell this script is actually launched in.
$fly = $null
foreach ($name in @("flyctl", "fly")) {
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if ($cmd) { $fly = $cmd.Source; break }
}
if (-not $fly) {
  $fallback = Join-Path $env:USERPROFILE ".fly\bin\flyctl.exe"
  if (Test-Path $fallback) { $fly = $fallback }
}
if (-not $fly) {
  throw "flyctl not found on PATH or in $env:USERPROFILE\.fly\bin. Install it, then run 'fly auth login'."
}
Write-Host "  flyctl  $fly"

# `auth whoami` writes its failure to stderr and returns non-zero rather than
# throwing, so a bare try/catch misses it and the script would sail on to ask for
# a token it cannot use. Check the exit code.
# $ErrorActionPreference = "Stop" (set at the top) turns a native command's
# STDERR into a terminating NativeCommandError, so flyctl's own "no access token"
# text would print as a stack-trace-looking block ahead of the useful message.
# Drop to Continue just for this call, and swallow both streams.
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $fly auth whoami *> $null
$loggedIn = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prevEAP

if (-not $loggedIn) {
  # Quote the RESOLVED path, not "fly auth login". The whole reason this script
  # had to go looking for the binary is that flyctl is often not on PATH -- so
  # telling the operator to run `fly auth login` reproduces the exact error they
  # just hit. This happened for real on 2026-08-30.
  throw "flyctl is not logged in. Run this first, then re-run this script:`n`n    & `"$fly`" auth login`n"
}

# -- token --------------------------------------------------------------------
Write-Host "Events Manager -> Datasets -> Tapeline -> Settings -> Conversions API"
Write-Host "-> Generate access token. Paste it below (input is hidden)." -ForegroundColor Yellow
Write-Host ""

$secure = Read-Host "CAPI access token" -AsSecureString
$token  = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))

if ([string]::IsNullOrWhiteSpace($token)) { throw "No token entered - nothing changed." }
# Meta CAPI tokens are long. A short paste is almost always a truncated copy.
if ($token.Length -lt 50) {
  throw "That token is only $($token.Length) characters, which is too short to be a Meta CAPI token. Re-copy it - the field truncates easily."
}

# -- set the secrets ----------------------------------------------------------
Write-Host ""
Write-Host "Setting Fly secrets (this restarts the backend)..." -ForegroundColor Cyan

# Passed as arguments to flyctl only. Never written to disk, never logged.
& $fly secrets set "META_PIXEL_ID=$PixelId" "META_CAPI_ACCESS_TOKEN=$token" --app $App
if ($LASTEXITCODE -ne 0) { throw "fly secrets set failed with exit code $LASTEXITCODE." }

Write-Host "Secrets set." -ForegroundColor Green

if ($SkipVerify) {
  Write-Host "Skipping verification (-SkipVerify)." -ForegroundColor Yellow
  return
}

# -- verify -------------------------------------------------------------------
# Sends one CompleteRegistration straight to Meta with a synthetic hashed
# identifier, exactly the shape services/meta_capi builds. This proves the
# TOKEN and PIXEL are a valid pair before real traffic depends on them.
Write-Host ""
Write-Host "Sending a verification event to Meta..." -ForegroundColor Cyan

$sha = [System.Security.Cryptography.SHA256]::Create()
function Hash-Pii([string]$v) {
  ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($v.Trim().ToLower()))  |
    ForEach-Object { $_.ToString("x2") }) -join ""
}

$evt = @{
  event_name    = "CompleteRegistration"
  event_time    = [int][double]::Parse((Get-Date -UFormat %s))
  event_id      = "golive-check-$([guid]::NewGuid().ToString('N').Substring(0,16))"
  action_source = "website"
  user_data     = @{
    em          = @(Hash-Pii "golive-check@tapeline.io")
    external_id = @(Hash-Pii "golive-check")
  }
  custom_data   = @{ content_name = "golive-check" }
}

$payload = @{ data = @($evt) }
if ($TestEventCode) { $payload.test_event_code = $TestEventCode }

$uri = "https://graph.facebook.com/$GraphV/$PixelId/events?access_token=$([uri]::EscapeDataString($token))"

try {
  $resp = Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json" `
                            -Body ($payload | ConvertTo-Json -Depth 6)
  Write-Host ""
  Write-Host "Meta accepted the event. events_received = $($resp.events_received)" -ForegroundColor Green
}
catch {
  # Deliberately does NOT echo $uri - it carries the token.
  $detail = $_.ErrorDetails.Message
  Write-Host ""
  Write-Host "Meta REJECTED the verification event." -ForegroundColor Red
  if ($detail) { Write-Host $detail -ForegroundColor Red }
  Write-Host ""
  Write-Host "The Fly secrets were still set. Most likely causes:" -ForegroundColor Yellow
  Write-Host "  - the token was generated for a different pixel"
  Write-Host "  - the token was truncated on copy"
  Write-Host "  - the token was revoked"
  Write-Host "Re-generate it in Events Manager and run this again."
  throw
}

Write-Host ""
if ($TestEventCode) {
  Write-Host "Open Events Manager -> Test Events to see it. It will NOT count toward optimisation." -ForegroundColor Cyan
} else {
  Write-Host "Open Events Manager -> Overview. 'CompleteRegistration / Server' should appear within a few minutes." -ForegroundColor Cyan
}
Write-Host ""
Write-Host "Live from now on: CompleteRegistration on signup, StartTrial when the" -ForegroundColor Green
Write-Host "card-required trial begins, Purchase on first charge." -ForegroundColor Green
Write-Host ""
# Both items that used to print here were done on 2026-08-26, and one of them was
# never possible in the first place. Leaving them up told the operator to go and
# repeat work already live, which is worse than saying nothing.
#
#   "Declare the Financial Products & Services Special Ad Category" - declared on
#   the live ad set (US - FPS - 3 concept message test).
#
#   "Exclude Australia from geo targeting" - Special Ad Categories do NOT permit
#   location EXCLUSIONS at all. The only mechanism protecting the Australia
#   constraint is US-only INCLUSION, which is set. See META_BURST_BUILD.md 16.
Write-Host "Ad-account prerequisites are already in place:" -ForegroundColor Green
Write-Host "  - Financial Products & Services Special Ad Category: declared"
Write-Host "  - Geo: United States only (SAC forbids location exclusions, so"
Write-Host "        US-only inclusion is what protects the Australia constraint)"
Write-Host ""
Write-Host "Next: confirm real events land once someone signs up. The browser and"
Write-Host "server copies of CompleteRegistration share a deterministic event_id,"
Write-Host "so Meta collapses them into ONE conversion rather than double-counting."
Write-Host ""
