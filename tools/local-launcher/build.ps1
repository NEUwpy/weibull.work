[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$launcherDirectory = Split-Path -Parent $PSCommandPath
$projectRoot = Resolve-Path (Join-Path $launcherDirectory '..\..')
$sourcePath = Join-Path $launcherDirectory 'WeibullLocalLauncher.cs'
$outputPath = Join-Path $projectRoot 'Weibull本地启动器.exe'

$windowsDirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::Windows)
if (-not $windowsDirectory) {
    $windowsDirectory = $env:SystemRoot
}
if (-not $windowsDirectory) {
    $windowsDirectory = 'C:\Windows'
}

$compilerCandidates = @(
    (Join-Path $windowsDirectory 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'),
    (Join-Path $windowsDirectory 'Microsoft.NET\Framework\v4.0.30319\csc.exe')
)
$compiler = $compilerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $compiler) {
    throw '未找到 Windows C# 编译器（.NET Framework v4）。'
}

if (Test-Path -LiteralPath $outputPath) {
    Remove-Item -LiteralPath $outputPath -Force
}

& $compiler /nologo /target:winexe /optimize+ `
    /reference:System.dll `
    /reference:System.Core.dll `
    /reference:System.Windows.Forms.dll `
    "/out:$outputPath" `
    $sourcePath

if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $outputPath)) {
    throw "启动器编译失败，退出码：$LASTEXITCODE"
}

$artifact = Get-Item -LiteralPath $outputPath
Write-Host "已生成：$($artifact.FullName)"
Write-Host "大小：$([math]::Round($artifact.Length / 1KB, 1)) KB"
