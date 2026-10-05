"""Write the current plot/table report from the saved summary, without estimating."""
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent;BATCH=HERE.parent
def main():
    summary=pd.read_csv(BATCH/'结果/三方法汇总.csv')
    previous=(BATCH/'README.md').read_text(encoding='utf-8')
    method=previous.split('## 方法依据\n\n',1)[1].split('## 统计与结果',1)[0]
    table=['| 方法 | n | 有解数/1200 | 有解率 | β Bias / SD / RMSE | η Bias / SD / RMSE | γ Bias / SD / RMSE |',
           '|---|---:|---:|---:|---|---|---|']
    for row in summary.to_dict('records'):
        metrics=[' / '.join(f"{row[p+'_'+m]:.3f}" if p=='beta' else f"{row[p+'_'+m]:.1f}" for m in ['bias','sd','rmse']) for p in ['beta','eta','gamma']]
        table.append(f"| {row['method']} | {row['n']} | {row['success']} | {row['success_rate']:.2%} | "+' | '.join(metrics)+' |')
    paths=[('小提琴组图','01_估计分布小提琴.png'),('有解率图','02_有解率.png'),('RMSE / Bias / SD 九格图','03_RMSE_Bias_SD九格.png')]
    path_text='\n'.join(f'- [{label}](结果/{file})：`{str(BATCH/"结果"/file)}`' for label,file in paths)
    text=f'''# MLE、MMLE 与 WMLE：样本、估计明细与九格指标图

2026-10-05 · 邮件009，沿用邮件007计算和008标记。只改图表，未重新抽样或拟合。

**一句话结论：本批 MMLE 与 WMLE 均全部有解，MMLE 的波动较小、形状RMSE较低但尺度和位置偏差较大，WMLE 的位置RMSE较低且n=50尺度更准；MLE小样本有解率低且波动大，随n增大改善。**

真值β=2、η=1000、γ=1000；n=7/10/15/20/50各1200组，三者共用6000组输入。结论仅针对本批数据和已记录版本。

## 方法依据

{method}## 统计与结果

**Bias是有符号的平均偏差**，不是平均绝对偏差：Bias=mean(θ̂−θ)。正值表示平均高估，负值表示平均低估。原始单位，不按图的显示范围裁剪。

SD=std(θ̂, ddof=0)，RMSE=√mean((θ̂−θ)²)，所以RMSE²=Bias²+SD²。每项都使用该方法的全部成功估计，失败不进入精度统计，有解率的分母包括所有1200组。共享指标模块的默认SD为ddof=1，本批沿用已约定的ddof=0，没有改共享模块。

成功要求收敛、β̂>0和η̂>0且有限、γ̂有限并小于**实际保留观测的最小值**。MMLE按原构造删除x₁，γ̂=x₁原值保留，检查γ̂<x₂；MLE/WMLE保留完整观测，检查γ̂<x₁。邮件中的x₍min₎据此指拟合数据的最小值。若对MMLE仍用被删除的x₁作为严格上界，会将其原版位置定义判失败。明细同时列“原始最小值”“支持检查最小值”“删除观测数”，保持前两封状态，没有修改成功口径或估计值。

{chr(10).join(table)}

MMLE的β RMSE在五个n都低于另外两者，η/γ SD也较小，但η偏低、γ偏高。WMLE的γ RMSE在五个n都最低，n=50的η RMSE为149.56，低于MMLE的165.52和MLE的166.63；较小SD并不自动意味着较小RMSE。MLE有效数由n=7的377增至n=50的1199，精度仍基于各自有效子集，不能将小样本条件精度当作全样本保证。

## 当前产物与图注

- [完整样本与估计Excel](结果/W(2,1000,1000)_完整样本与估计.xlsx)：三个工作表“样本”“估计明细”“汇总”。样本6000行、估计明细18000行、汇总15行。
- [样本CSV](结果/样本.csv)：每行一组，含n、组号、block、repeat_id、种子命名空间、SHA256及排序观测x(1)…x(50)；超过n的列留空，全部122400个实际观测保留。
- [估计明细CSV](结果/估计明细.csv)：每行方法×样本组，含真值、三个估计、收敛、成功/失败、失败原因及代码、原始/支持最小值、删除数、原记录耗时和样本SHA。失败估计为空时保持空值，不补为0。
- [汇总CSV](结果/三方法汇总.csv)：与Excel“汇总”和图点同源，包含成功数/比例及逐参数Bias、SD、RMSE。本轮移除联合列。

{path_text}

**小提琴图图注：**参数三行、n五列。方法固定MLE/MMLE/WMLE，粉色圆点是中位数、红色圆点是均值，两者都用全部成功估计并进入图例；四分位线0.5pt、中心线散点无抖动、细黑虚线是真值。β0–10、η/γ0–2000，跨方法与n共用线性范围；Scott密度只用显示范围内成功估计，轮廓止于实际端点。完整值和显示范围外记录在程序/绘图核验.json。

**有解率图图注：**每个n分母1200。MMLE与WMLE都100%，用不同线型/标记显示真实重合的两条线。

**九格图图注：**行依次RMSE、Bias、SD，列依次β、η、γ，每格三方法线和数据点。Bias=mean(θ̂−θ)为有符号平均偏差；SD=std(θ̂,ddof=0)；RMSE=√mean((θ̂−θ)²)，故RMSE²=Bias²+SD²。均按全部成功估计计算，失败排除，不按显示范围裁剪。各格线性固定范围，η和γ在同一指标行共用范围。没有联合RMSE格，也没有用联合量作结论。

## 数据对应、重导出与核验

程序/输入样本.npz是原6000组实际输入，按n分数组；程序/per_sample.csv.gz是原18000行估计。样本组键为n+block+repeat_id，三方法共享同一SHA。block0种子命名空间为`study01_selector_confirmation_20260922_v1`，block1–11增加`:research09-versions:blockNN`，每块100组。数据来自原共享Monte Carlo流水线，本次没有重新调用它估计。

程序/prepare_details.py从保存的输入/估计导出样本与明细JSON/CSV；程序/draw.py只读取这些估计及汇总绘图；程序/details_workbook.mjs用捆绑Node和artifact-tool创建三工作表Excel；程序/verify_details.py核对Excel/CSV/NPZ/原估计、状态、失败和图点。

重新导出同一数据的图表入口（不会重新抽样或求解，更新本批当前展示）：

```powershell
& '{str(HERE/'export_saved_results.ps1')}'
```

本次逐一核对6000组样本SHA及122400观测、18000行估计和状态、15行汇总、45个RMSE/Bias/SD恒等式、150个图点；Excel三个工作表的全部数据单元格核对JSON，15个有解率公式无错误。三PNG及所有工作表关键区域已渲染检查。小提琴沿用邮件008的粉点/红点要求。

270个科学输入/估计/源码文件与其他批次3882个文件内容及清单保持。本批旧的三张分图和旧汇总Excel移入程序/邮件008图表留记录，当前结果只含三PNG、完整Excel和三CSV；未改生产算法、其他批次或既有报告/PPT，未提交、未推送。环境、来源及完整哈希在程序目录。
'''
    (BATCH/'README.md').write_text(text,encoding='utf-8');print('Current README written from saved statistics.')
if __name__=='__main__':main()
