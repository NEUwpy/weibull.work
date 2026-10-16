param([Parameter(Mandatory=$true)][string]$Manifest,[switch]$RenderOnly)
$ErrorActionPreference = 'Stop'
$config = Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class Report1MathType {
 [DllImport(@"D:\software\MathPage\64\MathPage.wll", ExactSpelling=true)]
 public static extern int MTInitAPI(short options, short timeout);
 [DllImport(@"D:\software\MathPage\64\MathPage.wll", ExactSpelling=true)]
 public static extern int MTSetEqnFromLangStr([MarshalAs(UnmanagedType.IDispatch)] object eq, short lang, [MarshalAs(UnmanagedType.LPWStr)] string text, int length);
 [DllImport(@"D:\software\MathPage\64\MathPage.wll", ExactSpelling=true)]
 public static extern int MTCloseOleObject(int save, [MarshalAs(UnmanagedType.IDispatch)] object eq);
 [DllImport(@"D:\software\MathPage\64\MathPage.wll", ExactSpelling=true)]
 public static extern int MTTermAPI();
}
'@
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.ScreenUpdating = $false
$doc = $null
$records = [System.Collections.Generic.List[object]]::new()
try {
 if ($RenderOnly) {
  $doc = $word.Documents.Open((Join-Path $config.qa ($config.stem+'-complete.docx')),$false,$true)
  $doc.Repaginate()
  $doc.ExportAsFixedFormat((Join-Path $config.qa ($config.stem+'-complete.pdf')),17)
  Write-Output ("Rendered {0} pages; {1} inline objects." -f $doc.ComputeStatistics(2),$doc.InlineShapes.Count)
  return
 }
 $objectDir = Join-Path $config.qa 'objects'
 New-Item -ItemType Directory -Force -Path $objectDir | Out-Null
 $status = [Report1MathType]::MTInitAPI(0,15)
 Write-Output "MathType initialization: $status"
 if ($status -lt 0) { throw "MathType initialization failed: $status" }
 foreach ($job in $config.jobs) {
  Write-Output "Starting $($job.marker)"
  $doc = $word.Documents.Add()
  $range = $doc.Range(0,0)
  $eq = $doc.InlineShapes.AddOLEObject('Equation.DSMT4',[Type]::Missing,$false,$false,[Type]::Missing,[Type]::Missing,[Type]::Missing,$range)
  $eq.OLEFormat.DoVerb(2)
  $ole = $eq.OLEFormat.Object
  $status = [Report1MathType]::MTSetEqnFromLangStr($ole,2,$job.mathml,$job.mathml.Length)
  if ($status -ne 0) { throw "MathType equation $($job.number) failed: $status" }
  $status = [Report1MathType]::MTCloseOleObject(1,$ole)
  if ($status -ne 0) { throw "MathType equation close failed: $status" }
  if ($eq.Width -gt $job.max_width_pt) {
   $factor = $job.max_width_pt / $eq.Width
   $oldHeight = $eq.Height
   $eq.Width = $job.max_width_pt
   $eq.Height = $oldHeight * $factor
  }
  if (-not $job.display) {
   $eq.Range.ParagraphFormat.LineSpacingRule = 3
   $eq.Range.ParagraphFormat.LineSpacing = 28
  }
  $record = [pscustomobject]@{marker=$job.marker; number=$job.number; display=$job.display; width_pt=$eq.Width; height_pt=$eq.Height; progid=$eq.OLEFormat.ProgID}
  $records.Add($record)
  $objectPath = Join-Path $objectDir ($job.marker+'.docx')
  $doc.SaveAs2($objectPath,16)
  $doc.Close(0)
  [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc) | Out-Null
  $doc = $null
  Write-Output ("MathType {0}: {1:N1} x {2:N1} pt" -f $job.marker,$record.width_pt,$record.height_pt)
 }
 [pscustomobject]@{equations=$records; output=$config.output} |
  ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $config.qa 'word-verification.json') -Encoding UTF8
 Write-Output "Saved $($records.Count) native MathType objects."
} finally {
 try { [Report1MathType]::MTTermAPI() | Out-Null } catch {}
 if ($null -ne $doc) { $doc.Close(0) }
 $word.Quit()
 [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null
}
