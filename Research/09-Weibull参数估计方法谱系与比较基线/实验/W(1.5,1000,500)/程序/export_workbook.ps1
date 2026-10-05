param([string]$OutputDirectory = (Join-Path $PSScriptRoot '..\结果'))
$ErrorActionPreference = 'Stop'
$taskPython = 'D:\weibull\python\.venv\Scripts\python.exe'
$taskNode = 'C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$env:RUNTIME_NODE_MODULES = 'C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
$taskCache = if($env:R09_ARTIFACT_CACHE){$env:R09_ARTIFACT_CACHE}else{Join-Path ([IO.Path]::GetTempPath()) ('r09-tables-'+[guid]::NewGuid().ToString('N'))}
[IO.Directory]::CreateDirectory($taskCache) | Out-Null
$taskData=Join-Path $taskCache 'tables.json'
& $taskPython -B (Join-Path $PSScriptRoot 'prepare_tables.py') --output-json $taskData
if($LASTEXITCODE -ne 0){throw 'prepare_tables failed'}
& $taskNode --max-old-space-size=8192 (Join-Path $PSScriptRoot 'lean_workbook.mjs') $taskData ([IO.Path]::GetFullPath($OutputDirectory))
if($LASTEXITCODE -ne 0){throw 'workbook export failed'}
$taskConfig=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'config.json') -Raw | ConvertFrom-Json
$taskFilename='W('+(($taskConfig.truth | ForEach-Object {$_.ToString('g',[Globalization.CultureInfo]::InvariantCulture)}) -join ',')+').xlsx'
& $taskPython -B (Join-Path $PSScriptRoot 'verify_workbook.py') --tables $taskData --workbook (Join-Path $OutputDirectory $taskFilename)
if($LASTEXITCODE -ne 0){throw 'workbook verification failed'}
$taskInspection=Join-Path $OutputDirectory ($taskFilename+'.inspect.ndjson')
if(Test-Path -LiteralPath $taskInspection){Move-Item -LiteralPath $taskInspection -Destination (Join-Path $taskCache ($taskFilename+'.inspect.ndjson')) -Force}
