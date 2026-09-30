$ErrorActionPreference = 'Stop'
$repo = 'D:\weibull'
$root = [IO.Path]::GetFullPath((Join-Path $repo 'Research/00-方法对比'))
$manifestPath = Join-Path $root '复制清单.json'
$items = @(Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json)
$before = @($items | ForEach-Object { $_ | Select-Object * })
$moves = [System.Collections.Generic.List[object]]::new()
$additions = [System.Collections.Generic.List[object]]::new()
function SafePath([string]$relative) {
    $p = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (-not $p.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Outside archive: $p" }
    return $p
}
function Category([string]$name) {
    if ($name -match '\.(py|mjs|ps1)$' -or $name -match 'manifest\.json$' -or $name -match '\.md$') { return '程序' }
    return '结果'
}
# Preflight every source before changing any path.
foreach ($e in $items) {
    if ((Get-FileHash -LiteralPath (SafePath $e.destination)).Hash -ne $e.sha256) { throw "Source changed: $($e.destination)" }
}
foreach ($e in $items) {
    $old = $e.destination
    $new = $old
    if ($old -match '^(W\([^/]+\)/[^/]+)/(.*)$') {
        $batch = $Matches[1]; $rest = $Matches[2]
        if ($rest -match '^(程序|结果)/') { throw 'Already reorganized; do not run twice.' }
        if ($rest.StartsWith('交付文件/')) { $new = "$batch/结果/" + $rest.Substring(5) }
        elseif ($rest.StartsWith('数据与程序/')) {
            $tail=$rest.Substring(6); $cat=Category $tail
            $suffix=if ($cat -eq '程序') { $tail } else { "中间数据/$tail" }
            $new="$batch/$cat/$suffix"
        }
        elseif ($rest.StartsWith('附加诊断/')) { $cat=Category $rest; $new="$batch/$cat/$rest" }
        else { $cat=Category $rest; $new="$batch/$cat/$rest" }
    }
    elseif ($old.StartsWith('跨组合诊断/形状2与5/')) {
        $rest=$old.Substring('跨组合诊断/形状2与5/'.Length)
        if ($rest.StartsWith('图/')) { $new='跨组合诊断/形状2与5/结果/'+$rest.Substring(2) }
        elseif ($rest.StartsWith('数据与程序/')) { $tail=$rest.Substring(6); $cat=Category $tail; $new="跨组合诊断/形状2与5/$cat/$tail" }
    }
    if ($old -ne $new) {
        $src=SafePath $old; $dst=SafePath $new
        if (Test-Path -LiteralPath $dst) { throw "Collision: $new" }
        New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
        Move-Item -LiteralPath $src -Destination $dst
        $moves.Add([pscustomobject]@{old=$old;new=$new;sha256=$e.sha256})
        $e | Add-Member -NotePropertyName previous_destination -NotePropertyValue $old
        $e.destination=$new
    }
}
function Duplicate([string]$sourceArchive,[string]$destination) {
    $entry = $items | Where-Object destination -eq $sourceArchive | Select-Object -First 1
    if (-not $entry) { throw "Missing provenance: $sourceArchive" }
    $src=SafePath $sourceArchive; $dst=SafePath $destination
    if (Test-Path -LiteralPath $dst) { throw "Collision: $destination" }
    New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst
    $additions.Add([pscustomobject]@{source=$entry.source;destination=$destination;bytes=$entry.bytes;sha256=$entry.sha256;copied_from_archive=$sourceArchive})
}
foreach ($loc in 500,1000,3000) {
    foreach ($e in $items | Where-Object { $_.destination.StartsWith('共用资料/W3历史批量脚本与数据/') }) {
        $name=Split-Path $e.destination -Leaf
        $cat=Category $name
        $suffix=if ($cat -eq '程序') { $name } else { "中间数据/$name" }
        Duplicate $e.destination "W(3,1000,$loc)/20260907/$cat/$suffix"
    }
}
foreach ($loc in 500,3000) {
    foreach ($e in $items | Where-Object { $_.destination.StartsWith('共用资料/W5历史批量脚本/') }) {
        Duplicate $e.destination "W(5,1000,$loc)/20260906/程序/$(Split-Path $e.destination -Leaf)"
    }
}
$shared='共用资料/W5新抽样与平移脚本'
foreach ($name in 'fresh_batch.py','build_fresh.mjs') { Duplicate "$shared/$name" "W(5,1000,500)/20260929-新抽样/程序/$name" }
foreach ($name in 'export_translation_data.py','build_translation.mjs','verify_parameter_mapping.py','verify_samples.py','analyze.py') {
    Duplicate "$shared/$name" "W(5,1000,500)/20260929-原样本加2000检验/程序/$name"
}
Duplicate "$shared/translation_data.json" 'W(5,1000,500)/20260929-原样本加2000检验/结果/中间数据/translation_data.json'
foreach ($name in 'samples.csv','mdm_estimates.csv','other_method_estimates.csv') {
    Duplicate "W(5,1000,500)/20260906/结果/中间数据/$name" "W(5,1000,500)/20260929-原样本加2000检验/结果/原样本与原估计/$name"
}
# Only preserve current method sources where BOTH saved runs prove the exact historical hash.
$fresh='W(5,1000,500)/20260929-新抽样'
$a=Get-Content -Raw -LiteralPath (SafePath "$fresh/结果/中间数据/n7-n15/results.json") | ConvertFrom-Json
$b=Get-Content -Raw -LiteralPath (SafePath "$fresh/结果/中间数据/n30/results.json") | ConvertFrom-Json
foreach ($prop in $a.code_sha256.psobject.Properties) {
    $src=Join-Path $repo $prop.Name
    if ($b.code_sha256.($prop.Name) -ne $prop.Value -or (Get-FileHash -LiteralPath $src).Hash -ne $prop.Value) { throw "Historical method mismatch: $($prop.Name)" }
    $dest="$fresh/程序/哈希核实依赖/$($prop.Name)"
    $dst=SafePath $dest
    New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst
    $additions.Add([pscustomobject]@{source=$prop.Name;destination=$dest;bytes=(Get-Item -LiteralPath $dst).Length;sha256=$prop.Value.ToUpper();evidence='n7-n15 与 n30 的 results.json 均记录同一代码 SHA256'})
}
$all=@($items)+@($additions.ToArray())
foreach ($e in $all) { if ((Get-FileHash -LiteralPath (SafePath $e.destination)).Hash -ne $e.sha256) { throw "Hash mismatch: $($e.destination)" } }
$all | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding utf8
$moves | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (SafePath '目录调整映射.json') -Encoding utf8
# Remove only empty directory shells inside the verified archive, never source files.
Get-ChildItem -LiteralPath $root -Directory -Recurse | Sort-Object { $_.FullName.Length } -Descending | ForEach-Object {
    $verified=SafePath ($_.FullName.Substring($root.Length+1))
    if (@(Get-ChildItem -LiteralPath $verified -Force).Count -eq 0) { Remove-Item -LiteralPath $verified }
}
[pscustomobject]@{moved=$moves.Count;copied=$additions.Count;total=$all.Count;bytes=($all|Measure-Object bytes -Sum).Sum}|ConvertTo-Json
