"""Generate first-round method review boards from current source and local papers.

After discussion begins, edit the existing board and render it; do not regenerate
over feedback. This script never writes an estimator or a library source file.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import ast
import hashlib
import html
import json
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parent
LIBRARY = Path('D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法')
SKILL = Path('C:/Users/36089/.codex/skills/review-html')
sys.path.insert(0, str(SKILL / 'scripts'))
from math_html import render_html_batch

METHODS = [
    ('mdm', '最小差异法', '182-046', '谢里阳等，2025',
     '基于统计最小差异原理的Weibull分布参数估计方法'),
    ('mle', '极大似然估计', '182-105', 'Hideo Hirose，1996',
     'Maximum Likelihood Estimation in the 3-parameter Weibull Distribution: A Look through the Generalized Extreme-value Distribution'),
    ('wmle', '加权极大似然估计', '182-088', 'Denis Cousineau，2009',
     'Nearly unbiased estimators for the three-parameter Weibull distribution with greater efficiency than the iterative likelihood method'),
    ('lse', '最小二乘估计', '182-104', 'K. P. Soman 与 K. B. Misra，1992',
     'A Least Square Estimation of Three Parameters of a Weibull Distribution'),
    ('lre', '线性回归估计', '182-115', 'Chanseok Park，2017',
     'Weibullness Test and Parameter Estimation of the Three-Parameter Weibull Model Using the Sample Correlation Coefficient'),
    ('mm', '矩估计', '182-102', 'G. W. Cran，1988',
     'Moment Estimators for the 3-Parameter Weibull Distribution'),
    ('mmle', '修正极大似然估计', '182-119', 'Debasis Kundu 与 Mohammad Z. Raqab，2009',
     'Estimation of R = P(Y < X) for three-parameter Weibull distribution'),
]
NAMES = {m[0]: m[1] for m in METHODS}
STAMP = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
HEAD = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=PROJECT, text=True).strip()
snapshots = {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(relative):
    path = PROJECT / relative
    snapshots.setdefault(relative, {'sha256': digest(path), 'lines': path.read_text(encoding='utf-8').splitlines()})
    return snapshots[relative]


def excerpt(file, anchor, before=0, after=10):
    data = snapshot(file)
    positions = [i for i, line in enumerate(data['lines']) if anchor in line]
    if len(positions) != 1:
        raise ValueError(f'{file}: nonunique source anchor {anchor!r}: {positions}')
    start, end = max(0, positions[0]-before), min(len(data['lines']), positions[0]+after+1)
    return {'file': file, 'start': start+1, 'end': end, 'lines': data['lines'][start:end]}


def fixture(file, name):
    tree = ast.parse((PROJECT / file).read_text(encoding='utf-8'))
    for item in tree.body:
        if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in item.targets):
            return ast.literal_eval(item.value)
    raise ValueError(name)


def collect_cases():
    sys.path.insert(0, str(PROJECT / 'python'))
    import numpy as np
    from scipy.special import betaincinv
    from studies.common.runner import run_method
    output = {}
    def case(method, label, sample, expected, **kwargs):
        result = run_method(method, sample, **kwargs)
        selected = {k: result[k] for k in ['beta_hat', 'eta_hat', 'gamma_hat', 'converged']}
        selected.update(label=label, expected=expected, n=len(sample),
                        observations=[float(x) for x in sample], parameters=kwargs)
        return selected, result
    i = np.arange(1, 8)
    ideal = 1000+1000*np.sqrt(-np.log1p(-betaincinv(i, 8-i, .5)))
    output['mdm'] = []
    for rank in ['bernard', 'exact']:
        for delta in [0., .1]:
            row, _ = case('mdm', f'理想样本，{rank}秩，δ={delta:g}', ideal,
                          '原图4：δ=0时γ=990；δ=.1时γ=1025。原位置步长未完整给出，不能要求本连续程序逐值匹配。', offset=delta, rank_method=rank)
            output['mdm'].append(row)
    output['mle'] = [case('mle', 'Hirose Table 1 / case 2',
                         fixture('python/tests/test_mle_hirose1996.py', 'HIROSE_CASE2'),
                         'Table 2约为 β=4.529，η=6.239，γ=22.092；这里只核对结果，不证明经过GEV流程。')[0]]
    output['wmle'] = [case('wmle', 'Cousineau §4 十点算例',
                          fixture('python/tests/test_wmle_cousineau2009.py', 'COUSINEAU_X'),
                          '原文约 β=2.29，η=116.0，γ=283.7；当前权重表与印表分辨率不同。')[0]]
    output['lse'] = [case('lse', f'Soman–Misra Example {n}',
                         fixture('python/tests/test_lse_soman1992.py', f'SOMAN_EX{n}'),
                         '原表峰值约 β=1.603，η=39.26，γ=502.1。' if n == 1 else
                         '原表峰值约 β=.8361，η=8.8521，γ=99.9。')[0] for n in (1, 2)]
    output['lre'] = [case('lre', 'Park 24点 Proposed+Plot',
                         fixture('python/tests/test_lre_park2017.py', 'PARK_SAMPLE'),
                         'Table 1印β=1.363、η=15.116、γ=9.198；独立方程+OLS约β=1.363761，不能为凑末位改公式。')[0]]
    mm_sample = np.random.default_rng(0).weibull(2., 100)*100+10
    row, result = case('mm', '现有边界测试中的固定样本',
                       mm_sample, '这组不是原论文算例，用来显出位置修正及尺度重算的影响。', trace=True)
    row['raw_estimate'] = result['calculation']['selection']['raw_estimate']
    output['mm'] = [row]
    output['mmle'] = [case('mmle', '既有七点存档样本',
                          fixture('python/tests/test_mmle_kundu_raqab2009.py', 'SAMPLE'),
                          '单样本化简的独立得分根对照，非原文双样本R的完整算例。')[0]]
    return output


def content(unit_id, title, markup, kind='text'):
    return {'id': unit_id, 'title': title, 'mode': 'content', 'options': [
        {'id': unit_id+'-content', 'label': title,
         'blocks': [{'id': unit_id+'-body', 'kind': kind, 'html': markup}]}]}


def decision(unit_id, title, options):
    return {'id': unit_id, 'title': title, 'mode': 'choices', 'inline': True,
            'selection_mode': 'single', 'selected_ids': [],
            'options': [{'id': ident, 'label': label,
                         'blocks': [{'id': ident+'-text', 'kind': 'text', 'html': text}]}
                        for ident, label, text in options]}


class Review:
    def __init__(self, method, number):
        self.method, self.number = method, number
        self.units, self.paper_ranges, self.code_ranges = [], [], []

    def paper(self, start, end, label=''):
        self.paper_ranges.append((start, end))
        return f'<a href="assets/evidence.html#paper-L{start}" target="_blank" rel="noopener">{self.number} 原文 L{start}–{end}{html.escape(" · "+label) if label else ""}</a>'

    def code(self, file, anchor, before=0, after=9):
        ref = excerpt(file, anchor, before, after)
        self.code_ranges.append(ref)
        escaped = '\n'.join(f'{i:>4}  {line}' for i, line in enumerate(ref['lines'], ref['start']))
        return (f'<p style="font-size:14px;color:#52645d"><a href="assets/evidence.html#code-{len(self.code_ranges)}" '
                f'target="_blank" rel="noopener">{html.escape(file)} · L{ref["start"]}–{ref["end"]}</a></p>'
                f'<pre style="overflow:auto;background:#132723;color:#e9f0ec;padding:16px;border-radius:8px;font:14px/1.7 Consolas,monospace"><code>{html.escape(escaped)}</code></pre>')

    def section(self, ident, title, markup, kind='text'):
        self.units.append(content(ident, title, markup, kind))

    def compare(self, ident, title, original, current, assessment, proposal, impact):
        pair = (f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr));gap:24px">'
                f'<div><p style="color:#526d64;font-weight:650">原文依据</p>{original}</div>'
                f'<div><p style="color:#526d64;font-weight:650">当前实现</p>{current}</div></div>'
                f'<p><strong>核对判断：</strong>{assessment}</p>'
                f'<p><strong>可能修改：</strong>{proposal}</p><p><strong>影响：</strong>{impact}</p>')
        self.section(ident, title, pair)

    def choose(self, ident, title, options):
        self.units.append(decision(ident, title, options))


def mdm(r):
    r.section('identity', '1 方法与核对范围', '<p>论文的<mark>伪尺度离散度、条件最小差异与正偏移</mark>已在现行程序中体现；默认秩、搜索方式和边界返回规则仍有差异。优先讨论这三处，再决定怎样修改同一个 <code>mdm.py</code>。</p><p>以下提议尚未实施。原文未写全的网格与多交点规则，按“实现设置”讨论，不冒充作者规定。</p>')
    r.section('core', '2 已对应的统计构造',
              '<p>给定位置和形状，每个观测反算一个伪尺度；在固定位置处最小化其标准差，最终尺度取均值。</p>'
              + r.paper(65, 76, '式(3)(4)') + '；' + r.paper(133, 146, '式(6)(7)')
              + r'<p>$$\eta_i(\beta,\gamma)=\frac{t_{(i)}-\gamma}{[-\ln(1-p_i)]^{1/\beta}},\quad \beta^*(\gamma)=\arg\min_\beta \sigma_\eta(\beta,\gamma),\quad \widehat\eta=\frac1n\sum_i\eta_i(\widehat\beta,\widehat\gamma).$$</p>'
              + '<p>这不是直接把β、γ联合调到最小标准差，也不是按真值选择偏移。</p>'
              + r.code('python/methods/mdm.py', 'def calculate_eta_std(', after=5)
              + '<p><strong>标准差分母：</strong>代码取 <code>ddof=1</code>；本次核对的原文段落未明确分母。若改变分母，梯度和固定δ的含义一起改变，不能当成无关的代码清理。</p>')
    r.compare('ranks', '3 中位秩：精确式还是近似式',
              '<p>式(3)使用F分布中位数定义精确中位秩，等价于Beta分布中位数。</p>'+r.paper(65, 76, 'PDF第2页／印刷109页')
              + r'<p>$$p_i=\operatorname{Beta}^{-1}_{i,n+1-i}(0.5).$$</p>',
              '<p>MDM默认 <code>rank_method="bernard"</code>，精确秩已是同一程序的可选参数。</p>'
              + r.code('python/base.py', "if self.rank_method == 'exact':", before=1, after=4),
              '属于绘图概率定义的替换，不能只说“程序流程完全对应原文”。',
              '如确定以2025年式(3)作为方法定义，在mdm.py中把默认秩改成精确式，计算、流程说明及概率图一起更新。',
              '会改变伪尺度、β、γ、η；历史结果按旧源码追溯。AI偏移模型原有训练口径也需重新评估，不能只切换网站默认值。')
    r.choose('ranks-choice', '3.1 中位秩的处理', [
        ('rank-keep', '保持现有默认近似秩', '<p>不改变估计；明确标示Bernard近似与原文式(3)的差别。</p>'),
        ('rank-exact', '把同一MDM程序的默认秩改为精确式', '<p>按原文式(3)统一默认概率；补充旧结果差异和AI适用性核对。</p>')])
    r.compare('search', '4 连续求解与原文离散搜索',
              '<p>位置从最小观测向下搜索；形状序列举例0.10、0.11、0.12……最大值如20；式(7)给离散前向差分。</p>'
              + r.paper(123, 127, '§2搜索描述')+'；'+r.paper(141, 146, 'PDF第4页／印刷111页')
              + r'<p>$$g_h(\gamma)=\frac{\sigma_{\min}(\gamma+h)-\sigma_{\min}(\gamma)}h.$$</p>'
              + '<p>上式用h重写增量，避免原式中梯度与增量的符号混用。论文没有写全γ步长、下界、多交点与停止规则。</p>',
              '<p>β在0.1–15内连续有界优化；内部位置梯度主要用中心差分，靠近边界用单侧差分，再用Brent求g(γ)=δ。60点几何曲线同时用于诊断。</p>'
              + r.code('python/methods/mdm.py', 'nominal_h = scale * 1e-5', before=2, after=7)
              + r.code('python/methods/mdm.py', "bounds=(0.1, 15.0)", before=2, after=3),
              '统计构造有对应，但具体数值算法不同。连续算法不因不同就必然错误；离散算法也不因更像论文就自动更准确。',
              '先确定是否要求按离散构造计算。若采用，应在mdm.py中统一实现，并明确β步长、上限、γ序列及差分点归属；不能为凑图4的1025反推网格。',
              '影响离散误差、速度、根的位置和无交点概率。当前理想样本测试验证的是连续程序，不是原图4逐值复现。')
    r.choose('search-choice', '4.1 搜索与差分的处理', [
        ('search-continuous', '保留连续数值求解', '<p>保留现有估计口径，补清差分尺度、括根与网格的作用，准确说明与论文的数值差别。</p>'),
        ('search-discrete', '在mdm.py内统一改为离散搜索', '<p>先确定步长、范围、交点和停止规则，再改同一文件；新增设置单独明示。</p>')])
    r.compare('boundary', '5 无交点时，是否仍返回成功',
              '<p>论文以梯度达到正偏移的位置定位，δ=.1是120个案例的经验值。</p>'+r.paper(149, 159, '§3')
              + '<p>本次核对未见“近支撑端点自动设为交点”的规则；γ≥0截断和多交点选择也需作为项目规则说明。</p>',
              '<p>g(0)≥δ时取γ=0；右端探测仍不足δ时，取极靠近最小观测的内部点，并记录 <code>virtual_gradient=offset</code>。该位置不是已验证的方程根。</p>'
              + r.code('python/methods/mdm.py', '"virtual_gradient": float(offset)', before=3, after=3),
              '右端外推是当前增加的返回规则。真实过程图已将其标为外推，但run仍可能作为成功返回；显示真实不等于判据已满足。',
              '优先决定外推结果的成功语义，再单独讨论非负位置约束；不能用人为目标梯度证明找到根。',
              '改为失败会减少成功样本，并改变蒙特卡洛成功率和按成功样本汇总的统计。若保留近似估计，应与已达判据的结果区分。')
    r.choose('boundary-choice', '5.1 右端外推的返回方式', [
        ('edge-keep', '保留现有返回规则', '<p>保持结果与成功口径；继续清楚显示right_edge_fit和未验证残差。</p>'),
        ('edge-approx', '返回近似状态，单独统计', '<p>保留估计值，状态明确为近似；API、页面和统计不得混作已求得偏移方程根。</p>'),
        ('edge-fail', '未验证交点则返回失败', '<p>不返回外推三参数；保留探测证据和失败原因，更新成功率解释。</p>')])
    r.section('paper-images', '6 原PDF中的关键公式',
              '<p>精确秩见PDF第2页式(3)；离散差分见第4页式(7)。</p>', 'text')
    r.units[-1]['options'][0]['blocks'].extend([
        {'id': 'pdf-rank', 'kind': 'image', 'src': 'assets/pdf-rank.png', 'alt': '原PDF第2页，精确秩与伪尺度公式(3)(4)'},
        {'id': 'pdf-difference', 'kind': 'image', 'src': 'assets/pdf-difference.png', 'alt': '原PDF第4页，离散梯度公式(7)及上下文'}])


def mle(r):
    r.section('identity', '1 先明确MLE要对应什么',
              '<p>现行 <code>mle.py</code> 调用公共辅助函数，在<mark>β≥1、γ非负的范围内寻找标准似然的有限局部极大候选</mark>。Hirose论文则给出GEV空间的具体求解方案。部分算例数值一致，不能证明经过了同一算法。</p><p>辅助函数仍属于这一个MLE实现，不是供用户选择的第二版本。</p>')
    r.compare('algorithm', '2 Weibull条件剖面与GEV流程',
              '<p>附录1：Gumbel初值，k=±Δk，逐k二次外推σ、μ并作Newton求解，再精化三参数、检查鞍点和角点。Δk=.01为建议例值。</p>'
              + r.paper(252, 290, '附录1／PDF第9–10页'),
              '<p>固定γ求β，恢复η，扫描位置得分与似然峰，选择有限候选中似然最大的点；没有GEV参数化、Gumbel初值或观察信息矩阵检验。</p>'
              + r.code('python/methods/profile_solvers.py', 'cache[g] = mle_profile(z, g, shape_lower=1.)', before=2, after=4),
              '标准似然函数对应，不等于完整复现Hirose的数值流程。是否改求解器，取决于产品希望实现一般MLE还是作者的具体算法。',
              '先选定目标；若保留条件剖面，引用Hirose只作数值基准。若决定按附录重做，在mle.py及其同一套辅助函数内修改。',
              'GEV路线是实质求解改造，涉及参数变换、初值、可行性、鞍点及角点；不能只替换流程文字。')
    r.choose('algorithm-choice', '2.1 MLE的实现目标', [
        ('mle-profile', '保留标准似然条件剖面实现', '<p>说明受限域及有限候选的含义，以论文数据作数值核对；不称Hirose完整算法复现。</p>'),
        ('mle-gev', '按Hirose附录改造同一MLE实现', '<p>先确定参数域和边界约定，再在现有入口内实施GEV算法，逐步骤与原算例验收。</p>')])
    r.compare('domain', '3 非负位置约束与参数发散',
              '<p>论文讨论负位置、参数发散和Gumbel极限；部分样本不应简单等同于非负位置下的两参数拟合。</p>'+r.paper(49, 74, '引言及嵌入模型'),
              '<p>公共距离函数拒绝γ&lt;0；β下界为1。当前会在受限域中比较γ=0候选，不能搜索论文涉及的负位置方向。</p>'
              + r.code('python/methods/conditional_profiles.py', 'if not np.isfinite(gamma) or gamma < 0 or np.any(d <= 0):', before=2, after=2),
              'β≥1与Hirose本文采用的条件并不冲突；γ≥0则缩小了当前的估计域。受限MLE与一般三参数模型的结论须分开。',
              '如果目标是寿命场景下的受限MLE，可以保留并明示。若要扩展位置域，需设计负方向搜索与发散识别，不宜只删一个if。',
              '会改变边界解、失败/发散分类和结果比较；增加搜索范围也不能自动证明找到全局最大值。')
    r.compare('endpoint', '4 支撑边界：报告极限还是接纳角点',
              '<p>附录Step 5在k=1角点最优时给出γ=x_min、β=1、η=mean(x−x_min)。</p>'+r.paper(286, 290, 'PDF第10页／印刷52页'),
              '<p>仅返回γ&lt;x_min的有限候选。β=1的支撑边界似然单列诊断，即便它高于所选候选，也不作为实际估计返回。</p>'
              + r.code('python/methods/profile_solvers.py', 'eta_limit = float(np.mean(x - x[0]))', after=11),
              '这是不同的输出约定，不是显示格式差异。不能把当前no_finite_local_maximum解释为已经覆盖了作者角点处理。',
              '与实现目标一起确定是否接纳角点。若接纳，输入支持检查、概率图及后续模拟有效性检查也要同步定义。',
              'γ等于最小观测会改变后续对数距离及拟合度处理；不能在未同步约定时只放宽求解器边界。')
    r.choose('endpoint-choice', '4.1 支撑边界的输出约定', [
        ('endpoint-open', '保持开放支持域，边界仅作诊断', '<p>保留当前有限估计口径；明确显示边界极限与有限候选的似然比较。</p>'),
        ('endpoint-corner', '按作者规则纳入β=1角点', '<p>在同一MLE实现中纳入，并统一后续支持检查和未定义的概率图量。</p>')])
    r.section('numerics', '5 可以保留的数值处理与验证边界',
              '<p>归一化、中心化对数距离、log-sum-exp和Brent括根用于数值稳定，不必为了“像原文”删除。位置有限网格及各峰精化仍不构成穷尽全部峰的证明。</p>'
              + r'<p>$$\widehat\eta(\beta,\gamma)=\left[\frac1n\sum_i(t_i-\gamma)^\beta\right]^{1/\beta}.$$</p>'
              + r.code('python/methods/conditional_profiles.py', 'log_mean_power = logsumexp(beta * z) - np.log(len(d))', before=1, after=4)
              + '<p><strong>转录核对：</strong>附录式(13)原PDF为σ₀=(√6/π)s≈0.779697s；现有Markdown把根号范围转录得不一致。下图用于核对，当前程序没有使用该GEV初值，不据此修改估计器。</p>')
    r.units[-1]['options'][0]['blocks'].append({'id': 'pdf-initial', 'kind': 'image', 'src': 'assets/pdf-initial.png', 'alt': 'Hirose原PDF第10页，印刷52页，式(13)(14)'})


def wmle(r):
    r.section('identity', '1 已对应的加权方程',
              '<p>现行WMLE使用J₁、J₂、J₃中位数权重，形状/位置加权方程与尺度闭式解有对应。原文符号为γ=形状、β=尺度、α=位置；下文统一映射为β、η、γ。</p>'
              + r.paper(88, 104, '式(3)') + '；' + r.paper(178, 192, '式(4)及插值')
              + r'<p>$$T_1=\frac{J_2}{\beta}+\overline{\ln d}-\frac{\sum_i d_i^\beta\ln d_i}{\sum_i d_i^\beta},\quad T_2=\overline{d^{-1}}\frac{\sum_i d_i^\beta}{\sum_i d_i^{\beta-1}}-J_3,\quad d_i=t_i-\gamma.$$</p>'
              + '<p>求解器怎样找到零点与这些方程是否正确，是两个问题；更换未被作者指定的优化器，本身不必然改变统计构造。</p>')
    r.compare('weights', '2 权重覆盖：表内插值与表外替代',
              '<p>J₃随候选形状变化；作者明确使用查表和线性插值。n&gt;16时，文中建议按标准指数样本构造估计权重。</p>'+r.paper(144, 150, '校准')+'；'+r.paper(186, 194, '插值与大n'),
              '<p>J₃表覆盖至n=100、形状约0.1–5；查询把形状截至表端，但候选形状可接近9.99。n&gt;100时使用渐近近似，形状≤1时返回2。J₁则有精确Gamma中位数计算，不应与J₃混为同一种表外规则。</p>'
              + r.code('python/methods/wmle.py', 'gamma_clamped = max(0.1, min(5.0, gamma))', after=8)
              + r.code('python/methods/wmle.py', 'if n > available_ns[-1]:', after=6),
              '表内线性插值是作者明确采用的；表外固定端点或常数是当前的补充近似，不能自动归给论文。',
              '先决定保留近似并明确范围，还是表外拒绝；若要扩表，应按原构造校准、保存种子和误差，再更新同一权重文件及wmle.py。',
              '拒绝表外会缩小可用范围；扩表会改变权重和估计，需单独的校准验证，本轮不运行新的大规模权重模拟。')
    r.choose('weights-choice', '2.1 表外权重的处理', [
        ('weights-keep', '保留近似，结果明确标记', '<p>保持可用范围，返回权重是否截断、表外规则及实际权重；统计区分表内与表外。</p>'),
        ('weights-reject', '表外明确返回不可用', '<p>仅在已有有效权重覆盖内求解；同一wmle.py明确报告超界原因。</p>'),
        ('weights-extend', '先校准权重，再扩展同一实现', '<p>先讨论n与β范围和校准精度，完成独立权重验证后再改程序。</p>')])
    r.compare('domain', '3 位置参数是否允许为负',
              '<p>位置α属于实数且小于min(X)，并未要求非负。</p>'+r.paper(42, 48, '§2参数域'),
              '<p>距离函数、残差函数和最终候选都限定γ≥0，扫描域也是[0,min(t))。</p>'
              + r.code('python/methods/conditional_profiles.py', 'or np.any(~np.isfinite(g)) or np.any(g < 0)', before=1, after=2),
              '当前解的是带非负约束的加权方程问题；它是有意义的寿命场景限制，但范围比原文窄。',
              '若确定扩展，须同时改公共距离检查、残差检查、位置网格和选根规则，并核对公共函数对MLE的影响。',
              '负位置候选可能改变最终解；有限负域搜索失败不等于证明原方程无根。')
    r.choose('domain-choice', '3.1 位置域的处理', [
        ('domain-nonnegative', '保留γ≥0的应用限制', '<p>保持当前行为，文档与结果中明确“非负位置约束”。</p>'),
        ('domain-real', '在同一WMLE中允许负位置', '<p>先确定搜索扩展及停止规则，补负位置例和等变性核对，不另建原文版本。</p>')])
    r.compare('acceptance', '4 零点、边界近似与多根选择',
              '<p>原文式(4)寻求平方残差目标的零点，没有规定当前的非负边界特许或多根距离排序。</p>'+r.paper(178, 190, '§4'),
              '<p>候选接受T₁²+T₂²≤10⁻⁸；若无候选，可接受γ=0处的残差容差近似。近最小残差候选再按距β=2、γ=.9min(t)的规则选根。</p>'
              + r.code('python/methods/profile_solvers.py', "kind='boundary_residual_tolerance'", before=3, after=7),
              '数值求根需要容差，容差本身不是错误。需讨论的是未达条件交点的边界近似是否与方程根同算成功，以及多根依据。',
              '保留实际残差和近似标记；可考虑近似单独统计或拒绝。多根排序若保留，应明示是项目规则，不能按真值选根。',
              '可能改变成功率及最终根；不同残差量的尺度和容差要做敏感性核对，不把更小阈值自动当作更正确。')
    r.choose('acceptance-choice', '4.1 近似边界结果的口径', [
        ('accept-keep', '保留成功口径并明示近似', '<p>维持现有行为，保留approximate_boundary_root和残差。</p>'),
        ('accept-separate', '近似结果单独列为一种状态', '<p>保留参数，但和已求得条件方程交点的结果分开汇总。</p>'),
        ('accept-reject', '取消边界近似特许', '<p>未通过所约定根判据时返回失败，保留诊断。</p>')])
    r.section('solver', '5 条件求根与原文目标：保留什么',
              '<p>先求T₁=0、沿条件轨迹求T₂=0，是求同一联立零点的一种数值策略。原文没有要求某个特定SciPy求解器；前端旧Nelder–Mead说法不能作为作者算法依据。当前有限扫描仍可能漏掉根，需要用独立求根与方程残差验证，而非为了外观换算法。</p>'
              + r.code('python/methods/conditional_profiles.py', "solution = _shape(t, weight=j2, upper=weights.SHAPE_UPPER)", before=2, after=7)
              + '<p>权重表在代码中自述来自作者仓库。本次核对了本地权重文件与原文若干表值，不把代码注释当作对整个上游仓库的独立来源验证。</p>')


def lse(r):
    r.section('identity', '1 White回归与F比最大化',
              '<p>当前LSE对应Soman–Misra论文的White回归/F比主方法。它的回归方向与LRE不同：</p>'
              + r'<p>$$X_i=E[W_{(i:n)}],\quad Y_i=\ln(t_i-\gamma),\quad Y_i=a+bX_i,\quad \widehat\beta=1/b,\quad\widehat\eta=e^a.$$</p>'
              + r.paper(66, 100, '式(4)–(6)及Procedure')
              + '<p>当前完整失效样本的F比判据与参数恢复有对应；没有理由为统一界面改成LRE的绘图位置回归。</p>')
    r.compare('means', '2 顺序统计量期望：数表与积分',
              '<p>White方法用reduced Log-Weibull顺序统计量的期望代替未知Xᵢ，并据此回归。</p>'+r.paper(66, 75, 'White方法'),
              '<p>不读取White原数表，直接对顺序统计量密度作数值积分，再按n缓存。积分区间[-60,10]、精度与预算是程序设置。</p>'
              + r.code('python/methods/lse.py', 'value, _ = integrate.quad', before=2, after=2),
              '目标量相同，数值获得方式不同。原表舍入与积分误差需分开；不是公式不一致就必须回退原数表。',
              '优先保留积分，补不同n下误差和区间稳定性验证；若要求历史表逐值复现，再核得对应版本的原数表。',
              '影响论文表值末位及速度；仅收紧算法容差不能证明已消除期望积分误差。')
    r.compare('search', '3 位置搜索：递减试探与几何网格精化',
              '<p>从t₍₁₎−.01开始，递减位置、计算F比，选F最大的一行。原文没有列全递减序列。</p>'+r.paper(80, 100, 'Procedure'),
              '<p>在非负位置域用默认200点几何网格，取最大点后在邻域连续精化。只精化当前最优网格点邻域。</p>'
              + r.code('python/methods/lse.py', 'mus = _build_geometric_mu_grid(t_min, mu_steps)', after=3)
              + r.code('python/methods/lse.py', 'best_idx = int(np.argmax(f_values))', after=4),
              'F比定义一致，但搜索序列与原文不同；连续最优点不必等于原表粗网格的峰值行。',
              '可保留几何搜索并说明；若重点是减少漏峰，先验证F曲线是否存在多个峰，再决定是否逐峰精化。',
              '网格与多峰处理会影响位置估计、运算量与稳定性；不应把原表峰值行当作连续最优点的唯一正确值。')
    r.choose('search-choice', '3.1 位置搜索的优化方向', [
        ('lse-search-keep', '保留当前网格及邻域精化', '<p>保持数值口径，补网格密度与论文表行对照。</p>'),
        ('lse-search-peaks', '先核验多峰，再考虑逐峰精化', '<p>以F曲线和独立搜索为证据；证实漏峰后修改同一lse.py。</p>')])
    r.section('coverage', '4 原文覆盖与当前实现边界',
              '<p>原文主方法重点讨论0&lt;形状&lt;3；另给3&lt;形状&lt;6的近似位置迭代和失效率估计方案。当前lse.py只实现White/F比主方法，不包含另两种构造。</p>'
              + r.paper(132, 168, '高形状扩展')
              + '<p>原文提到删失样本，当前统一输入与本方法验收以完整失效样本为准；不能据论文范围声称本网站已支持删失LSE。</p>'
              + '<p><strong>建议：</strong>先把当前名称与范围写清，不把全部原文内容强塞进一个含混LSE入口。若以后决定扩展，应先讨论方法身份、数据输入及判据，再修改这一个权威实现。</p>')


def lre(r):
    r.section('identity', '1 当前实现对应Proposed+Plot',
              '<p>Park论文既包含Weibullness检验，也包含Proposed+Plot、Proposed+MLE2等不同组合。<mark>现行LRE明确对应Proposed+Plot</mark>：先最大化相关系数估位置，再作概率图OLS。</p>'
              + r.paper(156, 170, '§5与Table 1')
              + '<p>本次没有发现必须替换核心统计构造的证据。以下首先列出可保留内容，不为了优化而硬造另一套LRE。</p>')
    r.section('positions', '2 绘图位置与回归方向已对应',
              '<p>原文与当前都使用n≤10时的Blom位置，n≥11时用(i−.5)/n。</p>'
              + r.paper(47, 55, '§2')
              + r'<p>$$p_i=\begin{cases}(i-3/8)/(n+1/4),&n\le10,\\(i-1/2)/n,&n\ge11,\end{cases}\quad y_i=\ln[-\ln(1-p_i)],\quad x_i=\ln(t_i-\gamma).$$</p>'
              + r.code('python/methods/lre.py', 'F = (ranks - 3 / 8)', before=1, after=4)
              + '<p>β是OLS斜率，η由截距恢复。代码中的时间归一化只平移横坐标，在恢复尺度时乘回t_min，不改变这一回归含义。</p>'
              + r.code('python/methods/lre.py', 'eta_hat = t_min * math.exp(-intercept / beta_hat)', before=1, after=2))
    r.compare('location', '3 相关系数最大化与导数求根',
              '<p>论文明确允许最大化R(μ)，或求式(3)的驻点。位置域为[0,x₍₁₎)。</p>'+r.paper(128, 148, '式(2)(3)'),
              '<p>在同一位置域内，对数间隔网格覆盖近端点，精化所有被网格夹住的相关系数峰，并比较候选。</p>'
              + r.code('python/methods/lre.py', '# 精化所有被网格夹住的峰', after=8),
              '属于作者明确给出的求解途径之一，不能因为没有直接求式(3)就判为不忠实。',
              '当前保留。后续若出现具体漏峰、单位变化或退化样本故障，再凭案例修改数值实现。',
              '不建议在没有故障证据时替换求解器；现有独立式(3)定根测试已能交叉核对结果。')
    r.section('rounding', '4 原表末位与程序复算',
              '<p>原表Proposed+Plot印β=1.363；现行程序与独立式(3)+OLS复算约1.363761，通常三位小数会写1.364。η、γ和相关系数与表中精度对应。</p>'
              + r.paper(158, 170, 'Table 1')
              + '<p><strong>判断：</strong>这是需要保留记录的表值末位差异，不能靠改绘图位置、回归方向或截断数值去强凑。当前证据不足以断言原文究竟采用了哪种末位处理。</p>')
    r.section('scope', '5 需要明确的范围与后续验证',
              '<p>当前R²按同一组Park分数计算，并等于最终OLS的ρ²；它不是原文Weibullness检验的p值或AD统计量。</p>'
              + r.code('python/methods/lre.py', 'residual = y - (beta_hat * x_vals + intercept)', after=3)
              + '<p>建议保留当前核心实现，维持n=10/11切换、时间单位变化、全等和近等样本的回归测试。正式的p值、AD检验以及Proposed+MLE2不在本次LRE优化中混入。</p>')


def mm(r):
    r.section('identity', '1 三个Weibull矩与显式解',
              '<p>Cran的矩是<mark>生存函数幂的积分矩</mark>，不是普通样本幂矩。当前k=1、2、4的矩计算与显式反解有对应。</p>'
              + r.paper(79, 128, '式(1)–(3)')
              + r'<p>$$\bar m_k=\sum_{r=0}^{n-1}(1-r/n)^k[t_{(r+1)}-t_{(r)}],\quad t_{(0)}=0.$$</p>'
              + r.code('python/methods/mm.py', 'd12 = m1 - m2', after=8)
              + '<p>主要待讨论处在显式解之后的位置和尺度处理。</p>')
    r.compare('scale', '2 位置调整后是否重算尺度',
              '<p>式(2c)给b=(m₁−a)/Γ(1+1/c)；负位置时建议用0估计a。该段没有明确交代是只替换位置，还是把新a再次代回尺度公式。</p>'
              + r.paper(89, 128, '参数公式及可采纳性'),
              '<p>若原始位置&lt;0，先取γ=0，再以原形状重算η=m₁/Γ(1+1/β)。记录中保留原始三元组及位置调整。</p>'
              + r.code('python/methods/mm.py', 'if location < 0.0:', after=4),
              '尺度重算是当前作出的解释；原文未明确说“必须重算”，也未明确说“禁止重算”。不能把解释分歧直接写成确定的公式错误。',
              '需共同确定输出规则：维持矩关系而重算尺度，或只按原文明确的位置替换、保留初次尺度。选择后直接修改mm.py并补边界算例。',
              '会改变被截零样本的尺度估计，以及Monte Carlo偏差和均方误差；正常未调整样本不受这项规则影响。')
    r.choose('scale-choice', '2.1 位置截零后的尺度约定', [
        ('mm-recompute', '保留当前尺度重算', '<p>保持第一矩关系，明确这是对原文边界建议的项目解释。</p>'),
        ('mm-keep-scale', '只替换位置，保留初次尺度', '<p>减少额外更新；明确新三元组不再同时满足原先的全部矩关系，独立验证影响。</p>')])
    r.compare('alternative', '3 超过最小观测时的替代位置',
              '<p>作者给出一种可能的替代位置a**，并非唯一强制规则。</p>'+r.paper(123, 128, 'a**')
              + r'<p>$$a^{**}=t_{(1)}-\frac{b^*\Gamma(1+1/c^*)}{n^{1/c^*}}.$$</p>',
              '<p>计算a**后再次max(0,a**)，并重算尺度；这是在原替代式上又加了一层截断和更新。</p>'
              + r.code('python/methods/mm.py', 'alt = x_min - scale * gamma_fn', after=5),
              '非负位置是论文明确要求，但a**自身又负时怎样处理，该段未给完整规则。二次截零是补足，不能冒称原式直接推出。',
              '可保留现补足并标记，或在替代位置不可采纳时明确失败。不能为了保持成功率无声增加其他方法回退。',
              '影响边界样本的估计与成功率；要同时记录原始位置、a**及最后采用的三元组。')
    r.choose('alternative-choice', '3.1 替代位置再次不可采纳时', [
        ('mm-alt-clamp', '保留二次截零并记录', '<p>维持当前返回口径；尺度是否重算依前一项决定。</p>'),
        ('mm-alt-fail', '明确返回不可采纳', '<p>不继续修造位置值；保留原始与替代值作为失败诊断。</p>')])
    r.section('admissibility', '4 不可采纳矩与二参对照',
              '<p>当前判据m₁−m₂&gt;m₂−m₄&gt;0与显式正形状/尺度相容，失败时不改用别的方法。原文说可采用其他估计方法，不等于允许本程序静默回退。</p>'
              + '<p>原文还建议比较二参与三参的b、c，但没有给“足够接近”的数值阈值。代码记录二参对照、没有自动选模，这一点可保留。</p>'
              + r.paper(174, 186, '二参与三参比较')
              + '<p>原论文两例所引原始样本本次未核得完整输入，当前测试主要验证矩恒等式、手算、等变性和边界行为；不称两例已经逐值复现。</p>')


def mmle(r):
    r.section('identity', '1 原文双样本与当前单样本化简',
              '<p>Kundu–Raqab原文研究两组独立Weibull样本，共同形状和位置、不同尺度，并估计R=P(Y&lt;X)。现行mmle.py采用它的<mark>固定最小值、删除一个观测、再迭代形状</mark>构造，化简为单样本参数估计。</p>'
              + r.paper(25, 44, '原文模型')+'；'+r.paper(65, 88, '式(4)(6)')
              + '<p>可称“基于Kundu–Raqab构造的单样本化简”；不能称已经实现整篇双样本应力–强度推断。本文只讨论当前这一套MMLE，不启用其他历史实现。</p>')
    r.section('construction', '2 删除最小观测与尺度映射',
              '<p>原文尺度θ用于指数项exp[−(x−μ)^α/θ]，与网站参数的对应是α=β、μ=γ、θ=η^β。</p>'
              + r'<p>$$\widehat\gamma=t_{(1)},\quad y_i=t_{(i)}-\widehat\gamma,\ i=2,\ldots,n,\quad q=n-1,\quad \widehat\eta=\left(q^{-1}\sum_{i=2}^n y_i^{\widehat\beta}\right)^{1/\widehat\beta}.$$</p>'
              + r.code('python/methods/mmle.py', 'gamma = float(self.data[0])', after=4)
              + '<p>删除的是一个最小观测，不是删除所有与最小值相同的观测。原文连续模型以严格次序统计量叙述；舍入造成并列最小值时，当前会失败，不能无声多删数据。</p>')
    r.compare('iteration', '3 不动点公式与数值停止条件',
              '<p>式(9)–(11)给h(α)=α和不动点更新，要求相邻迭代绝对差足够小；作者未证明收敛。</p>'+r.paper(105, 123, 'PDF第4页／印刷1841页'),
              '<p>把两组构造化简为一组保留样本，初值1、绝对步长容差10⁻⁸、预算10000次；用稳定指数权重计算。</p>'
              + r.code('python/methods/mmle.py', 'denominator = float(q * (weights @ logs))', before=2, after=5)
              + r'<p>$$\beta_{j+1}=\frac{q+\beta_j\sum_{i=2}^n\ln y_i}{q\sum_{i=2}^n w_i(\beta_j)\ln y_i},\quad w_i=\frac{y_i^\beta}{\sum y_i^\beta}.$$</p>',
              '这里的单样本式是化简推导，不是原文直接印出的单样本公式。现有独立剖面得分根测试支持该化简；初值、容差与预算是明确的数值设置。',
              '可保留构造和现有停止条件；考虑在同一程序增加最终得分残差及尺度无关的停止诊断。若改变接受标准，须明确会改变哪些成功/失败。',
              '迭代步长小不总能独自证明满足得分方程。增加诊断不必改变返回值；把诊断升级为拒绝条件则需要讨论后验证。')
    r.choose('iteration-choice', '3.1 停止与残差检查', [
        ('mmle-diagnostic', '保留停止规则，补残差诊断', '<p>优先增加可核对证据，暂不改变成功集合。</p>'),
        ('mmle-score', '共同设定步长与得分的接受标准', '<p>先确定残差归一化及容差，再更新同一mmle.py的停止/失败规则。</p>')])
    r.compare('r2', '4 R²=0是占位值，不是拟合结果',
              '<p>原文并未定义本网站的全样本概率图R²。当前位置取样本最小值，该点对数平移距离为−∞，不能直接套通常全样本图。</p>'+r.paper(65, 72, '删最小值构造'),
              '<p>run返回R²=0.0；代码注释及过程记录明确它是历史占位。页面或导出若按普通R²排序，仍可能误解。</p>'
              + r.code('python/methods/mmle.py', 'return [beta, eta, gamma, 0., True]', after=0),
              '这是返回契约与呈现语义的问题，不是形状/尺度公式错。原样保留0会有被误用的风险。',
              '可以保留兼容字段并带未定义标志，或把R²正式改为null；不能自行补一个“看着合理”的全样本值。',
              '改null涉及结果类型、API、表格、排序及既有导出。若定义保留样本R²，也必须命名清楚，不与全样本指标混用。')
    r.choose('r2-choice', '4.1 未定义拟合度的输出方式', [
        ('mmle-r2-flag', '暂保留兼容值，明确未定义', '<p>新增有效性语义，展示为“未定义”，统计与排序跳过该占位。</p>'),
        ('mmle-r2-null', '统一返回null并调整调用方', '<p>使数据本身表达未定义；同步更新API类型、展示、统计和导出契约。</p>')])
    r.section('pdf-proof', '5 原PDF的不动点构造',
              '<p>下图为原PDF第4页、印刷1841页的式(9)–(11)及停止条件。原始公式保留双样本，前面用网站符号呈现的是有标识的化简推导。</p>')
    r.units[-1]['options'][0]['blocks'].append({'id': 'pdf-fixed-point', 'kind': 'image', 'src': 'assets/pdf-fixed-point.png', 'alt': 'Kundu–Raqab原PDF第4页，式(9)–(11)与绝对差停止条件'})


BUILDERS = dict(mdm=mdm, mle=mle, wmle=wmle, lse=lse, lre=lre, mm=mm, mmle=mmle)


def main():
    ROOT.mkdir(exist_ok=True)
    cases = collect_cases()
    results = []
    for method, name, number, author, title in METHODS:
        root = ROOT / ('method-'+method)
        if any((root / file).exists() for file in ('history.jsonl', 'draft.json', 'feedback.json', 'session.json')):
            raise ValueError('Review already exists; preserve feedback and edit its board instead: '+method)
        assets = root / 'assets'
        assets.mkdir(parents=True, exist_ok=True)
        (root / '.gitignore').write_text('/session.json\n/listener.json\n/draft.json\n/draft.previous.json\n/server.log\n/assets/methods.html\n*.tmp\n__pycache__/\n', encoding='utf-8')
        review = Review(method, number)
        BUILDERS[method](review)
        rows = []
        for case in cases[method]:
            values = [case[p] for p in ['beta_hat', 'eta_hat', 'gamma_hat']]
            rendered = ''.join('<td>'+html.escape(f'{v:.8g}' if isinstance(v, (int, float)) else str(v))+'</td>' for v in values)
            rows.append('<tr><td>'+html.escape(case['label'])+'</td>'+rendered+'</tr>')
        table = '<div style="overflow:auto"><table style="font-size:16px"><thead><tr><th>核对输入</th><th>β</th><th>η</th><th>γ</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
        notes = ''.join('<p>'+html.escape(text)+'</p>' for text in dict.fromkeys(c['expected'] for c in cases[method]))
        if method == 'mm':
            notes += '<p>该固定样本的初次公式三元组为'+html.escape(json.dumps(cases[method][0]['raw_estimate'], ensure_ascii=False))+'。其中原始位置不可采纳，不能把这组三元组当作建议直接返回的合法估计。</p>'
        final_section = max(int(u['title'].split(' ', 1)[0].split('.')[0]) for u in review.units)+1
        review.section('verification', f'{final_section} 当前数值核对与测试能证明什么', table+notes+
                       '<p>本轮重新执行七个方法的既有原文/公式套件，共80项通过。通过的是已覆盖的公式、若干算例和边界；不是原文所有算法步骤、数据及蒙特卡洛表已复现。上表为少量确定性核对，不是新蒙特卡洛性能结论。</p>', 'visual')
        pdf = next(LIBRARY.glob(number+'_*.pdf'))
        paper = LIBRARY / (number+'-pdf原文.md')
        main_source = snapshot('python/methods/'+method+'.py')
        refs = sorted({x['file'] for x in review.code_ranges} | {'python/methods/'+method+'.py'})
        source_manifest = [{'path': path, 'sha256': snapshot(path)['sha256']} for path in refs]
        if method == 'wmle':
            source_manifest.append({'path': 'python/methods/j3_weights.tsv',
                                    'sha256': digest(PROJECT / 'python/methods/j3_weights.tsv')})
        review.section('sources', f'{final_section+1} 论文、源码与核对快照',
                       '<p><strong>'+html.escape(author)+'</strong> · '+html.escape(title)+'</p>'
                       +'<p>当前方法入口：<code>python/methods/'+method+'.py</code>。核对时间 '+STAMP+'；Git基线 '+HEAD[:10]+'，工作区含未提交改动，以下哈希标识本轮实际文件。</p>'
                       +'<p style="font:14px/1.8 Consolas,monospace;overflow-wrap:anywhere">入口SHA-256 '+main_source['sha256']+'</p>'
                       +'<p><a href="assets/evidence.html" target="_blank" rel="noopener">查看逐项原文与源码摘录</a> · <a href="assets/provenance.json" target="_blank" rel="noopener">查看来源与哈希</a> · <a href="assets/methods.html" target="_blank" rel="noopener">其他方法</a></p>'
                       +'<p>摘录用于本轮讨论，不是另一份可编辑的算法实现。源文件变化后应重新核对；审阅期间不修改估计器或原论文。</p>')
        board = {'id': 'weibull-method-'+method+'-20261102', 'title': f'{name} {method.upper()} · 原文与实现',
                 'document': True, 'revision': 1, 'require_confirmation': True,
                 'archive_plan': f'依据最终确认的逐项决定修改 D:/weibull/python/methods/{method}.py 及实际共用辅助函数，同步方法说明、流程引用和测试；保留同一方法入口，不新建原文/工程分支。先展示具体修改与核对结果，再完成本方法审定记录 D:/weibull/docs/method-reviews/{method}.md。未决定的算法问题保持现状；历史数据不重算，不推送或部署。',
                 'units': review.units}
        blocks = [b for u in board['units'] for o in u['options'] for b in o['blocks'] if 'html' in b]
        for block, markup in zip(blocks, render_html_batch([b['html'] for b in blocks])):
            block['html'] = markup
        (root / 'board.json').write_text(json.dumps(board, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        provenance = {'method': method, 'checked_at': STAMP, 'head': HEAD, 'working_tree_modified': True,
                      'paper': {'id': number, 'title': title, 'pdf_path': str(pdf), 'pdf_sha256': digest(pdf),
                                'markdown_path': str(paper), 'markdown_sha256': digest(paper)},
                      'sources': source_manifest, 'cases': cases[method], 'tests': '80 passed in 7.22s; seven existing method suites, 2026-11-02'}
        (assets / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        evidence(review, paper, assets, source_manifest)
        results.append({'method': method, 'name': name, 'root': str(root), 'paper': number,
                        'units': len(review.units), 'sources': source_manifest})
    (ROOT / 'method-reviews.json').write_text(json.dumps({'checked_at': STAMP, 'methods': results}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps([{'method': r['method'], 'sections': r['units']} for r in results], ensure_ascii=False))


def evidence(review, paper, assets, sources):
    sections = []
    paper_lines = paper.read_text(encoding='utf-8').splitlines()
    for start, end in sorted(set(review.paper_ranges)):
        text = '\n'.join(paper_lines[start-1:end])
        sections.append(f'<section id="paper-L{start}"><h2>{review.number} 原文 L{start}–{end}</h2><pre>{html.escape(text)}</pre></section>')
    for i, ref in enumerate(review.code_ranges, 1):
        text = '\n'.join(f'{j:>4}  {line}' for j, line in enumerate(ref['lines'], ref['start']))
        sections.append(f'<section id="code-{i}"><h2>{html.escape(ref["file"])} L{ref["start"]}–{ref["end"]}</h2><pre><code>{html.escape(text)}</code></pre></section>')
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>原文与源码摘录</title><style>body{max-width:1100px;margin:40px auto;padding:0 20px;font:16px/1.8 system-ui,sans-serif;color:#213930;background:#f5f7f4}section{margin:36px 0;scroll-margin-top:20px}h1{font-size:28px}h2{font-size:19px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.8 Consolas,monospace;background:white;padding:20px;border:1px solid #dbe4dc;border-radius:10px}a{color:#17634a}</style><h1>'+NAMES[review.method]+' · 核对摘录</h1><p>以下是'+STAMP+'读取的本地原文与当前源码片段。行号分别对应原文Markdown与Python文件；数学转录以原PDF核对为准。</p><a href="../index.html">返回本方法审阅</a>'+''.join(sections)+'</html>'
    (assets / 'evidence.html').write_text('\n'.join(line.rstrip() for line in page.split('\n')), encoding='utf-8')


def render_boards():
    for method, *_ in METHODS:
        root = ROOT / ('method-'+method)
        subprocess.run([sys.executable, str(SKILL / 'scripts/review.py'), 'render', '--root', str(root)], check=True, capture_output=True)
        page = root / 'index.html'
        markup = page.read_text(encoding='utf-8')
        # Readability adjustments only; keep the skill's feedback UI and protocol.
        markup = markup.replace('</head>', '<style id="method-review-type">body{font-size:16px}.block table{font-size:16px}.option h3{font-size:16px}.block pre{max-width:100%}math[display="block"]{display:block;max-width:100%;overflow-x:auto;overflow-y:hidden;padding:.5em 0}</style></head>', 1)
        page.write_text(markup, encoding='utf-8')
    print('rendered seven method reviews')


if __name__ == '__main__':
    if '--render-only' in sys.argv:
        render_boards()
    else:
        main()
