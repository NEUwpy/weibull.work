$ErrorActionPreference = 'Stop'
$taskPython = 'D:\weibull\python\.venv\Scripts\python.exe'
$taskNode = 'C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
foreach ($taskScript in @('prepare_details.py', 'draw.py')) {
    & $taskPython (Join-Path $PSScriptRoot $taskScript)
    if ($LASTEXITCODE -ne 0) { throw "Failed: $taskScript" }
}
& $taskNode --max-old-space-size=8192 (Join-Path $PSScriptRoot 'details_workbook.mjs')
if ($LASTEXITCODE -ne 0) { throw 'Failed: details_workbook.mjs' }
$taskInspect = Join-Path $PSScriptRoot '..\结果\W(2,1000,1000)_完整样本与估计.xlsx.inspect.ndjson'
if (Test-Path -LiteralPath $taskInspect) { Move-Item -LiteralPath $taskInspect -Destination (Join-Path $PSScriptRoot '完整工作簿导出检查.ndjson') -Force }
& $taskPython (Join-Path $PSScriptRoot 'verify_details.py')
if ($LASTEXITCODE -ne 0) { throw 'Failed: verify_details.py' }
Write-Output 'Saved sample/estimate data exported; no simulation or fitting was run.'
