"""将第3章改为计算修正与针对样本敏感性的研究任务；不重算估计。"""
from pathlib import Path
import argparse
import importlib.util
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r2_plain_response', HERE / '20261012-方法响应直白表述.py')
stage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = stage
spec.loader.exec_module(stage)
base = stage.base
prior = stage.stage.stage.run.prior
QA = HERE / (Path(__file__).stem + '-核验.json')
BEFORE = '''## 3　改进方向

较好的拟合或方程平衡可以与较大的参数误差同时出现，改进需要对应异常实际形成的环节。

已定位的计算问题先在原样本上修正并复核：MLE需在搜索中施加β≥1，处理β=1分支，并检查返回候选是否仍能提高似然；MDM需将离散扫描得到的交点区间用于求根，并在回退前检查内部交点。

方法层面，回归方法可研究线性匹配与参数恢复之间的约束，MDM可研究补偿值与样本梯度的适配，WMLE可研究校准系数及权重表端点对交点的影响，MMLE可研究最小值定位后保留距离的分散程度与形状估计的关系。

后续对照应分别评价计算修正和方法调整，以参数误差、明显异常频率及求解成功率检验对应环节的改变是否有效。
'''
AFTER = '''## 3　改进方向

**（1）修正已确认的计算问题。**

MDM应将已检测的交点区间用于求根和候选选择，确认没有有效内部交点后再执行回退。MLE应在搜索中落实β≥1的接受条件，纳入β=1边界分支，检查过早停止及候选筛选，使较高似然的合格候选进入最终比较。修正后先复算原异常样本，确认交点采用和似然比较符合预定规则。

**（2）减少方法对异常样本结构的敏感性。**

**稳定性约束的参数选择。** 单一拟合准则没有约束参数恢复的稳定性。LSE、LRE为改善线性匹配而移动γ时，可能严重拉伸或压缩对数距离，放大形状与尺度偏移。可在拟合准则之外加入参数对样本轻微扰动的稳定性约束，研究能否减少为有限的拟合改善而选择极端参数的情况。

**MMLE的自适应位置修正。** 最小值定位使位置向上偏移，偏移幅度随样本条件变化。可依据样本量、下端间距与整体离散程度修正位置，再估计形状与尺度。真实参数未知时，可尝试用神经网络在已知真值的模拟样本上学习可观测特征与位置修正量的非线性映射，应用时仅凭观测样本给出修正。

这两个研究方向应在独立模拟样本上比较参数误差、明显异常频率及求解成功率，检验是否减少异常而未扩大其他条件下的误差。
'''


def correct(text):
    if (HERE / '20261012-删去图21-核验.json').exists():
        later = base.module('20261012-删去图21')
        before = later.restore(text)
        if before != text:
            return later.correct(correct(before))
    if text.count(AFTER) == 1:
        return text
    assert text.count(BEFORE) == 1, 'Unexpected Chapter 3 edit'
    return text.replace(BEFORE, AFTER)


def restore(text):
    return text.replace(AFTER, BEFORE)


def apply():
    if QA.exists():
        update_readme()
        verify()
        return
    text = base.REPORT.read_text(encoding='utf-8')
    assert base.text_digest(text) == base.load(stage.QA)['after_text_sha256']
    revised = correct(text)
    pair = base.module('20261011-MDM近真值对照')
    previous = base.load(prior.QA)
    assert base.text_digest(text) == previous['after_text_sha256']
    record = dict(before=BEFORE, after=AFTER, before_text_sha256=base.text_digest(text),
                  after_text_sha256=base.text_digest(revised),
                  previous_outside_sha256=previous['outside_after_sha256'])
    base.write_json(QA, record)
    pair.write_text(base.REPORT, revised)
    previous.update(after_text_sha256=record['after_text_sha256'],
                    outside_after_sha256=base.text_digest(pair.block(revised)[1]),
                    improvement_revision=QA.name)
    base.write_json(prior.QA, previous)
    old_pair = base.load(pair.QA)
    assert old_pair['outside_block_sha256'] == record['previous_outside_sha256']
    old_pair.update(outside_block_sha256=previous['outside_after_sha256'], improvement_revision=QA.name)
    base.write_json(pair.QA, old_pair)
    update_readme()
    verify()


def update_readme():
    pair = base.module('20261011-MDM近真值对照')
    readme = base.ROOT / 'README.md'
    content = readme.read_text(encoding='utf-8')
    anchor = ('[表述修订脚本](交付/程序/报告2/20261012-典型形成过程表述.py)'
              '提供`apply`、`verify`，核验记录留在程序目录。')
    addition = ('第3章先提出计算修正，再提出稳定性约束与MMLE自适应位置修正；'
                '[改进方向脚本](交付/程序/报告2/20261012-针对性改进任务.py)保存本次文字和核验。')
    if addition not in content:
        assert content.count(anchor) == 1
        pair.write_text(readme, content.replace(anchor, anchor + addition))


def verify():
    record = base.load(QA)
    text = base.REPORT.read_text(encoding='utf-8')
    if (HERE / '20261012-删去图21-核验.json').exists():
        text = base.module('20261012-删去图21').restore(text)
    assert correct(text) == text and text.count(AFTER) == 1
    assert base.text_digest(text) == record['after_text_sha256']
    assert base.text_digest(restore(text)) == record['before_text_sha256']
    assert restore(text).split(BEFORE)[0] == text.split(AFTER)[0]
    prior.verify()
    record.update(validation='passed', script_sha256=base.digest(__file__),
                  only_chapter3_changed=True, original_data_figures_unchanged=True)
    base.write_json(QA, record)
    print('PASS: targeted Chapter 3 tasks; preceding text, formulas, samples, estimates and figures unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
