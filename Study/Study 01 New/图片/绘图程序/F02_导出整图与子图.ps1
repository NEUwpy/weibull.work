param([string]$PptPath='')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
if(-not $PptPath){$PptPath=Join-Path $root 'F02_AMDM训练与估计流程-v2.pptx'}
$out=Join-Path $root '子图'
New-Item -ItemType Directory -Path $out -Force|Out-Null
$app=New-Object -ComObject PowerPoint.Application
try {
 $deck=$app.Presentations.Open($PptPath,-1,0,0)
 try {
  $slide=$deck.Slides.Item(1)
  $slide.Export((Join-Path $root 'F02_AMDM训练与估计流程-v2.png'),'PNG',4680,2900)
  $eqCount=0
  for($i=1;$i -le $slide.Shapes.Count;$i++){
   $sh=$slide.Shapes.Item($i)
   if($sh.Name.StartsWith('MathType.')){
    if($sh.OLEFormat.ProgID -ne 'Equation.DSMT4'){throw "Non-MathType equation: $($sh.Name)"}
    $eqCount++
   }
  }
  if($eqCount -ne 20){throw "Expected 20 MathType objects, got $eqCount"}
  Write-Output "Verified $eqCount MathType OLE equations"
 } finally {$deck.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck)|Out-Null}
 foreach($p in @(@{Name='F02a_离线学习';Prefix='a.';Y=0;H=640},@{Name='F02b_实际估计';Prefix='b.';Y=650;H=750})){
  $deck=$app.Presentations.Open($PptPath,-1,0,0)
  try {
   $slide=$deck.Slides.Item(1)
   $names=[object[]]@($slide.Shapes | Where-Object {$_.Name.StartsWith($p.Prefix) -or $_.Name.StartsWith('MathType.'+$p.Prefix)} | ForEach-Object {$_.Name})
   # Resizing a populated slide rescales its contents. Copy into an empty canvas instead.
   $panel=$app.Presentations.Add(0)
   try {
    $panel.PageSetup.SlideWidth=2300*.75;$panel.PageSetup.SlideHeight=$p.H*.75
    $panelSlide=$panel.Slides.Add(1,12)
    $range=$slide.Shapes.Range($names);$pasted=$null
    for($attempt=0;$attempt -lt 8;$attempt++){
     $range.Copy();Start-Sleep -Milliseconds 250
     try {$pasted=$panelSlide.Shapes.Paste();break} catch {Start-Sleep -Milliseconds 250}
    }
    if(-not $pasted){throw 'Cannot paste F02 panel'}
    foreach($copy in $pasted){$original=$slide.Shapes.Item($copy.Name);$copy.Left=$original.Left-20*.75;$copy.Top=$original.Top-$p.Y*.75}
    $panelSlide.Export((Join-Path $out ($p.Name+'.png')),'PNG',4600,($p.H*2))
   } finally {$panel.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($panel)|Out-Null}
  } finally {$deck.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck)|Out-Null}
 }
} finally {$app.Quit();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)|Out-Null}
