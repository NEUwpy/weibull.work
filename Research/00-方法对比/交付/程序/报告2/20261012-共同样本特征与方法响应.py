"""重组报告2的2.2、2.3：共同样本特征与方法响应，沿用现有公式和证据。"""
from pathlib import Path
import argparse
import importlib.util
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r2_structure_base', HERE / '20261012-MLE总述精简.py')
run = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = run
spec.loader.exec_module(run)
base = run.base
QA = HERE / (Path(__file__).stem + '-核验.json')
INTRO_BEFORE = '2.1节通过正常与异常样本对照，分析各方法的典型形成过程；2.2节讨论样本条件的影响；2.3节比较不同方法对同类样本特征的响应。'
INTRO_AFTER = '2.1节追踪典型异常在哪个估计环节形成；2.2节归纳这些个案背后的共同样本特征；2.3节比较不同方法怎样将这些特征转化为不同的参数响应。'
BODY = r'''### 2.2　样本特征如何为异常估计提供条件

2.1中的典型异常可从两个方面归纳：下端信息不足，使位置难以确定；距离结构过于集中或分散，使形状恢复不稳定。

**（1）下端信息不足，位置约束减弱。**

当最小观测远离真位置时，真位置附近缺少观测，样本对位置的约束减弱。形状与尺度的调整又可使不同位置候选保持较好的拟合，为位置偏移提供条件。

形状参数和样本量影响下端空缺出现的概率。独立Weibull样本的最小值满足：

$$
\Pr\{X_{(1)}>\gamma+a\eta\}
=[1-F_X(\gamma+a\eta)]^n
=\exp(-na^\beta),\qquad 0<a<1.
\tag{28}
$$

X₍₁₎为样本最小值，Fₓ为Weibull分布函数，a为以尺度计的下端距离。由式（28），取n=15、a=0.5，最小值进入γ+0.5η以内的概率，β=2时约98%，β=5时约37%。β增大或n减小，都使下端空缺更容易出现；增大n则增加下端观测，从这一环节加强位置约束。

**（2）距离结构过于集中或分散，形状恢复不稳定。**

小样本的偶然间距会改变距离结构。观测可能十分集中，也可能形成较小距离与较大距离并存的结构，这些差异进入形状估计所用的斜率或对数距离统计量。

W(5,1000,500)、n=7的第28、29组在同一真位置下比较（图21）。第28组的对数距离较分散，第29组则十分集中，后者同时支持较大的回归形状和似然形状。

由式（23），1/β等于对数距离的加权均值与普通均值之差。加权均值不超过最大值，因此方程的根满足：

$$
\hat\beta(\gamma)\ge\frac1{\max_i y_i-\bar y}.
\tag{29}
$$

按式（29），第29组的形状下界已达到33.62，式（23）的根为55.69；第28组的根为6.16。固定真位置的全量对照仍有15条高估，均发生于n=7。这说明部分高估在位置正确时仍会形成，样本自身的集中程度已足以使形状关系支持较大β。

![固定位置时对数距离集中对回归与似然形状的影响](交付/结果/报告2/固定位置的回归与形状得分.png)

**图21｜给定真位置后，第29组集中的对数距离仍支持较大形状。**

距离分散也会对应较小的形状。MMLE第11组的保留对数距离比正常样本更分散，似然峰对应较小β（图19）；第5组的保留距离更集中，似然峰对应较大β（图20）。两组采用相同的最小值定位规则，差别来自实际保留距离的结构。

下端空缺与距离结构异常可以出现在同一样本中。前者削弱位置约束，后者改变形状恢复所依据的距离关系；各方法怎样处理这两类特征，决定了后续的参数响应。

### 2.3　不同方法对样本特征的响应

同样的下端空缺或距离集中会进入不同的估计环节。位置候选按什么准则选择，距离结构按什么关系恢复为形状与尺度，是方法间的关键区别。

**位置和形状通过不同准则确定。**

| 方法 | 位置与形状怎样确定 | 样本特征怎样影响参数 |
|---|---|---|
| MDM | 各位置下按式（4）选形状，再按式（5）的梯度达到δ定位 | 所选位置改变伪尺度之间的差异；右侧交点可对应较小形状，尺度按式（6）取伪尺度均值 |
| LSE | 以顺序统计量期望为参考，按式（12）选择拟合最好的位置 | 左移压缩对数间距时，斜率可减小，式（10）取其倒数得到较大β；右移拉开间距时可形成低估 |
| LRE | 以绘图概率变换为参考，按式（16）选择相关性最高的位置 | 对数距离在横轴，压缩时斜率可增大，式（15）直接取斜率得到较大β；参考点和回归方向均不同于LSE |
| WMLE | 联立式（17）、（18）共同确定β、γ | 对数距离与倒数距离同时改变两式的平衡位置，共同交点可落在较小或较大的形状处 |
| MLE | 按式（21）比较形状、尺度和位置组合的似然 | 位置变化改变式（23）中的对数距离均值之差，影响对应的形状；较高似然候选可偏离真值 |
| MMLE | 按式（25）取最小观测为位置，再由式（26）的似然峰确定形状 | 最小值平移后的保留距离分散或集中，分别可对应较小或较大的形状峰 |

图21对相同样本、相同位置的比较显示了不同的形状恢复关系：第29组在LSE中形成较小斜率，按式（10）取倒数得到较大β；在LRE中形成较大斜率，按式（15）直接得到较大β；在MLE中，式（23）的均值之差较小，方程的根移向较大β。同一种距离集中，通过不同的参考点、回归方向或似然关系影响形状。

位置尺度比进一步改变了左侧候选呈现的距离结构。对真分布写成X=γ+ηZ，可得：

$$
\mathrm{CV}(X)=\frac{\mathrm{SD}(Z)}{\gamma/\eta+\mathbb E[Z]}.
\tag{30}
$$

Z为形状β、尺度1、位置0的Weibull变量，CV为标准差与均值之比，SD为标准差，𝔼为数学期望。由式（30），形状固定时，γ/η越大，原始观测的相对离散越小。

本批位置下界为0。较大的γ/η会使接近零位置的候选距离表现出更小的相对离散度；对于将较集中的距离结构对应为较大形状的回归或似然关系（式（10）、（15）、（23）），这会增强左侧候选产生形状高估的倾向。

**尺度恢复进一步形成不同的参数组合。**

MDM取伪尺度均值（式（6）），LSE、LRE使用回归截距（式（10）、（15）），WMLE使用校准幂均值（式（20）），MLE、MMLE使用距离幂均值（式（22）、（27））。位置与形状的变化通过这些关系共同带动尺度，因此相同样本特征会形成不同的参数偏移方向和幅度。

数值求解还决定程序实际返回哪个候选。MLE第37组的近零返回值来自停止和候选接受环节；MDM第5组的离散扫描已发现交点，最终选参分支未采用该结果，导致右端回退和高估。本批MDM、WMLE的形状搜索上限分别为15、10；β=5时的高估界限为15，这些上限限制了可计入高估的返回值。
'''


def correct(text):
    if (HERE / '20261012-按样本特征横向比较-核验.json').exists():
        later = base.module('20261012-按样本特征横向比较')
        before = later.restore(text)
        if before != text:
            return later.correct(correct(before))
    record = base.load(QA)
    if record['after_body'] not in text:
        assert text.count(record['before_body']) == 1
        text = text.replace(record['before_body'], record['after_body'])
    if INTRO_AFTER not in text:
        assert text.count(INTRO_BEFORE) == 1
        text = text.replace(INTRO_BEFORE, INTRO_AFTER)
    if (HERE / '20261012-按样本特征横向比较-核验.json').exists():
        text = base.module('20261012-按样本特征横向比较').correct(text)
    return text


def restore(text):
    if (HERE / '20261012-按样本特征横向比较-核验.json').exists():
        text = base.module('20261012-按样本特征横向比较').restore(text)
    if QA.exists():
        record = base.load(QA)
        text = text.replace(record['after_body'], record['before_body'])
        text = text.replace(INTRO_AFTER, INTRO_BEFORE)
    return text


def apply():
    if QA.exists():
        verify()
        return
    text = base.REPORT.read_text(encoding='utf-8')
    start, end = text.index('### 2.2'), text.index('## 3　改进方向')
    before = text[start:end]
    after = BODY.rstrip() + '\n\n'
    math = lambda s: re.findall(r'\$\$.*?\$\$', s, re.S)
    assert math(before) == math(after), 'Keep all existing formulas verbatim and in order'
    record = dict(before_body=before, after_body=after, intro_before=INTRO_BEFORE, intro_after=INTRO_AFTER,
                  before_text_sha256=base.text_digest(text),
                  section_contract=dict(section22='Lower-end information and distance structure as two sample-side conditions.',
                                        section23='Compare criteria and parameter recovery; location-scale ratio amplifies left candidates.',
                                        formulas='Keep 28, 29, 30 unchanged; move CV relation into method response.',
                                        figures='Keep Figure21 and all source results.'),
                  formulas_before=math(text), sample_tables_before=base.module('20261011-MDM近真值对照').tables(text))
    base.write_json(QA, record)
    revised = correct(text)
    pair = base.module('20261011-MDM近真值对照')
    previous = base.load(run.prior.QA)
    assert base.text_digest(text) == previous['after_text_sha256']
    record.update(after_text_sha256=base.text_digest(revised), previous_outside_sha256=previous['outside_after_sha256'])
    pair.write_text(base.REPORT, revised)
    base.write_json(QA, record)
    previous.update(after_text_sha256=record['after_text_sha256'], outside_after_sha256=base.text_digest(pair.block(revised)[1]),
                    structure_revision=QA.name)
    base.write_json(run.prior.QA, previous)
    existing = base.load(pair.QA)
    assert existing['outside_block_sha256'] == record['previous_outside_sha256']
    existing.update(outside_block_sha256=previous['outside_after_sha256'], structure_revision=QA.name)
    base.write_json(pair.QA, existing)
    readme = base.ROOT / 'README.md'
    content = readme.read_text(encoding='utf-8')
    old = '报告2按典型形成过程组织分析，'
    new = '报告2第二章按“个案追踪—共同样本特征—方法响应比较”组织，[结构修订脚本](交付/程序/报告2/20261012-共同样本特征与方法响应.py)保存当前正文与核验；'
    assert content.count(old) == 1
    pair.write_text(readme, content.replace(old, new))
    verify()


def verify():
    record = base.load(QA)
    text = base.REPORT.read_text(encoding='utf-8')
    assert correct(text) == text
    if (HERE / '20261012-按样本特征横向比较-核验.json').exists():
        text = base.module('20261012-按样本特征横向比较').restore(text)
    assert base.text_digest(text) == record['after_text_sha256']
    assert base.text_digest(restore(text)) == record['before_text_sha256']
    assert re.findall(r'\$\$.*?\$\$', text, re.S) == record['formulas_before']
    assert re.findall(r'\\tag\{(\d+)\}', text) == [str(i) for i in range(1, 31)]
    pair = base.module('20261011-MDM近真值对照')
    assert pair.tables(text) == record['sample_tables_before']
    assert re.findall(r'^\*\*图(\d+)｜', text, re.M) == [str(i) for i in range(1, 22)]
    run.prior.verify()
    record.update(validation='passed', script_sha256=base.digest(__file__), formulas_data_figures_unchanged=True)
    base.write_json(QA, record)
    print('PASS: two sample-side sources, method response comparison, unchanged formulas 1-30 and Figures1-21.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
