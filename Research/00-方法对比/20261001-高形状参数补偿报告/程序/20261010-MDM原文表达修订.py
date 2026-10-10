"""Restore the paper's MDM expressions; reuse saved finite-difference curves.

Only section 2.1, its generator source and the MDM PNG label are revised.
No observations, returned estimates or numerical curve data are replaced.
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
SECTION = r"""### 2.1 MDM：条件最小标准差梯度与固定补偿值

MDM比较各观测反算的尺度参数，以这些伪尺度之间的差异估计参数。原文首先通过秩估计得到排序观测的累计概率：

$$\hat F(t_{(i)})=
\frac{i}{i+(n+1-i)F_{2(n+1-i),\,2i,\,0.5}}.$$

其中，$t_{(i)}$为第i个排序观测，$\hat F(t_{(i)})$为对应的累计概率估计，$F_{2(n+1-i),\,2i,\,0.5}$为自由度分别为2(n+1−i)和2i的F分布中位数。本组存档计算采用Bernard近似$\hat F(t_{(i)})\approx(i-0.3)/(n+0.4)$。

将累计概率代入原文的尺度参数伪估计量：

$$\hat\eta_i(\gamma,\beta)=
\frac{t_{(i)}-\gamma}{[-\ln(1-\hat F(t_{(i)}))]^{1/\beta}}.$$

其中，η̂ᵢ为第i个观测反算的伪尺度。固定γ，尝试不同β，并以n个伪尺度的标准差$\sigma_\eta(\gamma,\beta)$衡量差异；取其中最小的标准差$\sigma_{\eta,\min}(\gamma)$，同时保留对应的β。

原文以条件最小标准差对γ的差分梯度确定位置：

$$\nabla(\gamma)=
\frac{\sigma_{\eta,\min}(\gamma+\Delta\gamma)
-\sigma_{\eta,\min}(\gamma)}{\Delta\gamma}.$$

其中，∇(γ)为条件最小标准差的梯度，Δγ为位置参数的差分步长。以梯度∇(γ)=0.10代替零梯度判据，得到位置估计γ̂；β̂取该位置对应的形状参数，最终尺度取伪尺度均值：

$$\hat\eta=\frac{1}{n}\sum_{i=1}^{n}
\frac{t_{(i)}-\hat\gamma}{[-\ln(1-\hat F(t_{(i)}))]^{1/\hat\beta}}.$$

其中，β̂、η̂、γ̂分别为形状、尺度和位置估计。图4以数值差分评价上述梯度。

![图4　MDM的条件最小标准差梯度](20261001-高形状参数补偿报告/结果/图3_MDM六格机制.png)

**图4｜β较大时，梯度与0.10的交点偏向较高的位置。**

图4显示，β=5时，真实γ附近的条件最小标准差变化较缓，梯度大多低于0.10。曲线在更大的γ处才达到固定补偿值，因而得到偏高的位置估计；该位置对应的β和η也降低。随n增大，这一偏移减轻。

在n=7的配对对照中，β由2增至5，真实γ处梯度中位数由0.064降至0.009，γ估计中位数由575升至973。

"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_bytes(path, old, new):
    source = path.read_bytes()
    if '\n' in old and b'\r\n' in source:
        old, new = old.replace('\n', '\r\n'), new.replace('\n', '\r\n')
    before, after = old.encode('utf-8'), new.encode('utf-8')
    if after in source:
        return
    assert source.count(before) == 1, (path, old)
    path.write_bytes(source.replace(before, after))


def sync_generator(text):
    source = GENERATOR.read_bytes()
    marker = b'REPORT_TEXT = r' + b'"' * 3
    start = source.index(marker) + len(marker)
    end = source.index(b'"' * 3, start)
    newline = '\r\n' if b'\r\n' in source[start:end] else '\n'
    GENERATOR.write_bytes(source[:start] + text.replace('\n', newline).encode('utf-8') + source[end:])
    spec = importlib.util.spec_from_file_location('current_report', GENERATOR)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generator.main()
    assert REPORT.read_text(encoding='utf-8') == generator.REPORT_TEXT == text


def sync_docs():
    readme = ROOT / 'README.md'
    replace_bytes(readme, 'MDM的梯度收缩与固定阈值', 'MDM的条件最小标准差梯度与固定补偿值')
    replace_bytes(readme,
                  'MDM解析梯度及权重标准差检查仍保存于mdm_envelope。',
                  'MDM正文沿用原文的秩概率、伪尺度、条件最小标准差、差分梯度和尺度均值表达。图4沿用存档数值差分曲线，纵轴为∇(γ)；不使用协方差式或其上界解释机制。历史计算使用Bernard近似秩概率、连续形状优化与中心差分，原文使用精确中位秩和离散搜索；旧解析核验仅留作历史记录。')
    row = '| [20261010-MDM原文表达修订.py](程序/20261010-MDM原文表达修订.py) | 当前MDM修订入口：按原文式(3)、(4)、(6)、(7)表述方法，删去协方差及上界推导；图4仅改纵轴符号，[核验记录](程序/20261010-MDM原文表达修订.json)确认曲线与估计数据保持，导出PNG |'
    source = readme.read_bytes()
    if row.encode('utf-8') not in source:
        needle = '| [核验交付.py](程序/核验交付.py)'
        newline = '\r\n' if b'\r\n' in source else '\n'
        assert source.count(needle.encode('utf-8')) == 1
        readme.write_bytes(source.replace(needle.encode('utf-8'), (row + newline + needle).encode('utf-8')))
    notes = ROOT / '本轮修改意见.md'
    heading = '## 2026-10-10：MDM沿用原文表达'
    source = notes.read_bytes()
    if heading.encode('utf-8') not in source:
        newline = '\r\n' if b'\r\n' in source else '\n'
        entry = '\n\n' + heading + '\n\n用户要求去掉协方差式及自行推导的梯度上界。2.1改按原文的精确中位秩、尺度伪估计量、条件最小标准差、差分梯度与尺度均值组织，直接以图4的差分梯度及0.10交点解释位置偏移；保留历史计算使用Bernard近似的简短说明。图4纵轴改为原文∇(γ)，复用存档曲线和同号配对单例，六格坐标保持；本次仅导出PNG。\n\n独立修订入口与记录保存在程序目录，生成母体和README同步。原样本、参数估计、数值曲线及其他图像保持；旧解析核验作为历史记录保存，不作为当前正文或绘图依据。\n'
        notes.write_bytes(source.rstrip(b'\r\n') + entry.replace('\n', newline).encode('utf-8'))


def main():
    seal = json.loads((ROOT / '结果/中间数据/封存清单.json').read_text(encoding='utf-8'))
    figure = '结果/图3_MDM六格机制.png'
    previous_record = json.loads(RECORD.read_text(encoding='utf-8')) if RECORD.exists() else {}
    previous_figure_hash = previous_record.get('previous_figure_sha256', seal['output_hashes'][figure])
    changed_outputs = {'结果/图3_MDM六格机制.png', '结果/中间数据/逐法图核验.json'}
    protected = {**seal['input_hashes'],
                 **{k: v for k, v in seal['output_hashes'].items() if k not in changed_outputs}}
    protected.update({k: v for k, v in seal['code_hashes'].items()
                      if k.startswith('程序/依赖快照/')})
    for name, expected in protected.items():
        assert digest(ROOT / name) == expected, name

    original = REPORT.read_text(encoding='utf-8')
    start = original.index('### 2.1 MDM')
    end = original.index('### 2.2 LSE', start)
    text = original[:start] + SECTION + original[end:]
    assert all(token not in SECTION for token in ('Cov', 'operatorname{SD}', 'w_i', '协方差', '权重', 'arg\\min'))
    assert re.findall(r'^!\[.*?\]\((.*?)\)', text, re.M) == re.findall(r'^!\[.*?\]\((.*?)\)', original, re.M)
    REPORT.write_text(text, encoding='utf-8', newline='\n')
    sync_generator(text)

    plotter = HERE / '绘制逐法分析图.py'
    replace_bytes(plotter, "ax.set_ylabel(r'$g(\\gamma)$')", "ax.set_ylabel(r'$\\nabla(\\gamma)$')")
    replace_bytes(plotter, "formats=('png', 'pdf', 'svg')", "formats=('png',)")
    import 绘制公式与拟合点图 as methods
    qa_path = methods.DATA / '逐法图核验.json'
    qa = json.loads(qa_path.read_text(encoding='utf-8'))
    before_mdm = next(r for r in qa['process_figures'] if r['method'] == 'mdm')
    after_mdm = methods.method_figure('mdm')
    before_core = {k: v for k, v in before_mdm.items()
                   if k not in ('criterion_symbol', 'criterion_definition', 'numerical_evaluation')}
    assert after_mdm == before_core, 'Curve provenance or six-panel axes changed.'
    after_mdm.update(criterion_symbol=r'\nabla(\gamma)',
                     criterion_definition='paper conditional minimum standard deviation gradient',
                     numerical_evaluation='saved finite differences; no covariance formula used for drawing')
    qa['process_figures'] = [after_mdm if r['method'] == 'mdm' else r for r in qa['process_figures']]
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')

    for name, expected in protected.items():
        assert digest(ROOT / name) == expected, name
    sync_docs()
    replace_bytes(HERE / '核验交付.py',
                  "    for item in compatibility['existing_exports_renumbered_without_redrawing']:\n        assert digest(ROOT / item['to']) == item['sha256']\n        assert not (ROOT / item['from']).exists()",
                  "    mdm_revision = json.loads((ROOT / '程序/20261010-MDM原文表达修订.json').read_text(encoding='utf-8'))\n    assert mdm_revision['plotted_numerical_curve_data_unchanged']\n    assert mdm_revision['six_panel_axes_unchanged']\n    assert mdm_revision['new_samples'] == mdm_revision['new_estimates'] == 0\n    for item in compatibility['existing_exports_renumbered_without_redrawing']:\n        if item['to'] == mdm_revision['figure']:\n            assert item['sha256'] == mdm_revision['previous_figure_sha256']\n            assert digest(ROOT / item['to']) == mdm_revision['figure_sha256']\n        else:\n            assert digest(ROOT / item['to']) == item['sha256']\n        assert not (ROOT / item['from']).exists()")
    record = dict(task='2026-10-10: use original MDM expressions in report 1',
                  source='Xie et al. 2025, equations 3, 4, 6, 7 and section 2',
                  paper_equations=['exact median rank', 'pseudo scale', 'finite-difference gradient', 'mean scale'],
                  removed=['covariance gradient expression', 'weight standard deviation bound', 'weight contraction explanation'],
                  implementation_disclosure='archived calculations retain Bernard ranks, continuous beta search and numerical differentiation',
                  report_sha256=digest(REPORT), generator_sha256=digest(GENERATOR),
                  figure=figure, previous_figure_sha256=previous_figure_hash,
                  figure_sha256=digest(ROOT / figure), figure_only_label_changed=True,
                  outside_mdm_section_unchanged=True, protected_files_unchanged=len(protected),
                  plotted_numerical_curve_data_unchanged=True, paired_examples_unchanged=True,
                  six_panel_axes_unchanged=True, redrawn_figures=1, new_export_formats=['png'],
                  new_samples=0, new_estimates=0)
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    main()
