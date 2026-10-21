$ErrorActionPreference = 'Stop'
$Out = Split-Path -Parent $MyInvocation.MyCommand.Path

function New-Canvas([string]$Id, [string]$Name, [int]$Width, [int]$Height) {
    $doc = New-Object System.Xml.XmlDocument
    $doc.AppendChild($doc.CreateXmlDeclaration('1.0', 'UTF-8', $null)) | Out-Null
    $file = $doc.CreateElement('mxfile')
    $file.SetAttribute('host', 'app.diagrams.net')
    $file.SetAttribute('agent', 'Codex')
    $file.SetAttribute('version', '26.0.9')
    $doc.AppendChild($file) | Out-Null
    $diagram = $doc.CreateElement('diagram')
    $diagram.SetAttribute('id', $Id)
    $diagram.SetAttribute('name', $Name)
    $file.AppendChild($diagram) | Out-Null
    $model = $doc.CreateElement('mxGraphModel')
    $model.SetAttribute('page', '1')
    $model.SetAttribute('pageWidth', [string]$Width)
    $model.SetAttribute('pageHeight', [string]$Height)
    $model.SetAttribute('grid', '1')
    $model.SetAttribute('gridSize', '10')
    $model.SetAttribute('math', '1')
    $model.SetAttribute('background', '#ffffff')
    $diagram.AppendChild($model) | Out-Null
    $root = $doc.CreateElement('root')
    $model.AppendChild($root) | Out-Null
    foreach($pair in @(@('0', $null), @('1', '0'))) {
        $cell = $doc.CreateElement('mxCell')
        $cell.SetAttribute('id', $pair[0])
        if($null -ne $pair[1]) { $cell.SetAttribute('parent', $pair[1]) }
        $root.AppendChild($cell) | Out-Null
    }
    return [pscustomobject]@{ Doc=$doc; Root=$root }
}

function Add-Cell($Canvas, [string]$Id, [string]$Value, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Style, [bool]$Edge=$false, [string]$Source=$null, [string]$Target=$null) {
    $cell = $Canvas.Doc.CreateElement('mxCell')
    $cell.SetAttribute('id', $Id)
    $cell.SetAttribute('value', [System.Security.SecurityElement]::Escape($Value))
    $cell.SetAttribute('parent', '1')
    if($Edge) {
        $cell.SetAttribute('edge', '1')
        if($Source) { $cell.SetAttribute('source', $Source) }
        if($Target) { $cell.SetAttribute('target', $Target) }
        $geo = $Canvas.Doc.CreateElement('mxGeometry')
        $geo.SetAttribute('relative', '1')
        $geo.SetAttribute('as', 'geometry')
        $cell.AppendChild($geo) | Out-Null
    } else {
        $cell.SetAttribute('vertex', '1')
        $geo = $Canvas.Doc.CreateElement('mxGeometry')
        $geo.SetAttribute('as', 'geometry')
        $geo.SetAttribute('x', [string]$X)
        $geo.SetAttribute('y', [string]$Y)
        $geo.SetAttribute('width', [string]$W)
        $geo.SetAttribute('height', [string]$H)
        $cell.AppendChild($geo) | Out-Null
    }
    $cell.SetAttribute('style', $Style)
    $Canvas.Root.AppendChild($cell) | Out-Null
}

function Box($Canvas, [string]$Id, [string]$Value, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Fill='#F7F9FB', [string]$Stroke='#63758A', [string]$Font='#263238', [int]$Size=20, [bool]$Dashed=$false, [bool]$Bold=$false, [string]$Align='left', [string]$Valign='middle') {
    $style = "whiteSpace=wrap;html=1;fontFamily=Microsoft YaHei;fontSize=$Size;fontColor=$Font;strokeWidth=1.6;rounded=1;arcSize=8;fillColor=$Fill;strokeColor=$Stroke;align=$Align;verticalAlign=$Valign;spacing=10;"
    if($Dashed) { $style += 'dashed=1;dashPattern=6 4;' }
    if($Bold) { $style += 'fontStyle=1;' }
    Add-Cell $Canvas $Id $Value $X $Y $W $H $style
}

function Text($Canvas, [string]$Id, [string]$Value, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Color='#63758A', [int]$Size=18, [bool]$Bold=$false, [string]$Align='left') {
    $style = "whiteSpace=wrap;html=1;fontFamily=Microsoft YaHei;fontSize=$Size;fontColor=$Color;strokeWidth=0;fillColor=none;strokeColor=none;align=$Align;verticalAlign=middle;spacing=0;"
    if($Bold) { $style += 'fontStyle=1;' }
    Add-Cell $Canvas $Id $Value $X $Y $W $H $style
}

function Edge($Canvas, [string]$Id, [string]$Source, [string]$Target, [string]$Label='', [string]$Color='#263238', [bool]$Dashed=$false, [double]$Width=2.0, [string]$Arrow='block') {
    $style = "html=1;strokeColor=$Color;strokeWidth=$Width;endArrow=$Arrow;endFill=1;rounded=0;"
    if($Dashed) { $style += 'dashed=1;dashPattern=6 4;' }
    Add-Cell $Canvas $Id $Label 0 0 0 0 $style $true $Source $Target
}

function Save-Canvas($Canvas, [string]$FileName) {
    $settings = New-Object System.Xml.XmlWriterSettings
    $settings.Indent = $true
    $settings.Encoding = New-Object System.Text.UTF8Encoding($false)
    $path = Join-Path $Out $FileName
    $writer = [System.Xml.XmlWriter]::Create($path, $settings)
    $Canvas.Doc.Save($writer)
    $writer.Close()
}

$categories = @(
    @{ File='01-似然估计路线-机制图.drawio'; Id='likelihood-route-v04'; Title='机制图 01｜似然估计路线'; Subtitle='核心问题：样本在候选参数下有多“可能”？'; Info='观测处密度 f(tᵢ;β,η,γ)；位置参数决定支持边界，联合密度同时携带三参数信息。'; Principle='构造 L(θ|D) 或得分方程，最大化联合似然，或对其位置方程、权重和偏差项作明确修正。'; Output='β̂、η̂、γ̂<br>并伴随边界、局部极大、失败与求解诊断'; Caution='采用智能优化器搜索同一似然目标时，仍属于似然路线；有限搜索不自动证明全局MLE存在。'; Branches=@(@('原始 MLE','保留原始密度准则；区分局部候选、边界响应与全局存在性。'),@('WMLE','在估计方程中加入样本量相关权重，仍以似然方程为骨架。'),@('MMLE 分支','以最小值、均值、方差或中位数关系替换部分位置方程；同名分支需分开。'),@('K–R／DMMLE','最小值定位、删点与偏差修正组合；来源和作用环节分别记录。'),@('CMLE／罚似然','替换边界处密度项或加入经验因子，改变边界处理而非简单换求解器。')); Tags=@('方程加权','位置／支持边界','偏差修正','初值与搜索','PSO／SA／DE求解既定目标') },
    @{ File='02-分布匹配路线-机制图.drawio'; Id='distribution-matching-route-v04'; Title='机制图 02｜分布匹配路线'; Subtitle='核心问题：理论分布能否再现样本呈现的分布结构？'; Info='经验分布、绘图概率、CDF概率间隔、概率图坐标、密度或由观测反推的伪尺度。'; Principle='选择使理论分布与样本结构最一致的参数：最小化残差／距离、最大化概率间距，或最小化伪尺度差异。'; Output='β̂、η̂、γ̂<br>以及拟合评分、间距评分或一致性曲线'; Caution='最大化概率间距与最大化密度似然的统计对象不同；共同使用概率量不自动表示沿袭。'; Branches=@(@('概率图分支','White／Soman／Park：分数、位置判据、回归方向和参数恢复共同决定估计器。'),@('LSE／WLSE','在经验分布或变换关系上最小化残差；权重属于实现与改进标签。'),@('MPS／QMP','使用排序样本在理论CDF上的概率间距；MPS可作为特定QMP设置的特例。'),@('MDM','比较每个观测反推的尺度伪估计是否一致；位置用条件差异曲线及梯度规则定位。'),@('CDF／密度／最小距离','直接把理论分布与经验对象比较；具体目标函数和支持条件需逐篇核对。')); Tags=@('绘图概率','回归方向','概率间距','残差／距离','伪尺度一致性','位置搜索') },
    @{ File='03-统计关系反演路线-机制图.drawio'; Id='statistical-inversion-route-v04'; Title='机制图 03｜统计关系反演路线'; Subtitle='核心问题：样本统计特征与总体参数之间有什么理论关系？'; Info='样本矩、PWM／L矩、分位数、次序统计量、枢轴量、位置—尺度不变统计量及其期望／协方差。'; Principle='建立理论等式、匹配关系或枢轴反演关系，再求解三个参数；条件线性估计通过协方差选择权重。'; Output='β̂、η̂、γ̂<br>以及方程残差、矩差、枢轴区间或条件方差'; Caution='统计量相近不等于估计准则相同；已知参数条件、迭代代入和整体三参数性质需要逐篇区分。'; Branches=@(@('MM／Weibull moments','用样本矩或Weibull矩显式恢复参数；近奇异的矩差会放大波动。'),@('PWM／L矩／TL矩','改变统计量权重或端部使用方式，保留矩关系反演的主线。'),@('分位数／次序统计量','用理论分位数、次序统计量分布或枢轴关系确定位置和其他参数。'),@('不变统计量 LSPF／LPF','先消除位置或尺度的一部分影响，再用统计量似然或恢复方程估计。'),@('条件线性最小方差','在给定参数或估计条件下，用期望与协方差选线性组合权重；性质不能无条件外推。')); Tags=@('矩／权重','消元','枢轴反演','次序统计量','协方差权重','参数恢复') },
    @{ File='04-后验推断路线-机制图.drawio'; Id='posterior-route-v04'; Title='机制图 04｜后验推断路线'; Subtitle='核心问题：如何把样本证据与参数先验合成为估计？'; Info='样本似然 L(θ|D) 与先验 p(θ)，以及参数化、支持域和后验计算所需的条件分布。'; Principle='形成 p(θ|D) ∝ L(θ|D)p(θ)，再按平方损失、绝对损失或其他规则取后验均值、众数或中位数。'; Output='点估计或后验区间<br>并伴随先验敏感性、支持域与链混合诊断'; Caution='共享似然不意味着后验推断等同于MLE；计算链运行成功也不自动证明先验和支持域设定合理。'; Branches=@(@('后验模型','先验、似然和参数支持域共同决定推断对象；贝叶斯与MLE可共享似然。'),@('点估计规则','后验均值、后验中位数、MAP等是不同输出规则，不能只按计算算法分类。'),@('后验计算','Gibbs、Laplace、MH、ARS等负责计算后验量，属于实现标签。'),@('经验先验组合','灰色拟合、参数自助或外部知识可提供先验，但独立信息与同样本重抽样需区分。'),@('关系线','MAP与似然最大化存在数学联系；先验、损失和支持域仍改变完整推断机制。')); Tags=@('先验支持域','参数化','后验规则','Gibbs／MH／Laplace','先验敏感性','链混合') },
    @{ File='05-学习映射路线-机制图.drawio'; Id='learning-route-v04'; Title='机制图 05｜学习映射路线'; Subtitle='核心问题：能否从训练样本中学习样本到参数的估计函数？'; Info='模拟样本或历史样本、可观测特征、真参数标签、训练域和损失函数。'; Principle='训练 hφ(D) 或 hφ(features) 使预测参数在预设损失下表现良好，使用时直接输出参数估计。'; Output='β̂、η̂、γ̂<br>并伴随训练域、外推、校准、回退与不确定性边界'; Caution='训练集上的误差不能替代新样本泛化证据；学习路线的先验范围、输入表示和损失共同定义方法边界。'; Branches=@(@('直接参数映射','ANN／BPNN等从样本特征直接预测三个参数；训练数据和特征属于方法本身。'),@('目标与损失','参数损失、寿命点损失或联合约束会改变估计函数的取向。'),@('训练域与泛化','参数范围、样本量、尺度处理和外推位置决定可声明边界。'),@('混合学习','网络可学习似然过程量、权重或修正量；主归属按它最终改变的环节判断。'),@('工具区分','PSO、SA等搜索既定目标不等于学习映射；直接学习才形成独立估计范式。')); Tags=@('训练数据','特征表示','损失／约束','训练域','外推与校准','回退／拒绝') }
)

foreach($cat in $categories) {
    $c = New-Canvas $cat.Id $cat.Title 1800 1100
    Text $c 'title' $cat.Title 40 24 1720 48 '#263238' 32 $true
    Text $c 'subtitle' $cat.Subtitle 40 78 1720 32 '#63758A' 19 $false
    Text $c 'legend' '蓝灰：共同信息与主流程　珊瑚：本路线的决定性原则　绿色：参数输出　紫灰：实现、改进与边界' 40 112 1720 28 '#63758A' 18 $false
    Box $c 'sample' '<b>① 样本 D</b><br>排序寿命样本<br>完整样本或指定观测条件' 40 170 360 170 '#F7F9FB' '#63758A' '#263238' 21
    Box $c 'info' "<b>② 信息利用</b><br>$($cat.Info)" 475 170 360 170 '#F7F9FB' '#63758A' '#263238' 20
    Box $c 'principle' "<b>③ 参数确定原则</b><br>$($cat.Principle)" 910 170 360 170 '#FFF5F2' '#B44948' '#6F2F2B' 20
    Box $c 'output' "<b>④ 三参数估计</b><br>$($cat.Output)" 1345 170 360 170 '#EEF8F2' '#548A74' '#263238' 20
    Edge $c 'flow-1' 'sample' 'info' '' '#263238' $false 2.4
    Edge $c 'flow-2' 'info' 'principle' '' '#263238' $false 2.4
    Edge $c 'flow-3' 'principle' 'output' '' '#263238' $false 2.4
    Box $c 'branches-panel' '<b>主要构造与方法分支</b>' 40 385 1665 300 '#FFFFFF' '#63758A' '#263238' 24 $true $false 'left' 'top'
    for($i=0;$i -lt $cat.Branches.Count;$i++) {
        $x=70 + ($i % 3) * 545; $y=445 + [math]::Floor($i/3) * 105; $id="branch-$i"; $b=$cat.Branches[$i]
        Box $c $id "<b>$($b[0])</b><br>$($b[1])" $x $y 500 82 '#FFF5F2' '#B44948' '#6F2F2B' 18
        Edge $c "branch-edge-$i" 'principle' $id '' '#B44948' $true 1.4 'open'
    }
    Box $c 'tags-panel' '<b>实现与改进标签（横向，不另立一级类别）</b>' 40 725 1665 175 '#FFFFFF' '#7F6B93' '#57436B' 23 $true $false 'left' 'top'
    for($i=0;$i -lt $cat.Tags.Count;$i++) {
        $x=70 + ($i % 4) * 405; $y=785 + [math]::Floor($i/4) * 55; $id="tag-$i"
        Box $c $id $cat.Tags[$i] $x $y 365 42 '#F4F0F8' '#7F6B93' '#57436B' 17
        Edge $c "tag-edge-$i" ($(if($i % 2 -eq 0){'info'}else{'principle'}) ) $id '' '#7F6B93' $true 1.2 'open'
    }
    Box $c 'caution' "<b>解释边界</b><br>$($cat.Caution)" 40 945 1665 90 '#FFFBEA' '#B18B2C' '#6B5310' 18
    Save-Canvas $c $cat.File
}

# Complete map: route lanes, internal progression, and explicit cross-route interactions.
$c = New-Canvas 'complete-method-map-v04' '完整机理地图｜五簇路线与方法交互' 2600 1900
Text $c 'title' '完整机理地图｜五簇路线与方法交互' 40 22 2520 48 '#263238' 34 $true
Text $c 'subtitle' '从样本信息进入，经信息变换和决定性原则，沿路线内部推进到三参数输出；跨路线关系单独连出。' 40 74 2520 32 '#63758A' 20
Text $c 'legend' '金色边框：本轮七种比较实现　实线：沿袭／扩展　虚线：数学联系　点划线：局部借用／组合' 40 112 2520 30 '#63758A' 18
$stages = @(@('stage-info','样本信息',300),@('stage-transform','信息变换／压缩',620),@('stage-principle','决定性原则',950),@('stage-chain','路线内部的推进',1280),@('stage-output','三参数输出／诊断',1840))
foreach($s in $stages) { Box $c $s[0] $s[1] $s[2] 132 250 44 '#F7F9FB' '#B7C1C9' '#455A64' 17 $false $true 'center' 'middle' }

function MethodBox($Canvas,[string]$Id,[string]$Value,[double]$X,[double]$Y,[double]$W,[double]$H,[string]$RouteFill,[string]$RouteStroke,[bool]$Current=$false) {
    if($Current) { Box $Canvas $Id $Value $X $Y $W $H '#FFFBEA' '#B18B2C' '#6B5310' 16 $false $true 'center' 'middle' }
    else { Box $Canvas $Id $Value $X $Y $W $H $RouteFill $RouteStroke '#263238' 16 $false $false 'center' 'middle' }
}

$lanes = @(
    @{ Key='like'; Y=190; Title='① 似然估计路线'; Desc='密度／联合贡献 → 似然或得分 → 方程变体'; Fill='#FFF8F5'; Stroke='#B44948'; Info='观测处密度、联合密度、支持边界'; Principle='最大化 L(θ|D) 或修正得分方程'; Output='β̂ η̂ γ̂<br>边界／局部极大／失败诊断'; Methods=@(@('m-mle','MLE', $true),@('m-wmle','WMLE',$true),@('m-kr','K–R<br>删最小值',$true),@('m-dmmle','DMMLE',$true)) },
    @{ Key='dist'; Y=465; Title='② 分布匹配路线'; Desc='CDF／概率图／间距／伪尺度 → 匹配判据'; Fill='#EFF7FB'; Stroke='#4F7D9A'; Info='经验CDF、绘图分数、概率间距、伪尺度'; Principle='最小偏离、最大间距或尺度一致性'; Output='β̂ η̂ γ̂<br>评分／残差／一致性曲线'; Methods=@(@('p-white','White',$false),@('p-soman','Soman LSE',$true),@('p-park','Park LRE',$true),@('p-yang','Yang迭代',$false),@('p-mdm','MDM',$true)) },
    @{ Key='stat'; Y=740; Title='③ 统计关系反演路线'; Desc='矩／分位数／次序统计量 → 理论关系 → 反解'; Fill='#EEF8F2'; Stroke='#548A74'; Info='矩、PWM／L矩、分位数、次序统计量、枢轴'; Principle='匹配、消元、枢轴反演或条件协方差选权'; Output='β̂ η̂ γ̂<br>矩差／枢轴／条件方差'; Methods=@(@('s-mm','MM<br>Cran',$true),@('s-pwm','PWM',$false),@('s-lmom','L矩→TL矩',$false),@('s-lspf','LSPF→LPF',$false),@('s-mvle','MVLUE',$false)) },
    @{ Key='post'; Y=1015; Title='④ 后验推断路线'; Desc='似然＋先验 → 后验 → 决策规则'; Fill='#F4F0F8'; Stroke='#7F6B93'; Info='样本似然、先验、支持域、条件分布'; Principle='后验均值、MAP、中位数或区间'; Output='点估计／区间<br>先验敏感性／链诊断'; Methods=@(@('b-model','Bayes<br>模型',$false),@('b-map','MAP／后验均值',$false),@('b-compute','Gibbs／MH／Laplace',$false)) },
    @{ Key='learn'; Y=1290; Title='⑤ 学习映射路线'; Desc='训练样本／特征 → 损失 → 参数映射'; Fill='#FFF1EB'; Stroke='#B46A48'; Info='模拟样本、特征、真参数、训练域'; Principle='学习 hφ(D) 或 hφ(features)'; Output='β̂ η̂ γ̂<br>外推／校准／回退边界'; Methods=@(@('l-ann','ANN／BPNN',$false),@('l-loss','损失／约束',$false),@('l-svr','SVR／混合学习',$false)) }
)
foreach($lane in $lanes) {
    $y=$lane.Y
    Box $c "lane-$($lane.Key)" '' 40 $y 2520 220 $lane.Fill $lane.Stroke '#263238' 18 $true $false 'left' 'top'
    Box $c "lane-label-$($lane.Key)" "<b>$($lane.Title)</b><br>$($lane.Desc)" 60 ($y+32) 205 150 $lane.Fill $lane.Stroke '#263238' 18 $false $true 'left' 'middle'
    Box $c "info-$($lane.Key)" $lane.Info 300 ($y+55) 275 78 $lane.Fill $lane.Stroke '#263238' 17 $false $false 'center' 'middle'
    Box $c "principle-$($lane.Key)" $lane.Principle 620 ($y+55) 285 78 $lane.Fill $lane.Stroke '#6F2F2B' 17 $false $true 'center' 'middle'
    Box $c "chain-$($lane.Key)" '方法链：从共同材料到具体版本' 940 ($y+24) 805 165 '#FFFFFF' $lane.Stroke '#455A64' 16 $true $false 'left' 'top'
    $count=$lane.Methods.Count; $w=([math]::Floor(730/$count))-8; $x=970
    for($i=0;$i -lt $count;$i++) {
        $m=$lane.Methods[$i]; MethodBox $c $m[0] $m[1] $x ($y+82) $w 58 $lane.Fill $lane.Stroke $m[2]
        if($i -gt 0) { Edge $c "edge-$($lane.Key)-$i" $lane.Methods[$i-1][0] $m[0] '' $lane.Stroke $false 1.8 'block' }
        $x += $w + 8
    }
    Box $c "output-$($lane.Key)" $lane.Output 1810 ($y+55) 450 78 '#EEF8F2' '#548A74' '#263238' 17 $false $false 'center' 'middle'
    Edge $c "flow-info-$($lane.Key)" "info-$($lane.Key)" "principle-$($lane.Key)" '' $lane.Stroke $false 2.3 'block'
    Edge $c "flow-principle-$($lane.Key)" "principle-$($lane.Key)" $lane.Methods[0][0] '' $lane.Stroke $false 2.3 'block'
    Edge $c "flow-output-$($lane.Key)" $lane.Methods[$count-1][0] "output-$($lane.Key)" '' $lane.Stroke $false 2.3 'block'
}

# Cross-route interactions: these are the part that makes the map a relationship map rather than five isolated lists.
Edge $c 'cross-like-post' 'm-mle' 'b-model' '共享似然模型' '#7F6B93' $true 2.0 'open'
Edge $c 'cross-wmle-dmmle' 'm-wmle' 'm-dmmle' '方程加权→偏差修正' '#B44948' $true 1.7 'open'
Edge $c 'cross-kr-dmmle' 'm-kr' 'm-dmmle' '最小值定位＋Firth' '#B44948' $false 1.9 'block'
Edge $c 'cross-white-soman' 'p-white' 'p-soman' 'White扩展' '#4F7D9A' $false 1.9 'block'
Edge $c 'cross-soman-park' 'p-soman' 'p-park' '不同定位／回归方向' '#4F7D9A' $true 1.6 'open'
Edge $c 'cross-lspf-yang' 's-lspf' 'p-yang' '位置修正局部借用' '#7D8790' $true 1.8 'open'
Edge $c 'cross-plot-order' 'p-soman' 's-mvle' '共享次序统计量／位置关系' '#7D8790' $true 1.6 'open'
Edge $c 'cross-mps-qmp' 'p-white' 'p-yang' '概率关系组合' '#4F7D9A' $true 1.3 'open'
Edge $c 'cross-mm-pwm' 's-mm' 's-pwm' '矩的线性重组' '#548A74' $true 1.7 'open'
Edge $c 'cross-pwm-lmom' 's-pwm' 's-lmom' 'PWM↔L矩' '#548A74' $true 1.7 'open'
Edge $c 'cross-lspflpf' 's-lspf' 's-lmom' '不变统计量改造' '#548A74' $false 1.8 'block'
Edge $c 'cross-ann-svr' 'l-ann' 'l-svr' '当前样本拟合 vs 跨样本映射' '#B46A48' $true 1.6 'open'

# Horizontal layer: modifications and tools act on particular nodes, not as new route boxes.
Box $c 'interaction-panel' '<b>横向交互层：改进、组合与工具</b><br>这些节点连接到具体路线中的某一步；它们描述“改了哪里”，不抢占方法的主要归属。' 40 1570 2520 250 '#FFFFFF' '#7F6B93' '#57436B' 20 $true $false 'left' 'top'
$interactions=@(
    @('int-weight','加权：改变方程／统计量贡献',80,1650,360,60),
    @('int-bias','偏差修正：改变得分或输出',480,1650,360,60),
    @('int-position','位置处理：最小值／消元／搜索',880,1650,360,60),
    @('int-solver','求解工具：PSO／SA／DE搜索既定目标',1280,1650,390,60),
    @('int-hybrid','混合估计：跨路线分阶段恢复',1710,1650,360,60),
    @('int-boundary','边界与可用域：支持域／训练域／先验',2110,1650,390,60)
)
foreach($i in $interactions) { Box $c $i[0] $i[1] $i[2] $i[3] $i[4] $i[5] '#F4F0F8' '#7F6B93' '#57436B' 16 $false $false 'center' 'middle' }
Edge $c 'int-weight-link' 'int-weight' 'm-wmle' '作用于方程' '#7F6B93' $true 1.2 'open'; Edge $c 'int-bias-link' 'int-bias' 'm-dmmle' '作用于得分／输出' '#7F6B93' $true 1.2 'open'; Edge $c 'int-position-link' 'int-position' 'm-kr' '作用于位置' '#7F6B93' $true 1.2 'open'; Edge $c 'int-solver-link' 'int-solver' 'm-mle' '搜索既定目标' '#7F6B93' $true 1.2 'open'; Edge $c 'int-hybrid-link' 'int-hybrid' 'p-yang' '跨路线组合' '#7F6B93' $true 1.2 'open'; Edge $c 'int-boundary-link' 'int-boundary' 'output-learn' '可用边界' '#7F6B93' $true 1.2 'open'
Save-Canvas $c '06-完整机理地图-五簇分类与方法关系.drawio'

Write-Output "Generated v0.4 mechanism diagrams in $Out"
