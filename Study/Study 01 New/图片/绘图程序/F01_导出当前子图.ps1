# Export the current composite and its A-D panels from PowerPoint.
param([string]$PptPath='')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
if(-not $PptPath){$PptPath=Join-Path $root 'F01_MDM流程与圆周误差-v21.pptx'}
$out=Join-Path $root '子图'
New-Item -ItemType Directory -Path $out -Force|Out-Null
$panels=@(
 @{Name='F01a_位置求解';X=630;Y=26;W=500;H=500;Prefix='gamma.';Equations=@('gradient','root','gamma-est')},
 @{Name='F01b_形状回代';X=1240;Y=26;W=520;H=500;Prefix='beta.';Equations=@('beta-min','beta-est')},
 @{Name='F01c_重复抽样梯度';X=630;Y=645;W=500;H=520;Prefix='ensemble.';Equations=@('delta0','delta01')},
 @{Name='F01d_圆周误差与三参数RMSE';X=1240;Y=645;W=1060;H=520;Prefix='radial.';Equations=@('radial.delta0','radial.delta1','radial.error-formula','rmse.legend0','rmse.legend1','rmse.parameter0','rmse.parameter1','rmse.parameter2')}
)
$app=New-Object -ComObject PowerPoint.Application
try {
 $full=$app.Presentations.Open($PptPath,-1,0,0)
 try {$full.Slides.Item(1).Export((Join-Path $root 'F01_MDM流程与圆周误差-v21.png'),'PNG',4680,2440)} finally {$full.Close()}
 foreach($p in $panels){
  $deck=$app.Presentations.Open($PptPath,-1,0,0)
  try {
   $slide=$deck.Slides.Item(1)
   $names=[object[]]@($slide.Shapes | Where-Object {
    $name=$_.Name
    $name.StartsWith($p.Prefix) -or (($p.Name -like 'F01d_*') -and $name.StartsWith('rmse.')) -or ($name.StartsWith('MathType.') -and $name.Substring(9) -in $p.Equations)
   } | ForEach-Object {$_.Name})
   $panel=$app.Presentations.Add(0)
   try {
    $panel.PageSetup.SlideWidth=$p.W*.75;$panel.PageSetup.SlideHeight=$p.H*.75
    $panelSlide=$panel.Slides.Add(1,12)
    $range=$slide.Shapes.Range($names);$pasted=$null
    for($attempt=0;$attempt -lt 8;$attempt++){
     $range.Copy();Start-Sleep -Milliseconds 250
     try {$pasted=$panelSlide.Shapes.Paste();break} catch {Start-Sleep -Milliseconds 250}
    }
    if(-not $pasted){throw 'Cannot paste F01 panel'}
    foreach($copy in $pasted){$original=$slide.Shapes.Item($copy.Name);$copy.Left=$original.Left-$p.X*.75;$copy.Top=$original.Top-$p.Y*.75}
    $panelSlide.Export((Join-Path $out ($p.Name+'.png')),'PNG',($p.W*3),($p.H*3))
   } finally {$panel.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($panel)|Out-Null}
  } finally {$deck.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck)|Out-Null}
 }
} finally {$app.Quit();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)|Out-Null}
