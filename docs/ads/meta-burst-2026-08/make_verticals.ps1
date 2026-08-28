Add-Type -AssemblyName System.Drawing

# Write next to this script, so a clean checkout reproduces the committed
# assets. This previously hardcoded a machine-specific scratchpad path, which
# meant regeneration silently wrote somewhere else and the committed PNGs went
# stale while the source looked correct.
$out = $PSScriptRoot
$concepts = @(
  @{ file = "concept-a-screener-9x16.png"
     head = @("Retire the", "Sunday-night", "spreadsheet.")
     sub  = @("One 0-100 score", "and one plain", "sentence per ticker.") },
  @{ file = "concept-b-trial-9x16.png"
     head = @("`$0 today.", "The charge", "date is on", "the page.")
     sub  = @("14-day Premium trial.", "Card required.", "Cancel in one click.") },
  @{ file = "concept-c-record-9x16.png"
     head = @("We publish", "the record,", "misses", "included.")
     sub  = @("Top 10 scores,", "logged daily,", "measured against SPY.") }
)

foreach ($c in $concepts) {
  $bmp = New-Object System.Drawing.Bitmap 1080, 1920
  $g   = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode     = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
  $g.Clear([System.Drawing.ColorTranslator]::FromHtml("#0B1220"))

  # keep everything inside the Stories safe zone (top 250px / bottom 340px reserved)
  $accent = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#2D7DF6"))
  $g.FillRectangle($accent, 88, 330, 54, 12)

  $wordmark = New-Object System.Drawing.Font("Segoe UI Semibold", 23, [System.Drawing.FontStyle]::Bold)
  $bWord    = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#E8EDF5"))
  $g.DrawString("Tapeline", $wordmark, $bWord, 160, 316)

  $hFont = New-Object System.Drawing.Font("Segoe UI", 52, [System.Drawing.FontStyle]::Bold)
  $bH    = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
  $y = 640
  foreach ($line in $c.head) { $g.DrawString($line, $hFont, $bH, 82, $y); $y += 86 }

  $sFont = New-Object System.Drawing.Font("Segoe UI", 24, [System.Drawing.FontStyle]::Regular)
  $bS    = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#9BA9BE"))
  $y += 40
  foreach ($line in $c.sub) { $g.DrawString($line, $sFont, $bS, 86, $y); $y += 44 }

  $pen = New-Object System.Drawing.Pen ([System.Drawing.ColorTranslator]::FromHtml("#1C2839")), 2
  $g.DrawLine($pen, 88, 1320, 992, 1320)

  $fFont = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Regular)
  $bF    = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#8FA0B6"))
  $g.DrawString("Informational only.", $fFont, $bF, 86, 1360)
  $g.DrawString("Descriptive scores, not recommendations.", $fFont, $bF, 86, 1392)

  $uFont = New-Object System.Drawing.Font("Segoe UI Semibold", 18, [System.Drawing.FontStyle]::Bold)
  $bU    = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#2D7DF6"))
  $g.DrawString("tapeline.io", $uFont, $bU, 86, 1444)

  $g.Dispose()
  $path = Join-Path $out $c.file
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  Write-Output ("{0}  {1} bytes" -f $c.file, (Get-Item $path).Length)
}
