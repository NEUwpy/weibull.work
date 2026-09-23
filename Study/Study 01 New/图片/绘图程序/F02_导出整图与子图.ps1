param([string]$PptPath='')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
if(-not $PptPath){$PptPath=Join-Path $root 'F02_AMDM估计器流程-v8.pptx'}
$out=Join-Path $root '子图'
New-Item -ItemType Directory -Path $out -Force|Out-Null
$app=New-Object -ComObject PowerPoint.Application
try {
 $deck=$app.Presentations.Open($PptPath,-1,0,0)
 try {
  $slide=$deck.Slides.Item(1)
  $slide.Export((Join-Path $root 'F02_AMDM估计器流程-v8.png'),'PNG',4680,1600)
  $eqCount=0
  for($i=1;$i -le $slide.Shapes.Count;$i++){
   $sh=$slide.Shapes.Item($i)
   if($sh.Name.StartsWith('MathType.')){
    if($sh.OLEFormat.ProgID -ne 'Equation.DSMT4'){throw "Non-MathType equation: $($sh.Name)"}
    $eqCount++
   }
  }
  if($eqCount -ne 8){throw "Expected 8 MathType objects, got $eqCount"}
  Write-Output "Verified $eqCount MathType OLE equations"
 } finally {$deck.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck)|Out-Null}
 foreach($p in @(@{Name='F02a_MDM主流程';Prefix='main.';X=1110;Y=150;W=690;H=600},@{Name='F02b_样本驱动调节';Prefix='adapt.';X=440;Y=150;W=570;H=600})){
  $deck=$app.Presentations.Open($PptPath,-1,0,0)
  try {
   $slide=$deck.Slides.Item(1)
   $geometry=@{}
   for($i=$slide.Shapes.Count;$i -ge 1;$i--){
    $sh=$slide.Shapes.Item($i)
    $keep=$sh.Name.StartsWith($p.Prefix) -or $sh.Name.StartsWith('MathType.'+$p.Prefix)
    if(-not $keep){$sh.Delete();continue}
    $font=$null
    if($sh.HasTextFrame -eq -1 -and $sh.TextFrame.HasText -eq -1){$font=$sh.TextFrame.TextRange.Font.Size}
    $geometry[$sh.Name]=@{X=$sh.Left;Y=$sh.Top;W=$sh.Width;H=$sh.Height;Font=$font}
   }
   $deck.PageSetup.SlideWidth=$p.W*.75;$deck.PageSetup.SlideHeight=$p.H*.75
   foreach($sh in $slide.Shapes){
    $g=$geometry[$sh.Name]
    $sh.LockAspectRatio=0;$sh.Width=$g.W;$sh.Height=$g.H
    $sh.Left=$g.X-$p.X*.75;$sh.Top=$g.Y-$p.Y*.75
    if($null -ne $g.Font){$sh.TextFrame.TextRange.Font.Size=$g.Font}
   }
   $slide.Export((Join-Path $out ($p.Name+'.png')),'PNG',($p.W*3),($p.H*3))
  } finally {$deck.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck)|Out-Null}
 }
} finally {$app.Quit();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)|Out-Null}
