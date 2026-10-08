param([switch]$Generate)
$ErrorActionPreference='Stop'
$env:PYTHONUTF8='1'; $env:PYTHONDONTWRITEBYTECODE='1'
$taskPython='D:\weibull\python\.venv\Scripts\python.exe'
$taskReadPython='C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$taskNode='C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
if($Generate){
    & $taskPython (Join-Path $PSScriptRoot '本次补算.py')
    if($LASTEXITCODE -ne 0){throw 'Calculation failed'}
    $taskLink=Join-Path $PSScriptRoot 'node_modules'
    $taskBundledDeps='C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
    $taskCreatedLink=$false
    if(-not(Test-Path -LiteralPath $taskLink)){
        New-Item -ItemType Junction -Path $taskLink -Target $taskBundledDeps | Out-Null
        $taskCreatedLink=$true
    }
    try{
        & $taskNode (Join-Path $PSScriptRoot '本次建表.mjs')
        if($LASTEXITCODE -ne 0){throw 'Table build failed'}
    }finally{
        if($taskCreatedLink){
            $taskItem=Get-Item -LiteralPath $taskLink
            if($taskItem.LinkType -ne 'Junction' -or $taskItem.Target -ne $taskBundledDeps){throw 'Unexpected runtime link'}
            [System.IO.Directory]::Delete($taskItem.FullName)
        }
    }
}
& $taskReadPython (Join-Path $PSScriptRoot '核对本次表.py')
if($LASTEXITCODE -ne 0){throw 'Workbook check failed'}
if($Generate){
    & $taskPython (Join-Path $PSScriptRoot '本次分布图.py')
    if($LASTEXITCODE -ne 0){throw 'Distribution plotting failed'}
    & $taskPython (Join-Path $PSScriptRoot '本次MDM图.py')
    if($LASTEXITCODE -ne 0){throw 'MDM plotting failed'}
}
