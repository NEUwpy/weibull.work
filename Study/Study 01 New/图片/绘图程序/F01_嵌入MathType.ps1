# Replace editable text formula components with true MathType OLE equations.
# Requires installed PowerPoint and MathType 7 (64-bit MathPage API).
param([string]$Candidate = 'D:\weibull\tmp\f01-ppt-v16\candidate.pptx',
      [string]$Output = 'D:\weibull\tmp\f01-ppt-v16\mathtype-candidate.pptx')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$specs=Get-Content -Raw -LiteralPath (Join-Path $root '数据\F01_MathType公式.json') | ConvertFrom-Json
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class F01MathType {
 [DllImport(@"D:\software\MathPage\64\MathPage.wll", CallingConvention=CallingConvention.StdCall)]
 public static extern int MTInitAPI(short options, short timeout);
 [DllImport(@"D:\software\MathPage\64\MathPage.wll", CallingConvention=CallingConvention.StdCall)]
 public static extern int MTTermAPI();
 [DllImport(@"D:\software\MathPage\64\MathPage.wll", CallingConvention=CallingConvention.StdCall)]
 public static extern int MTSetEqnFromLangStr(IntPtr obj, int lang, [MarshalAs(UnmanagedType.LPWStr)] string tex, int len);
 [DllImport(@"D:\software\MathPage\64\MathPage.wll", CallingConvention=CallingConvention.StdCall)]
 public static extern int MTCloseOleObject(int save, IntPtr obj);
}
'@
$init=[F01MathType]::MTInitAPI(0,15)
if($init -lt 0){throw "MathType initialization failed: $init"}
$app=$null;$deck=$null
try {
 $app=New-Object -ComObject PowerPoint.Application
 $deck=$app.Presentations.Open($Candidate,0,0,0)
 $slide=$deck.Slides.Item(1)
 foreach($spec in $specs){
  # -1 uses the server's natural extent; preset dimensions stretch MathType glyphs.
  $sh=$slide.Shapes.AddOLEObject(0,0,-1,-1,'Equation.DSMT4')
  $sh.Name='MathType.'+$spec.id
  $obj=$sh.OLEFormat.Object
  $ptr=[Runtime.InteropServices.Marshal]::GetIDispatchForObject($obj)
  try {
   $rc=[F01MathType]::MTSetEqnFromLangStr($ptr,1,$spec.tex,$spec.tex.Length)
   if($rc -ne 0){throw "Formula $($spec.id) failed: $rc"}
   $rc=[F01MathType]::MTCloseOleObject(1,$ptr)
   if($rc -ne 0){throw "Saving formula $($spec.id) failed: $rc"}
  } finally {
   [Runtime.InteropServices.Marshal]::Release($ptr)|Out-Null
   [Runtime.InteropServices.Marshal]::FinalReleaseComObject($obj)|Out-Null
  }
  # MathType returns before PowerPoint receives the final OLE extent callback.
  # Poll COM properties until the server-updated dimensions have settled.
  $last='';$stable=0
  for($attempt=0;$attempt -lt 60;$attempt++){
   Start-Sleep -Milliseconds 100
   $w=[double]$sh.Width;$h=[double]$sh.Height
   $sizeKey="$w,$h"
   if($sizeKey -eq $last){$stable++}else{$stable=0;$last=$sizeKey}
   if($stable -ge 10){break}
  }
  Write-Output "$($spec.id): intrinsic $w x $h pt"
  $factor=[Math]::Min(($spec.w*.75)/$w,($spec.h*.75)/$h)
  $factor=[Math]::Min($factor,($spec.font*.75)/12)
  $sh.LockAspectRatio=0
  $sh.Width=$w*$factor;$sh.Height=$h*$factor
  $sh.Left=($spec.x+$spec.w/2)*.75-$sh.Width/2
  $sh.Top=($spec.y+$spec.h/2)*.75-$sh.Height/2
  $sh.LockAspectRatio=-1
  for($i=$slide.Shapes.Count;$i -ge 1;$i--){
   $item=$slide.Shapes.Item($i)
   foreach($prefix in $spec.remove){
    if($item.Name -eq $prefix -or $item.Name.StartsWith($prefix+'.')){
     $item.Delete();break
    }
   }
   if($item.Name -ne $sh.Name){[Runtime.InteropServices.Marshal]::ReleaseComObject($item)|Out-Null}
  }
  Write-Output "$($spec.id): $($sh.OLEFormat.ProgID), $([Math]::Round($sh.Width,1)) x $([Math]::Round($sh.Height,1)) pt"
  [Runtime.InteropServices.Marshal]::FinalReleaseComObject($sh)|Out-Null
 }
 foreach($note in $slide.NotesPage.Shapes){
  if($note.HasTextFrame -eq -1 -and $note.TextFrame.HasText -eq -1){
   $text=$note.TextFrame.TextRange.Text
   $text=$text.Replace('公式为可编辑原生文本与分式线条','公式为可双击编辑的MathType OLE对象')
   $text=$text.Replace('公式底稿为文本，随后由F01_嵌入MathType.ps1替换为MathType OLE对象','公式为可双击编辑的MathType OLE对象')
   $note.TextFrame.TextRange.Text=$text
  }
 }
 $deck.SaveAs($Output,24)
 $slide.Export((Join-Path (Split-Path $Output) 'mathtype-preview.png'),'PNG',3510,975)
 [Runtime.InteropServices.Marshal]::FinalReleaseComObject($slide)|Out-Null
 $deck.Close()
 [Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck)|Out-Null
 $deck=$null
 $app.Quit()
 [Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)|Out-Null
 $app=$null
} finally {
 if($deck){$deck.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck)|Out-Null}
 if($app){$app.Quit();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)|Out-Null}
 [F01MathType]::MTTermAPI()|Out-Null
 [GC]::Collect();[GC]::WaitForPendingFinalizers()
}
