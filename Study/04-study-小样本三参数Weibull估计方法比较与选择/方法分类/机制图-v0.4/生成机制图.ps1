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
    $cell.SetAttribute('value', $Value)
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

# 完整地图由显式的方法对关系生成，避免按列表位置推断沿袭。
& python (Join-Path $Out '生成完整机理地图.py')
if($LASTEXITCODE -ne 0) { throw '完整机理地图生成失败' }
Write-Output "Generated v0.4 mechanism diagrams in $Out"
