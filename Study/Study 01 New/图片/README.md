# 论文图件

当前仅保留正式整图、当前内部子图及其代码和数据。旧版与试作已归档于Git提交`0b9b574a`，工作目录不再保存副本。

| 图件 | 整图 | 内部图 | 代码与数据 |
|---|---|---|---|
| F01 / 图1 | [可编辑PPT v20](F01_MDM流程与圆周误差-v20.pptx) · [PNG](F01_MDM流程与圆周误差-v20.png) | [A位置求解](子图/F01a_位置求解.png) · [B形状回代](子图/F01b_形状回代.png) · [C重复抽样梯度](子图/F01c_重复抽样梯度.png) · [D圆周误差与RMSE](子图/F01d_圆周误差与三参数RMSE.png) | `绘图程序/F01*` · `数据/F01*` |
| F02 / 图2 | [可编辑PPT v2](F02_AMDM训练与估计流程-v2.pptx) · [PNG](F02_AMDM训练与估计流程-v2.png) | [A离线学习](子图/F02a_离线学习.png) · [B实际估计](子图/F02b_实际估计.png) | [绘图程序](绘图程序/F02_绘制PPT.mjs) · [流程数据](数据/F02_AMDM训练与估计流程.json) · [公式](数据/F02_MathType公式.json) |

## 图1的数据和含义

样本来自项目[已保存的30组观测](../../../public/case-studies/mdm/verification-182-046/data.csv)，总体为W(2,1000,1000)，每组n=7。A、B使用Sample-1-3，C、D使用全部30组。依据[MDM文献原理](../../../src/content/182-046-pdf原文.md)重新计算，未声称精确复现原文样本。

[曲线CSV](数据/F01_MDM原理联图.csv)按panel、series、kind映射曲线与样本；[元数据](数据/F01_MDM原理联图.json)保存设置、全部参数估计及来源。秩概率为(i−0.3)/(n+0.4)，标准差ddof=1，形状搜索区间[0.1,15]。原数据保留完整轨迹，展示区间聚焦判据附近。

D图圆周1–30对应源sample_ids顺序，半径为位置参数绝对误差，两圆共用0–1000线性刻度。全部60个位置估计均保留，包括零判据下10个下界解。右侧β、η、γ使用独立纵轴比较原始单位RMSE。[D图数据](数据/F01d_圆周误差图.json)保存逐样本误差与汇总；结果仅代表这组示例。

## 图1复现

需要Node及Artifact Tool、PowerPoint、MathType；程序当前配置本机运行环境。先在项目根目录运行：

```powershell
node "Study/Study 01 New/图片/绘图程序/F01_绘制PPT.mjs"
& "Study/Study 01 New/图片/绘图程序/F01_嵌入MathType.ps1"
node "Study/Study 01 New/图片/绘图程序/F01d_圆周误差图.mjs"
& "Study/Study 01 New/图片/绘图程序/F01_嵌入MathType.ps1" -Candidate "D:/weibull/tmp/f01d-radial-v20/radial-base.pptx" -Output "D:/weibull/tmp/f01d-radial-v20/radial-mathtype.pptx" -SpecPath "D:/weibull/Study/Study 01 New/图片/数据/F01d_圆周误差公式.json"
& "Study/Study 01 New/图片/绘图程序/F01d_合成圆周误差PPT.ps1"
node "Study/Study 01 New/图片/绘图程序/F01d_圆周误差图.mjs" --finalize
& "Study/Study 01 New/图片/绘图程序/F01_导出当前子图.ps1"
```

所有中间稿写入项目tmp；合成不再依赖已删除的旧PPT。发布文件存在时，先在程序中指定新版本名。整图PNG由最终PPT用PowerPoint导出。子图从当前整图直接导出，公式保存在整图的MathType对象中。

`F01_MDM原理联图.py`用于重新计算曲线数据；诊断图写入tmp/f01-data-check，不在当前图片目录生成旧版。其余F01程序负责当前PPT布局、MathType和D图。

## 图2口径

训练阶段区分观测样本输入与真参数构造的监督目标；推断阶段只使用观测样本预测候选损失并选择偏移，再将原始样本和偏移交给MDM。真参数不进入实际估计。数据JSON保存节点、连线、示例样本与来源，版面坐标由绘图程序定义。

图2沿用图1的分区配色、虚线边框、字体和箭头样式。20处公式为可编辑MathType对象；网络仅示意映射关系，不代表实际层宽。样本散点复用图1的Sample-1-3，仅说明输入形式，不构成新的实验结果。A、B子图直接从整图导出。

## 图2复现

```powershell
node "Study/Study 01 New/图片/绘图程序/F02_绘制PPT.mjs"
& "Study/Study 01 New/图片/绘图程序/F01_嵌入MathType.ps1" -Candidate "D:/weibull/tmp/f02-v2/candidate.pptx" -Output "D:/weibull/tmp/f02-v2/mathtype-candidate.pptx" -SpecPath "D:/weibull/Study/Study 01 New/图片/数据/F02_MathType公式.json"
node "Study/Study 01 New/图片/绘图程序/F02_绘制PPT.mjs" --finalize
& "Study/Study 01 New/图片/绘图程序/F02_导出整图与子图.ps1"
```

发布文件已存在时指定新版本名后再运行finalize。旧图2及旧Python绘图程序可从`03be98ab`恢复。
