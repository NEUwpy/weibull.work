$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$repo=[IO.Path]::GetFullPath((Join-Path $root '..\..\..'))
$build=Join-Path $repo 'tmp\f01d-radial-v20'
$app=New-Object -ComObject PowerPoint.Application
$base=$null;$part=$null
try {
 $base=$app.Presentations.Open((Join-Path $repo 'tmp\f01-base\mathtype-candidate.pptx'),0,0,0)
 $part=$app.Presentations.Open((Join-Path $build 'radial-mathtype.pptx'),-1,0,0)
 $slide=$base.Slides.Item(1)
 $sourceSlide=$part.Slides.Item(1)
 $names=[object[]]@($sourceSlide.Shapes | ForEach-Object {$_.Name})
 $sourceRange=$sourceSlide.Shapes.Range($names)
 $pasted=$null
 for($attempt=0;$attempt -lt 8;$attempt++){
  $sourceRange.Copy();Start-Sleep -Milliseconds 250
  try {$pasted=$slide.Shapes.Paste();break} catch {Start-Sleep -Milliseconds 250}
 }
 if(-not $pasted){throw 'Cannot paste radial panel'}
 # Mixed ShapeRange coordinates are sentinels, so position by each source shape.
 foreach($copy in $pasted){
  $original=$sourceSlide.Shapes.Item($copy.Name)
  $copy.Left=$original.Left+1240*.75
  $copy.Top=$original.Top+715*.75
 }
 $sourceSlide.Export((Join-Path $root '子图\F01d_圆周误差与三参数RMSE.png'),'PNG',2120,1040)
 # Remove the former overall heading, including when reusing a saved base.
 for($i=$slide.Shapes.Count;$i -ge 1;$i--){if($slide.Shapes.Item($i).Name -eq 'title.main'){$slide.Shapes.Item($i).Delete()}}
 $geometry=@{}
 foreach($sh in $slide.Shapes){
  $font=$null
  if($sh.HasTextFrame -eq -1 -and $sh.TextFrame.HasText -eq -1){$font=$sh.TextFrame.TextRange.Font.Size}
  $geometry[$sh.Name]=@{X=$sh.Left;Y=$sh.Top;W=$sh.Width;H=$sh.Height;Font=$font}
 }
 $base.PageSetup.SlideHeight=1220*.75
 foreach($sh in $slide.Shapes){
  $g=$geometry[$sh.Name];$sh.LockAspectRatio=0;$sh.Width=[double]$g.W;$sh.Height=[double]$g.H
  $sh.Left=[double]$g.X;$sh.Top=[double]$g.Y-70*.75
  if($null -ne $g.Font){$sh.TextFrame.TextRange.Font.Size=[double]$g.Font}
 }
 $base.SaveAs((Join-Path $build 'full-candidate.pptx'),24)
 $slide.Export((Join-Path $build 'full-preview.png'),'PNG',3510,1830)
 Write-Output "Pasted $($pasted.Count) panel elements"
} finally {
 if($part){$part.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($part)|Out-Null}
 if($base){$base.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($base)|Out-Null}
 $app.Quit();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)|Out-Null
}
