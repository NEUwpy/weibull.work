"""Clarify the support -> compensation -> method-selection argument.

Only chapter 2's opening prose changes. Reuse the report generator and
the archived sample; retain every formula, figure and numerical result.
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

REPLACEMENTS = [
    (
        '解释第一章的偏移，需要考察偏移后的参数为何仍能与样本相容，以及各方法的估计准则为何选中这些组合。首先分析样本对位置参数的约束和三参数的补偿关系，再分别考察各方法的判定过程。',
        '高β、小n下，最小观测对γ上移的限制较弱；γ上移后，η和β又可通过补偿维持中部拟合。各方法的准则进一步决定是否选中这些偏移组合。',
    ),
    (
        '候选位置必须低于最小观测。记排序观测到候选γ的距离为：',
        '位置参数γ是分布起点，所有观测均须大于γ，因此最小观测给出γ的上限。记排序观测到候选γ的距离为：',
    ),
    (
        '对于第一章中接近1000的位置估计，只要t₁仍大于该值，它就没有违反样本支持条件。固定η、γ，高β、小n下最小观测通常离真实γ较远，使明显偏高的γ仍可能满足γ<t₁；随n增大，最小观测向真实γ靠近，位置上移的可行区间总体缩小。图2比较这一约束随β和n的变化。',
        '图2显示，固定η和γ时，β=5的最小观测通常比β=2更远离真实γ，尤其在小n下。因此，γ即使明显高于真值，也可能仍低于最小观测，未被样本排除。随n增大，最小观测总体向真实γ靠近，对γ上移的限制增强。',
    ),
    (
        '**图2｜高β、小n下最小观测离真实γ较远，γ上移的可行区间较大。**',
        '**图2｜高β、小n下，最小观测对γ上移的限制较弱。**',
    ),
    (
        '较高γ满足起点约束后，还需说明它为何能与观测分布相容。γ上移使tᵢ−γ缩短，若η、β随之调整后仍能保持样本覆盖区间内的分位点接近，偏移组合就可维持中部拟合。由F(Q(p))=p，解得寿命分位点：',
        'γ未被最小观测排除，只说明它可行。偏移组合要能拟合样本，还需η和β补偿。γ升高时，观测到起点的距离tᵢ−γ缩短。由F(Q(p))=p，得到寿命分位点：',
    ),
    (
        '其中，z为累计概率的双对数变换，z=0对应63.2%分位。γ+η决定中部位置，η/β是该处分位曲线关于z的斜率。γ上移时，降低η可保持中部位置接近，再按相近比例降低β可保持局部斜率接近；因此，γ偏高、η和β偏低的组合仍可能拟合同一组中部观测。',
        '其中，z为累计概率的双对数变换，z=0对应63.2%分位。γ+η决定中部位置，η/β是此处分位曲线关于z的斜率。升高γ并降低η，可保持中部位置接近；再按相近比例降低β，可保持局部斜率接近。这样，γ偏高、η和β偏低的组合仍可能拟合同一组中部观测。',
    ),
    (
        '图3所用的7个观测来自W(5,1000,500)，最小值约1167，因此γ=1000仍满足起点约束。真分布与接近该组MDM估计的W(2,500,1000)在样本覆盖区间较接近，展示了参数补偿后的中部拟合。黑点的累计概率由样本排序近似，反映单组抽样的波动。',
        '图3中，来自W(5,1000,500)的7个观测也能贴近W(2,500,1000)的中部曲线。样本最小值约1167，使γ=1000仍可行；对照分布接近该组MDM估计，说明γ上移、η和β下降后仍可能拟合同一样本。黑点的累计概率由样本排序近似，反映抽样波动。',
    ),
    (
        '**图3｜γ升高、η和β降低后，中部拟合仍可接近真分布。**',
        '**图3｜γ升高、η和β降低后的分布仍可贴近同一组样本。**',
    ),
    (
        '起点约束和参数补偿解释了偏移组合为何仍能与样本相容，实际选中哪组参数则取决于各方法的判据。下面比较真实位置与偏移位置处的梯度、回归匹配、校准残差和似然，解释判据为何选中偏移组合。MDM以梯度交点定位γ；WMLE和MLE联合估计，γ条件曲线用于观察其联合准则的变化。',
        '以上说明了偏移组合为何仍可行且能拟合样本。它是否被选中，取决于各方法的梯度阈值、回归匹配、校准方程或似然。下面逐法分析这些判据为何会选择偏移组合。MDM按梯度交点定位γ；WMLE、MLE联合估计，其γ条件曲线用于分析联合准则。',
    ),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    seal = json.loads((ROOT / '结果/中间数据/封存清单.json').read_text(encoding='utf-8'))
    protected = {**seal['input_hashes'], **seal['output_hashes']}
    protected.update({name: sha for name, sha in seal['code_hashes'].items()
                      if name.startswith(('程序/依赖快照/', '程序/输入快照/'))})
    for name, sha in protected.items():
        assert digest(ROOT / name) == sha, name

    before = REPORT.read_bytes()
    original = before.decode('utf-8')
    chapter1, rest = original.split('## 第二章', 1)
    _, methods_and_conclusion = rest.split('### 2.1 ', 1)
    equations = re.findall(r'\$\$[\s\S]*?\$\$', original)
    figures = re.findall(r'^!\[.*$', original, re.M)
    text = original
    for old, new in REPLACEMENTS:
        if old in text:
            assert text.count(old) == 1
            text = text.replace(old, new)
        else:
            assert text.count(new) == 1, new
    assert text.split('## 第二章', 1)[0] == chapter1
    assert text.split('### 2.1 ', 1)[1] == methods_and_conclusion
    assert re.findall(r'\$\$[\s\S]*?\$\$', text) == equations
    assert re.findall(r'^!\[.*$', text, re.M) == figures

    example = json.loads((HERE / '样本相容绘图数据.json').read_text(encoding='utf-8'))
    assert example['n'] == 7 and round(min(example['observations'])) == 1167
    assert example['sample_regeneration_max_error'] == 0
    assert min(example['observations']) > 1000.
    assert example['curves'][0]['parameters_beta_eta_gamma'] == [5., 1000., 500.]
    assert example['curves'][1]['parameters_beta_eta_gamma'] == [2., 500., 1000.]
    assert example['max_cdf_difference_on_observed_interval'] < .06

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
    for name, sha in protected.items():
        assert digest(ROOT / name) == sha, name

    record = dict(task='2026-10-10: minimum-value bound, same-sample fit, method selection',
                  previous_report_sha256=hashlib.sha256(before).hexdigest(),
                  report_sha256=digest(REPORT), generator_sha256=digest(GENERATOR),
                  revised_passages=len(REPLACEMENTS), chapter1_unchanged=True,
                  method_sections_and_conclusion_unchanged=True,
                  equations_unchanged=len(equations), figure_links_unchanged=len(figures),
                  protected_scientific_and_figure_files_unchanged=len(protected),
                  example=dict(sample_id=example['sample_id'], minimum=min(example['observations']),
                               actual_fit=example['actual_fit_parameters_beta_eta_gamma'],
                               illustrative_parameters=[2., 500., 1000.],
                               maximum_cdf_difference=example['max_cdf_difference_on_observed_interval']),
                  argument=['High-beta small samples can leave a weaker upper bound on gamma.',
                            'Eta and beta compensation can preserve the central fit to the same sample.',
                            'Method-specific criteria determine which feasible combination is returned.'],
                  new_random_draws=0, new_estimates=0, redrawn_figures=0)
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8', newline='\n')
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    main()
