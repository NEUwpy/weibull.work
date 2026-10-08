$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' (Join-Path $PSScriptRoot 'read_excel.py')
if ($LASTEXITCODE -ne 0) { throw 'Excel check failed' }
& 'D:\weibull\python\.venv\Scripts\python.exe' (Join-Path $PSScriptRoot 'draw.py')
if ($LASTEXITCODE -ne 0) { throw 'Plotting failed' }
