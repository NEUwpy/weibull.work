"""Revise annotation placement; preserve tables, equations and scientific results."""
from pathlib import Path
import re
import os

ROOT = Path(__file__).resolve().parents[1]

def replace_once(text, old, new):
    assert text.count(old) == 1, (old[:90], text.count(old))
    return text.replace(old, new, 1)

def caption(text, prefix, new):
    matches = [line for line in text.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, prefix
    return replace_once(text, matches[0], new)

def archived_source(folder, name):
    source = ROOT / 'shelve' / folder / name
    text = source.read_text(encoding='utf-8')
    def restore_link(match):
        target = match[2]
        if target.startswith(('https:', 'http:', '#')):
            return match[0]
        absolute = (source.parent / target).resolve()
        relative = absolute.name if absolute.name.startswith('Study01论文') else os.path.relpath(absolute, ROOT).replace('\\', '/')
        return match[1] + relative + match[3]
    return re.sub(r'(!?\[[^\]\n]*\]\()([^\n]*?)(\))', restore_link, text)

main = archived_source('正文', 'Study01论文初稿-v1.10.md')
app = archived_source('附录', 'Study01论文附录-v1.8.md')
main = main.replace('中文修订稿 v1.10', '中文修订稿 v1.11').replace('附录 v1.8', '附录 v1.9').replace('Study01论文附录-v1.8.md', 'Study01论文附录-v1.9.md')
app = caption(app, '> 中文修订稿', '> 中文修订稿 v1.9，与[正文 v1.11](Study01论文初稿-v1.11.md)配套。本附录补充实验设计、训练细节、初始化敏感性、完整分层结果及复现信息。')

main_caps = {
    '**图 1 ': r'**图 1  样本自适应偏移量选择方法。** **a，** 用模拟样本的实际候选损失训练损失曲线预测网络；**b，** 根据当前样本的预测损失选择偏移量，再由 MDM 估计参数。示意曲线连接 26 个候选点，橙色圆点表示所选偏移量；蓝色表示损失预测与选点，虚线表示网络参数更新。',
    '**图 2 ': r'**图 2  正偏移量对估计稳定性和联合误差的影响。** **a，** 26 个候选偏移量的汇总 $J_1$，标出网格最低点与固定偏移量 0.10；**b，** $\delta=0$ 与 $\delta=0.10$ 在 160 个参数组合上的组合内标准化估计 SD 分布，每个组合含 300 次重复抽样。小提琴表示分布，箱体表示四分位距和中位数，百分数表示组合间中位 SD 的降幅。',
    '**图 3 ': r'**图 3  固定宽度参数域对统一偏移量的影响。** **a，** 11 个参数域在 26 个候选偏移量上的汇总 $J_1$；**b，** 各域的离散最低点及最低 $J_1$ 以上 1% 内的候选范围，竖虚线表示固定偏移量 0.10。',
    '**图 4 ': r'**图 4  不同信息条件下的估计风险。** **a，** Default 与 L1–L6 的汇总 $J_1$，水平线段表示相对 Default 的降低幅度；虚线分隔条件平均规则 L1–L5 与逐样本事后参照 L6。**b，** 四个样本量下各规则的 $J_1$ 相对降幅，颜色和数字均表示百分比。',
    '**图 6 ': r'**图 6  有限样本波动与 MDM 偏移量选择。** **a，** 相同真参数 $(\beta,\gamma/\eta,n)=(3,0.5,10)$ 下三个确认样本的经验梯度轨迹；**b，** 搜索交点区域的局部放大。小圆点为重建节点，大圆点为 L6 交点。**c，** 20 个诊断单元的 2,000 个确认样本按单元内固定偏移量位置估计分为低、中、高三组后的平均超额损失，圆点为 26 个候选偏移量；**d，** 各单元内固定偏移量位置估计与 L6 偏移量的 Spearman 相关。',
    '**表 2 ': '**表 2  不同信息条件下的偏移量选择。**',
    '**表 3 ': '**表 3  样本自适应选择的汇总与分样本量联合误差。**',
    '**表 4 ': '**表 4  固定偏移量与样本自适应选择的逐参数误差。**',
}
for prefix, new in main_caps.items():
    main = caption(main, prefix, new)
main = caption(main, '注：各样本等权。', r'注：误差按第 2.2 节标准化。Bias 和 SD 为汇总误差的均值和标准差；P5–P95 为带符号误差的第 5—95 百分位区间。')

# Put statistical definitions where the evaluation procedure is introduced.
main = replace_once(main,
    '并分别报告三个参数的标准化 Bias、SD 和 RMSE。稳定性比较则先在每个参数组合内根据 300 次重复抽样计算标准化误差 SD，再汇总 160 个组合的分布。',
    '并分别报告三个参数的标准化 Bias、SD 和 RMSE。汇总时各样本等权，Bias 为标准化误差的均值，SD 包含组合内抽样波动和组合间平均误差差异。稳定性比较则先在每个参数组合内根据 300 次重复抽样计算标准化误差 SD，再汇总 160 个组合的分布。')
main = replace_once(main,
    '输入表示也在这批折外样本上进行过筛选，因此该结果是选定方法的折外评价，尚不是独立于方法筛选的最终确认；筛选过程见附录 B.3。',
    '输入表示筛选与主评价使用同一批折外样本，本文报告选定表示后的折外结果；筛选过程见附录 B.3。')
main = replace_once(main,
    '主结果的不确定性采用保持方法间配对关系的重复块 bootstrap。',
    '主结果的不确定性采用保持方法间配对关系的重复块 bootstrap，区间条件于已训练选择器和当前设计，不包含表示筛选与重新训练的不确定性。')
main = replace_once(main, '该区间条件于已训练选择器和当前设计，不包含表示筛选与重新训练的不确定性。', '')
main = replace_once(main,
    '上述展开只描述两条给定样本曲线的局部交点差；估计稳定性与风险变化仍由重复抽样评价，展开条件及边界见附录 B.7。',
    '估计稳定性与风险变化通过重复抽样评价，局部展开的详细条件见附录 B.7。')
main = replace_once(main, '按位置尺度比水平留出评价，样本自适应选择', '选定输入表示后，在按位置尺度比水平留出的折外评价中，样本自适应选择')
main = replace_once(main, '；评价样本参与过输入表示筛选，尚需独立确认。', '。')
main = replace_once(main, '对于范围较窄且事先明确的应用域，可依据该域的汇总风险曲线确定统一值；当前结果并不支持脱离评价范围推荐唯一的最优常数。', '对于范围较窄且事先明确的应用域，可依据该域的汇总风险曲线确定统一值。')
main = replace_once(main, 'L1—L2 与 MLP 的划分方式不同，前述降幅分别说明各自评价任务中的收益，不用于计算跨协议的净增益。', '')
main = replace_once(main, '这些结果为上述计算联系提供了关联性证据，但尚未确定网络具体利用了哪些样本特征，或分解各环节对收益的贡献。', '这些轨迹与分组结果为样本变化影响偏移量选择的计算联系提供了关联性证据。')
main = replace_once(main, '，不能全部解释为网络尚未学好。', '。')
main = replace_once(main, '这一同域比较与正文的未见位置尺度比水平评价承担不同任务；经验参照不等于精确的条件最优风险，与 L6 的剩余差距也不能完全归于不可获得的信息。', '这一同域比较检验模型对当前样本信息的利用程度；灵活规则与 L6 的剩余差距仍同时包含可改进的预测误差与事后信息差。')
main = replace_once(main, '该收益限于所评价的参数设计与样本量，独立于输入表示筛选的确认尚待完成。', '')

app_caps = {
    '**表 E1 ': '**表 E1  WMLE 与 LSE 在原参数尺度下的 Bias 和 RMSE。**',
    '**图 C1 ': r'**图 C1  利用初估参数选择偏移量的评价。** **a，** 12 种单步变体相对 Default 的 $J_1$ 差及配对重复块 bootstrap 95% 置信区间，正值表示误差更高；**b，** 最佳单步规则按真 $\beta$ 的结果；**c，** MDM-0.1 与 WMLE 初步 $\hat\beta$ 落入最近正确 $\beta$ 网格单元的比例。',
    '**图 D1 ': r'**图 D1  未见形状参数水平验证。** 逐一留出八个 $\beta$ 水平时，均值归一化 MLP、Default 和 L6 的 $J_1$。折线为主种子 42 的结果，蓝色阴影表示三个随机种子的取值范围。',
    '**图 E1 ': r'**图 E1  传统方法的分样本量参照。** 均值归一化 MLP、Default、L6、WMLE 和 LSE 在 $n=7,10,15,20$ 下的 $J_1$。',
    '**图 F1 ': r'**图 F1  不同决策条件下的确认风险。** **a，** 同一参数单元内 L6 事后偏移量的多样性；**b，** 五种决策条件在确认集上的均方损失 $\mathcal R=J_1^2$。',
    '**图 F2 ': r'**图 F2  参数条件下的效果分布。** 四个样本量下各 $(\beta,\gamma/\eta)$ 单元相对 Default 的 $J_1$ 降幅。勾边表示误差增加的单元，共 35 个；其余 125 个单元改善。',
    '**图 F3 ': r'**图 F3  $Z$-only 经验参照的数据量诊断。** 各样本量模型在固定确认集上的均方损失随训练样本数的变化；每个参数条件的拟合重复数依次为 40、80、120、160 和 200。',
}
for prefix, new in app_caps.items():
    app = caption(app, prefix, new)
app = replace_once(app, '本表仅定义分组，不表示估计性能。', '')
app = replace_once(app, '这一选择不表明样本均值归一化在其他任务中普遍优于均方根归一化。', '')
app = replace_once(app,
    '由于表示筛选与主结果使用同一批折外样本，主结果不构成独立于筛选的最终确认。本文的配对 bootstrap 条件于现有预测，不能消除这一选择效应；固定方案后的新增独立重复确认尚未完成。',
    '表示筛选与主结果使用同一批折外样本；配对 bootstrap 条件于现有预测，未计入表示筛选的不确定性。独立确认的安排见正文第 4.4 节。')
app = replace_once(app, '因此不能将汇总 SD 下降等同于所有组合内波动均下降。', '')
app = replace_once(app, '，用于观察典型误差与上尾误差，不在正文重复展开。', '，用于观察典型误差与上尾误差。')
app = replace_once(app, '这些折外模型的汇总表现不能直接当作一个在全部数据上重训模型的独立测试结果。', '本文主结果汇总这 20 个折外模型的预测；全部设计单元上的重训模型在附录 F 中单独评价。')
app = replace_once(app, '；边界解占比较低，但本诊断没有定量分解边界切换、曲线形态及其他因素对总体收益的贡献。', '。')
app = replace_once(app, '### F.4 数据量诊断\n\n', '### F.4 数据量诊断\n\n在固定候选规则及确认集后，逐步增加各参数条件的拟合重复数。由 160 增至 200 次时，均方损失 $\\mathcal R$ 降低 0.43%（以 160 次时的 $\\mathcal R$ 为分母），说明当前数据规模下增加训练样本仍可缓慢降低风险。\n\n')

main = main.replace('fig1_adaptive_selection_drawio.png', 'fig1_adaptive_selection_drawio_v111.png')
for stem in ['supp_fig_unseen_beta', 'supp_fig_quantile_rmse', 'supp_fig_parameter_landscape', 'supp_fig_z_only_learning_curve']:
    app = app.replace(f'{stem}.png', f'{stem}_v111.png')

for name, text in [('Study01论文初稿-v1.11.md', main), ('Study01论文附录-v1.9.md', app)]:
    (ROOT / name).write_text(text, encoding='utf-8', newline='\n')
print('Wrote v1.11 main and v1.9 appendix')
