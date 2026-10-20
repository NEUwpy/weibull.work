"""将第13轮确认的图表与内容整理为报告下v0.4；只复用现有结果。"""
from pathlib import Path
import hashlib
import json

import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent.parent
ROOT = STUDY / 'reviewbyhtml/方法对比'
TARGET = STUDY / '报告下（方法对比）-v0.4.md'


def export():
    board = json.loads((ROOT / 'board.json').read_text(encoding='utf-8'))
    assert board['id'] == 'study04-comparison-v04' and board['revision'] == 13
    feedback = json.loads((ROOT / 'feedback.json').read_text(encoding='utf-8'))
    assert feedback['submission_id'] == '636211f6-f0ba-4b88-9f91-b3eb13bcba2f'
    assert feedback['intent'] == 'archive' and feedback['confirmation']['confirmed']
    assert not feedback['confirmation']['edited']
    assert all(u['mode'] == 'content' and len(u['options']) == 1 for u in board['units'])
    units = {u['id']: u for u in board['units']}
    model = json.loads((HERE.parent / '分析数据/比较论证-v0.4.json').read_text(encoding='utf-8'))
    for relative, digest in model['sources'].items():
        assert hashlib.sha256((STUDY / relative).read_bytes()).hexdigest() == digest
    normalized = np.array(model['stats']['common']['rmse'])[:3].copy()
    normalized /= np.array([[1.5,2,2.5,3,3.5,4,4.5,5],[1000]*8,[1000]*8])[:,None,:,None]
    out = []

    def text(value):
        out.extend([value.strip(), ''])

    def pictures(unit_id, block_ids=None):
        for block in units[unit_id]['options'][0]['blocks']:
            if block_ids is not None and block['id'] not in block_ids:
                continue
            if block['kind'] not in ('image', 'gallery'):
                continue
            slides = block['images'] if block['kind'] == 'gallery' else [block]
            for slide in slides:
                if block['kind'] == 'gallery':
                    text('#### ' + slide['label'])
                path = ROOT / slide['src']
                assert path.is_file()
                text(f'![{slide.get("alt", "")}]({path.as_posix()})')

    text('# 小样本三参数Weibull参数估计方法的比较与选择')
    text('**报告下（方法对比）v0.4｜2026-10-21**')
    text('魏鹏宇｜东北大学机械工程与自动化学院')
    text('分会场3：装备寿命与可靠性评估')
    text('本版按已确认的内容与图表组织下篇，沿“整体差异 → 条件变化 → 误差与代价 → 典型解释 → 选择启示”展开。引用块用于讲述衔接，其余文字与图组保留读图依据；图组按播放顺序展开，交互查看与批注记录见[HTML审阅页](reviewbyhtml/方法对比/index.html)。')

    text('## 1　比较对象与共同条件')
    text('> 前面介绍了方法的原理分类以及文献之间的联系。接下来把七种具体实现放到相同样本上：先看方法之间究竟有多大差距，再观察差距怎样随样本量和形状条件改变，最后讨论这些差异对实际使用意味着什么。')
    text('| 项目 | 本轮设置 |\n|---|---|\n| 方法 | MDM-0.1、LSE、LRE（Park）、WMLE、MLE、MMLE（K–R）、MM |\n| 参数 | η=1000、γ=500；β=1.5、2、2.5、3、3.5、4、4.5、5 |\n| 样本量 | n=50、20、15、10、7 |\n| 重复抽样 | 每个条件1200组；各方法使用相同样本 |\n| 主要观察 | 参数RMSE、估计分布、明显异常与有效返回 |')
    text('方法版本与求解约定见[实验设置](实验设置.md)。精度主图使用每个条件内七法均有效的共同样本；分布图使用各方法自身有效结果。异常与失败另行统计，不把失败填成参数误差。形状RMSE除以真实β，尺度与位置RMSE均除以1000，以便在同图中观察三个参数。')

    text('## 2　方法之间究竟相差多少')
    text('> 先从全体条件看差距在哪些地方明显。如果只看一个方法的极端值，其他方法可能被挤在一起；因此先看多数方法与当前最小RMSE之间的距离，具体是谁、差距怎样改变，再由下一组图展开。')
    pictures('figure-global')
    text('每格为七法RMSE中位数相对该条件最小值多出的百分比。三列分别对应形状、尺度、位置参数，共用同一分档色标；数字直接给出差距幅度。中位数意味着七种方法中至少四种的RMSE达到该水平。')
    text('这张图定位值得继续观察的条件区域，不单独承担方法推荐。中位数压缩了方法身份，具体方法的误差轮廓由下一组玫瑰图补充。')

    text('## 3　差距怎样随n和β一起改变')
    text('八个β排成两行四列；五张图的六法主图共用0～1.5的线性半径，方法方位、参数颜色与量程均不变。MM的三项实际标准化RMSE在各β图下单列，避免其量级压缩其余方法。半径长度对应标准化RMSE，扇形面积不表示误差倍数。')
    pictures('figure-change')
    def span(i, j):
        values = normalized[0, i, j, :6]
        return f'{values.min():.3f}～{values.max():.3f}'
    text(f'例如，β=1.5时，六法形状标准化RMSE在n=50下为{span(0,0)}，到n=7为{span(4,0)}；β=5时，相应区间由{span(0,7)}变为{span(4,7)}。差距并非按同一个倍数扩大，变化还依赖β。图中保留了全部中间样本量，可逐档检查具体变化。')
    text('这些是各条件共同有效样本上的点估计。共同有效数随条件而变，为348～1199组；它用于对齐同一条件的方法比较，返回情况在第4节另看。')

    text('## 4　误差差距表现成什么样')
    text('### 4.1　分开看系统偏移与重复波动')
    text('> RMSE告诉我们误差大小，还需要看看估计结果本身。有的方法集中却偏离真值，有的方法平均位置较接近真值，但重复抽样波动更大。把分布位置和宽度分开看，才能理解前面的差距。')
    text('以下按β=1.5～5顺序展示。每张均以n=50、7纵向排列，形状、尺度、位置横向排列，七法顺序不变。虚线是真值，红点为均值，深色横线为25%～75%区间；三列显示范围固定为0～10、0～2000、0～1500。')
    pictures('figure-error')
    text('β=5的视图可用于说明“集中”与“准确”的区别：部分方法的主体分布在形状、尺度上偏低，在位置上偏高；与之相比，有些方法的形状分布更宽。切换β后继续观察这些方向和宽度是否保持。密度仅展示窗口内主体，均值及四分位区间使用全部有效值；窗外结果并未从统计中删除。')

    text('### 4.2　明显异常与没有返回有效估计分别展示')
    text('> 有些问题在总体RMSE里容易被淹没：少数极端输出可能明显改变平均误差，而失败根本没有可用于计算误差的估计值。因此，除了看精度和分布，还要单独说明异常发生的频率，以及方法是否能返回有效结果。')
    pictures('figure-tail')
    text('形状明显异常沿用β̂≤β/3或β̂≥3β，异常率以有效结果数为分母；有效率以每条件1200次尝试为分母。两图覆盖全部n、β条件，分别回答“有效输出中明显偏离的情况是否反复发生”与“有多少次未返回有效估计”。')
    text('异常频率不直接表示损失大小，0次发生也仅表示本批未观察到。判断方法表现时，需要将频率与前面的误差轮廓、分布位置和波动一起看。')

    text('## 5　用典型案例简要解释偏移与异常')
    text('> 这里不展开全部技术机制。先说明小样本为什么可能不足以约束起点，再沿一个具体方法的步骤，看看位置选择怎样带动形状和尺度。系统偏移与明显异常可以用同一条过程线来解释。')
    text('### 5.1　共同背景：起点信息有限与参数补偿')
    mechanism = units['figure-mechanism']['options'][0]['blocks']
    def source_picture(filename):
        block = next(b for b in mechanism if b.get('src','').endswith(filename))
        path = ROOT / block['src']; assert path.is_file()
        text(f'![{block["alt"]}]({path.as_posix()})')
    source_picture('R00_图2_样本与真实起点.png')
    text('复用Research00报告1图2：β=2与5，n=7、15、30，每格50组，下排给出样本最小值的理论密度。高β、样本较少时，最小观测往往仍离真实起点较远，位置参数缺少直接约束。')
    source_picture('R00_图2_样本与分布相容.png')
    text('报告1图3进一步展示W(5,1000,500)与W(2,500,1000)：参数相差明显，在这组观测覆盖的中部区间却有相近曲线。两个分布用于解释局部相容性，并非两种方法的估计比较；黑点来自原β=5、n=7第31组。')
    text('### 5.2　沿K–R的定位、形状确定与尺度恢复追踪')
    source_picture('R00_图15_MMLE定位与形状尺度.png')
    text('报告1第2.6节、图15展示50组历史样本中的规律性偏移：K–R由最小值定位，再拟合保留距离；高β例呈现位置偏高、形状与尺度偏低。位置改变了后续拟合所用的距离，影响会传递到其他参数。')
    source_picture('R00_配对情形_MMLE_low.png')
    text('再看报告2图19的明显异常例：W(5,100,500)、n=7，上排正常第10组，下排异常第11组。异常样本先以575.95定位，保留距离更分散，形状峰落在1.54，低于5/3，尺度随之得到28.69。三列依次读“怎样定位—形状怎样确定—尺度怎样恢复”。')
    text('历史案例用于解释形成过程，不并入本轮1200次统计。正式讲述可只展开其中一例。来源：[Research00报告1](../../Research/00-方法对比/报告1：小样本情况下高形状参数的估计偏移.md)、[报告2](../../Research/00-方法对比/报告2：小样本情况下的明显异常估计.md)。')

    text('## 6　将差异转为条件性选择依据')
    text('> 前面的比较最后可以形成一个按n和β查看的候选表。但实际使用时，真实β通常未知，评价目标也可能不同。表格提供参考，选择仍需要结合已经掌握的信息、关心的参数或寿命指标，以及可以接受的风险。')
    pictures('figure-life')
    text('表内方法为该条件共同有效样本上RMSE最小者；下行百分数为第二低RMSE比最低值高多少。颜色只区分方法。B10对应可靠度0.90，B1对应0.99；参数误差较小，不保证寿命目标上的排序相同。细小差距仍须核对不确定性，真β条件表不能直接当作可用的自动选择器。')
    text('只知道n时，需要在明确的β参考范围中比较候选，并说明采用什么精度与风险规则；若还知道β的大致范围，可以缩小检查区域，再结合目标参数或寿命指标判断。当前表展示条件差异，尚未验证一套实际选法的收益。')

    text('## 7　下一步：利用具体样本信息辅助选法')
    text('> 即使n与总体参数相同，具体样本仍有差异。后续希望利用样本可观察到的特征和使用目标，辅助选择估计方法，并继续优化方法的过程量与求解过程。比较表提供前期依据，真正的选择规则及其收益还需要另外验证。')
    text('最后简要介绍[weibull.work](https://weibull.work)，作为方法计算和研究成果展示的入口，邀请同行试用。平台仍在建设，具体开放方法和实现版本以[项目当前状态](../../README.md#当前状态快照)为准；本轮七种比较实现与线上开放范围分别说明。')
    text('材料入口：[实验设置](实验设置.md)、[结果图及统计口径](结果呈现/README.md)、[审阅内容镜像](结果呈现/比较探索/表达方式发散.md)。')
    TARGET.write_text('\n'.join(out).rstrip()+'\n', encoding='utf-8')
    return TARGET


if __name__ == '__main__':
    print(export())
