$ErrorActionPreference = 'Stop'
$taskPython = 'D:\weibull\python\.venv\Scripts\python.exe'
$taskNode = 'C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
& $taskPython (Join-Path $PSScriptRoot 'prepare_lean_workbook.py')
if ($LASTEXITCODE -ne 0) { throw 'Failed: prepare_lean_workbook.py' }
& $taskNode --max-old-space-size=8192 (Join-Path $PSScriptRoot 'lean_workbook.mjs')
if ($LASTEXITCODE -ne 0) { throw 'Failed: lean_workbook.mjs' }
$taskInspect = Join-Path $PSScriptRoot '..\结果\W(2,1000,1000).xlsx.inspect.ndjson'
if (Test-Path -LiteralPath $taskInspect) {
    Move-Item -LiteralPath $taskInspect -Destination (Join-Path $PSScriptRoot '精简工作簿导出检查.ndjson') -Force
}
& $taskPython (Join-Path $PSScriptRoot 'verify_lean_workbook.py')
if ($LASTEXITCODE -ne 0) { throw 'Failed: verify_lean_workbook.py' }
Write-Output 'Research00-format workbook exported from saved data; no samples or estimates recomputed.'
