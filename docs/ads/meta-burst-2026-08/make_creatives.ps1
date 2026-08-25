Add-Type -AssemblyName System.Drawing

$out = "C:\Users\Chamara\AppData\Local\Temp\claude\C--Project-1\54061250-568f-4a4d-b24c-9ea6df2f0c68\scratchpad\ads"
New-Item -ItemType Directory -Force $out | Out-Null

$concepts = @(
  @{ file = "concept-a-screener.png"
     l1   = "Retire the Sunday-night"
     l2   = "spreadsheet."
     sub  = "One 0-100 score and one plain sentence per ticker." },
  @{ file = "concept-b-trial.png"
     l1   = "`$0 today. The charge"
     l2   = "date is on the page."
     sub  = "14-day Premium trial. Card required. Cancel in one click." },
  @{ file = "concept-c-record.png"
     l1   = "We publish the record,"
     l2   = "misses included."
     sub  = "Every top-10 pick, logged daily, measured against SPY." }
)

foreach ($c in $concepts) {
  $bmp = New-Object System.Drawing.Bitmap 1200, 628
  $g   = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode     = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit

  $g.Clear([System.Drawing.ColorTranslator]::FromHtml("#0B1220"))

  # accent bar
  $accent = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#2D7DF6"))
  $g.FillRectangle($accent, 80, 74, 54, 12)

  $wordmark = New-Object System.Drawing.Font("Segoe UI Semibold", 21, [System.Drawing.FontStyle]::Bold)
  $bWord    = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#E8EDF5"))
  $g.DrawString("Tapeline", $wordmark, $bWord, 150, 62)

  $hFont = New-Object System.Drawing.Font("Segoe UI", 50, [System.Drawing.FontStyle]::Bold)
  $bH    = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
  $g.DrawString($c.l1, $hFont, $bH, 74, 210)
  $g.DrawString($c.l2, $hFont, $bH, 74, 288)

  $sFont = New-Object System.Drawing.Font("Segoe UI", 22, [System.Drawing.FontStyle]::Regular)
  $bS    = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#9BA9BE"))
  $g.DrawString($c.sub, $sFont, $bS, 78, 390)

  # divider
  $pen = New-Object System.Drawing.Pen ([System.Drawing.ColorTranslator]::FromHtml("#1C2839")), 2
  $g.DrawLine($pen, 80, 500, 1120, 500)

  $fFont = New-Object System.Drawing.Font("Segoe UI", 15, [System.Drawing.FontStyle]::Regular)
  $bF    = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#6B7B92"))
  $g.DrawString("Informational only. Descriptive scores, not recommendations.", $fFont, $bF, 78, 530)

  $uFont = New-Object System.Drawing.Font("Segoe UI Semibold", 15, [System.Drawing.FontStyle]::Bold)
  $bU    = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#2D7DF6"))
  $sz    = $g.MeasureString("tapeline.io", $uFont)
  $g.DrawString("tapeline.io", $uFont, $bU, (1122 - $sz.Width), 530)

  $g.Dispose()
  $path = Join-Path $out $c.file
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  $fi = Get-Item $path
  Write-Output ("{0}  {1} bytes" -f $fi.Name, $fi.Length)
}
