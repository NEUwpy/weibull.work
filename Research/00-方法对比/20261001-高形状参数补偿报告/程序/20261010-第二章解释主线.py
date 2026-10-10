"""Revise chapter 2 around compatibility and method-specific selection.

Reuse the reviewed report generator and frozen evidence. This entry changes
prose only; every equation, figure, sample and estimate is preserved.
"""
import hashlib
import importlib.util
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPORT = ROOT.parent / '报告1：高形状参数下的估计偏移.md'
GENERATOR = HERE / '生成报告.py'
RECORD = Path(__file__).with_suffix('.json')
CHECKPOINT = '099639f9'

REPLACEMENTS = [
    (
        '## 第二章　机制分析与对照实验\n\n三参数Weibull分布的分布函数与概率密度为：',
        '## 第二章　机制分析与对照实验\n\n解释第一章的偏移，需要考察偏移后的参数为何仍能与样本相容，以及各方法的估计准则为何选中这些组合。首先分析样本对位置参数的约束和三参数的补偿关系，再分别考察各方法的判定过程。\n\n三参数Weibull分布的分布函数与概率密度为：',
    ),
    (
        '排序观测到候选γ的距离为：',
        '候选位置必须低于最小观测。记排序观测到候选γ的距离为：',
    ),
    (
        '所有观测都必须满足tᵢ>γ，因此t₁限制了γ的上界。最小观测靠近真实γ时，γ稍有上移就可能越过该观测；最小观测离真实γ较远时，明显偏高的γ也仍满足这一约束。固定η、γ，高β、小n下最小观测通常离真实γ更远，为γ上移留下了较大的可行区间；随n增大，这一区间总体缩小（图2）。',
        '对于第一章中接近1000的位置估计，只要t₁仍大于该值，它就没有违反样本支持条件。固定η、γ，高β、小n下最小观测通常离真实γ较远，使明显偏高的γ仍可能满足γ<t₁；随n增大，最小观测向真实γ靠近，位置上移的可行区间总体缩小。图2比较这一约束随β和n的变化。',
    ),
    (
        '在这一可行区间内，γ上移会使各观测到起点的距离tᵢ−γ缩短。若η和β能够随之调整、保持样本覆盖区间内的分位点接近，偏移后的组合就仍可能维持拟合。由F(Q(p))=p，解得寿命分位点：',
        '较高γ满足起点约束后，还需说明它为何能与观测分布相容。γ上移使tᵢ−γ缩短，若η、β随之调整后仍能保持样本覆盖区间内的分位点接近，偏移组合就可维持中部拟合。由F(Q(p))=p，解得寿命分位点：',
    ),
    (
        '例如，W(5,1000,500)与W(2.5,500,1000)的中部分位均为1500、局部斜率均为200。两者尾部仍不同，上述近似只适用于z/β较小的范围。图3则以接近原案例MDM估计的W(2,500,1000)作对照，同一组观测也贴近两条分布曲线。',
        '例如，W(5,1000,500)与W(2.5,500,1000)的中部分位均为1500、局部斜率均为200。两者尾部仍不同，上述近似只适用于z/β较小的范围。\n\n图3所用的7个观测来自W(5,1000,500)，最小值约1167，因此γ=1000仍满足起点约束。真分布与接近该组MDM估计的W(2,500,1000)在样本覆盖区间较接近，展示了参数补偿后的中部拟合。黑点的累计概率由样本排序近似，反映单组抽样的波动。',
    ),
    (
        '**图3｜γ升高、η和β降低后的分布仍能贴近样本。** W(5,1000,500)与W(2,500,1000)在样本覆盖区间的分布曲线较接近。',
        '**图3｜γ升高、η和β降低后，中部拟合仍可接近真分布。**',
    ),
    (
        '高β、小n为γ上移留下较大的可行区间，η、β的补偿又使偏移后的组合保有相近的中部拟合。各方法为什么会选中这样的组合，还需考察其准则对样本的响应。下面分别分析固定阈值、回归匹配、校准方程和似然；MDM以梯度交点定位γ，WMLE和MLE联合估计。',
        '起点约束和参数补偿解释了偏移组合为何仍能与样本相容，实际选中哪组参数则取决于各方法的判据。下面比较真实位置与偏移位置处的梯度、回归匹配、校准残差和似然，解释判据为何选中偏移组合。MDM以梯度交点定位γ；WMLE和MLE联合估计，γ条件曲线用于观察其联合准则的变化。',
    ),
    (
        'LSE以理论顺序统计量作为参考，选择线性匹配最好的参数。小样本的实际间距有随机波动；调整参数若能改善这些间距与参考值的匹配，回归准则就可能在偏离真值的组合处更优。',
        'LSE以理论顺序统计量作为参考，选择线性匹配最好的参数。有限样本的间距会偏离理论参考，真实位置未必对应最佳匹配；位置调整若能改善匹配，方法就会选择偏移后的参数组合。',
    ),
    (
        'LRE用固定绘图位置近似各观测的实际累计概率，再选择线性相关最强的参数。小样本的实际概率位置存在随机波动；相关性最高的组合，可能同时匹配了这组样本的概率位置误差。',
        'LRE用固定绘图位置近似各观测的实际累计概率，再选择线性相关最强的参数。即使样本来自真分布，按排序给定的概率位置也不等于F(tᵢ)。调整参数可部分匹配这种随机差异，因此最高相关性未必对应真参数。',
    ),
    (
        'WMLE用有限样本校准系数调整似然方程，联合求解β与γ，再计算η。高β样本的距离较集中，其方程响应与校准目标之间可能出现差异，使共同平衡偏离真参数。',
        'WMLE用有限样本校准系数调整似然方程，联合求解β与γ，再计算η。高β样本在真实位置处可能无法同时满足两条校准方程，需调整β、γ才能达到共同平衡。下面考察样本统计量与校准目标的差异如何使平衡位置偏离真值。',
    ),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    seal = json.loads((ROOT / '结果/中间数据/封存清单.json').read_text(encoding='utf-8'))
    protected = {**seal['input_hashes'], **seal['output_hashes']}
    protected.update({name: sha for name, sha in seal['code_hashes'].items()
                      if name.startswith(('程序/依赖快照/', '程序/输入快照/'))})
    for name, expected in protected.items():
        assert digest(ROOT / name) == expected, name
    original = REPORT.read_text(encoding='utf-8')
    before = REPORT.read_bytes()
    chapter1 = original.split('## 第二章', 1)[0]
    chapter3_and_supplements = original.split('## 第三章', 1)[1]
    equations = re.findall(r'\$\$[\s\S]*?\$\$', original)
    figures = re.findall(r'^!\[.*$', original, re.M)
    text = original
    for old, new in REPLACEMENTS:
        if old in text:
            assert text.count(old) == 1
            text = text.replace(old, new)
        else:
            assert text.count(new) == 1
    assert text.split('## 第二章', 1)[0] == chapter1
    assert text.split('## 第三章', 1)[1] == chapter3_and_supplements
    assert re.findall(r'\$\$[\s\S]*?\$\$', text) == equations
    assert re.findall(r'^!\[.*$', text, re.M) == figures

    example = json.loads((HERE / '样本相容绘图数据.json').read_text(encoding='utf-8'))
    assert example['n'] == 7 and round(min(example['observations'])) == 1167
    assert min(example['observations']) > 1000.
    assert example['curves'][0]['parameters_beta_eta_gamma'] == [5.,1000.,500.]
    assert example['curves'][1]['parameters_beta_eta_gamma'] == [2.,500.,1000.]

    REPORT.write_text(text, encoding='utf-8', newline='\n')
    source = GENERATOR.read_bytes()
    marker = b'REPORT_TEXT = r' + b'"' * 3
    start = source.index(marker) + len(marker)
    end = source.index(b'"' * 3, start)
    newline = '\r\n' if b'\r\n' in source[start:end] else '\n'
    GENERATOR.write_bytes(source[:start] + text.replace('\n', newline).encode('utf-8') + source[end:])
    spec = importlib.util.spec_from_file_location('reviewed_report', GENERATOR)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generator.main()
    assert REPORT.read_text(encoding='utf-8') == generator.REPORT_TEXT == text
    for name, expected in protected.items():
        assert digest(ROOT / name) == expected, name

    record = dict(task='2026-10-10: chapter 2 explains compatibility, then criterion selection',
                  prior_checkpoint=CHECKPOINT, previous_report_sha256=hashlib.sha256(before).hexdigest(),
                  report_sha256=digest(REPORT), generator_sha256=digest(GENERATOR),
                  revised_passages=len(REPLACEMENTS), chapter1_unchanged=True,
                  chapter3_and_supplements_unchanged=True,
                  equations_unchanged=len(equations), figure_links_unchanged=len(figures),
                  protected_scientific_and_figure_files_unchanged=len(protected),
                  example=dict(sample_id=example['sample_id'], minimum=min(example['observations']),
                               illustrative_gamma=1000., support_satisfied=True),
                  argument=['Pose the observed parameter-shift problem before the support analysis.',
                            'Minimum observations bound feasible gamma; they do not select it.',
                            'Quantile compensation explains similar central fits.',
                            'Method-specific criteria explain the returned parameter combination.'],
                  new_random_draws=0, new_estimates=0, redrawn_figures=0)
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8', newline='\n')
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    main()
