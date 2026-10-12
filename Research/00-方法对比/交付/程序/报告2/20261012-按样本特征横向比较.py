"""2.2只归纳样本结构，2.3按结构比较方法响应；复用存档结果。"""
from pathlib import Path
import argparse
import importlib.util
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r2_previous_structure', HERE / '20261012-共同样本特征与方法响应.py')
stage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = stage
spec.loader.exec_module(stage)
base = stage.base
QA = HERE / (Path(__file__).stem + '-核验.json')
BODY = r'''### 2.2　明显异常样本的共同特征

2.1中的明显异常样本反复出现以下三类结构，这些特征可以在同一样本中叠加。

**（1）下端信息异常。**

包括最小观测离真位置较远、最小值孤立、下端若干观测聚集，以及下端与其余点列之间存在较大空缺。W(2,1000,3000)、n=7的第35组有四个观测集中在3215.58—3274.68，最大观测达到4698.54；第5组的最小观测为3301.70，第二小观测为3818.64，后续点列较集中。前者表现为下端成簇与远端观测并存，后者表现为孤立的最小值。

β和n影响下端空缺出现的概率。独立Weibull样本的最小值满足：

$$
\Pr\{X_{(1)}>\gamma+a\eta\}
=[1-F_X(\gamma+a\eta)]^n
=\exp(-na^\beta),\qquad 0<a<1.
\tag{28}
$$

X₍₁₎为样本最小值，Fₓ为Weibull分布函数，a为以尺度计的下端距离。由式（28），取n=15、a=0.5，最小值进入γ+0.5η以内的概率，β=2时约98%，β=5时约37%。β增大或n减小，下端缺少观测的情形更常见。

**（2）整体或局部距离过度集中。**

集中可以发生在整个点列，也可以发生在最小观测以外的局部点列。上述第5组以最小观测为基准后，其余六个距离落在516.94—789.60，对数跨度仅0.42；同条件正常第4组的保留距离为279.54—1540.59，对数跨度为1.71。W(5,1000,500)、n=7的第29组在真位置下的对数距离也明显比第28组集中。

**（3）距离过度分散或存在远端点。**

W(2,1000,500)、n=7第19组的前六个观测位于779.38—1302.69，最大观测达到2480.21，明显远离其余点列。W(5,100,500)、n=7第11组以最小观测为基准后，保留距离由约9.34增至53.94，对数距离标准差为0.80，高于正常第10组的0.42。

明显异常并不是由某一种固定样本形态造成，而是集中表现为下端信息不足、局部间距异常，以及距离过度集中或分散等结构。

### 2.3　不同方法对异常样本特征的响应

2.2节归纳了明显异常样本中反复出现的几类特征。它们的影响取决于方法怎样使用位置、距离跨度、局部间距和整体离散程度，同一类特征因而可能形成不同方向和不同程度的参数偏移。

#### 2.3.1　对下端信息异常的响应

下端结构使真位置下的点列弯曲时，LSE、LRE通过移动位置改善线性匹配。第19组在两种回归方法中都选择靠近最小观测的右侧位置，分别改善式（12）的拟合程度和式（16）的相关性。位置移动吸收了部分下端间距异常，也改变了后续用于估计形状的对数跨度。

MDM对这类特征的响应体现在梯度阈值交点。第35组直到距最小观测仅3.91的位置才达到δ=0.20（图3），于是采用靠右位置，并在该位置得到较小形状与尺度。下端结构在回归方法中改变最佳线性位置，在MDM中则改变式（5）的阈值交点。

最小距离的变化还会进入WMLE式（18）的倒数距离项，其位置响应要与式（17）的形状关系共同平衡。MLE则按式（21）评价这些距离与形状、尺度共同形成的似然。MMLE直接按式（25）把最小观测作为位置，最小值偏离真位置的程度随即进入保留距离。相同的下端信息，分别经过线性匹配、梯度交点、联合方程、整体似然或最小值定位影响参数。

#### 2.3.2　对距离过度集中的响应

W(2,100,500)、n=15第36组提供了同一样本的横向比较。LSE左移位置后，对数跨度由1.74压缩至0.20，斜率降至0.046，按式（10）取倒数得到β̂=21.70。LRE的对数距离在横轴，跨度缩至0.23时拟合线变陡，按式（15）直接取斜率得到β̂=18.80。MLE的零位置候选比真位置条件拟合提高约0.68的对数似然，对应β̂=23.54。三种方法对集中结构都形成了明显高估，但起作用的环节分别是斜率倒数、回归斜率与整体似然。

同一第36组在MDM（δ=0.20）、WMLE、MMLE中的β̂分别为2.91、5.01、3.26，均未达到高估界限6。这些方法按伪尺度差异、两条加权关系或最小值定位后的保留距离确定参数，未选择前述回归或似然方法的左侧组合。MMLE取γ̂=524.67、恢复η̂=83.27，与LSE的γ̂=0、η̂=609.36相比，位置与尺度的偏移方向也不同。

距离集中还可以在位置正确时直接进入形状关系。由式（23），1/β等于对数距离的加权均值与普通均值之差。加权均值不超过最大值，因此方程的根满足：

$$
\hat\beta(\gamma)\ge\frac1{\max_i y_i-\bar y}.
\tag{29}
$$

按式（29），W(5,1000,500)、n=7第29组在真位置下的形状下界为33.62，式（23）的根为55.69；第28组的根为6.16。图21同时展示这种集中结构在LSE、LRE和MLE中的不同响应。固定真位置的全量对照仍有15条高估，均发生于n=7。

![固定位置时对数距离集中对回归与似然形状的影响](交付/结果/报告2/固定位置的回归与形状得分.png)

**图21｜给定真位置后，第29组集中的对数距离仍支持较大形状。**

MMLE第5组则体现局部集中：最小值固定为位置后，六个保留距离相近，式（26）的似然峰落在β̂=7.69（图20）。集中结构在这里通过保留观测的似然影响形状。

γ/η的作用也发生在这一距离集中环节。对真分布写成X=γ+ηZ，可得：

$$
\mathrm{CV}(X)=\frac{\mathrm{SD}(Z)}{\gamma/\eta+\mathbb E[Z]}.
\tag{30}
$$

Z为形状β、尺度1、位置0的Weibull变量，CV为标准差与均值之比，SD为标准差，𝔼为数学期望。由式（30），形状固定时，γ/η越大，原始观测的相对离散越小。

本批位置下界为0。较大的γ/η会使接近零位置的候选距离表现出更小的相对离散度；对于将较集中的距离结构对应为较大形状的回归或似然关系（式（10）、（15）、（23）），这会增强左侧候选产生形状高估的倾向。

#### 2.3.3　对距离过度分散或远端点的响应

第19组的远端最大值使真位置下的点列弯曲。LSE、LRE右移位置后，下端对数间距被拉开，线性匹配改善；LSE的斜率增大，取倒数后β̂=0.58，LRE的拟合线变平，直接取斜率后β̂=0.56。同一第19组在MMLE中得到β̂=0.87，虽低于真值2，但未越过低估界限2/3。相同的分散点列，经不同位置与形状关系形成了不同程度的低估。

MMLE第11组的保留对数距离比正常样本更分散，式（26）的似然峰位于β̂=1.54（图19）。WMLE对同一个第11组则在β̂=1.10、γ̂=573.51处同时满足两条加权方程（图12）。距离变化同时进入对数均值、幂加权均值和倒数距离项，WMLE的偏移方向与幅度由共同交点确定。

上述比较可归纳为以下对应关系：

| 样本特征 | 起作用的估计环节 | 可能的参数响应 |
|---|---|---|
| 下端空缺、局部间距异常 | LSE、LRE移动位置改善线性匹配 | γ偏移，β随斜率变化 |
| 下端观测成簇、局部间距异常 | MDM的梯度阈值交点移动 | 交点靠近最小值时，β与η可降低 |
| 距离过度集中 | LSE、LRE的跨度与斜率变化 | β增大 |
| 距离过度集中 | MLE的整体似然比较 | 可能支持左侧大β组合 |
| 最小值偏大、保留距离集中或分散 | MMLE的最小值定位与保留观测似然 | 集中可对应大β，分散可对应小β |
| 局部间距与整体距离变化 | WMLE的两条加权方程共同平衡 | 方向与幅度由联合交点确定 |

第36组和第19组显示，同一个样本可以在部分方法中越过异常阈值，在另一些方法中只产生较小偏移。差别来自样本特征进入的估计环节，以及位置、形状与尺度在该环节中的配合。

实际返回的形状还受搜索范围限制。本批MDM、WMLE的形状搜索上限分别为15、10；β=5时的高估界限为15，这些上限限制了可计入高估的返回值。
'''


def correct(text):
    if (HERE / '20261012-方法响应直白表述-核验.json').exists():
        later = base.module('20261012-方法响应直白表述')
        before = later.restore(text)
        if before != text:
            return later.correct(correct(before))
    record = base.load(QA)
    if record['after_body'] in text:
        return base.module('20261012-方法响应直白表述').correct(text) if (HERE / '20261012-方法响应直白表述-核验.json').exists() else text
    assert text.count(record['before_body']) == 1
    text = text.replace(record['before_body'], record['after_body'])
    return base.module('20261012-方法响应直白表述').correct(text) if (HERE / '20261012-方法响应直白表述-核验.json').exists() else text


def restore(text):
    if (HERE / '20261012-方法响应直白表述-核验.json').exists():
        text = base.module('20261012-方法响应直白表述').restore(text)
    if QA.exists():
        record = base.load(QA)
        text = text.replace(record['after_body'], record['before_body'])
    return text


def shared_cases():
    sources = base.load(base.PROGRAM / '跨参数对比/13组合取数.json')['sources']
    cases = {}
    for combination, n, group in [('W(2,100,500)', 15, 36), ('W(2,1000,500)', 7, 19)]:
        src = next(s for s in sources if s['combination'] == combination)
        path = base.matrix_path(src)
        assert base.digest(path) == src['matrix_sha256']
        data = base.load(path)
        rows = [r for r in data['results'] if r['n'] == n and r['id'] == group
                and (r['method_id'] != 'mdm' or r['delta'] == .2)]
        cases[combination] = dict(n=n, group=group, source_sha256=base.digest(path), results=rows)
    return cases


def apply():
    if QA.exists():
        verify()
        return
    text = base.REPORT.read_text(encoding='utf-8')
    a, b = text.index('### 2.2'), text.index('## 3　改进方向')
    before, after = text[a:b], BODY.rstrip() + '\n\n'
    assert re.findall(r'\$\$.*?\$\$', before, re.S) == re.findall(r'\$\$.*?\$\$', after, re.S)
    revised = text[:a] + after + text[b:]
    pair = base.module('20261011-MDM近真值对照')
    previous = base.load(stage.run.prior.QA)
    assert base.text_digest(text) == previous['after_text_sha256']
    record = dict(before_body=before, after_body=after, before_text_sha256=base.text_digest(text),
                  after_text_sha256=base.text_digest(revised), previous_outside_sha256=previous['outside_after_sha256'],
                  shared_cases=shared_cases(), formulas=re.findall(r'\$\$.*?\$\$', text, re.S),
                  sample_tables=pair.tables(text), images=re.findall(r'!\[[^\]]*\]\((.*?)\)', text),
                  section_contract=dict(section22='Describe lower-end structure, concentration, dispersion/remote points only.',
                                        section23='Compare parameter responses by the same feature, including same archived samples.',
                                        evidence='Group36 and group19 matched comparisons; Figure21 retained.', new_calculations=0))
    base.write_json(QA, record)
    pair.write_text(base.REPORT, revised)
    previous.update(after_text_sha256=record['after_text_sha256'], outside_after_sha256=base.text_digest(pair.block(revised)[1]),
                    horizontal_response_revision=QA.name)
    base.write_json(stage.run.prior.QA, previous)
    old_pair = base.load(pair.QA)
    assert old_pair['outside_block_sha256'] == record['previous_outside_sha256']
    old_pair.update(outside_block_sha256=previous['outside_after_sha256'], horizontal_response_revision=QA.name)
    base.write_json(pair.QA, old_pair)
    readme = base.ROOT / 'README.md'
    content = readme.read_text(encoding='utf-8')
    old = '[结构修订脚本](交付/程序/报告2/20261012-共同样本特征与方法响应.py)保存当前正文与核验；'
    new = '[当前结构脚本](交付/程序/报告2/20261012-按样本特征横向比较.py)保存按样本特征组织的2.2、2.3及同组结果核验；'
    assert content.count(old) == 1
    pair.write_text(readme, content.replace(old, new))
    verify()


def verify():
    record = base.load(QA)
    text = base.REPORT.read_text(encoding='utf-8')
    assert correct(text) == text
    if (HERE / '20261012-方法响应直白表述-核验.json').exists():
        text = base.module('20261012-方法响应直白表述').restore(text)
    assert base.text_digest(text) == record['after_text_sha256']
    assert base.text_digest(restore(text)) == record['before_text_sha256']
    assert re.findall(r'\$\$.*?\$\$', text, re.S) == record['formulas']
    assert re.findall(r'\\tag\{(\d+)\}', text) == [str(i) for i in range(1, 31)]
    assert base.module('20261011-MDM近真值对照').tables(text) == record['sample_tables']
    assert re.findall(r'!\[[^\]]*\]\((.*?)\)', text) == record['images']
    assert re.findall(r'^\*\*图(\d+)｜', text, re.M) == [str(i) for i in range(1, 22)]
    assert shared_cases() == record['shared_cases']
    group36 = {r['method_id']: r for r in record['shared_cases']['W(2,100,500)']['results']}
    assert all(r['status'] == 'success' for r in group36.values())
    assert all(group36[m]['beta_hat'] >= 6 for m in ('lse', 'lre', 'mle'))
    assert all(2/3 < group36[m]['beta_hat'] < 6 for m in ('mdm', 'wmle', 'mmle'))
    assert group36['lse']['gamma_hat'] < 500 < group36['mmle']['gamma_hat']
    assert group36['mmle']['eta_hat'] < 100 < group36['lse']['eta_hat']
    group19 = {r['method_id']: r for r in record['shared_cases']['W(2,1000,500)']['results']}
    assert all(group19[m]['status'] == 'success' and group19[m]['beta_hat'] < 2/3 for m in ('lse', 'lre'))
    assert group19['mmle']['status'] == 'success' and group19['mmle']['beta_hat'] > 2/3
    stage.run.prior.verify()
    record.update(validation='passed', script_sha256=base.digest(__file__), formulas_data_figures_unchanged=True)
    base.write_json(QA, record)
    print('PASS: feature-based structure and matched-case response differences; original formulas, tables, figures and data retained.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
