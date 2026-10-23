$ErrorActionPreference = 'Stop'
$DiagramRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Generators = @(
    '生成似然细图.py',
    '生成分布与统计细图.py',
    '生成后验与学习细图.py',
    '生成路线流程图.py',
    '生成完整机理地图.py'
)
foreach ($Generator in $Generators) {
    & python -X utf8 (Join-Path $DiagramRoot $Generator)
    if ($LASTEXITCODE -ne 0) { throw "生成失败：$Generator" }
}
& python -X utf8 (Join-Path $DiagramRoot '生成预览图.py')
if ($LASTEXITCODE -ne 0) { throw '预览生成失败' }
