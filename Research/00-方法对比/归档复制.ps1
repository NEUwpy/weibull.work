$ErrorActionPreference = 'Stop'
$repo = 'D:\weibull'
$target = Join-Path $repo 'Research\00-方法对比'
$base = 'docs/临时任务/临时任务-W2-1000-3000-MDM偏移量估计-20260825'
$work = 'docs/临时任务/工作输出'
$records = [System.Collections.Generic.List[object]]::new()
$skipped = [System.Collections.Generic.List[object]]::new()
function CopyEvidence([string]$source, [string]$destination) {
    $src = Join-Path $repo $source
    $dst = Join-Path $target $destination
    if (Test-Path -LiteralPath $dst) { throw "Destination already exists: $dst" }
    New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
    $before = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
    Copy-Item -LiteralPath $src -Destination $dst
    $after = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash
    if ($before -ne $after) { throw "Hash mismatch: $source" }
    $records.Add([pscustomobject]@{source=$source; destination=$destination; bytes=(Get-Item -LiteralPath $dst).Length; sha256=$after})
}
function CopyTree([string]$source, [string]$destination, [string]$exclude = '') {
    $src = Join-Path $repo $source
    foreach ($item in Get-ChildItem -LiteralPath $src -Force) {
        $rel = "$source/$($item.Name)"
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.Name -match '^(node_modules|__pycache__|qa|_qa_workbook)$' -or $item.Name -match '\.inspect\.|inspection|preview|contact.sheet|\.log$|\.tiff?$' -or ($exclude -and $item.Name -match $exclude)) {
            $skipped.Add([pscustomobject]@{source=$rel; reason='不复制缓存、检查预览、重复导出或另行归类的材料；原件保留'})
            continue
        }
        if ($item.PSIsContainer) { CopyTree $rel "$destination/$($item.Name)" $exclude }
        else { CopyEvidence $rel "$destination/$($item.Name)" }
    }
}
CopyTree "$base/260825给老师" 'W(2,1000,3000)/20260825/交付文件' '200组|WMLE过程图|LS_LRE|第5组'
CopyTree "$base/260826-W2,1000,500" 'W(2,1000,500)/20260826/交付文件'
foreach ($location in 500,1000,3000) {
    CopyTree "$base/260907-W3参数估计案例/W(3,1000,$location)" "W(3,1000,$location)/20260907/交付文件"
}
foreach ($location in 500,3000) {
    CopyTree "$base/260906-W5参数估计案例/W(5,1000,$location)" "W(5,1000,$location)/20260906/交付文件" '原样本加2000'
    CopyTree "$work/20260906-W5-parameters/W5-1000-$location" "W(5,1000,$location)/20260906/数据与程序"
}
CopyTree "$base/260921-W2参数估计案例/W(2,1000,1000)" 'W(2,1000,1000)/20260921/交付文件'
CopyTree "$base/260906-W5参数估计案例/260929-W5-1000-500新样本" 'W(5,1000,500)/20260929-新抽样/交付文件'
CopyEvidence "$base/260906-W5参数估计案例/W(5,1000,500)/原样本加2000_估计结果对照.xlsx" 'W(5,1000,500)/20260929-原样本加2000检验/原样本加2000_估计结果对照.xlsx'
CopyTree "$work/20260825-n7-200-seed20260826" 'W(2,1000,3000)/20260826-200组补充抽样'
CopyTree "$work/20260826-gamma500-six-figures-table" 'W(2,1000,500)/20260826/数据与程序' '\.png$'
CopyTree "$work/20260929-W5新样本" 'W(5,1000,500)/20260929-新抽样/数据与程序/n7-n15' '\.png$'
CopyTree "$work/20260929-W5新样本-n30" 'W(5,1000,500)/20260929-新抽样/数据与程序/n30' '\.png$'
CopyTree "$base/四种对照方法-代码与原文" '共用资料/历史方法代码与原文'
CopyTree "$base/260929-MDM形状2与5梯度对比" '跨组合诊断/形状2与5/图'
CopyTree "$work/20260929-MDM形状2与5梯度对比" '跨组合诊断/形状2与5/数据与程序'
foreach ($name in '零值机制图','MDM第5组梯度图','WMLE过程图') {
    CopyTree "$base/$name" "W(2,1000,3000)/20260825/附加诊断/$name"
}
CopyTree "$base/最终交付" '历史版本/早期最终交付'
foreach ($file in Get-ChildItem -LiteralPath (Join-Path $repo $base) -File) {
    if ($file.Extension -eq '.zip') { CopyEvidence "$base/$($file.Name)" "历史版本/原始压缩包/$($file.Name)" }
    elseif ($file.Name -match 'inspect|inspection') { $skipped.Add([pscustomobject]@{source="$base/$($file.Name)";reason='检查输出，原件保留'}) }
    elseif ($file.Name -match '^gradient_location_') { $skipped.Add([pscustomobject]@{source="$base/$($file.Name)";reason='主交付已保留中文命名图；此导出版仍在原处'}) }
    else { CopyEvidence "$base/$($file.Name)" "W(2,1000,3000)/20260825/数据与程序/$($file.Name)" }
}
foreach ($name in '260906-W5参数估计案例','260907-W3参数估计案例','260921-W2参数估计案例') {
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $repo "$base/$name") -File -Filter '*.zip') {
        CopyEvidence "$base/$name/$($file.Name)" "历史版本/原始压缩包/$($file.Name)"
    }
}
foreach ($file in Get-ChildItem -LiteralPath (Join-Path $repo "$work/20260906-W5-parameters") -File) {
    CopyEvidence "$work/20260906-W5-parameters/$($file.Name)" "共用资料/W5历史批量脚本/$($file.Name)"
}
CopyTree 'tmp/w3-cases-20260907' '共用资料/W3历史批量脚本与数据' '^outputs$|contact'
CopyTree 'tmp/w2-case-20260921' 'W(2,1000,1000)/20260921/数据与程序' '^outputs$'
CopyTree 'tmp/w5-mechanism-20260929' '共用资料/W5新抽样与平移脚本' '\.png$'
# 旧工作输出可能不同于交付版；仅保存不相同的文件，不用它覆盖交付版。
foreach ($pair in @(@('tmp/w3-cases-20260907/outputs',"$base/260907-W3参数估计案例"),@('tmp/w2-case-20260921/outputs',"$base/260921-W2参数估计案例"))) {
    $root = Join-Path $repo $pair[0]
    foreach ($file in Get-ChildItem -LiteralPath $root -Recurse -File) {
        $rel = $file.FullName.Substring($root.Length+1).Replace('\','/')
        $canonical = Join-Path $repo "$($pair[1])/$rel"
        if ((Test-Path -LiteralPath $canonical) -and (Get-FileHash -LiteralPath $file.FullName).Hash -eq (Get-FileHash -LiteralPath $canonical).Hash) {
            $skipped.Add([pscustomobject]@{source="$($pair[0])/$rel";reason="与交付版字节一致：$($pair[1])/$rel"})
        } else { CopyEvidence "$($pair[0])/$rel" "历史版本/工作输出差异版/$rel" }
    }
}
$records | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $target '复制清单.json') -Encoding utf8
$skipped | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $target '未复制清单.json') -Encoding utf8
[pscustomobject]@{copied=$records.Count; bytes=($records | Measure-Object bytes -Sum).Sum; skipped=$skipped.Count} | ConvertTo-Json
