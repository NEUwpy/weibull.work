"""Revise only the support-to-compensation bridge in the reviewed report.

Keep archived samples, estimates, figures and method sections unchanged. The
report mother remains the reusable generator; this entry records this revision.
"""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT.parent / '报告1：高形状参数下的估计偏移.md'
GENERATOR = ROOT / '程序' / '生成报告.py'
RECORD = Path(__file__).with_suffix('.json')

REPLACEMENTS = [
    (
        '固定η、γ时，高β样本较集中，最小观测通常离真实γ更远。n较小时，γ<t₁给出的上界较宽，较高的γ仍满足样本支持；随n增大，最小值总体向γ靠近，但β=5时n=15与30的分布仍较接近（图2）。',
        '所有观测都必须满足tᵢ>γ，因此t₁限制了γ的上界。最小观测靠近真实γ时，γ稍有上移就可能越过该观测；最小观测离真实γ较远时，明显偏高的γ也仍满足这一约束。固定η、γ，高β、小n下最小观测通常离真实γ更远，为γ上移留下了较大的可行区间；随n增大，这一区间总体缩小（图2）。',
    ),
    (
        '**图2｜高β下最小观测离真实γ更远，n=15与30的最小值分布仍较接近。**',
        '**图2｜高β、小n下最小观测离真实γ较远，γ上移的可行区间较大。**',
    ),
    (
        '较高γ能否成为估计结果，还取决于其他参数能否维持样本拟合，以及方法准则如何选择。由F(Q(p))=p，对生存概率取负对数并解出寿命分位点：',
        '在这一可行区间内，γ上移会使各观测到起点的距离tᵢ−γ缩短。若η和β能够随之调整、保持样本覆盖区间内的分位点接近，偏移后的组合就仍可能维持拟合。由F(Q(p))=p，解得寿命分位点：',
    ),
    (
        '其中，z为累计概率的双对数变换，z=0对应63.2%分位，η/β是该处分位曲线关于z的斜率。在固定的中部概率区间，β增大使z/β更小，分位曲线更接近这一形式。γ+η决定中部位置，η/β决定局部斜率；保持这两个组合接近，γ升高、η和β降低也可维持中部拟合。',
        '其中，z为累计概率的双对数变换，z=0对应63.2%分位。γ+η决定中部位置，η/β是该处分位曲线关于z的斜率。γ上移时，降低η可保持中部位置接近，再按相近比例降低β可保持局部斜率接近；因此，γ偏高、η和β偏低的组合仍可能拟合同一组中部观测。',
    ),
    (
        '样本的起点约束较弱、参数又可相互补偿，为偏移保留了拟合空间。具体选中哪组参数，由各方法的准则决定。以下分别分析这种样本条件如何影响固定阈值、回归匹配、校准方程和似然；MDM以梯度交点定位γ，WMLE和MLE按实际算法联合估计。',
        '高β、小n为γ上移留下较大的可行区间，η、β的补偿又使偏移后的组合保有相近的中部拟合。各方法为什么会选中这样的组合，还需考察其准则对样本的响应。下面分别分析固定阈值、回归匹配、校准方程和似然；MDM以梯度交点定位γ，WMLE和MLE联合估计。',
    ),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    seal = json.loads((ROOT / '结果' / '中间数据' / '封存清单.json').read_text(encoding='utf-8'))
    frozen = {**seal['input_hashes'], **seal['output_hashes']}
    frozen.update({name: value for name, value in seal['code_hashes'].items()
                   if name.startswith('程序/依赖快照/')})
    for name, expected in frozen.items():
        assert digest(ROOT / name) == expected, name

    original = REPORT.read_bytes()
    original_text = original.decode('utf-8')
    chapter1 = original_text.split('## 第二章')[0]
    method_sections = original_text.split('### 2.1 MDM', 1)[1]
    report_bytes = original
    for old, new in REPLACEMENTS:
        old_bytes, new_bytes = old.encode('utf-8'), new.encode('utf-8')
        if old_bytes in report_bytes:
            assert report_bytes.count(old_bytes) == 1
            report_bytes = report_bytes.replace(old_bytes, new_bytes)
        else:
            assert report_bytes.count(new_bytes) == 1
    REPORT.write_bytes(report_bytes)

    # Replace only the report literal, preserving the mother's surrounding bytes.
    source = GENERATOR.read_bytes()
    marker = b'REPORT_TEXT = r' + b'"' * 3
    start = source.index(marker) + len(marker)
    end = source.index(b'"' * 3, start)
    newline = '\r\n' if b'\r\n' in source[start:end] else '\n'
    text = REPORT.read_text(encoding='utf-8')
    GENERATOR.write_bytes(source[:start] + text.replace('\n', newline).encode('utf-8') + source[end:])
    tree = ast.parse(GENERATOR.read_text(encoding='utf-8'))
    literal = next(node.value.value for node in tree.body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'REPORT_TEXT' for t in node.targets))
    assert literal == text

    spec = importlib.util.spec_from_file_location('reviewed_report', GENERATOR)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generator.main()
    final = REPORT.read_text(encoding='utf-8')
    assert final == literal
    assert final.split('## 第二章')[0] == chapter1
    assert final.split('### 2.1 MDM', 1)[1] == method_sections
    for name, expected in frozen.items():
        assert digest(ROOT / name) == expected, name

    record = dict(task='2026-10-10: explain support feasibility before parameter compensation',
                  previous_report_sha256=hashlib.sha256(original).hexdigest(),
                  report_sha256=digest(REPORT), generator_sha256=digest(GENERATOR),
                  changed_paragraphs=len(REPLACEMENTS), chapter1_unchanged=True,
                  method_sections_and_conclusion_unchanged=True,
                  frozen_scientific_and_figure_files_unchanged=len(frozen),
                  argument=['Support requires every observation to exceed candidate gamma.',
                            'A large minimum leaves a larger feasible upward shift.',
                            'Compensation can preserve central location and local slope.',
                            'Actual criterion selection is explained separately by method.'],
                  new_random_draws=0, new_estimates=0, redrawn_figures=0)
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8', newline='\n')
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    main()
