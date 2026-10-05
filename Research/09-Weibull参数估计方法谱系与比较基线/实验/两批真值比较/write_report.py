"""Write the comparison brief from verified, read-only analysis outputs."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
METHODS = ['MLE', 'MMLE', 'WMLE']
SIZES = [7, 10, 15, 20, 50]
SYMBOL = {'beta': 'β', 'eta': 'η', 'gamma': 'γ'}
METRICS = ['bias', 'sd', 'rmse']
LABEL = {'bias': 'Bias', 'sd': 'SD', 'rmse': 'RMSE'}

def link(label, path):
    return f'[{label}](<{Path(path).as_posix()}>)'

def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])

def main():
    guard = json.loads((HERE / '输入保护.json').read_text(encoding='utf-8'))
    d = pd.read_csv(HERE / '全部差异与噪声.csv', float_precision='round_trip')
    diag = pd.read_csv(HERE / '支持距离与相对位置.csv')
    bins = pd.read_csv(HERE / 'MLE真值边界距离分层.csv')
    theory = pd.read_csv(HERE / 'MMLE位置偏差理论.csv')
    # Verify that all summary values used to center bootstrap differences agree
    # with the underlying successful estimates. No parameter fits are rerun.
    for batch, gamma in [('A', 1000.), ('B', 500.)]:
        detail = pd.read_csv(ROOT / f'W(2,1000,{int(gamma)})/结果/估计明细.csv', float_precision='round_trip')
        for method in METHODS:
            for n in SIZES:
                rows = detail[(detail['方法'] == method) & (detail.n == n) & detail['状态'].eq('成功')]
                for parameter in SYMBOL:
                    e = rows[SYMBOL[parameter] + '估计'].to_numpy() - {'beta': 2., 'eta': 1000., 'gamma': gamma}[parameter]
                    expected = [e.mean(), e.std(ddof=0), np.sqrt(np.mean(e * e))]
                    for metric, value in zip(METRICS, expected):
                        recorded = d[(d.method == method) & (d.n == n) & (d.parameter == parameter) & (d.metric == metric)].iloc[0][batch]
                        assert np.isclose(value, recorded, rtol=2e-12, atol=2e-12), (batch, method, n, parameter, metric)
    # Common-scale comparisons avoid dividing location error by an arbitrary origin.
    d['reference_scale'] = d.parameter.map({'beta': 2., 'eta': 1000., 'gamma': 1000., 'all': 1.})
    d['reference_name'] = d.parameter.map({'beta': 'beta_truth=2', 'eta': 'eta_truth=1000', 'gamma': 'eta_truth=1000', 'all': 'probability=1'})
    d['delta_percent_reference'] = 100 * d.delta / d.reference_scale
    d['delta_percent_A'] = np.where(d.metric.isin(['sd', 'rmse']), 100 * d.delta / d.A, np.nan)
    d.to_csv(HERE / '全部差异与噪声.csv', index=False, encoding='utf-8-sig')
    out = ['# 两批位置真值比较：γ=1000 → γ=500',
           '> 2026-10-05 · 邮件014 · 只分析既有数据；两批96个文件的SHA及文件清单保持。',
           '## 结论与能体现的内容',
           '两批的主要格局一致：MMLE、WMLE均1200/1200有解，MLE随n增加由约三成升至接近全部；MMLE仍是位置高估、尺度低估。改变γ没有改变这些主要现象。**但不能说所有差异都落在噪声内**：150项比较中，142项的单项95%差值区间包含0，8项不包含0，且全部集中于n=20；把150项作为一个比较族作Holm校正后，0项达到0.05，最小校正p=0.420。现有数据未识别出经多重比较后仍成立的位置依赖差异，不能据此证明无效应或两批等价。',
           '更有解释力的发现是：MMLE的绝对位置误差由样本最小值决定，理论上与γ无关；当γ减半，误差除以γ的相对比例大致翻倍。负位置估计也会随坐标原点改变而增多。这些比例或符号变化，不等于估计的绝对精度变差。WMLE的选根规则含绝对位置项，存在潜在平移敏感性，但本次12000组候选根平移复核没有改选。',
           '## 比较对象与判定口径',
           'A为W(2,1000,1000)，B为W(2,1000,500)。β=2、η=1000固定；n=7/10/15/20/50，各1200组，MLE / Kundu–Raqab原版MMLE / WMLE的实现及成功判定保持。Δ统一为B−A。种子规则包含γ，**A/B是不同随机样本，不能按组号配对，也不能把B−A直接归因于γ**。同一批内三方法共享输入。',
           'Bias为成功估计的有符号平均误差；SD为成功估计的总体标准差（ddof=0）；RMSE为成功估计的均方根误差。有解率分母始终1200。MLE的精度来自各自成功子集，A/B成功数并不相同；这些精度不是计入失败惩罚的无条件风险。',
           '有限模拟重复会产生Monte Carlo误差，需要报告性能指标自身的抽样不确定性；本报告按这一思路将差值与其MC标准误同时给出。[Morris、White与Crowther，2019](https://doi.org/10.1002/sim.8086)。',
           '### 噪声如何计算',
           r'对Bias，$SE(\Delta)=\sqrt{s_A^2/m_A+s_B^2/m_B}$，其中$s^2$采用成功估计误差的无偏样本方差，$m$是成功的Monte Carlo组数，**不是每组内部的n**。全部45项Bias差值的自助法SE与解析SE之比为0.9864–1.0108。',
           '对Bias、SD、RMSE，在A/B各自的1200组上独立重采样9999次（种子2026100514），包含失败组，每次再按该方法的成功组计算指标；同一批内三方法和三参数使用相同组权重，保留共享输入带来的相关性。用重采样差值的标准差作MCSE，用basic bootstrap给出单项95%差值区间。表中“落在噪声内”表示该区间包含0；它不是“真实差异为0”的证明。basic区间与独立重采样见[SciPy官方说明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)，脚本用等价的多项式组权重实现，未调用SciPy bootstrap。',
           r'解析交叉检查还使用SD的影响量$[(e-\bar e)^2-SD^2]/(2SD)$与RMSE的影响量$[e^2-RMSE^2]/(2RMSE)$：取其样本方差除以有效组数，A/B独立相加开方。解析与自助法SE均保存于CSV。',
           '有解率采用两独立比例的Newcombe–Wilson 95%差值区间与双侧Fisher精确检验；100%/100%时插件SE虽为0，区间仍为±0.319个百分点，避免将“本次没有失败”写成“失败概率必为0”。区间方法见[statsmodels官方说明](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.confint_proportions_2indep.html)，Fisher检验见[SciPy官方说明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html)。',
           '对135项精度与15项有解率检验统一进行150项Holm逐步Bonferroni校正，保留所有单项结果与校正结果；该范围是本次分析所选比较族，没有预先登记。没有设等价界值、没有做等价性检验。自助法区间与p值是有限重采样下的近似推断，尤其小样本MLE的重尾误差会增加不确定性。[Holm方法说明](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html)。',
           '## 有解率：全部方法与n',
           'A/B为百分比，Δ、SE及区间均为百分点（pp）。最后一列全部为单项95%区间包含0；15项Fisher检验也均未拒绝。']
    rate_rows = []
    for method in METHODS:
        for n in SIZES:
            r = d[(d.method == method) & (d.n == n) & d.metric.eq('success_rate')].iloc[0]
            se = '0（退化）' if r.degenerate_plugin_se else f'{100*r.se_analytic:.3f}'
            rate_rows.append([method, n, f'{100*r.A:.3f} ({r.valid_A}/1200)', f'{100*r.B:.3f} ({r.valid_B}/1200)', f'{100*r.delta:+.3f}', se, f'[{100*r.ci_low:.3f}, {100*r.ci_high:.3f}]', '噪声内'])
    out.append(table(['方法', 'n', 'A %', 'B %', 'Δ pp', '解析SE pp', '95%区间 pp', '单项判定'], rate_rows))
    out += ['## 参数精度：全部A/B/差值及噪声量级',
            '下面每个三元组均依次为 **Bias / SD / RMSE**；“SEΔ”是差值的自助法MCSE，不是估计量SD。β保留4位、η/γ保留3位；判定按未舍入值。每行“噪声内”指三个指标都包含0，例外行列出超出单项区间的指标。完整135项单独区间、p及Holm p保存在CSV。',
            '量级参照：β差值除以固定真值2；η差值除以1000；γ的绝对误差差值也除以共同尺度η=1000，避免因位置分母减半制造表面变化。CSV另列SD/RMSE差值相对A的百分比；Bias接近0时不用Bias相对A比值。']
    scale_rows = []
    for parameter in SYMBOL:
        g = d[d.parameter.eq(parameter)]
        maxdelta = g.delta.abs().max()
        rm = g[g.metric.eq('rmse')]
        scale_rows.append([SYMBOL[parameter], '2' if parameter == 'beta' else '1000', f'{maxdelta:.4f}', f'{g.delta_percent_reference.abs().max():.2f}%', f'{rm.delta_percent_A.abs().max():.2f}%'])
    out.append(table(['参数', '共同参照', '最大绝对Δ（含三指标）', '最大Δ/参照', 'RMSE最大相对A变化'], scale_rows))
    for parameter in SYMBOL:
        digits = 4 if parameter == 'beta' else 3
        rows = []
        for method in METHODS:
            for n in SIZES:
                g = d[(d.method == method) & (d.n == n) & d.parameter.eq(parameter)].set_index('metric').loc[METRICS]
                triple = lambda col: ' / '.join(f'{v:.{digits}f}' for v in g[col])
                exceptions = [LABEL[k] for k in METRICS if g.loc[k, 'outside_pointwise_noise']]
                rows.append([method, n, triple('A'), triple('B'), triple('delta'), triple('se_boot'), '超出：' + '、'.join(exceptions) if exceptions else '三项噪声内'])
        out += [f'### {SYMBOL[parameter]}：Bias / SD / RMSE', table(['方法', 'n', 'A', 'B', 'Δ=B−A', 'SEΔ', '单项95%判定'], rows)]
    out += ['## 8项超出单项噪声区间的差异',
            '这些差异必须保留，不能统称为“全是噪声”。它们全部发生在n=20；η偏差向下、γ偏差向上的现象在共享输入的方法中会相关，不能把8项当成8份独立确认。Holm后最小p=0.420，现阶段不能据此确认γ系统效应。']
    exceptional = []
    for r in d[d.outside_pointwise_noise].itertuples():
        digits = 4 if r.parameter == 'beta' else 3
        exceptional.append([r.method, r.n, f'{SYMBOL[r.parameter]} {LABEL[r.metric]}', f'{r.delta:+.{digits}f}', f'{r.se_boot:.{digits}f}', f'[{r.ci_low:.{digits}f}, {r.ci_high:.{digits}f}]', f'{r.p:.4f}', f'{r.p_holm:.4f}'])
    out += [table(['方法', 'n', '指标', 'Δ', 'MCSE', '单项95%区间', '原p', 'Holm p'], exceptional),
            '例如WMLE n=20的η Bias差为−31.219（共同尺度的−3.122%，MCSE=9.982），γ Bias差为+23.809（+2.381%，MCSE=7.890）。这两项在单项分析中较突出，校正后p分别0.4768、0.4200。较大差值不必然有更强信号：MLE n=10 η RMSE差虽为−60.030，其MCSE约58.317，仍在单项噪声区间内。',
            '## MMLE的“γ高估、η低估”是稳定结构吗？',
            '是本次固定β、η与五个n下的稳定结构：两批10个条件中γ Bias全部为正、η Bias全部为负，且随n增加绝对偏差整体缩小。下面列出同号同量级的直接证据；这不外推到所有β、η、n。']
    mmle_rows = []
    for n in SIZES:
        def value(param, metric, batch):
            return float(d[(d.method == 'MMLE') & (d.n == n) & d.parameter.eq(param) & d.metric.eq(metric)].iloc[0][batch])
        t = theory[theory.n == n].iloc[0]
        mmle_rows.append([n, f'{value("eta", "bias", "A"):.3f}', f'{value("eta", "bias", "B"):.3f}', f'{t.A_bias:.3f}', f'{t.B_bias:.3f}', f'{t.gamma_bias_theory:.3f}', f'{100*t.A_bias/1000:.2f}% / {100*t.B_bias/500:.2f}%'])
    out += [table(['n', 'η Bias A', 'η Bias B', 'γ Bias A', 'γ Bias B', 'γ Bias理论值', 'γ相对Bias A/B'], mmle_rows),
            r'原版MMLE令$\hat\gamma=X_{(1)}$，删除一个最小观测后，用其余$X_i-X_{(1)}$估计β、η。给所有观测加常数c时，$\hat\gamma$也加c，差分观测完全相同，所以β、η及绝对位置误差的分布保持。这里的位置高估还有精确解释：对β=2，$X_{(1)}-\gamma\sim W(2,1000/\sqrt n)$，因而',
            r'$$Bias_\gamma=\frac{1000\sqrt\pi}{2\sqrt n},\qquad SD_\gamma=\frac{1000\sqrt{1-\pi/4}}{\sqrt n},\qquad RMSE_\gamma=\frac{1000}{\sqrt n}.$$',
            '这些绝对量不含γ。理论γ Bias由n=7的334.962下降到n=50的125.331；两批观察值围绕同一理论值波动。A批n=20的191.177比理论198.166低约2.34个理论MCSE，故不声称所有单批均落在单项95%理论区间；A/B该项差值+7.961仍落在两批差的95%区间内。',
            'η低估是当前实现与设定下的数值证据：n=7从−291.023到−299.408，n=50从−134.374到−135.255。扣除最小值使有效差分变小，与尺度低估方向相符；完整估计仍联合求β、η，不能把这一解释当作所有设定的偏差定理。',
            '## 哪些量不敏感，哪些量敏感？',
            table(['量', '位置改变的含义', '本次证据或限制'], [
                ['β、η的绝对误差；γ估计−γ的绝对误差', '平移等变方法的误差分布不随原点变', 'MMLE可直接由差分式证明；MLE方程、域及选最大似然根规则平移协变；WMLE需另看选根'],
                ['有解率、真值到样本最小值距离、有效支持间隙', '平移协变方程/规则下不受位置原点影响', '两批有解率差都在单项区间内；支持间隙诊断同尺度，见下表'],
                ['γ估计或样本最小值的绝对数值', '随γ整体平移', '不是精度改变的证据'],
                ['γ误差/γ、γ RMSE/γ', '分母减半会约翻倍', 'MMLE n=7相对Bias 33.58%→66.38%；n=50 12.60%→25.05%'],
                ['负γ估计所占比例', 'γ降低使同样绝对误差更易越过坐标0', '当前没有γ≥0截断，负估计被接受；比例见下表'],
                ['WMLE的最终候选根选择', '现选根评分含绝对位置，理论上可能受原点影响', '12000组存档根的±500平移未改选，包括20组多根；不证明全域不敏感']
            ]),
            'MLE采用既有有限驻点与局部极大根口径。位置域为样本均值−10×样本SD至样本最小值−ε，ε固定原始单位；平移时两端同步平移，形状上下界不变。因此当前MLE方程、验收与最大似然根选择具备平移协变结构，但数值精度与有限根搜索仍是实现限制。',
            r'WMLE的加权方程与位置域也平移协变，现选根评分为$\log^2(\beta/2)+[(\gamma/1000-0.9x_{(1)}/1000)/\max(x_{(1)}/1000,1)]^2$。平移−500会改变该评分，故不能将其最终实现宣称为普遍平移等变。A批5988组单根、12组三根；B批5992组单根、8组三根。将存档候选位置与样本最小值共同平移−500或+500后，全部12000组的选中根索引保持。这是针对已有候选集合的复核，**没有重新拟合**，不能排除其他样本、位置范围或数值求根误差中的位置效应。',
            '### 负位置估计：坐标效应的量化',
            '比例以各方法成功组为分母；负值没有被判失败。']
    negative_rows = []
    for method in METHODS:
        for n in SIZES:
            a = diag[(diag.batch == 'A') & (diag.method == method) & (diag.n == n)].iloc[0]
            b = diag[(diag.batch == 'B') & (diag.method == method) & (diag.n == n)].iloc[0]
            negative_rows.append([method, n, f'{a.negative_gamma_estimates}/{a.success} ({100*a.negative_share:.2f}%)', f'{b.negative_gamma_estimates}/{b.success} ({100*b.negative_share:.2f}%)'])
    out += [table(['方法', 'n', 'A：γ估计<0', 'B：γ估计<0'], negative_rows),
            '例如MLE n=7由10.61%变16.15%，WMLE n=7由0.083%变2.333%。变化兼有原点改变与不同随机样本两部分，不能直接作纯γ因果差值；当前的负估计被接受，因此负值增多不是本批失败的直接原因。',
            '## 边界距离与失败率：可以看到什么？',
            r'区分两个量：$d_{true}=X_{(1)}-\gamma$可对所有1200组计算；$d_{fit}=X_{min,retained}-\hat\gamma$只对成功估计计算。MMLE原完整样本的$X_{(1)}-\hat\gamma=0$是定义，不是贴边失败；它删除一个最小值，实际有效支持间隙是$X_{(2)}-X_{(1)}>0$。MLE/WMLE未删除样本。二者都可除以共同η=1000，且在同一输入平移时保持。',
            '成功估计的有效支持间隙中位数（原始单位；若需共同尺度比例除以1000）：']
    gap_rows = []
    for method in METHODS:
        for n in [7, 20, 50]:
            a = diag[(diag.batch == 'A') & (diag.method == method) & (diag.n == n)].iloc[0]
            b = diag[(diag.batch == 'B') & (diag.method == method) & (diag.n == n)].iloc[0]
            gap_rows.append([method, n, f'{a.fitted_retained_gap_median:.3f}', f'{b.fitted_retained_gap_median:.3f}', f'{b.fitted_retained_gap_median-a.fitted_retained_gap_median:+.3f}'])
    out += [table(['方法', 'n', 'd_fit中位数 A', 'd_fit中位数 B', 'B−A'], gap_rows),
            '这些成功组距离同量级，但不能用它们解释失败组的γ估计距离，因为失败组不存在可用γ估计。对MLE失败关系，改用对所有组都定义的d_true，以其同一个理论分布的四分位界值分层：界值为η√[−log(1−p)/n]，p=0.25/0.5/0.75，A/B使用完全相同的界值。下面为各层有解率（%）。']
    bin_rows = []
    for n in SIZES:
        for batch in ['A', 'B']:
            q = bins[(bins.n == n) & (bins.batch == batch)].sort_values('quartile')
            bin_rows.append([n, batch] + [f'{100*r.success_rate:.2f} ({int(r.success)}/{int(r.total)})' for r in q.itertuples()])
    out += [table(['n', '批次', 'Q1：距离最小', 'Q2', 'Q3', 'Q4：距离最大'], bin_rows),
            '在两批中，n=7的MLE有解率均由Q1约40%降至Q4约25%；n=20均由约96%降至约79%。这是同一个平移不变量与有限根可解性的共同关联：**观测到的是距离越大有解率越低，不能写成越靠真值边界越易失败**。它是描述性分层，不是控制其他样本形态后的因果分析，也不是γ依赖效应；层内比例的不确定性及多变量机制未在本简报另立检验。MMLE/WMLE在所有层均无失败。',
            '## 可作为论文稳健性证据吗？',
            '可以作为**固定β=2、η=1000及所列n下，对两个位置真值的有限补充检查**，并把MMLE的数学平移性质与数值比较分开。建议写：',
            '> 在β=2、η=1000、n=7/10/15/20/50且每条件1200次模拟下，将位置真值由1000改为500后，三方法的主要表现及MMLE尺度低估、位置高估结构保持；两批独立样本的150项性能差值中8项超出单项95%区间，但无一通过Holm多重比较校正，因此该检查未提供可确认的位置依赖性能差异，结论限于所考察设定。',
            '必须注明：种子包含γ，样本不同，差值含MC噪声；只检查两个γ与一个β/η组合；精度条件于各方法自身成功，MLE低n成功选择不能忽略；不拒绝差异不等于等价；自助法是近似推断；WMLE当前选根规则含原点项，局部候选复核不能证明全域平移等变。现有数据不支持“γ减小使方法更好/更差”，也不支持“所有位置真值均稳健”。',
            '如果后续需要专门隔离数值实现的原点效应，可另设同一组基础随机样本的成对平移检查；本任务按只分析既有批次执行，没有重抽样生成新的实验数据或重新估计。',
            '## 文件与复现',
            f'- {link("A汇总", ROOT / "W(2,1000,1000)/结果/三方法汇总.csv")}；{link("B汇总", ROOT / "W(2,1000,500)/结果/三方法汇总.csv")}。',
            f'- {link("全部150项差值、参照、噪声区间及校正p", HERE / "全部差异与噪声.csv")}；{link("支持距离与相对位置30行", HERE / "支持距离与相对位置.csv")}；{link("MLE理论距离分层40行", HERE / "MLE真值边界距离分层.csv")}。',
            f'- {link("MMLE位置偏差理论", HERE / "MMLE位置偏差理论.csv")}；{link("WMLE候选根平移复核12000行", HERE / "WMLE平移选根复核.csv")}；{link("核验摘要", HERE / "分析核验.json")}；{link("96文件SHA保护", HERE / "输入保护.json")}。',
            f'- 分析脚本：{link("compare.py", HERE / "compare.py")}；报告与量级参照脚本：{link("write_report.py", HERE / "write_report.py")}。',
            'PowerShell复现（项目已有科学运行环境；仅向本分析目录写入输出）：',
            '```powershell',
            "$env:PYTHONIOENCODING='utf-8'",
            "$env:OPENBLAS_NUM_THREADS='1'",
            "$env:OMP_NUM_THREADS='1'",
            f"& 'D:\\weibull\\python\\.venv\\Scripts\\python.exe' -B '{HERE / 'compare.py'}'",
            f"& 'D:\\weibull\\python\\.venv\\Scripts\\python.exe' -B '{HERE / 'write_report.py'}'",
            '```',
            'compare.py读取A/B标准CSV；额外的选根诊断读取邮件007旧批次和邮件013运行记录中的既有per_sample.csv.gz（路径明确写在脚本RAW映射），不会改写它们。报告写入前后再核对A/B全部文件SHA及清单；没有改两批数据、图、Excel、脚本或说明，没有新拟合、Git提交或推送。']
    report = '\n\n'.join(out) + '\n'
    (HERE / '两批真值比较.md').write_text(report, encoding='utf-8')
    current = {str(p) for name in ['W(2,1000,1000)', 'W(2,1000,500)'] for p in (ROOT / name).rglob('*') if p.is_file()}
    assert current == set(guard)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == value for p, value in guard.items())
    assert len(d) == 150 and d.outside_pointwise_noise.sum() == 8 and not d.holm_reject.any()
    print(json.dumps({'report_characters': len(report), 'precision_rows': 135, 'rate_rows': 15, 'protected_files_unchanged': len(guard), 'summary_values_rechecked': 270}, ensure_ascii=False))

if __name__ == '__main__':
    main()
