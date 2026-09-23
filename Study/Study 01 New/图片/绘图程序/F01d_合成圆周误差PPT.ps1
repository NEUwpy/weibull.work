$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$repo=[IO.Path]::GetFullPath((Join-Path $root '..\..\..'))
$build=Join-Path $repo 'tmp\f01d-radial-v20'
$app=New-Object -ComObject PowerPoint.Application
$base=$null;$part=$null
try {
 $base=$app.Presentations.Open((Join-Path $root 'F01_MDM流程与重复抽样-v18.pptx'),0,0,0)
 $part=$app.Presentations.Open((Join-Path $build 'radial-mathtype.pptx'),-1,0,0)
 $slide=$base.Slides.Item(1)
 for($i=$slide.Shapes.Count;$i -ge 1;$i--){
  $shape=$slide.Shapes.Item($i)
  if($shape.Name.StartsWith('comparison.') -or $shape.Name -in @('MathType.comparison0','MathType.comparison01','MathType.gammaTruth')){$shape.Delete()}
 }
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
 $sourceSlide.Export((Join-Path $root 'F01d_圆周误差与三参数RMSE-v20.png'),'PNG',2120,1040)
 $base.SaveAs((Join-Path $build 'full-candidate.pptx'),24)
 $slide.Export((Join-Path $build 'full-preview.png'),'PNG',3510,1935)
 Write-Output "Pasted $($pasted.Count) panel elements"
} finally {
 if($part){$part.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($part)|Out-Null}
 if($base){$base.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($base)|Out-Null}
 $app.Quit();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)|Out-Null
}
