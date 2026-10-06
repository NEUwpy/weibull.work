param([string]$OutputDirectory = (Join-Path $PSScriptRoot '..\结果'))
$ErrorActionPreference = 'Stop'
$taskPython = 'D:\weibull\python\.venv\Scripts\python.exe'
$taskNode = 'C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$taskDependencies = 'C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
$env:RUNTIME_NODE_MODULES = $taskDependencies
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$taskCache = if ($env:R09_ARTIFACT_CACHE) { [System.IO.Path]::GetFullPath($env:R09_ARTIFACT_CACHE) } else { Join-Path ([System.IO.Path]::GetTempPath()) ('weibull-export-' + [guid]::NewGuid().ToString('N')) }
New-Item -ItemType Directory -Path $taskCache -Force | Out-Null
$taskJunction = Join-Path $taskCache 'node_modules'
if (-not (Test-Path -LiteralPath $taskJunction)) { New-Item -ItemType Junction -Path $taskJunction -Target $taskDependencies | Out-Null }
$taskData = Join-Path $taskCache 'tables.json'
$taskBuilder = Join-Path $taskCache 'lean_workbook.mjs'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'lean_workbook.mjs') -Destination $taskBuilder -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'config.json') -Destination (Join-Path $taskCache 'config.json') -Force
& $taskPython -B (Join-Path $PSScriptRoot 'prepare_tables.py') --output-json $taskData
if ($LASTEXITCODE -ne 0) { throw 'Failed: prepare_tables.py' }
& $taskNode --max-old-space-size=8192 $taskBuilder $taskData $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw 'Failed: lean_workbook.mjs' }
& $taskPython -B (Join-Path $PSScriptRoot 'verify_workbook.py') --tables $taskData --workbook (Join-Path $OutputDirectory 'W(1.5,100,500).xlsx')
if ($LASTEXITCODE -ne 0) { throw 'Failed: verify_workbook.py' }
$taskInspect = Join-Path $OutputDirectory 'W(1.5,100,500).xlsx.inspect.ndjson'
if (Test-Path -LiteralPath $taskInspect) { Remove-Item -LiteralPath $taskInspect }
Write-Output 'Current 11-sheet workbook exported and verified from saved CSVs; no fitting.'
