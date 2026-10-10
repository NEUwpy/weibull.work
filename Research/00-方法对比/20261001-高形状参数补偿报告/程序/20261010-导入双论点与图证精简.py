"""Keep chapter 2's two arguments prominent; move supporting algebra to the end.

Reuse every archived equation and figure. No sampling, estimation or plotting.
"""
from collections import Counter
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
APPENDIX_TITLE = '**补充推导｜最小观测与局部分位补偿**'

INTRO = r"""## 第二章　机制分析与对照实验

高β、小n下，较弱的位置约束与三参数补偿，使偏移后的参数组合仍可能保持相近的中部拟合。

三参数Weibull分布为：

$$\begin{aligned}
F(t)&=1-\exp\left[-\left(\frac{t-\gamma}{\eta}\right)^\beta\right],\\
f(t)&=\frac{\beta}{\eta}\left(\frac{t-\gamma}{\eta}\right)^{\beta-1}
\exp\left[-\left(\frac{t-\gamma}{\eta}\right)^\beta\right].
\end{aligned}$$

其中，t为寿命，F(t)为分布函数，f(t)为概率密度，β、η、γ分别为形状、尺度和位置参数；β>0、η>0、t>γ。后文ln表示自然对数。

位置参数须满足γ<t₁，其中t₁为最小观测。最小观测与真实γ之间的距离，决定了位置上移所受的上界约束。

![图2　样本观测与真实起点](20261001-高形状参数补偿报告/结果/图2_样本与真实起点.png)

**图2｜高β、小n下，样本对γ上移的上界约束较弱，随n增大而增强。**

γ与η、β的相互补偿，使参数偏移未必造成明显的中部拟合差异（图3）。

![图3　参数补偿后的分布与样本](20261001-高形状参数补偿报告/结果/图2_样本与分布相容.png)

**图3｜同一组W(5,1000,500)观测可同时贴近真分布与W(2,500,1000)的中部曲线。**

这些结果解释了偏移组合为何仍能与样本相容。下面从各方法的判据出发，分析实际估计为何发生偏移。

记排序观测到候选γ的距离为：

$$d_i=t_i-\gamma,\qquad 0\leq\gamma<t_1.$$

其中，tᵢ为从小到大排序的第i个观测，dᵢ为该观测到候选位置的距离，i=1,…,n，n为样本量。后文求和均遍历这n个观测，帽号表示估计值。

"""

APPENDIX = r"""**补充推导｜最小观测与局部分位补偿**

最小观测超过t，要求n个独立观测都超过t，故其生存概率为$[1-F(t)]^n$；对t取负导数，得到：

$$f_{t_1}(t)=n[1-F(t)]^{n-1}f(t).$$

其中，fₜ₁(t)为最小观测的概率密度，图2下方的理论密度按此式计算。

由F(Q(p))=p，解得寿命分位点：

$$Q(p)=\gamma+\eta[-\ln(1-p)]^{1/\beta},\qquad
Q(1-e^{-1})=\gamma+\eta.$$

其中，Q(p)为累计概率p对应的寿命分位点，0<p<1，e为自然指数的底数，1−e⁻¹≈0.632。将分位公式在63.2%分位附近作一阶展开：

$$z=\ln[-\ln(1-p)],\qquad
Q(p)=\gamma+\eta\exp(z/\beta)
\approx(\gamma+\eta)+\frac{\eta}{\beta}z.$$

其中，z为累计概率的双对数变换，z=0对应63.2%分位。γ+η决定中部位置，η/β是此处分位曲线关于z的斜率。升高γ并降低η，可保持中部位置接近；再按相近比例降低β，可保持局部斜率接近。

例如，W(5,1000,500)与W(2.5,500,1000)的中部分位均为1500、局部斜率均为200。两者尾部仍不同，上述近似只适用于z/β较小的范围。

图3以接近原案例MDM估计的W(2,500,1000)作对照。所用7个观测来自W(5,1000,500)，最小值约1167，γ=1000满足支持条件γ<t₁。黑点的累计概率由样本排序近似，反映抽样波动；该例展示中部拟合的相近，不表示两套分布相同。

图4–8对比β=2、5和n=7、15，每个条件使用50组样本；同一样本量下两种β共用潜在单位指数样本E。下排两格分别展开上排两条深蓝曲线。MDM按梯度交点定位γ；WMLE、MLE联合估计，其γ条件曲线用于分析联合准则。
"""


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
    chapter1, body = original.split('## 第二章', 1)
    old_intro, tail = body.split('### 2.1 MDM', 1)
    tail = tail.split(APPENDIX_TITLE, 1)[0].rstrip()
    equations = Counter(re.findall(r'\$\$[\s\S]*?\$\$', original))
    figures = re.findall(r'^!\[.*$', original, re.M)
    text = chapter1 + INTRO + '### 2.1 MDM' + tail + '\n\n' + APPENDIX
    assert text.split('## 第二章', 1)[0] == chapter1
    assert text.split('### 2.1 MDM', 1)[1].split(APPENDIX_TITLE, 1)[0].rstrip() == tail
    assert Counter(re.findall(r'\$\$[\s\S]*?\$\$', text)) == equations
    assert re.findall(r'^!\[.*$', text, re.M) == figures
    assert len(re.findall(r'\$\$[\s\S]*?\$\$', INTRO)) == 2

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
    spec = importlib.util.spec_from_file_location(
        'minimum_density_entry', HERE / '20261010-图2最小值密度曲线.py')
    density_entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(density_entry)
    generated_hashes = digest(REPORT), digest(GENERATOR)
    density_entry.sync_density_derivation()
    assert (digest(REPORT), digest(GENERATOR)) == generated_hashes
    for name, sha in protected.items():
        assert digest(ROOT / name) == sha, name

    record = dict(task='2026-10-10: two arguments and figure evidence in chapter 2 opening',
                  previous_report_sha256=hashlib.sha256(before).hexdigest(),
                  report_sha256=digest(REPORT), generator_sha256=digest(GENERATOR),
                  chapter1_unchanged=True, method_sections_and_existing_end_material_unchanged=True,
                  equations_preserved=sum(equations.values()), moved_equations=3,
                  density_sync_preserves_supplement_position=True,
                  intro_display_equations=2, original_intro_characters=len(old_intro),
                  current_intro_characters=len(INTRO.split('## 第二章', 1)[1]),
                  figure_links_unchanged=len(figures),
                  protected_scientific_and_figure_files_unchanged=len(protected),
                  claims=['Figure 2: high-beta small samples impose a weaker upper bound on gamma.',
                          'Figure 3: compensated parameters can retain a similar central sample fit.'],
                  inference='Both explain compatibility; subsequent method criteria explain returned shifts.',
                  new_random_draws=0, new_estimates=0, redrawn_figures=0)
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8', newline='\n')
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    main()
