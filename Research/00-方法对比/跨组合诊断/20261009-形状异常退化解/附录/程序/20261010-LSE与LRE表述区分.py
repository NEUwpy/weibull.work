"""Clarify reference coordinates and regression directions in report2.

Revise wording only. Preserve the six method figures, every sample table,
the existing examples and all archived counts and estimates.
"""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REPORT = ROOT/'报告2：小样本情况下的明显异常估计.md'
QA = HERE/'20261010-LSE与LRE表述区分核验.json'
LSE_PRINCIPLE = r'''LSE先将Weibull变量的对数距离写成标准变量的线性变换：

$$
\ln(X-\gamma)=\ln\eta+\frac{Z}{\beta}.
$$

X为Weibull随机变量，Z=βln[(X−γ)/η]为标准对数Weibull变量。对n个变量排序后取期望，得到：

$$
\operatorname{E}[\ln(X_{(i)}-\gamma)]
=\ln\eta+\frac{z_i}{\beta}.
$$

n为样本量，X₍ᵢ₎为第i小的随机观测，zᵢ=E[Z₍ᵢ₎]为对应标准变量的顺序统计量期望，只由i和n决定。

因此，对每个候选γ，将实际观测x₍ᵢ₎转换为对数距离yᵢ=ln dᵢ，其中dᵢ=x₍ᵢ₎−γ。以zᵢ为横坐标、yᵢ为纵坐标，拟合直线yᵢ≈a+bzᵢ。截距a对应lnη，斜率b对应1/β，由此得到：

$$
\hat\beta(\gamma)=\frac1b,
\qquad
\hat\eta(\gamma)=e^a.
$$

LSE选择直线拟合程度最好的位置γ，即寻找F比最大的γ。F比与回归决定系数R²的关系为：

$$
F(\gamma)=\frac{n-2}{(n-1)[1-R^2(\gamma)]}.
$$

对同一组样本，n固定，F越大，1−R²越小。因此，寻找F比的最大值可转化为寻找1−R²的最低点：

$$
\hat\gamma=\underset{0\le\gamma<x_{(1)}}{\arg\min}\,[1-R^2(\gamma)].
$$

以γ为横坐标绘制1−R²，曲线最低点对应LSE选择的位置估计。'''
LRE_PRINCIPLE = r'''LRE从Weibull分布函数的线性化出发：

$$
\ln[-\ln(1-F(x))]
=\beta\ln(x-\gamma)-\beta\ln\eta.
$$

F(x)为Weibull分布函数。将第i个排序观测x₍ᵢ₎的累积概率用绘图位置pᵢ代替，得到：

$$
z_i=\ln[-\ln(1-p_i)]
\approx\beta y_i-\beta\ln\eta,
\qquad y_i=\ln(x_{(i)}-\gamma).
$$

pᵢ为按次序i和样本量n分配的累积概率，zᵢ为相应的概率图参考坐标。LRE以样本对数距离yᵢ为横坐标、zᵢ为纵坐标，拟合直线zᵢ≈a+byᵢ。斜率b直接对应形状β，截距a对应−βlnη，因此：

$$
\hat\beta(\gamma)=b,
\qquad
\hat\eta(\gamma)=e^{-a/b}.
$$

LRE选择两列坐标相关性最大的位置。带截距的一元回归满足R²=ρ²，两列坐标随观测次序同向增加，ρ>0，因此原相关系数判据可转化为：

$$
\hat\gamma
=\underset{0\le\gamma<x_{(1)}}{\arg\max}\,\rho(\gamma)
=\underset{0\le\gamma<x_{(1)}}{\arg\min}\,[1-R^2(\gamma)].
$$

ρ为yᵢ与zᵢ的线性相关系数。

两者的位置准则都追求最好的线性拟合，但LSE对齐的是排序对数值的期望，LRE对齐的是绘图位置对应的分位坐标。参考坐标不同，它们的1−R²曲线及所选γ可能不同；交换回归方向本身不改变R²，影响的是斜率与参数的对应关系。'''
REPLACEMENTS = [
    (
        '左移位置对下端观测的影响更大，压缩了对数样本距离的间距。第36组的对数跨度从1.74缩至0.20，拟合斜率从0.369降至0.046；形状取斜率倒数，便从2.71升至21.70，超过高估界限6。这里，改善线性程度的位置同时对应了过小的斜率。',
        '左移位置对下端观测的影响更大，压缩了纵轴y上的对数样本间距，而横轴z的理论参考点保持。第36组的纵向跨度从1.74缩至0.20，拟合斜率从0.369降至0.046；LSE取斜率倒数，形状便从2.71升至21.70，超过高估界限6。这里，改善线性程度的位置同时对应了过小的斜率。'
    ),
    (
        '同一平移还使整个对数跨度由1.64缩至0.42，而参考坐标z保持。拟合斜率由0.450降至0.119，形状随其倒数由2.22升至8.42，超过界限6。这类异常由改善下端点列拟合的左移形成，最低点停在内部位置时，斜率已经小到足以造成明显高估。',
        '同一平移还使纵轴y的对数跨度由1.64缩至0.42，而横轴z的参考坐标保持。拟合斜率由0.450降至0.119，LSE取其倒数，形状由2.22升至8.42，超过界限6。这类异常由改善下端点列拟合的左移形成，最低点停在内部位置时，斜率已经小到足以造成明显高估。'
    ),
    (
        '此时γ距最小观测仅5.04，下端对数距离被大幅拉低，整个对数跨度由1.96扩大至5.83。固定的z范围对应更陡的拟合线，斜率由0.542增至1.727，形状由1.85降至0.58，低于界限2/3。这类异常由使点列更接近直线的右移形成，较好的线性拟合同时对应了过大的斜率。',
        '此时γ距最小观测仅5.04，下端对数距离被大幅拉低，纵轴y的跨度由1.96扩大至5.83。横轴z的参考范围固定，拟合线变陡，斜率由0.542增至1.727；LSE取斜率倒数，形状由1.85降至0.58，低于界限2/3。这类异常由使点列更接近直线的右移形成，较好的线性拟合同时对应了过大的斜率。'
    ),
    (
        '这里的异常形成于内部最佳拟合与大斜率的共同出现。',
        'LRE直接将斜率作为形状，内部最佳拟合对应的大斜率便形成了明显高估。'
    ),
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replace_principle(text, heading, caption, principle):
    leading, section = text.split(heading, 1)
    intro, body = section.split(caption, 1)
    _, cases = body.split('\n\n**（1）零边界高估。**', 1)
    return (leading+heading+intro+caption+'\n\n'+principle
            +'\n\n**（1）零边界高估。**'+cases)


def main():
    graph_qa_path = HERE/'20261010-逐方法异常分类三子图核验.json'
    graph_qa = json.loads(graph_qa_path.read_text(encoding='utf-8'))
    sources = dict(graph_qa['source_sha256'])
    sources.update({str(p):digest(p) for p in [graph_qa_path,Path(__file__)]})
    assert all(digest(p) == value for p,value in sources.items())
    protected = {str(p):digest(p) for p in (HERE.parents[1]/'图片').glob('*.png')}
    before = REPORT.read_text(encoding='utf-8')
    revised = before
    for old,new in REPLACEMENTS:
        if old in revised:
            assert revised.count(old) == 1
            revised = revised.replace(old,new,1)
        else:
            assert new in revised
    revised = replace_principle(revised, '#### 2.1.1　LSE',
                                '**图2｜LSE各类明显异常估计的发生次数。**', LSE_PRINCIPLE)
    revised = replace_principle(revised, '#### 2.1.2　LRE',
                                '**图6｜LRE各类明显异常估计的发生次数。**', LRE_PRINCIPLE)
    assert before.split('#### 2.1.1',1)[0] == revised.split('#### 2.1.1',1)[0]
    assert before.split('#### 2.1.3',1)[1] == revised.split('#### 2.1.3',1)[1]
    tables = lambda text:re.findall(r'^\|[^\n]*(?:\n\|[^\n]*)*',text,flags=re.M)
    assert tables(before) == tables(revised)
    images = lambda text:re.findall(r'!\[[^\]]*\]\([^\n]*\)',text)
    assert images(before) == images(revised) and len(images(revised)) == 24
    assert re.findall(r'\*\*图(\d+)｜',revised) == list(map(str,range(1,25)))
    assert before.count('**（') == revised.count('**（')
    assert all(digest(p) == value for p,value in sources.items())
    assert all(digest(p) == value for p,value in protected.items())
    REPORT.write_text(revised,encoding='utf-8')
    result = dict(
        scope='Wording only in sections 2.1.1 LSE and 2.1.2 LRE.',
        purpose='Distinguish expected order-statistic reference points from plotting-position quantiles, '
                'derive each regression from its principle, explain inverse/direct slope parameter recovery, '
                'and derive the shared 1-R2 display from F/correlation criteria.',
        examples_added=False, controlled_experiments_added=False, estimates_recomputed=False,
        source_sha256=sources, sources_unchanged=True, protected_png_sha256=protected,
        all_pngs_unchanged=True, all_sample_tables_unchanged=True, all_24_images_and_numbers_unchanged=True,
        before_LSE_and_after_LRE_unchanged=True, anomaly_items_preserved=True,
        replacements=[dict(before=old,after=new) for old,new in REPLACEMENTS],
        principle_text={'LSE':LSE_PRINCIPLE, 'LRE':LRE_PRINCIPLE},
        same_reference_direction_invariance_explained=True,
        report_sha256=digest(REPORT))
    QA.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS: LSE/LRE wording distinguishes reference construction, regression direction and shape recovery; '
          'all tables, 24 images, original sources and other sections unchanged; no additional examples or experiments.')


if __name__ == '__main__':
    main()
