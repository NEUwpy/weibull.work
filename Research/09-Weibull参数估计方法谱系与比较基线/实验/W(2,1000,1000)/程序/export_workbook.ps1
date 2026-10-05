param([string]$OutputDirectory = (Join-Path $PSScriptRoot '..\结果'))
$ErrorActionPreference = 'Stop'
$taskPython = 'D:\weibull\python\.venv\Scripts\python.exe'
$taskNode = 'C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$taskDependencies = 'C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
$taskJunction = Join-Path $PSScriptRoot 'node_modules'
if (-not (Test-Path -LiteralPath $taskJunction)) {
    New-Item -ItemType Junction -Path $taskJunction -Target $taskDependencies | Out-Null
}
$taskCache = Join-Path ([System.IO.Path]::GetTempPath()) ('weibull-w210001000-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskCache | Out-Null
$taskData = Join-Path $taskCache 'tables.json'
& $taskPython (Join-Path $PSScriptRoot 'prepare_tables.py') --output-json $taskData
if ($LASTEXITCODE -ne 0) { throw 'Failed: prepare_tables.py' }
& $taskNode --max-old-space-size=8192 (Join-Path $PSScriptRoot 'lean_workbook.mjs') $taskData ([System.IO.Path]::GetFullPath($OutputDirectory))
if ($LASTEXITCODE -ne 0) { throw 'Failed: lean_workbook.mjs' }
& $taskPython (Join-Path $PSScriptRoot 'verify_workbook.py') --tables $taskData --workbook (Join-Path $OutputDirectory 'W(2,1000,1000).xlsx')
if ($LASTEXITCODE -ne 0) { throw 'Failed: verify_workbook.py' }
$taskInspect = Join-Path $OutputDirectory 'W(2,1000,1000).xlsx.inspect.ndjson'
if (Test-Path -LiteralPath $taskInspect) { Remove-Item -LiteralPath $taskInspect }
Write-Output 'Current 11-sheet workbook exported from adjacent CSVs; no estimates recomputed.'
