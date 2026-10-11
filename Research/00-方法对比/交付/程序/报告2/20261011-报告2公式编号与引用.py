"""Number Report 2 equations and connect derivations, figures and explanations.

Only edits equation tags and prose references. Historical data and figures stay
unchanged. Run apply once; verify checks the saved equation/reference mapping.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, write_atomic

HERE = Path(__file__).resolve().parent
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
README = ROOT / 'README.md'
RECORD = HERE / (Path(__file__).stem + '.json')
SOURCE_SHA256 = 'd56d9dbbb1c7d204c25d859a2e0ff6d5d017c9cec4ef1e71210cea45aec8cc4c'
DISPLAY = re.compile(r'\$\$(.*?)\$\$', re.S)
TAG = re.compile(r'\\tag\{(\d+)\}')

EDITS = [
    ('其中，β为形状真值，β̂为估计值。',
     '式（1）中，β为形状真值，β̂为估计值；图1按此判据统计异常频率。'),
    ('对n个变量排序后取期望，得到：',
     '对式（2）中的n个变量排序后取期望，得到：'),
    ('以zᵢ为横坐标、yᵢ为纵坐标拟合直线yᵢ≈a+bzᵢ，',
     '根据式（3），以zᵢ为横坐标、yᵢ为纵坐标拟合直线yᵢ≈a+bzᵢ，'),
    ('同一组样本的n固定，最大化F比等价于最小化1−R²，位置判据便写成：',
     '固定n后，式（5）的F比最大化等价于最小化1−R²，位置判据便写成：'),
    ('图中的1−R²曲线显示位置如何被选取，形状曲线则显示该位置对应的斜率倒数。',
     '图中的1−R²曲线按式（6）确定位置，形状曲线按式（4）取对应斜率的倒数。'),
    ('图3将零边界与内部左侧两条异常曲线放在一起，对照正常样本的位置判据与拟合斜率。',
     '图3将两条异常曲线放在一起，对照式（6）的位置判据及式（4）的斜率与形状关系。'),
    ('两者都经较小斜率的倒数形成高估，区别在于最佳位置是否落在零边界。',
     '两者都按式（4）取较小斜率的倒数形成高估，区别在于最佳位置是否落在零边界。'),
    ('图4比较右侧最低点附近的下端对数间距及拟合斜率。',
     '图4对照式（6）的右侧最低点、下端对数间距及式（4）对应的拟合斜率。'),
    ('拟合斜率增至1.727，取倒数后β降至0.58。',
     '拟合斜率增至1.727，按式（4）取倒数后β降至0.58。'),
    ('将第i个排序观测的累计概率F(x₍ᵢ₎)用绘图位置pᵢ代替，得到：',
     '将式（7）中第i个排序观测的累计概率F(x₍ᵢ₎)用绘图位置pᵢ代替，得到：'),
    ('LRE以yᵢ为横坐标、zᵢ为纵坐标拟合直线zᵢ≈a+byᵢ。',
     '根据式（8），LRE以yᵢ为横坐标、zᵢ为纵坐标拟合直线zᵢ≈a+byᵢ。'),
    ('图中的ρ曲线显示位置选择，拟合线和形状曲线显示该位置对应的斜率。',
     '图中的ρ曲线按式（10）确定位置，形状曲线按式（9）取对应的拟合斜率。'),
    ('图6比较两个异常样本的相关性最高点及其对应拟合线。',
     '图6对照式（10）的相关性最高点及式（9）对应的拟合斜率与形状。'),
    ('斜率分别达到13.78、18.80，直接得到形状高估。',
     '斜率分别达到13.78、18.80，按式（9）直接得到形状高估。'),
    ('图7比较两组右侧位置下的概率图横向跨度及回归斜率。',
     '图7对照式（10）选择的右侧位置、概率图横向跨度及式（9）的斜率与形状关系。'),
    ('直接取斜率后得到β=0.56。',
     '按式（9）直接取斜率后得到β=0.56。'),
    ('先对尺度求导，令其为零：',
     '先对式（11）的尺度求导，令其为零：'),
    ('将该尺度代回似然，对β求导并除以n，得到条件形状得分：',
     '将式（12）的尺度代回式（11），对β求导并除以n，得到条件形状得分：'),
    ('记方程的未约束根为β₀(γ)，',
     '记式（13）的未约束根为β₀(γ)，'),
    ('再计算对应尺度，得到条件最优对数似然：',
     '再按式（12）计算对应尺度，代入式（11）得到条件最优对数似然：'),
    ('ℓₚ(γ)表示该位置下能达到的最高对数似然。',
     '式（14）的ℓₚ(γ)表示该位置下能达到的最高对数似然。'),
    ('图9比较不同位置的条件似然及其对应形状。',
     '图9对照式（14）的条件似然及式（13）对应的形状。'),
    ('得分方程要求这个差等于1/β，因此条件形状由真位置处的3.50升至23.54。',
     '式（13）要求这个差等于1/β，因此条件形状由真位置处的3.50升至23.54。'),
    ('图10比较左侧与右侧候选，同时保留β=1时的条件最优分支。',
     '图10按式（14）比较左侧与右侧候选，同时保留β=1时的条件最优分支。'),
    ('形状得分中的均值之差增大，条件形状降至1.44。',
     '式（13）的均值之差增大，条件形状降至1.44。'),
    ('图11检查原返回点的位置，以及向右调整后是否仍有更高似然。',
     '图11用式（14）的条件似然检查原返回点，以及向右调整后是否仍有更高似然。'),
    ('形状得分因而对应β≈13.10。',
     '式（13）因而对应β≈13.10。'),
    ('原文使用精确中位秩，本批程序及过程图采用Bernard近似',
     '式（15）使用精确中位秩，本批程序及过程图采用Bernard近似'),
    ('给定γ和β，每个观测反算的尺度伪估计量为：',
     '给定γ和β，将式（15）的累计概率代入尺度反算关系，每个观测的尺度伪估计量为：'),
    ('η̂ᵢ为第i个观测反算的伪尺度，',
     '式（16）的η̂ᵢ为第i个观测反算的伪尺度，'),
    ('最小化在候选形状范围内进行，',
     '式（17）的最小化在候选形状范围内进行，'),
    ('比较相邻位置的最小标准差，得到差分梯度：',
     '比较式（17）在相邻位置的最小标准差，得到差分梯度：'),
    ('梯度曲线与δ的交点确定γ̂，再取该位置下标准差最低点的形状为β̂。',
     '式（18）的梯度达到δ时确定γ̂，再按式（17）取该位置下标准差最低点的形状为β̂。'),
    ('式中F(t₍ᵢ₎)采用上述秩估计的累计概率。对每个γ都按条件形状β̂(γ)取均值，便得到图中的条件尺度曲线：',
     '式（19）中F(t₍ᵢ₎)采用式（15）后的Bernard近似。对每个γ按式（17）求条件形状β̂(γ)，再按式（19）取伪尺度均值，得到条件尺度曲线：'),
    ('图13、14分别展示梯度定位、所选位置下的形状选择和条件尺度。',
     '图13、14分别按式（18）、（17）、（20）展示梯度定位、所选位置下的形状选择和条件尺度。'),
    ('图13比较两组样本的阈值交点及其对应的形状和尺度。',
     '图13对照式（18）的阈值交点及式（17）、（20）对应的形状和尺度。'),
    ('标准差最低点对应的形状由真位置处的6.00降至1.35，伪尺度均值也下降。',
     '式（17）的标准差最低点对应的形状由真位置处的6.00降至1.35，式（20）的伪尺度均值也下降。'),
    ('图14对照内部交点与右端回退位置下的形状和尺度。',
     '图14对照式（18）的内部交点与右端回退位置，以及式（17）、（20）对应的形状和尺度。'),
    ('最低点对应β=6.43，伪尺度均值为568.02。',
     '式（17）的最低点对应β=6.43，按式（19）取伪尺度均值得568.02。'),
    ('两式同时为零才确定形状与位置；',
     '式（21）、（22）同时为零才确定形状与位置；'),
    ('先在每个γ下求形状方程的根β̂(γ)：',
     '先在每个γ下求式（21）的根β̂(γ)：'),
    (r'将它代入位置方程，绘制$T_2[\hat\beta(\gamma),\gamma]$。第一式已经满足，因此这条曲线与零线的交点也满足第二式，对应两方程的联合解。',
     r'将式（23）的条件形状代入式（22），绘制$T_2[\hat\beta(\gamma),\gamma]$。式（21）已经满足，因此曲线与零线的交点也满足式（22），对应两方程的联合解。'),
    ('J₁为尺度校准系数。',
     '式（24）的J₁为尺度校准系数。'),
    ('图16比较两组样本的联合交点及其对应形状。',
     '图16对照式（21）、（22）的联合交点及其对应形状。'),
    ('两组在真位置处的T₂都为负，',
     '两组在真位置处按式（22）计算的T₂都为负，'),
    ('形状方程对应的β由真位置处的4.96降至1.10。',
     '式（21）对应的β由真位置处的4.96降至1.10。'),
    ('图17比较点列较分散和较集中时，交点对应的形状。',
     '图17比较点列较分散和较集中时，式（21）、（22）的联合交点对应的形状。'),
    ('在真位置处，形状方程已给出4.25，',
     '在真位置处，式（21）已给出4.25，'),
    ('对这些距离应用形状得分关系，将MLE得分中的样本均值改为n−1个保留观测的均值，得到：',
     '对式（25）的保留距离应用式（13）的形状得分关系，将样本均值改为n−1个保留观测的均值，得到：'),
    ('此处γ取已确定的γ̂。程序从β=1作固定点迭代，方程的根给出β̂，再由保留距离计算尺度：',
     'Uβ为形状得分，γ取式（25）确定的γ̂。程序从β=1作固定点迭代，求式（26）的根得到β̂，再按式（27）计算尺度：'),
    ('Uβ为形状得分。方程要求1/β等于保留对数距离的加权均值与普通均值之差。',
     '由式（26），1/β等于保留对数距离的加权均值与普通均值之差。'),
    ('图19、20对照正常与异常样本的实际保留距离及形状得分曲线，',
     '图19、20对照正常与异常样本的实际保留距离及式（26）的形状得分曲线，'),
    ('这种相对离散增大了形状方程中的均值之差，',
     '这种相对离散增大了式（26）的均值之差，'),
    ('第5组集中的对数距离使加权均值与普通均值之差较小，',
     '第5组集中的对数距离使式（26）的加权均值与普通均值之差较小，'),
    ('取n=15、a=0.5，最小值进入γ+0.5η以内的概率，',
     '由式（28），取n=15、a=0.5，最小值进入γ+0.5η以内的概率，'),
    ('LSE中，集中点列使斜率1/β较小；LRE中，固定参考坐标对应较窄的横向跨度，使斜率β较大。MLE的形状得分要求1/β等于对数距离的加权均值与普通均值之差；',
     'LSE按式（4）取斜率倒数，集中点列对应较大β；LRE按式（9）直接取斜率，固定参考坐标对应较窄的横向跨度，使β较大。MLE的式（13）要求1/β等于对数距离的加权均值与普通均值之差；'),
    ('第29组的形状下界已达到33.62，',
     '按式（29），第29组的形状下界已达到33.62，'),
    ('形状固定时，γ/η越大，原始观测的相对离散越小。',
     '由式（30），形状固定时，γ/η越大，原始观测的相对离散越小。'),
    ('用顺序统计量期望作参考，最大化F比，再取回归斜率倒数',
     '用顺序统计量期望作参考，按式（6）定位，再按式（4）恢复参数'),
    ('用绘图概率作参考，最大化相关系数，再直接取回归斜率',
     '用绘图概率作参考，按式（10）定位，再按式（9）恢复参数'),
    ('联合比较形状、尺度和位置的似然 |',
     '按式（11）联合比较形状、尺度和位置的似然 |'),
    ('以条件最小标准差的梯度达到固定δ来定位 |',
     '以式（18）的梯度达到δ定位，再按式（17）、（19）恢复参数 |'),
    ('使校准后的形状与位置方程同时平衡 |',
     '使式（21）、（22）的形状与位置残差同时为零 |'),
    ('直接用最小值定位，再由保留距离的形状方程确定β |',
     '按式（25）作最小值定位，再由式（26）、（27）确定形状与尺度 |'),
]

NOTE = ('报告2的公式编号与正文引用由[20261011-报告2公式编号与引用.py]'
        '(交付/程序/报告2/20261011-报告2公式编号与引用.py)保存；'
        '`apply`应用本次修改，`verify`核对编号、引用及公式和图表数据的一致性。\n\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def formula_bodies(text):
    return [TAG.sub('', match.group(1)).strip() for match in DISPLAY.finditer(text)]


def prose(text):
    return DISPLAY.sub('', text)


def reference_numbers(text):
    # Accept a single reference, lists (式（21）、（22）), or a range.
    refs = []
    for match in re.finditer(r'式（(\d+)）((?:[、—]（\d+）)*)', prose(text)):
        first = int(match.group(1))
        refs.append(first)
        for sep, number in re.findall(r'([、—])（(\d+)）', match.group(2)):
            number = int(number)
            refs.extend(range(first + 1, number + 1) if sep == '—' else [number])
            first = number
    return refs


def protected_files(text):
    paths = [(ROOT / path).resolve() for path in re.findall(r'!\[[^\]]*\]\((.*?)\)', text)]
    for source in json.loads((PROGRAM / '跨参数对比/13组合取数.json').read_text(encoding='utf-8'))['sources']:
        paths.append(matrix_path(source))
        paths.extend((RESULT / source['program']).glob('*.xlsx'))
    return {str(path): digest(path) for path in paths}


def sample_rows(text):
    # Rows containing observations/estimates, separate from the method summary.
    return [line for line in text.splitlines() if line.startswith('|') and
            ('组 |' in line or re.match(r'\| (?:真值|LSE|LRE|MLE) \| (?:\*\*)?\d', line))]


def image_blocks(text):
    return re.findall(r'^!\[.*?\]\(.*?\)$|^\*\*图\d+｜.*$', text, re.M)


def verify():
    record = json.loads(RECORD.read_text(encoding='utf-8'))
    text = REPORT.read_text(encoding='utf-8')
    matches = list(DISPLAY.finditer(text))
    tags = [TAG.findall(match.group(1)) for match in matches]
    assert tags == [[str(i)] for i in range(1, 31)], tags
    assert formula_bodies(text) == record['formula_bodies_before'], 'Equation content changed'
    refs = reference_numbers(text)
    assert set(refs) == set(range(1, 31)), 'Missing or dangling references'
    assert image_blocks(text) == record['image_blocks_before'], 'Figure or caption changed'
    assert sample_rows(text) == record['sample_rows_before'], 'Sample or estimate table changed'
    for path, sha in record['protected_files'].items():
        assert digest(path) == sha, path
    assert digest(REPORT) == record['report_after_sha256'], 'Report differs from this revision'
    print(f'PASS: equations 1-30 numbered and referenced; {len(refs)} prose references; formulas, samples and figures unchanged.')


def apply():
    if RECORD.exists() and digest(REPORT) == json.loads(RECORD.read_text(encoding='utf-8'))['report_after_sha256']:
        verify()
        return
    assert digest(REPORT) == SOURCE_SHA256, 'Report changed; review the source before applying this revision'
    original_bytes = REPORT.read_bytes()
    original = original_bytes.decode('utf-8').replace('\r\n', '\n')
    assert len(DISPLAY.findall(original)) == 30 and not TAG.search(original)
    protected = protected_files(original)
    after = original
    for old, new in EDITS:
        assert after.count(old) == 1, old
        after = after.replace(old, new, 1)
    count = 0

    def number(match):
        nonlocal count
        count += 1
        return '$$' + match.group(1).rstrip() + f'\n\\tag{{{count}}}\n$$'

    after = DISPLAY.sub(number, after)
    assert count == 30 and formula_bodies(original) == formula_bodies(after)
    assert set(reference_numbers(after)) == set(range(1, 31))
    assert image_blocks(original) == image_blocks(after)
    assert sample_rows(original) == sample_rows(after)
    readme_bytes = README.read_bytes()
    readme = readme_bytes.decode('utf-8').replace('\r\n', '\n')
    rule = '报告1的陈列公式按全文顺序连续编号'
    assert readme.count(rule) == 1
    readme = readme.replace(rule, '两份报告的陈列公式分别按全文顺序连续编号', 1)
    assert '## 整理与恢复\n' in readme and NOTE not in readme
    readme = readme.replace('## 整理与恢复\n', NOTE + '## 整理与恢复\n', 1)
    newline = '\r\n' if b'\r\n' in original_bytes else '\n'
    write_atomic(REPORT, after.replace('\n', newline).encode('utf-8'))
    readme_newline = '\r\n' if b'\r\n' in readme_bytes else '\n'
    write_atomic(README, readme.replace('\n', readme_newline).encode('utf-8'))
    assert protected_files(after) == protected
    mapping = []
    for i, match in enumerate(DISPLAY.finditer(after), 1):
        headings = re.findall(r'^#{2,4} (.*)', after[:match.start()], re.M)
        mapping.append({'number': i, 'section': headings[-1],
                        'prose_reference_count': reference_numbers(after).count(i)})
    record = {'report_before_sha256': SOURCE_SHA256, 'report_after_sha256': digest(REPORT),
              'script_sha256': digest(__file__), 'formula_bodies_before': formula_bodies(original),
              'equation_mapping': mapping, 'image_blocks_before': image_blocks(original),
              'sample_rows_before': sample_rows(original), 'protected_files': protected,
              'new_samples': 0, 'new_estimates': 0, 'redrawn_figures': 0}
    write_atomic(RECORD, (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    verify()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
