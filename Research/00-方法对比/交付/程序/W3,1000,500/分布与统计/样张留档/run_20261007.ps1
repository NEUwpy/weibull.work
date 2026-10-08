$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$taskReader = 'C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$taskPlotter = 'D:\weibull\python\.venv\Scripts\python.exe'
& $taskReader (Join-Path $PSScriptRoot 'prepare_pilot.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $taskPlotter (Join-Path $PSScriptRoot 'draw_pilot.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
