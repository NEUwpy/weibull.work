param([switch]$Generate)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$taskProgram = Split-Path -Parent $PSScriptRoot
$taskRoot = $taskProgram
while (-not (Test-Path -LiteralPath (Join-Path $taskRoot 'python/.venv/Scripts/python.exe'))) {
    $taskParent = Split-Path -Parent $taskRoot
    if (-not $taskParent -or $taskParent -eq $taskRoot) { throw 'Project Python was not found' }
    $taskRoot = $taskParent
}
$taskAction = if ($Generate) { 'generate' } else { 'verify' }
& (Join-Path $taskRoot 'python/.venv/Scripts/python.exe') -B (Join-Path $taskProgram '运行交付.py') $taskAction --group (Split-Path -Leaf $PSScriptRoot)
if ($LASTEXITCODE -ne 0) { throw 'Research00 delivery command failed' }
