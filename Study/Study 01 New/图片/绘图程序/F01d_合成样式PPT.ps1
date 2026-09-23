# Reuse the verified v18 axes, summaries and MathType equations on three alternatives.
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$repo=[IO.Path]::GetFullPath((Join-Path $root '..\..\..'))
$build=Join-Path $repo 'tmp\f01d-styles-v19'
$app=New-Object -ComObject PowerPoint.Application
$source=$null;$deck=$null
try {
 $source=$app.Presentations.Open((Join-Path $root 'F01_MDM流程与重复抽样-v18.pptx'),-1,0,0)
 $deck=$app.Presentations.Open((Join-Path $build 'overlay.pptx'),0,0,0)
 $titles=@('① 小提琴图：分布轮廓与全部估计点','② 云雨图：分布轮廓、箱线与全部估计点','③ 蜂群散点图：直接呈现全部估计值')
 for($page=1;$page -le 3;$page++){
  $slide=$deck.Slides.Item($page)
  foreach($shape in $source.Slides.Item(1).Shapes){
   $name=$shape.Name
   $keep=($name.StartsWith('comparison.') -and -not $name.StartsWith('comparison.estimate-') -and -not $name.StartsWith('comparison.row')) -or $name -in @('MathType.comparison0','MathType.comparison01','MathType.gammaTruth')
   if(-not $keep){continue}
   $range=$null
   for($attempt=0;$attempt -lt 8;$attempt++){
    $shape.Copy()
    Start-Sleep -Milliseconds 180
    try {$range=$slide.Shapes.Paste();break} catch {Start-Sleep -Milliseconds 250}
   }
   if(-not $range){throw "Cannot copy $name to slide $page"}
   $copy=$range.Item(1)
   $copy.Left=$shape.Left-(1240-30)*.75
   $copy.Top=$shape.Top-(715-30)*.75
   if($name -eq 'MathType.comparison0'){$copy.Top-=12*.75}
   if($name -eq 'comparison.title'){$copy.TextFrame.TextRange.Text=$titles[$page-1]}
   if($name -eq 'comparison.note'){
    if($page -lt 3){$copy.TextFrame.TextRange.Text='每组30个解；平滑轮廓描述非零解，0处10个下界解单独保留。'}
    else{$copy.TextFrame.TextRange.Text='每组30个解，0处10个下界解全部保留；横坐标不变，竖向堆叠仅为避免遮盖。'}
   }
   [Runtime.InteropServices.Marshal]::ReleaseComObject($copy)|Out-Null
   [Runtime.InteropServices.Marshal]::ReleaseComObject($range)|Out-Null
  }
  $slide.Export((Join-Path $build "style-$page.png"),'PNG',2240,1200)
  [Runtime.InteropServices.Marshal]::ReleaseComObject($slide)|Out-Null
 }
 $deck.SaveAs((Join-Path $build 'candidate.pptx'),24)
} finally {
 if($deck){$deck.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck)|Out-Null}
 if($source){$source.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($source)|Out-Null}
 $app.Quit();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)|Out-Null
}
