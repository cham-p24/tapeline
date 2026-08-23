<#
.SYNOPSIS
  Turn on the Meta Conversions API: set the secrets, then prove events arrive.

.DESCRIPTION
  The browser pixel (id 28351455154543230) is already live and verified. This
  script switches on the SERVER-SIDE half — the one that matters most here,
  because the money event lands via a Stripe webhook 14 days after the click
  with no browser involved, and because this audience blocks trackers heavily.
  (Measured: fbevents.js came back with transferSize 0 in the founder's own
  Chrome, and 107,766 bytes in a clean browser. Same page, same deploy.)

  The token never leaves this machine. It is read with -AsSecureString so it
  is not echoed to the terminal, never written to a file, and never printed —
  including in the verification step, which sends it as a query parameter to
  Meta directly.

.PARAMETER TestEventCode
  Optional. From Events Manager -> Test Events. When supplied, the
  verification event is flagged as a test so it appears in the Test Events tab
  and is EXCLUDED from ad optimisation. Recommended for the first run.
  Do NOT set META_CAPI_TEST_EVENT_CODE as a Fly secret — that would quietly
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
Write-Host "Meta Conversions API — go live" -ForegroundColor Cyan
Write-Host "  pixel   $PixelId"
Write-Host "  fly app $App"
Write-Host ""

# ── preflight ────────────────────────────────────────────────────────────────
if (-not (Get-Command flyctl -ErrorAction SilentlyContinue) -and
    -not (Get-Command fly    -ErrorAction SilentlyContinue)) {
  throw "flyctl not found on PATH. Install it, then run 'fly auth login'."
}
$fly = (Get-Command flyctl -ErrorAction SilentlyContinue) ?? (Get-Command fly)

try { & $fly auth whoami 2>&1 | Out-Null }
catch { throw "flyctl is not logged in. Run 'fly auth login' first." }

# ── token ────────────────────────────────────────────────────────────────────
Write-Host "Events Manager -> Datasets -> Tapeline -> Settings -> Conversions API"
Write-Host "-> Generate access token. Paste it below (input is hidden)." -ForegroundColor Yellow
Write-Host ""

$secure = Read-Host "CAPI access token" -AsSecureString
$token  = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))

if ([string]::IsNullOrWhiteSpace($token)) { throw "No token entered — nothing changed." }
# Meta CAPI tokens are long. A short paste is almost always a truncated copy.
if ($token.Length -lt 50) {
  throw "That token is only $($token.Length) characters, which is too short to be a Meta CAPI token. Re-copy it — the field truncates easily."
}

# ── set the secrets ──────────────────────────────────────────────────────────
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

# ── verify ───────────────────────────────────────────────────────────────────
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
  # Deliberately does NOT echo $uri — it carries the token.
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
Write-Host "Still required before any spend — neither is a code step:" -ForegroundColor Yellow
Write-Host "  1. Declare the Financial Products & Services Special Ad Category"
Write-Host "  2. Exclude Australia from geo targeting (see docs/META_GO_LIVE.md section 4)"
Write-Host ""
