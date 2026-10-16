"""2.3用直白文字比较响应；原推导归回方法介绍与样本特征。"""
from pathlib import Path
import argparse
from collections import Counter
import importlib.util
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r2_horizontal_structure', HERE / '20261012-按样本特征横向比较.py')
stage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = stage
spec.loader.exec_module(stage)
base = stage.base
QA = HERE / (Path(__file__).stem + '-核验.json')
NUMBERS = {25: 26, 26: 27, 27: 28, 28: 29, 29: 25}
TAG = re.compile(r'\\tag\{(\d+)\}')
REF = re.compile(r'式（\d+）(?:[、—]（\d+）)*')
BODY = r'''### 2.3　不同方法对异常样本特征的响应

同一种样本结构，进入不同方法后会经过不同的估计环节，因而产生不同方向和不同程度的参数偏移。

#### 2.3.1　对下端信息异常的响应

下端间距与直线不匹配时，LSE、LRE通过移动位置改善线性匹配，形状随回归斜率一起变化。MDM则通过梯度阈值交点响应：交点靠近最小观测时，所选位置偏右，随后形状与尺度可能偏小。

MMLE直接把最小观测作为位置，最小值偏离真位置的程度会直接进入后续距离。WMLE将下端距离的变化放入两条加权关系共同平衡，MLE则评价这些距离与形状、尺度组成的整体似然。它们使用同样的下端信息，但确定位置的依据不同。

#### 2.3.2　对距离过度集中的响应

LSE和LRE都对对数跨度敏感，但回归方向不同：跨度压缩时，LSE的斜率变小，取倒数后形状变大；LRE的拟合线变陡，直接取斜率后形状变大。

MLE、MMLE通过似然响应集中结构：较集中的距离可以让大形状组合得到更高似然。MMLE采用的是最小值定位后的保留距离；这些距离越集中，似然峰越容易偏向大形状。

MDM通过伪尺度的一致程度选择形状，WMLE通过两条加权关系的共同交点确定形状与位置。它们读取的统计关系与回归斜率不同，所以相同的集中结构可以产生不同大小的偏移。

真位置相对尺度较大时，接近零位置的候选距离更集中。采用这类候选的回归或似然方法，更容易将集中结构放大成形状高估。

![固定位置时对数距离集中对回归与似然形状的影响](交付/结果/报告2/固定位置的回归与形状得分.png)

**图21｜固定真位置时，距离集中仍可能对应较大形状。**

#### 2.3.3　对距离过度分散或远端点的响应

远端点可能使回归点列弯曲。LSE、LRE通过右移位置拉开下端对数间距，改善线性匹配；LSE取斜率倒数，LRE直接取斜率，两条不同的恢复关系都可能给出较小形状。位置靠近最小值时，参与估计的距离缩小，尺度也容易随之降低。

MMLE保留距离较分散时，似然峰更容易偏向小形状。WMLE中的分散结构则同时改变对数距离、幂加权距离和倒数距离，最终方向与幅度由两条关系共同平衡的位置决定。

这些差别使同一类特征在部分方法中形成明显异常，在另一些方法中只产生较小偏移。

| 样本特征 | 方法怎样响应 | 可能的参数变化 |
|---|---|---|
| 下端空缺、局部间距异常 | LSE、LRE移动位置改善线性匹配 | γ偏移，β随斜率变化 |
| 下端观测成簇、局部间距异常 | MDM的梯度阈值交点移动 | 交点靠近最小值时，β与η可降低 |
| 距离过度集中 | LSE、LRE的跨度与斜率变化 | β增大 |
| 距离过度集中 | MLE的整体似然比较 | 可能支持左侧大β组合 |
| 最小值偏大、保留距离集中或分散 | MMLE直接定位，再拟合保留距离 | 集中可对应大β，分散可对应小β |
| 局部间距与整体距离变化 | WMLE的两条加权关系共同平衡 | 方向与幅度由联合交点决定 |
'''


def correct(text):
    if (HERE / '20261012-删去图21-核验.json').exists():
        later = base.module('20261012-删去图21')
        before = later.restore(text)
        if before != text:
            return later.correct(correct(before))
    if (HERE / '20261012-针对性改进任务-核验.json').exists():
        later = base.module('20261012-针对性改进任务')
        before = later.restore(text)
        if before != text:
            return later.correct(correct(before))
    record = base.load(QA)
    assert text in (record['after_text'], record['before_text'], record['previous_check_text']), 'Keep this approved revision scoped'
    result = record['after_text']
    if (HERE / '20261012-针对性改进任务-核验.json').exists():
        result = base.module('20261012-针对性改进任务').correct(result)
    if (HERE / '20261012-删去图21-核验.json').exists():
        result = base.module('20261012-删去图21').correct(result)
    return result


def restore(text):
    if (HERE / '20261012-删去图21-核验.json').exists():
        text = base.module('20261012-删去图21').restore(text)
    if (HERE / '20261012-针对性改进任务-核验.json').exists():
        text = base.module('20261012-针对性改进任务').restore(text)
    if QA.exists():
        record = base.load(QA)
        if text == record['after_text']:
            return record['previous_check_text']
    return text


def revise(text):
    formulas = re.findall(r'\$\$.*?\$\$', text, re.S)
    bound = next(f for f in formulas if r'\tag{29}' in f)
    cv = next(f for f in formulas if r'\tag{30}' in f)
    a, b = text.index('### 2.3'), text.index('## 3　改进方向')
    text = text[:a] + BODY.rstrip() + '\n\n' + text[b:]
    mle_anchor = '原结果分为左侧较高似然高估、右侧较高似然低估和近零停点高估。'
    mle_extra = ('由式（23），对数距离的加权均值不超过最大值，形状的根满足：\n\n' + bound
                 + '\n\n式（29）表明，对数距离集中、最大值与均值的差较小时，形状下界较大。\n\n')
    assert text.count(mle_anchor) == 1
    text = text.replace(mle_anchor, mle_extra + mle_anchor)
    cv_anchor = '**（3）距离过度分散或存在远端点。**'
    cv_extra = ('位置与尺度的比值也影响原始观测的相对离散。写成X=γ+ηZ，可得：\n\n' + cv
                + '\n\nZ为形状β、尺度1、位置0的Weibull变量，CV为标准差与均值之比，SD为标准差，𝔼为数学期望。'
                '由式（30），形状固定时，γ/η越大，原始观测的相对离散越小。\n\n')
    assert text.count(cv_anchor) == 1
    text = text.replace(cv_anchor, cv_extra + cv_anchor)
    mdm_anchor = '式（4）的最小化在候选形状范围内进行，'
    assert text.count(mdm_anchor) == 1
    text = text.replace(mdm_anchor, '本批形状搜索上限为15；当真形状为5时，高估界限同为15。' + mdm_anchor)
    wmle_anchor = '本批J₃权重表覆盖β=0.1—5，β>5采用端点工程近似。'
    assert text.count(wmle_anchor) == 1
    text = text.replace(wmle_anchor, wmle_anchor + '形状搜索上限为10。')
    text = TAG.sub(lambda m: r'\tag{' + str(NUMBERS.get(int(m[1]), int(m[1]))) + '}', text)
    text = REF.sub(lambda m: re.sub(r'\d+', lambda n: str(NUMBERS.get(int(n[0]), int(n[0]))), m[0]), text)
    return text.rstrip() + '\n'


def apply():
    if QA.exists():
        verify()
        return
    text = base.REPORT.read_text(encoding='utf-8')
    revised = revise(text)
    pair = base.module('20261011-MDM近真值对照')
    previous = base.load(stage.stage.run.prior.QA)
    previous_text = text
    if base.text_digest(text) != previous['after_text_sha256']:
        previous_text = text + '[计算记录与推导](README.md#复现入口)\n'
        assert base.text_digest(previous_text) == previous['after_text_sha256'], 'Unexpected working-copy change'
    record = dict(before_text=text, previous_check_text=previous_text, after_text=revised, before_text_sha256=base.text_digest(text),
                  after_text_sha256=base.text_digest(revised), equation_map=NUMBERS,
                  previous_outside_sha256=previous['outside_after_sha256'],
                  existing_footer_removal_preserved=(previous_text != text),
                  section_contract='2.3: three feature responses in plain language; derivations and bounds at their logical source.')
    base.write_json(QA, record)
    pair.write_text(base.REPORT, revised)
    previous.update(after_text_sha256=record['after_text_sha256'], outside_after_sha256=base.text_digest(pair.block(revised)[1]),
                    plain_response_revision=QA.name)
    base.write_json(stage.stage.run.prior.QA, previous)
    old_pair = base.load(pair.QA)
    assert old_pair['outside_block_sha256'] == record['previous_outside_sha256']
    old_pair.update(outside_block_sha256=previous['outside_after_sha256'], plain_response_revision=QA.name)
    base.write_json(pair.QA, old_pair)
    readme = base.ROOT / 'README.md'
    content = readme.read_text(encoding='utf-8')
    old = '[当前结构脚本](交付/程序/报告2/20261012-按样本特征横向比较.py)保存按样本特征组织的2.2、2.3及同组结果核验；'
    new = ('[当前表述脚本](交付/程序/报告2/20261012-方法响应直白表述.py)保存直白的2.3及原公式归位，'
           '[横向比较记录](交付/程序/报告2/20261012-按样本特征横向比较.py)保留同组证据；')
    assert content.count(old) == 1
    pair.write_text(readme, content.replace(old, new))
    verify()


def verify():
    record = base.load(QA)
    text = base.REPORT.read_text(encoding='utf-8')
    assert correct(text) == text
    if (HERE / '20261012-删去图21-核验.json').exists():
        text = base.module('20261012-删去图21').restore(text)
    if (HERE / '20261012-针对性改进任务-核验.json').exists():
        text = base.module('20261012-针对性改进任务').restore(text)
    assert base.text_digest(text) == record['after_text_sha256']
    assert record['before_text_sha256'] == base.text_digest(record['before_text'])
    assert restore(text) == record['previous_check_text']
    bodies = lambda s: Counter(TAG.sub('', f) for f in re.findall(r'\$\$.*?\$\$', s, re.S))
    assert bodies(text) == bodies(record['before_text'])
    assert TAG.findall(text) == [str(i) for i in range(1, 31)]
    refs = {int(n) for m in REF.finditer(text) for n in re.findall(r'\d+', m[0])}
    assert refs == set(range(1, 31))
    section = text[text.index('### 2.3'):text.index('## 3　改进方向')]
    assert not re.search(r'第\d+组|式（|\$\$', section)
    pair = base.module('20261011-MDM近真值对照')
    assert pair.tables(text) == pair.tables(record['before_text'])
    images = lambda s: re.findall(r'!\[[^\]]*\]\((.*?)\)', s)
    assert images(text) == images(record['before_text'])
    assert re.findall(r'^\*\*图(\d+)｜', text, re.M) == [str(i) for i in range(1, 22)]
    stage.stage.run.prior.verify()
    record.update(validation='passed', script_sha256=base.digest(__file__),
                  formulas_unchanged_and_relocated=True, original_data_figures_unchanged=True,
                  section23_characters_before=len(record['before_text'][record['before_text'].index('### 2.3'):record['before_text'].index('## 3　改进方向')]),
                  section23_characters_after=len(section))
    base.write_json(QA, record)
    print('PASS: plain 2.3 without case/formula citations; all 30 formulas, figures and source estimates preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
