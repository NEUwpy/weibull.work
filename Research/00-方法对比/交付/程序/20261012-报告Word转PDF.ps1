param([string]$ResearchRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path)
$ErrorActionPreference = 'Stop'
$ResearchRoot = [System.IO.Path]::GetFullPath($ResearchRoot)
$workspace = Split-Path (Split-Path $ResearchRoot -Parent) -Parent
$qa = Join-Path $workspace 'tmp/report-pdf-20261012'
New-Item -ItemType Directory -Force -Path $qa | Out-Null
$reports = @('报告1：小样本情况下高形状参数的估计偏移', '报告2：小样本情况下的明显异常估计')
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.ScreenUpdating = $false
$doc = $null
$records = [System.Collections.Generic.List[object]]::new()
try {
 foreach ($name in $reports) {
  $source = Join-Path $ResearchRoot ($name+'.docx')
  $output = Join-Path $ResearchRoot ($name+'.pdf')
  $temporary = Join-Path $qa ($name+'.pdf')
  $before = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
  $doc = $word.Documents.Open($source,$false,$true)
  $doc.Repaginate()
  $doc.ExportAsFixedFormat($temporary,17)
  $pages = $doc.ComputeStatistics(2)
  $doc.Close(0)
  [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc) | Out-Null
  $doc = $null
  if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $before) {
   throw "Source Word document changed: $source"
  }
  Copy-Item -LiteralPath $temporary -Destination $output -Force
  $records.Add([pscustomobject]@{source=$source; source_sha256=$before; output=$output; pages=$pages; pdf_sha256=(Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash})
  Write-Output ("Exported {0}: {1} pages" -f $name,$pages)
 }
 $records | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $qa 'exports.json') -Encoding UTF8
} finally {
 if ($null -ne $doc) { $doc.Close(0) }
 $word.Quit()
 [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null
}
