# 结果生成程序

- [运行参数估计.py](运行参数估计.py)：读取已保存的原始样本，调用七种方法并另存估计表、条件汇总和求解明细；`--verify`只核对现有结果。
- [实验配置.json](实验配置.json)：40个条件、重复数、方法选项、边界及计算实现的校验值。
- [计算实现-20261016](计算实现-20261016/)：当时使用的方法、权重表和共用计算流程，保持原字节；复算直接使用此目录。依赖版本见其中的`requirements.txt`，记录的是本次整理时已验证可运行的环境。
- [b10_feature_selector.py](b10_feature_selector.py)：30维样本特征与样本量输入、七法B10风险预测、选法、失败回退与既有条件留出；[研究方案](../B10方法选择-研究方案-v1.0.md)与[简要报告](../B10方法选择-简要报告-v1.0.md)说明口径和边界。新增独立样本使用[b10_fresh_validation.py](b10_fresh_validation.py)调用固定共享流水线；[b10_feature_analysis.py](b10_feature_analysis.py)分析样本量及结构关系，[verify_b10_feature_selector.py](verify_b10_feature_selector.py)检查交付。
- [更新前版本](历史版本/2026-10-16-求解更新前/版本说明.md)：按此前要求保留的日期备份，不参与当前计算。

结果统计与绘图程序在[结果呈现](../结果呈现/README.md)，方法关系图程序在[方法分类](../方法分类/README.md)。其余旧补算、导出和一次性核查程序已退出当前目录。

精简前材料已移至[外部恢复目录](D:/weibull-backups/study04-20261018-精简前/退出当前目录/)，其上级目录另有校验通过的恢复ZIP；当前计算不依赖这些旧文件。

在项目根目录执行，仅核对当前数据：

```powershell
python/.venv/Scripts/python.exe "Study/04-study-小样本三参数Weibull估计方法比较与选择/程序/运行参数估计.py" --verify
```

例如，另存β=5、n=7的1200次复算：

```powershell
python/.venv/Scripts/python.exe "Study/04-study-小样本三参数Weibull估计方法比较与选择/程序/运行参数估计.py" --beta 5 --n 7 --output "Study/04-study-小样本三参数Weibull估计方法比较与选择/结果/复算/β5-n7"
```

不指定`--beta`和`--n`时复算全部40条件；可用`--workers`调整进程数。另存目录必须不存在，原结果不覆盖。原结果包含经过核验的历史估计，复算则全部重新求解，可能出现浮点精度差异；原样本、原估计及其来源以[现有结果](../结果/README.md)为准。

## B10特征网络的复现与预测

当前收敛目标是[直接学习既有地图的方法类别](../B10方法选择-地图分类匹配-v1.0.md)。`b10_map_classifier.py run`训练或读取另存分类模型、评价逐组与逐格地图匹配并核验；`predict --sample ...`直接给出地图方法类别和分类概率。`b10_map_classifier_plot.py`生成原地图与测试多数票图的对照PNG/PDF。复用原数据集、30维样本特征及划分，不输入真实参数或七法估计值；单次初始化结果另存`结果/B10方法选择-v1/map_classifier/`。下面是此前风险预测路线的复现入口，继续保留。

`b10_lse_diagnosis.py`冻结原模型，核对4个LSE格在训练/验证/测试中的召回与概率、固定类别比例校正、已知仿真参数下的完整样本似然参照及地图冠军稳定性；生成[LSE错分诊断](../B10方法选择-LSE错分诊断-v1.0.md)。它不重新训练分类网络，不改变原图；似然参照额外知道真η、γ，仅用于判断原因。

`b10_classifier_ablation.py`复用分类器训练函数，对6种特征组删除设置匹配3个种子并重新训练，生成[分类器特征消融](../B10方法选择-分类器特征消融-v1.0.md)。结果与20个新增模型另存`结果/B10方法选择-v1/map_classifier/ablation/`，原种子42完整模型保持不变；汇总条件等权匹配率、各类召回、逐格恢复及配对区间，并核对特征间的精确重叠关系。

各法误差因素的量化见[消融与实际误差幅度补充](../B10方法选择-误差因素量化补充-v1.0.md)。`b10_factor_quantification.py train/evaluate/verify`分别补齐匹配的三初始化消融、计算七法分组预测损失与真实误差分位对比、核对结果；`b10_factor_report.py`生成图与报告。前者不改原网络或原方法，消融贡献不作为因果占比。

与报告下B10性能地图的逐格和逐样本对照见[补充报告](../B10方法选择-性能地图对照补充-v1.0.md)；[b10_map_comparison.py](b10_map_comparison.py)仅使用冻结预测作比较，不重新训练。原图使用全数据，独立测试参照为训练部分重建的条件表。

实际训练环境为Python 3.11、NumPy 2.4.4、SciPy 1.17.1、PyTorch 2.11.0+cpu，训练不依赖pandas或scikit-learn。固定种子、划分、预处理和模型配置随产物保存。原结果和模型在本地`结果/B10方法选择-v1/`，由Git忽略；下载代码仍需另外同步原88份CSV、求解明细和数据说明。

独立重做时指定新的输出目录，保留本轮结果。下列命令在项目根目录运行：

```powershell
$env:B10_SELECTOR_OUTPUT = Join-Path (Get-Location) 'Study/04-study-小样本三参数Weibull估计方法比较与选择/结果/B10方法选择-复现'
$entry = 'Study/04-study-小样本三参数Weibull估计方法比较与选择/程序'
python "$entry/b10_feature_selector.py" prepare
python "$entry/b10_feature_selector.py" train
python "$entry/b10_feature_selector.py" evaluate
python "$entry/b10_fresh_validation.py" run --repeats 200 --workers 4
python "$entry/b10_fresh_validation.py" evaluate
python "$entry/b10_feature_analysis.py"
python "$entry/verify_b10_feature_selector.py"
Remove-Item Env:B10_SELECTOR_OUTPUT
```

`prepare`拒绝覆盖已有数据集，新增实验拒绝覆盖已有条件目录；`train`会复用同一输出目录中已存在的模型。重新训练应使用新的输出目录。作图及报告使用`b10_report_assets.py`，另需matplotlib；本次图形环境位于项目忽略目录`.codex-tmp/b10-plot-deps`，没有更改系统包。

使用本轮保存模型，仅输入一组观测即可输出七法预计RMS误差和排序，例如：

```powershell
python "Study/04-study-小样本三参数Weibull估计方法比较与选择/程序/b10_feature_selector.py" predict --sample 700 820 950 1100 1280 1430 1710
```

这个入口仅预测风险和排序，不自动运行传统方法；本轮选法收益由存档返回状态模拟依序回退，并用独立新生成的七法返回复核。模型不输入真参数，也不能在实际应用时自动判断真实尺度、位置是否属于已验证范围。跨尺度、位置的失败证据见报告。
