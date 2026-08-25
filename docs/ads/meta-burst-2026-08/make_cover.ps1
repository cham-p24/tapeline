Add-Type -AssemblyName System.Drawing

$out  = "C:\Users\Chamara\AppData\Local\Temp\claude\C--Project-1\54061250-568f-4a4d-b24c-9ea6df2f0c68\scratchpad\ads"
$path = Join-Path $out "tapeline-fb-cover.png"

$W = 1640; $H = 856
$bmp = New-Object System.Drawing.Bitmap $W, $H
$g   = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode     = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
$g.Clear([System.Drawing.ColorTranslator]::FromHtml("#0B1220"))

# centred block — Facebook crops the sides hard on mobile, so keep everything mid-frame
$cx = $W / 2

$sf = New-Object System.Drawing.StringFormat
$sf.Alignment = [System.Drawing.StringAlignment]::Center

$accent = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#2D7DF6"))
$g.FillRectangle($accent, ($cx - 46), 300, 92, 14)

$wordFont = New-Object System.Drawing.Font("Segoe UI", 64, [System.Drawing.FontStyle]::Bold)
$bWord    = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
$g.DrawString("Tapeline", $wordFont, $bWord, $cx, 350, $sf)

$subFont = New-Object System.Drawing.Font("Segoe UI", 26, [System.Drawing.FontStyle]::Regular)
$bSub    = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#9BA9BE"))
$g.DrawString("One 0-100 score and one plain sentence per ticker.", $subFont, $bSub, $cx, 470, $sf)

$linkFont = New-Object System.Drawing.Font("Segoe UI Semibold", 22, [System.Drawing.FontStyle]::Bold)
$bLink    = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#2D7DF6"))
$g.DrawString("tapeline.io", $linkFont, $bLink, $cx, 530, $sf)

$fFont = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Regular)
$bF    = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#6B7B92"))
$g.DrawString("Informational only. Descriptive scores, not recommendations.", $fFont, $bF, $cx, 640, $sf)

$g.Dispose()
$bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output ("{0}  {1} bytes" -f (Split-Path $path -Leaf), (Get-Item $path).Length)
