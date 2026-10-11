"""复现本次报告1文字调整；--verify只核对，不计算或制图。"""
from pathlib import Path
import argparse
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPORT = ROOT / '报告1：高形状参数下的估计偏移.md'
README = ROOT / 'README.md'
RECORD = HERE / '20261011-高β偏移论述收束.json'
SOURCE_SHA256 = '08a07d59b2e89411759700385b3664f5532c63c85ba9dcae485f39bbac0c0c34'

REPLACEMENTS = [
    (
        '本报告研究当前13个参数组合中高β条件下的参数偏移。图1展示原触发案例，当前13组用于核对偏移规律，配对补充实验用于分析形成过程。\n\n原W(5,1000,500)案例中，多种方法出现γ偏高、η和β偏低的共同偏移（图1）。',
        '在W(5,1000,500)的原案例中，多种方法出现γ偏高、η和β偏低的共同偏移：小样本下，γ的估计中心接近1000，η接近500（图1）。',
    ),
    (
        '**图1｜随样本量增大，位置与尺度的估计中位数向真值靠近，改善程度因方法而异。**',
        '**图1｜随着n增大，β和η低估、γ高估的现象总体减轻。**',
    ),
    (
        'n=7时，MDM和WMLE的同向偏移较集中，LSE、LRE和MLE的分布更宽，也出现位置低估和零边界结果。',
        '如图1所示，MDM和WMLE在大多数样本中高估γ、低估β和η。LSE、LRE和MLE还出现γ低估、β和η高估的结果。',
    ),
    (
        '高β、小n下，样本缺少真实起点附近的信息，对位置上移的约束较弱；尺度与形状的补偿又使偏移后的组合可能保持相近的中部拟合。',
        '以下先分析高β、小n下，参数偏离真值的分布为何仍能拟合样本，再分析各方法的估计判据为何会选中这些分布。',
    ),
    (
        '**图3｜同一样本下的参数补偿。** 黑点的累计概率由样本排序近似。',
        '**图3｜γ升高、η和β降低后，分布仍可贴近同一组观测。** 黑点的累计概率由样本排序近似。\n\n起点信息不足与参数补偿，使偏移组合仍能拟合观测；偏移的方向和程度则取决于各方法对这些组合的评价。以下固定γ考察判据变化，WMLE和MLE的条件曲线用于分析联合准则，不代表先估计γ的求解顺序。',
    ),
    (
        '**图4｜固定正梯度阈值使高β样本的位置交点右移。**',
        '**图4｜高β时，固定正梯度阈值的交点总体右移。**',
    ),
    (
        '其中，t̄为样本均值。改变γ主要改变截距和整体比例，相关系数对此保持不变，位置区分来自一阶近似省略的曲率。高β样本较集中，准则对位置变化的区分较弱；随机间距则通过曲率改变最低点。',
        '其中，t̄为样本均值。在这一近似范围内，改变γ主要改变截距和整体比例，相关系数对此保持不变，位置区分来自一阶近似省略的曲率。高β样本较集中，准则对位置变化的区分较弱；随机间距则通过曲率改变最低点。',
    ),
    (
        '原β=5代表样本右移后，残差比例降低，条件β和η也降低；配对样本中还出现左侧最低点（补充图6b）。',
        '原β=5代表样本右移后，残差比例降低，条件β和η也降低（补充图6b）；配对样本中还出现左侧最低点。因此，匹配改善可以伴随右移，但偏移方向随样本改变。',
    ),
    (
        '**图6｜固定绘图位置下的相关性响应。**',
        '**图6｜提高线性相关性可伴随参数偏移。**',
    ),
    (
        '原β=5代表样本右移后，残差比例降低，β和η随之降低；配对展开例则返回零边界（补充图6d）。',
        '原β=5代表样本右移后，残差比例降低，β和η随之降低（补充图6d）；配对展开例则返回零边界。高β下较好的线性匹配，同样可以对应不同方向的位置偏移。',
    ),
    (
        '**图7｜高β下，联合校准交点偏向真位置右侧。**',
        '**图7｜本组高β对照中，联合校准交点总体偏向真位置右侧。**',
    ),
    (
        '条件曲线取0<β<10内的T₁零点并代入T₂，T₂零点对应两式共同成立，无T₁解处留空。部分配对样本在真位置的T₁根超出范围。程序联合最小化T₁²+T₂²，以残差平方和≤1e−8接受结果。',
        '条件曲线与原程序均采用0<β<10。曲线将T₁零点代入T₂，T₂零点对应两式共同成立，无T₁解处留空。β=5、n=7的50组配对样本中，45组在真位置有条件解，其余5组的根超出范围。程序联合最小化T₁²+T₂²，以残差平方和≤1e−8接受结果。',
    ),
    (
        '高β展开例在真位置的条件形状较大，进入J₃端点区间，样本乘积低于校准目标，T₂为负，共同交点向右移动得更多。原β=5代表样本也呈现右移（补充图6f）。',
        '高β展开例在真位置的条件形状较大，进入J₃端点区间，样本乘积低于校准目标，T₂为负，共同交点向右移动得更多。原β=5代表样本也呈现右移（补充图6f）。这里使用了β<10的形状范围和J₃端点近似，两者对偏移的贡献尚未与原文校准方程的作用分离。',
    ),
    (
        'MLE以对数似然为准则，联合优化β、η、γ。高β、小样本下，参数补偿使部分组合的似然接近，随机波动可改变高点位置。本批接受域为β≥1、η>0、0≤γ<t₁；程序允许β<1参与搜索，结束后剔除这些候选。',
        'MLE以对数似然为准则，联合优化β、η、γ。高β、小样本下，参数补偿使部分组合的似然接近，随机波动可改变高点位置。本批按β≥1、η>0、0≤γ<t₁接受结果。',
    ),
    # 保留其他编辑者已经补入的量化说明，本次不改动其数值。
    (
        '原β=5代表样本中，较大的参数偏移只换来很小的似然改善，表明目标对这类参数变化区分较弱；配对展开例的返回位置则位于零边界。',
        '原β=5代表样本中，较大的参数偏移相对于固定真位置的条件拟合，仅提高对数似然0.053，表明目标对这类参数变化区分较弱；配对展开例的返回位置则位于零边界。',
    ),
    (
        '当前W(5,1000,500)、n=7的第4组还有更好的β=1合格候选，说明原搜索存在求解不足。该样本中，似然支持右移候选与数值求解不足同时存在，详见[报告2的MLE分析](报告2：小样本情况下的明显异常估计.md)。',
        'W(5,1000,500)、n=7第4组的右移候选比真位置条件拟合具有更高似然，但另有更好的β=1合格候选。这说明似然准则支持右移与搜索不足可以同时存在，原返回值不能直接视为准则的最优解。具体候选见[报告2的MLE分析](报告2：小样本情况下的明显异常估计.md)。',
    ),
    (
        '本批偏移由样本信息不足、参数补偿、方法判据及实际求解共同形成。配对对照支持MDM、WMLE较稳定的同向偏移，回归和似然方法的方向更依赖具体样本。已定位的数值求解问题，应先修正实现并用原样本复核。\n\n后续应分别检验MDM阈值、WMLE校准系数与表端点处理对偏移的贡献，并比较回归和似然方法中正反向偏移的样本，辨明随机间距与准则区分能力的作用。',
        '高β、小n下，起点附近的观测不足，γ上移及η、β降低仍可保留相近的中部拟合。在本组对照中，MDM的固定梯度阈值和WMLE的校准方程使偏移组合被选中；回归与似然准则也可支持偏移，但方向随样本改变。\n\n较好的样本拟合并不保证三个参数接近真值。后续应检验MDM阈值、WMLE校准目标、形状范围与端点处理对偏移的贡献，并比较回归和似然方法的正反向偏移样本。',
    ),
]

README_OLD = '两份报告的第二章均解释当前结果的形成过程，并在末尾汇总表现分类、计算或方法环节和本批规律。报告1保留原触发案例及配对补充实验，同时用当前13组中三个β=5组合的中位数检查适用范围；报告2沿用原异常表现分组，另标注叠加的数值求解证据。'
README_NEW = '报告1按高β下的偏移现象、样本约束与参数补偿、逐法判据和研究启示组织论证；影响原因判断的求解或权重近似问题保留在对应方法中。原案例与配对实验用于分析机制，跨组合数据保留为复核资料。报告2沿用原异常表现分组，另标注叠加的数值求解证据。\n\n报告1本次文字调整由[20261011-高β偏移论述收束.py](交付/程序/报告1/20261011-高β偏移论述收束.py)复现；加`--verify`只核对。[同名记录](交付/程序/报告1/20261011-高β偏移论述收束.json)保存输入版本、公式及图链接核对和数据、图片的字节一致性结果。'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(directory, excluded=()):
    rows = [(p.relative_to(directory).as_posix(), digest(p))
            for p in sorted(directory.rglob('*'))
            if p.is_file() and p not in excluded]
    return {'files': len(rows), 'sha256': hashlib.sha256(
        json.dumps(rows, ensure_ascii=False).encode('utf-8')).hexdigest()}


def protected_inputs():
    return {
        '交付/结果': tree_digest(ROOT / '交付/结果'),
        '交付/程序/报告1': tree_digest(HERE, (Path(__file__).resolve(), RECORD)),
        '13组合取数': digest(ROOT / '交付/程序/跨参数对比/13组合取数.json'),
    }


def verify():
    record = json.loads(RECORD.read_text(encoding='utf-8'))
    assert digest(REPORT) == record['report_after_sha256'], '报告文字已变化'
    assert digest(Path(__file__)) == record['revision_script_sha256'], '修订脚本已变化'
    assert protected_inputs() == record['protected_inputs'], '原程序、数据或图片已变化'
    text = REPORT.read_text(encoding='utf-8')
    formulas = re.findall(r'\$\$.*?\$\$', text, re.S)
    assert len(formulas) == record['display_formulas']
    assert hashlib.sha256('\n'.join(formulas).encode('utf-8')).hexdigest() == record['formulas_sha256']
    assert re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text) == record['main_figure_paths']
    assert '### 2.6 当前结果的分类与规律' not in text
    assert '当前13组中' not in text.split('## 第二章', 1)[0]
    print(f"PASS：报告文字、原公式、{len(record['main_figure_paths'])}张主图链接及"
          f"{record['protected_inputs']['交付/结果']['files']}份结果文件保持本次记录一致。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify or (RECORD.exists() and digest(REPORT) != SOURCE_SHA256):
        verify()
        return
    assert digest(REPORT) == SOURCE_SHA256, '输入不是本次精简版本，请勿覆盖后续修改'
    protected = protected_inputs()
    before = REPORT.read_text(encoding='utf-8')
    after = before
    for old, new in REPLACEMENTS:
        assert after.count(old) == 1, old
        after = after.replace(old, new, 1)
    start = after.index('当前13组中，β=5、n=7')
    end = after.index('## 第二章　机制分析与对照实验\n', start)
    after = after[:start] + after[end:]
    start = after.index('### 2.6 当前结果的分类与规律\n')
    end = after.index('## 第三章　结论与研究启示\n', start)
    after = after[:start] + after[end:]
    formulas = re.findall(r'\$\$.*?\$\$', before, re.S)
    images = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', before)
    assert re.findall(r'\$\$.*?\$\$', after, re.S) == formulas
    assert re.findall(r'!\[[^\]]*\]\(([^)]+)\)', after) == images
    assert len(images) == 8
    assert not re.findall(r'^\|.*\|$', after.split('## 第二章', 1)[0], re.M)
    readme_bytes = README.read_bytes()
    readme_newline = '\r\n' if b'\r\n' in readme_bytes else '\n'
    readme = readme_bytes.decode('utf-8').replace('\r\n', '\n')
    assert readme.count(README_OLD) == 1
    REPORT.write_text(after, encoding='utf-8', newline='\n')
    README.write_bytes(readme.replace(README_OLD, README_NEW, 1)
                       .replace('\n', readme_newline).encode('utf-8'))
    assert protected_inputs() == protected
    record = {
        'date': '2026-10-11',
        'source_commit': '3330be86',
        'report_before_sha256': SOURCE_SHA256,
        'report_after_sha256': digest(REPORT),
        'revision_script_sha256': digest(Path(__file__)),
        'changes': ['首章集中呈现偏移及样本量趋势', '衔接起点信息、参数补偿与逐法判据',
                    '权重近似与求解不足留在对应方法', '删除重复分类表并收束研究启示',
                    '第一章移出13组合对照表及取数说明'],
        'new_samples': 0, 'new_estimates': 0, 'redrawn_figures': 0,
        'display_formulas': len(formulas),
        'formulas_sha256': hashlib.sha256('\n'.join(formulas).encode('utf-8')).hexdigest(),
        'main_figure_paths': images,
        'chapter1_table_removed': True,
        'removed_chapter1_table': re.findall(r'^\|.*\|$', before, re.M)[:5],
        'protected_inputs': protected,
    }
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8', newline='\n')
    verify()


if __name__ == '__main__':
    main()
