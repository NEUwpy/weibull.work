$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$r00TaskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$r00TaskEntries = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'combinations.json') -Raw -Encoding utf8 | ConvertFrom-Json
foreach ($r00TaskEntry in $r00TaskEntries) {
    $r00TaskBatch = Join-Path $r00TaskRoot $r00TaskEntry.path
    & (Join-Path $r00TaskBatch '程序/分布与统计/run_20261007.ps1')
}
& 'D:\weibull\python\.venv\Scripts\python.exe' (Join-Path $PSScriptRoot 'aggregate.py')
if ($LASTEXITCODE -ne 0) { throw 'Aggregation failed' }
