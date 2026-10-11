"""从保存的过程数据核对逐法论证并修改报告文字；--verify只核对。

不抽样、不拟合、不制图，不改变原估计、工作簿或图片。
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
from 共用 import write_atomic

REPORT = ROOT / '报告1：高形状参数下的估计偏移.md'
README = ROOT / 'README.md'
RESULT = ROOT / '交付/结果/报告1'
RECORD = HERE / '20261011-逐法偏移因果解释.json'
SOURCE_SHA256 = 'b07c00705bf5b408266746f5247115711313b7242c0bc01242a916030e56b8a7'
SOURCES = {
    'criteria': RESULT / '中间数据/逐法过程曲线.json',
    'selected_cases': RESULT / '中间数据/配对单例与推导核验.json',
    'mmle': HERE / '20261011-MMLE估计与曲线.json',
    'original_estimates': HERE / '输入快照/原案例估计.json',
    'original_samples': HERE / '输入快照/原案例核验.json',
    'figure3_program': HERE / '绘制样本相容分布.py',
    'figure3_selection': HERE / '绘制寿命对照图.py',
}

REPLACEMENTS = [
    (
        '配对对照中，高β样本在真位置附近的条件最小标准差较平，梯度偏小。固定正阈值要在更大的γ处才能达到，该位置的条件β和η随之降低。',
        '由伪尺度式可见，β较大时，各观测的概率因子更接近1，改变γ对各伪尺度的影响更接近共同平移，因此伪尺度标准差对γ的响应较弱。β=5、n=7和15的配对对照中，分别有46/50和43/50组在真γ处的梯度低于0.10；这些组的阈值交点均位于真γ右侧，造成γ高估。\n\n'
        'γ上移缩短各观测到起点的距离，其中小距离缩短的比例更大，使观测间的距离比增大。按伪尺度式，要使各η̂ᵢ仍尽可能一致，就需以较小β对应较大的距离比；本组右移样本的伪尺度均值η也随之降低。位置偏差由此带动形状与尺度偏差。\n\n'
        '图3所用原案例第31组在γ=500处的梯度约为−0.011，在γ约1015处才达到0.10，最终返回W(1.95,512,1015)。这组参数仍能贴近观测中部，却偏离生成分布W(5,1000,500)：固定阈值确定了偏高的位置，随后按伪尺度一致性拟合的β、η形成补偿，因而得到第一章所示的偏移分布。',
    ),
    (
        '原β=5代表样本右移后，残差比例降低，条件β和η也降低（补充图6b）；配对样本中还出现左侧最低点。因此，匹配改善可以伴随右移，但偏移方向随样本改变。',
        '原β=5、n=7第37组中，γ由500移至约974时，残差比例由0.047降至0.019（补充图6b）。因此，偏高的位置在LSE准则下优于固定真位置的条件拟合：它更好地匹配了该样本的随机间距，却不代表位置更准确。\n\n'
        'γ右移使较小观测的对数距离下降更多，y对z的回归斜率增大，按β=1/b得到较小形状；回归以较小尺度匹配缩短的中部距离，最终返回W(1.97,335,974)。LSE选择了变换后相对残差更小的分布，而该分布的参数已偏离真值。图5也有左侧最低点，说明这种匹配可产生双向偏移。',
    ),
    (
        '原β=5代表样本右移后，残差比例降低，β和η随之降低（补充图6d）；配对展开例则返回零边界。高β下较好的线性匹配，同样可以对应不同方向的位置偏移。',
        '原β=5、n=7第11组中，γ由500移至约914时，R²由0.953升至0.987（补充图6d）。固定的绘图概率与这组观测在右移后更接近直线，因而相关性准则接受了偏高的位置。\n\n'
        '此时X的间距增大，而Y保持不变，回归斜率b降低，β=b也降低；较小η则对应缩短后的中部距离，最终返回W(1.36,461,914)。更高相关性来自对该样本概率位置误差的匹配，不能保证三个参数接近真值。图6的配对展开例返回γ=0，说明LRE同样没有固定的偏移方向。',
    ),
    (
        '高β展开例在真位置的条件形状较大，进入J₃端点区间，样本乘积低于校准目标，T₂为负，共同交点向右移动得更多。原β=5代表样本也呈现右移（补充图6f）。这里使用了β<10的形状范围和J₃端点近似，两者对偏移的贡献尚未与原文校准方程的作用分离。',
        '图7f的β=5样本在γ=500处，满足T₁=0的条件β约为8.79，但T₂约为−0.108，真实位置不能使两式同时平衡。γ右移增大距离的相对差异，并沿T₁=0改变条件β；在γ约979处，T₂达到0，β降至约4.20。尺度式随后对应较短的观测距离，得到η约512。\n\n'
        '因此，返回的偏移参数满足本组校准方程，而固定真实位置的条件解不满足另一项校准要求，联合平衡遂落在γ偏高、β和η偏低的分布上。该例的真位置条件β已超过J₃表上端；本批还采用β<10的范围，端点近似和形状范围对偏移的贡献尚未与原文校准方程的作用分离。',
    ),
    (
        '原β=5代表样本中，较大的参数偏移相对于固定真位置的条件拟合，仅提高对数似然0.053，表明目标对这类参数变化区分较弱；配对展开例的返回位置则位于零边界。',
        '原β=5、n=7第33组返回W(3.48,637,907)，相对于固定γ=500的条件最优拟合，对数似然提高0.053。位置上移后，条件形状方程以较小β匹配增大的距离相对差异，尺度式则拟合较短的距离。补偿后的分布虽偏离真参数，却使这组观测的似然更高，因而在准则比较中优于真位置条件拟合。\n\n'
        '较大参数偏移仅对应很小的似然改善，表明本例对这类参数组合的区分较弱，有限样本波动便可改变更高似然的位置。图8的配对展开例反而返回γ=0，因此这种区分不足并不只产生右移。',
    ),
    (
        'β=5时最小观测更远离真起点，位置上移也更大。γ上移扩大保留距离的相对差异，图中形状方程的根随之降低。展开例中，γ从500移至约1162，β由约8.4降至3.5，η由约1199降至524，最终呈现γ高估、β和η低估。随n增大，最小值定位造成的位置偏移减轻。',
        'MMLE的位置偏差在γ̂=t₁这一步已被确定，后续拟合只能调整β、η。高β时t₁更远离真起点，保留距离因位置上移而缩短、相对差异增大，形状方程的根及对应尺度随之降低。图9f中，γ由500移至约1162时，条件β由约8.4降至3.5，η由约1199降至524。后两项参数适应了偏高的起点，因而返回γ高估、β和η低估的分布；随n增大，最小值定位造成的偏移减轻。',
    ),
]

README_NOTE = (
    '2026-10-11报告1补全逐法解释：由各方法实际判据说明偏移位置如何被接受，再用形状、尺度公式解释返回分布。'
    '[独立脚本](交付/程序/报告1/20261011-逐法偏移因果解释.py)读取既有过程数据复核后修改文字；'
    '`--verify`只核对。[同名记录](交付/程序/报告1/20261011-逐法偏移因果解释.json)保存MDM阈值统计、'
    '各例准则与参数及输入哈希。原公式、图片、工作簿、样本和估计均保留。\n\n'
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def protected_files():
    paths = set(SOURCES.values()) | {p for p in RESULT.rglob('*') if p.is_file()}
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}


def saved_evidence():
    """仅评价存档节点和伪尺度均值，未调用任何估计器。"""
    curves = read_json(SOURCES['criteria'])['curves']

    def case(method, sample_id, source='original'):
        matches = [c for c in curves if c['source'] == source and c['beta'] == 5
                   and c['n'] == 7 and c['sample_id'] == sample_id and c['method'] == method]
        assert len(matches) == 1
        c = matches[0]
        assert c['fit']['converged']
        assert np.allclose(c['returned'][2:4],
                           [c['fit']['beta_hat'], c['fit']['eta_hat']], rtol=2e-7)
        return {
            'source': source, 'sample_id': sample_id, 'n': 7, 'generating_beta': 5,
            'at_gamma_500': c['truth'], 'at_return': c['returned'],
            'fit_beta_eta_gamma': [c['fit'][k] for k in ('beta_hat', 'eta_hat', 'gamma_hat')],
        }

    mdm_counts = {}
    factor_checks = {}
    for n, expected in [(7, 46), (15, 43)]:
        rows = [c for c in curves if c['source'] == 'paired' and c['beta'] == 5
                and c['n'] == n and c['method'] == 'mdm']
        assert len(rows) == 50 and all(c['fit']['converged'] for c in rows)
        below = sorted(c['sample_id'] for c in rows if c['truth'][1] < .10)
        right = sorted(c['sample_id'] for c in rows if c['fit']['gamma_hat'] > 500)
        assert below == right and len(below) == expected
        assert all(abs(c['returned'][1] - .10) < 1e-7 for c in rows)
        assert all(c['returned'][2] < c['truth'][2] and c['returned'][3] < c['truth'][3]
                   for c in rows if c['sample_id'] in right)
        mdm_counts[str(n)] = {'total': 50, 'true_gradient_below_010': len(below),
                              'same_ids_have_gamma_above_500': True, 'sample_ids': below,
                              'right_shift_conditional_beta_and_eta_decrease': True}
        low = {c['sample_id']: c for c in curves if c['source'] == 'paired'
               and c['beta'] == 2 and c['n'] == n and c['method'] == 'mdm'}
        p = (np.arange(1, n + 1) - .3) / (n + .4)
        q = -np.log1p(-p)
        checks = [np.std(q ** (-1 / c['truth'][2]), ddof=1)
                  < np.std(q ** (-1 / low[c['sample_id']]['truth'][2]), ddof=1)
                  for c in rows]
        assert all(checks)
        factor_checks[str(n)] = {'paired_cases': 50,
                                 'smaller_spread_of_gamma_coefficients_at_beta5': sum(map(int, checks))}

    examples = {m: case(m, i) for m, i in [('mdm', 31), ('lse', 37), ('lre', 11), ('mle', 33)]}
    examples['wmle'] = case('wmle', 29, 'paired')
    assert examples['mdm']['at_gamma_500'][1] < .1
    for m in ['lse', 'lre']:
        assert examples[m]['at_return'][1] < examples[m]['at_gamma_500'][1]
    assert examples['wmle']['at_gamma_500'][1] < 0
    assert examples['wmle']['at_gamma_500'][4] is True
    assert abs(examples['wmle']['at_return'][1]) < 1e-7
    delta_ll = examples['mle']['at_return'][5] - examples['mle']['at_gamma_500'][5]
    assert round(delta_ll, 3) == .053
    examples['mle']['loglik_gain_against_fixed_true_location'] = delta_ll

    selected = {x['method']: x['sample_id'] for x in read_json(SOURCES['selected_cases'])['methods']}
    assert selected['wmle'] == 29
    mmle = read_json(SOURCES['mmle'])
    assert mmle['selected_id'] == 3
    c = next(c for c in mmle['curves'] if c['beta'] == 5 and c['n'] == 7 and c['sample_id'] == 3)
    fit = c['fit']
    assert fit['gamma_hat'] == min(c['observations'])
    assert fit['fixed_truth']['beta'] > fit['beta_hat']
    assert fit['fixed_truth']['eta'] > fit['eta_hat']
    examples['mmle'] = {'source': 'paired', 'sample_id': 3, 'n': 7, 'generating_beta': 5,
                        'fixed_gamma_500_beta_eta': [fit['fixed_truth'][k] for k in ('beta', 'eta')],
                        'fit_beta_eta_gamma': [fit[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat')]}

    # 图3与MDM解释共用原β=5、n=7第31组，不将配对样本误当成原案例。
    originals = read_json(SOURCES['original_estimates'])
    original = next(x for x in originals if x['beta'] == 5 and x['n'] == 7
                    and x['sample_id'] == 31 and x['method'] == 'mdm')
    assert original['converged']
    assert examples['mdm']['fit_beta_eta_gamma'] == [original[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat')]
    sample = next(x for x in read_json(SOURCES['original_samples'])['samples']
                  if x['beta_true'] == 5 and x['n'] == 7 and x['sample_id'] == 31)
    assert sample['regeneration_max_error'] == 0
    p = (np.arange(1, 8) - .3) / 7.4
    pseudo_eta = (np.asarray(sample['observations']) - original['gamma_hat']) / (
        -np.log1p(-p)) ** (1 / original['beta_hat'])
    assert np.isclose(pseudo_eta.mean(), original['eta_hat'], rtol=1e-12)
    return {'mdm_threshold_counts': mdm_counts, 'mdm_gamma_factor_spread': factor_checks,
            'examples': examples, 'figure3_same_original_sample_as_mdm_example': True,
            'original_mdm_eta_mean_check': float(pseudo_eta.mean())}


def formula_hash(text):
    formulas = re.findall(r'\$\$.*?\$\$', text, re.S)
    return len(formulas), hashlib.sha256('\n'.join(formulas).encode('utf-8')).hexdigest()


def verify():
    record = read_json(RECORD)
    assert digest(REPORT) == record['report_after_sha256'], '报告已被后续修改'
    assert digest(Path(__file__).resolve()) == record['script_sha256']
    assert protected_files() == record['protected_inputs'], '原数据或结果已变化'
    assert saved_evidence() == record['evidence']
    text = REPORT.read_text(encoding='utf-8')
    assert list(formula_hash(text)) == record['display_formulas_count_and_hash']
    assert re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text) == record['figure_paths']
    assert all(new in text and old not in text for old, new in REPLACEMENTS)
    assert README_NOTE.strip() in README.read_text(encoding='utf-8')
    print('PASS：逐法论证的存档数值、样本对应、原公式、九张主图及原数据与结果一致；未抽样、拟合或制图。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify or RECORD.exists():
        verify()
        return
    assert digest(REPORT) == SOURCE_SHA256, '输入版本变化，请勿覆盖后续修改'
    evidence = saved_evidence()
    protected = protected_files()
    before = REPORT.read_text(encoding='utf-8')
    after = before
    for old, new in REPLACEMENTS:
        assert after.count(old) == 1
        after = after.replace(old, new, 1)
    images = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', before)
    assert len(images) == 9
    assert re.findall(r'!\[[^\]]*\]\(([^)]+)\)', after) == images
    assert formula_hash(before) == formula_hash(after)
    for stage in ['## 第一章', '## 第三章']:
        assert before.split(stage, 1)[1].split('## ', 1)[0] == after.split(stage, 1)[1].split('## ', 1)[0]
    readme_bytes = README.read_bytes()
    newline = '\r\n' if b'\r\n' in readme_bytes else '\n'
    readme = readme_bytes.decode('utf-8').replace('\r\n', '\n')
    assert readme.count('## 整理与恢复\n') == 1
    write_atomic(REPORT, after.encode('utf-8'))
    write_atomic(README, readme.replace('## 整理与恢复\n', README_NOTE + '## 整理与恢复\n', 1)
                 .replace('\n', newline).encode('utf-8'))
    assert protected_files() == protected
    record = {'date': '2026-10-11', 'report_before_sha256': SOURCE_SHA256,
              'report_after_sha256': digest(REPORT), 'script_sha256': digest(Path(__file__).resolve()),
              'display_formulas_count_and_hash': list(formula_hash(after)), 'figure_paths': images,
              'protected_inputs': protected, 'evidence': evidence,
              'new_samples': 0, 'new_estimates': 0, 'redrawn_figures': 0}
    write_atomic(RECORD, (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    verify()


if __name__ == '__main__':
    main()
