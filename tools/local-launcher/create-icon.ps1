$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

# Vector-drawn icon: a Weibull density curve and a play button, legible at desktop sizes.
$iconDirectory = Split-Path -Parent $PSCommandPath
$canvas = New-Object System.Drawing.Bitmap 256, 256
$graphics = [System.Drawing.Graphics]::FromImage($canvas)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::Transparent)
$tile = New-Object System.Drawing.Drawing2D.GraphicsPath
$tile.AddArc(8, 8, 64, 64, 180, 90)
$tile.AddArc(184, 8, 64, 64, 270, 90)
$tile.AddArc(184, 184, 64, 64, 0, 90)
$tile.AddArc(8, 184, 64, 64, 90, 90)
$tile.CloseFigure()
$blue = New-Object System.Drawing.Drawing2D.LinearGradientBrush ([System.Drawing.Point]::new(24, 16)), ([System.Drawing.Point]::new(224, 240)), ([System.Drawing.Color]::FromArgb(36, 113, 238)), ([System.Drawing.Color]::FromArgb(16, 41, 108))
$graphics.FillPath($blue, $tile)
$axis = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(135, 203, 231, 255)), 5
$axis.StartCap = $axis.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
$graphics.DrawLines($axis, [System.Drawing.PointF[]]@([System.Drawing.PointF]::new(45, 52), [System.Drawing.PointF]::new(45, 199), [System.Drawing.PointF]::new(213, 199)))
$curve = New-Object System.Drawing.Drawing2D.GraphicsPath
$curve.AddBezier(47, 182, 56, 170, 64, 63, 98, 62)
$curve.AddBezier(98, 62, 130, 60, 131, 175, 208, 179)
$line = New-Object System.Drawing.Pen ([System.Drawing.Color]::White), 12
$line.StartCap = $line.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
$graphics.DrawPath($line, $curve)
$cyan = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(110, 243, 231))
$graphics.FillEllipse($cyan, 87, 51, 22, 22)
$badge = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(10, 31, 79))
$graphics.FillEllipse($badge, 164, 164, 79, 79)
$graphics.FillPolygon($cyan, [System.Drawing.PointF[]]@([System.Drawing.PointF]::new(190, 183), [System.Drawing.PointF]::new(190, 224), [System.Drawing.PointF]::new(221, 203.5)))
$canvas.Save((Join-Path $iconDirectory 'weibull-debug.png'), [System.Drawing.Imaging.ImageFormat]::Png)

# Windows ICO directory with PNG payloads for every common shell icon size.
$sizes = @(16, 24, 32, 48, 64, 128, 256)
$frames = @()
foreach ($size in $sizes) {
    $bitmap = New-Object System.Drawing.Bitmap $size, $size
    $draw = [System.Drawing.Graphics]::FromImage($bitmap)
    $draw.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $draw.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $draw.DrawImage($canvas, 0, 0, $size, $size)
    $buffer = New-Object System.IO.MemoryStream
    $bitmap.Save($buffer, [System.Drawing.Imaging.ImageFormat]::Png)
    $frames += ,$buffer.ToArray()
    $buffer.Dispose(); $draw.Dispose(); $bitmap.Dispose()
}
$stream = [System.IO.File]::Create((Join-Path $iconDirectory 'weibull-debug.ico'))
$writer = New-Object System.IO.BinaryWriter $stream
$writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$sizes.Count)
$offset = 6 + 16 * $sizes.Count
for ($i = 0; $i -lt $sizes.Count; $i++) {
    $dimension = if ($sizes[$i] -eq 256) { 0 } else { $sizes[$i] }
    $writer.Write([byte]$dimension); $writer.Write([byte]$dimension)
    $writer.Write([byte]0); $writer.Write([byte]0)
    $writer.Write([uint16]1); $writer.Write([uint16]32)
    $writer.Write([uint32]$frames[$i].Length); $writer.Write([uint32]$offset)
    $offset += $frames[$i].Length
}
foreach ($frame in $frames) { $writer.Write([byte[]]$frame) }
$writer.Dispose()
$graphics.Dispose(); $canvas.Dispose(); $tile.Dispose(); $blue.Dispose()
$axis.Dispose(); $curve.Dispose(); $line.Dispose(); $cyan.Dispose(); $badge.Dispose()
Write-Host 'Generated weibull-debug.ico and preview PNG.'
