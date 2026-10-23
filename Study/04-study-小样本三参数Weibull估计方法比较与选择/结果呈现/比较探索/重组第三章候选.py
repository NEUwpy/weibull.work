"""将第三章的机制解释候选放入原HTML任务，保留其余章节及审阅记录。"""
from pathlib import Path
import copy
import hashlib
import json
import shutil

STUDY = Path(__file__).resolve().parents[2]
REVIEW = STUDY / 'reviewbyhtml/方法对比-v1.0'
RESEARCH = STUDY.parents[1] / 'Research/00-方法对比'


def text(key, html):
    return dict(id=key, kind='text', html=html)


def image(key, filename, alt):
    return dict(id=key, kind='image', src='assets/' + filename, alt=alt)


def option(key, label, *blocks):
    return dict(id=key, label=label, blocks=list(blocks))


def main():
    path = REVIEW / 'board.json'
    board = json.loads(path.read_text(encoding='utf-8'))
    before = copy.deepcopy(board)
    source_map = {}
    for src, dst in [
        ('报告1/图2_样本与分布相容.png', 'R00_图3_参数组合与样本相容.png'),
        ('报告2/配对情形_LSE_zero.png', 'R00_报告2_LSE零边界.png'),
    ]:
        original = RESEARCH / '交付/结果' / src
        target = REVIEW / 'assets' / dst
        shutil.copyfile(original, target)
        assert original.read_bytes() == target.read_bytes()
        source_map[dst] = dict(source=str(original), sha256=hashlib.sha256(original.read_bytes()).hexdigest())

    u31 = next(u for u in board['units'] if u['id'] == 'mechanism-high-beta')
    old_kr = next(x for x in u31['options'][0]['blocks'] if x['id'] == 'n-kr-exact')
    kr = copy.deepcopy(old_kr)
    # Keep the formula, replace the surrounding prose with its role in this option.
    start = kr['html'].index('<span class="katex">')
    end = kr['html'].index('</span>', start) + len('</span>')
    kr['html'] = '<p>K–R直接用样本最小值定位，因此位置误差对样本量的响应可以精确写为：</p>' + kr['html'][start:end] + '<p>它说明：当位置由最小值直接确定时，下端空缺以明确的样本量关系进入误差。MDM和LSE采用不同定位判据，需要另看交点或最低点如何改变。</p>'
    u31.update(mode='choices', state='expand', selection_mode='multiple', selected=None, selected_ids=[],
               context='核心问题：固定β，样本减少为什么会经不同估计规则形成不同的偏差与波动？三个方案可组合。推荐B作主要证据、A解释具体步骤；C适合压缩讲解。')
    u31['options'] = [
        option('n-criterion-paths', 'A｜直接看三种定位规则怎样响应删点',
            text('n-a-opening', '<p>同样的观测减少，进入不同方法后，改变的估计环节并不相同。K–R的位置由最小值直接确定；MDM的位置由梯度与固定阈值的交点确定；LSE则在不同位置间比较线性匹配。</p>'),
            dict(id='n-a-criteria', kind='gallery', aspect_ratio=2.83, images=[
                dict(id='path1055', label='删点路径1055：最小值保留，另外两法的位置仍改变', src='assets/31A_固定形状定位判据_样本1055.png', alt='固定β=5，三种定位依据在n=50、20、7时的变化'),
                dict(id='path474', label='删点路径474：下端空缺增大，三法以不同依据定位', src='assets/31A_固定形状定位判据_样本474.png', alt='另一固定β=5删点路径中的最小值、阈值交点和线性匹配最低点'),
            ]),
            text('n-a-reading', '<p>第一条路径中，最小观测一直保留，K–R的位置因而不变；但删去其他点仍改变了MDM的梯度曲线和LSE的匹配曲线。MDM的交点左移，LSE的最佳位置则从内部转到零边界。第二条路径中，删点还增大了下端空缺，三种方法的位置均向右改变，但确定位置的依据与移动程度不同。</p><p>因此，样本量减少并不是给所有方法增加同一种误差。它先改变各法使用的统计关系，再由最小值、交点或最优位置传递到参数。哪种响应在小样本下更合适，要回到重复模拟中的偏差、波动与风险评价。</p>'),
            text('n-a-source', '<p><em>固定W(5,1000,500)。复用本轮两条固定随机删点路径，n=50、20、7；未按表现筛选新路径。虚线为真位置，MDM横点线为δ=0.1，圆点为原返回位置；LSE越低越好。定位曲线的解释依据Research00报告1，本图重新计算这些样本的判据，不重写正式结果。个案说明传递环节，不给出方法总体名次。</em></p>'),
            text('n-a-value', '<p><strong>采用理由：</strong>能直接把“相同样本变化、不同参数响应”连接到方法规则。适合讲具体过程；曲线较多，需要沿三列依次讲。</p>')),
        option('n-fixed-position', 'B｜固定真位置，查明偏差从哪一步传入（推荐）',
            text('n-b-opening', '<p>要判断形状偏移是否与位置估计有关，可以对同一批样本做一个诊断：先固定真实位置，只恢复形状；再与原方法同时估计位置和形状的结果比较。这样改变的是定位环节，样本本身保持相同。</p>'),
            image('n-b-control', '31B_固定真位置与原定位.png', 'β=5的MDM与LSE：固定真位置和按原规则定位时，形状均值随n的变化'),
            text('n-b-reading', '<p>MDM固定真位置后，形状均值在各档n下均接近真值；采用原梯度阈值定位后，形状均值向下偏移，且n越小，两个结果相隔越远。这说明本组条件下，明显的形状低估与定位环节的传递有关，不能只归因于形状恢复本身。</p><p>LSE也受到定位环节影响，但均值改变的幅度较小。这并不意味着LSE更稳定：n=7时，其原形状估计的波动明显大于MDM。因此，同样的定位不确定性，可以在一种方法中更多表现为方向性偏差，在另一种方法中更多表现为波动。</p>'),
            dict(id='n-b-bias-sd', kind='visual', html='<table><tr><th>β=5，n=7</th><th>原形状偏差</th><th>原形状SD</th><th>固定真位置后的形状偏差</th></tr><tr><td>MDM</td><td>−2.62</td><td>1.14</td><td>+0.47</td></tr><tr><td>LSE</td><td>−0.58</td><td>3.54</td><td>+0.73</td></tr></table>'),
            text('n-b-source', '<p><em>固定W(5,1000,500)，每档n使用本法全部1200个有效样本。原估计读取存档；MDM固定γ=500后仍用原伪尺度最小标准差和形状范围，LSE固定γ后仍用原顺序统计量期望和回归关系。表中SD按总体标准差计算。固定真位置是模拟诊断，实际应用不能获得这一条件；差值不是完整的因果贡献分解。</em></p>'),
            text('n-b-value', '<p><strong>推荐理由：</strong>用同样本的条件对照定位偏差形成环节，比再次展示“样本少、误差大”更进一步。若与A组合，可先用本图确认定位环节的重要性，再用交点和最低点说明怎样传入。</p>')),
        option('n-rule-map', 'C｜用一张机制关系图作精简讲解',
            image('n-c-route', '31C_样本到定位的分路.png', '样本量减少通过最小值、梯度交点及线性匹配三条路线进入参数估计'),
            text('n-c-reading', '<p>样本量减少后，少数点及局部间距对估计的作用更突出。K–R将下端空缺直接转为位置误差；MDM让间距变化先改变梯度交点；LSE则让它改变最佳匹配位置及回归斜率。各法使用的信息和确定位置的规则不同，偏差与波动便可能以不同方式改变。</p>'),
            kr,
            text('n-c-value', '<p><strong>适用方式：</strong>适合口头汇报时快速交代三条传递路径。关系图归纳Research00及本轮诊断，除K–R精确关系外，并不定量证明哪种方法更适应小样本；若要展开这一判断，宜保留A或B作为图证。</p>')),
    ]

    old32 = next(u for u in board['units'] if u['id'] == 'mechanism-n')
    source_origin = copy.deepcopy(next(x for x in old32['options'][0]['blocks'] if x['id'] == 'origin-probability-figure'))
    source_caption = copy.deepcopy(next(x for x in old32['options'][0]['blocks'] if x['id'] == 'gap-interpretation'))
    background = dict(id='mechanism-n-background', title='3.2　形状条件下的偏移与边界聚集', mode='content', options=[option('shape-common', '共同内容',
        source_origin, source_caption,
        image('shape-compatible', 'R00_图3_参数组合与样本相容.png', 'Research00报告1：W(5,1000,500)与W(2,500,1000)在样本覆盖区间内接近'),
        text('shape-compatible-reading', '<p>最小观测远离起点时，有限样本主要覆盖分布中部。图中的两组参数虽然相差较大，在这些观测所在的区间内，分布曲线仍较接近。因此，样本可能容许不同的参数组合；还需要追踪方法判据为什么选中了其中某一组。</p><p><em>复用Research00报告1图3：β=5、n=7第31组样本；黑点累计概率由样本排序近似。两条曲线用于说明参数相容，不代表该样本必然被估成其中某一组参数。</em></p>'))])
    old32.update(title='偏移与边界：解释方案', mode='choices', inline=True, outline_level=4, state='expand', selection_mode='multiple', selected=None, selected_ids=[],
                 context='共同的样本起点图与参数相容图只展示一次。下面选择怎样解释“判据为何选出偏移参数”及“为何返回零边界”。推荐A作完整叙述；B为当前结果的简洁核对，可与A组合；C用于压缩主讲。')
    old32['options'] = [
        option('shape-r00-process', 'A｜沿Research00的估计流程解释（推荐）',
            text('shape-a-opening', '<h4>先解释有方向的参数偏移</h4><p>MDM仍按同一个梯度阈值定位。高β时，各观测反算的伪尺度随位置变化更接近同步，标准差梯度较小，阈值交点可能出现在偏高位置。位置提高后，小观测到起点的距离缩短比例更大，需要更小的形状维持伪尺度的一致，再恢复出更小尺度。</p>'),
            image('shape-a-mdm', 'R00_MDM_位置形状尺度传递.png', 'Research00报告1：梯度阈值选中较高位置后，形状和尺度随之降低'),
            text('shape-a-mdm-reading', '<p>图中先看梯度交点，再沿同一位置看形状与尺度。这样，位置偏高、形状偏低、尺度偏低对应的是同一估计过程的传递，三个参数的偏差有共同来源。</p><p><em>Research00报告1图5，δ=0.1；β=2、5，n=7第48组配对样本。用于说明传递路径，不据单例认定全部方法或全部样本均如此。</em></p><h4>再解释为什么会在零位置聚集</h4>'),
            image('shape-a-lse-zero', 'R00_报告2_LSE零边界.png', 'Research00报告2：LSE左移位置改善线性匹配，最佳位置可落在零边界或内部'),
            text('shape-a-boundary-reading', '<p>LSE移动位置是为了让对数距离与参考坐标更接近直线。左移位置会压缩下端对数间距；当这能改善点列匹配时，准则倾向于更低位置。图中橙色样本在允许范围内的最低点落到γ=0，紫色样本的最低点则留在内部。γ≥0的约束使不同样本都可能返回同一个零值，重复估计中便形成边界聚集。</p><p>选低位置也压缩了整体对数跨度，使LSE回归斜率减小，取倒数后形状升高。因此，边界位置和形状高估可以沿同一条恢复关系连接起来。</p><p><em>复用报告2图6：正常与零边界样本为W(2,100,500)、n=15第35、36组；内部左偏为W(2,1000,3000)、n=7第1组。这里借用其机制图，不将这些历史条件并入本轮β=5统计。当前条件的边界核对见B。</em></p>'),
            text('shape-a-value', '<p><strong>推荐理由：</strong>按“判据怎样定位—位置怎样传递到其他参数”讲，分别回应规律性偏移和边界聚集；尽量复用报告1、报告2的现成证据。</p>')),
        option('shape-current-profiles', 'B｜用当前同一条件的两条判据直接对照',
            image('shape-b-profiles', '32B_内部偏移与边界选择.png', '当前β=5、n=7的LSE：一个内部偏移样本和一个零边界样本的位置准则'),
            text('shape-b-reading', '<p>两图使用相同参数条件、相同方法。左例的准则最低点位于真位置右侧，方法因此选中较高位置；右例的准则向低位置方向持续改善，但允许范围从零开始，实际返回值停在γ=0。零边界并不是用零代替失败，而是当前准则与非负位置约束共同给出的结果。</p><p>位置选定后，形状继续由同一回归斜率恢复。右移位置会拉开下端对数距离，可能对应较小形状；左移则压缩跨度，可能对应较大形状。这条关系解释了为什么两种定位方向会伴随不同的形状偏移。</p><p><em>W(5,1000,500)、n=7、本轮LSE原样本。左例沿用第0组，右例为零边界组中向γ=−600延伸的准则改善量接近中位数的第214组；不是按最大异常程度选例。灰区为原方法不允许的负位置，仅作廓线诊断；两图纵轴范围不同，比较各自最低点位置，不比较曲线绝对高低。</em></p>'),
            text('shape-b-value', '<p><strong>采用理由：</strong>用较少子图说明当前结果里的两种位置选择。它直接核对定位准则，关于点列怎样变直及参数怎样恢复，可接A中的报告2原图。</p>')),
        option('shape-two-routes', 'C｜用偏移与边界两条路径归纳',
            image('shape-c-routes', '32C_偏移与边界两条路径.png', '从高β下的起点信息不足分别走向内部参数偏移和零边界聚集'),
            text('shape-c-reading', '<p>前两图说明高β、小样本下，起点附近信息不足，不同参数组合在中部仍可能相容。随后存在两类选择路径：一类在内部选中偏移位置，并带动形状、尺度改变；另一类的判据倾向于更低位置，在非负约束下集中返回零边界。</p><p>这张图将两个现象放回同一估计过程，同时保留它们的区别。它是对机制证据的归纳；如果主讲只使用此图，A或B中的实际判据图应作为解释依据，而不是仅凭箭头作结论。</p>'),
            text('shape-c-value', '<p><strong>适用方式：</strong>用作主讲的压缩图或本节收束。优点是路径清楚，细节少；定量说服力来自A、B及Research00，不宜独自承担全部验证。</p>')),
    ]
    index = board['units'].index(old32)
    board['units'].insert(index, background)

    u33 = next(u for u in board['units'] if u['id'] == 'mechanism-boundary')
    u33['options'] = [option('mechanism-boundary', '当前内容',
        text('anomaly-opening', '<p>明显异常估计要追踪异常在哪个估计环节形成。Research00报告2区分了两种情况：当前方法的准则确实支持一组明显偏离真值的参数；或搜索、停止、候选接受没有正确落实预定规则。</p><h4>样本结构改变判据，异常参数仍可满足方法规则</h4>'),
        dict(id='anomaly-statistical', kind='gallery', aspect_ratio=1.68, images=[
            dict(id='lse-right', label='LSE：改善线性匹配后，形状反而明显低估', src='assets/R00_报告2_LSE_right.png', alt='报告2图7：远端观测改变点列，位置右移改善匹配并使形状降低'),
            dict(id='wmle-low', label='WMLE：两条方程均满足，参数仍明显偏离真值', src='assets/R00_报告2_WMLE_low.png', alt='报告2图12：样本距离改变共同交点，残差趋零但形状与尺度仍低估'),
        ]),
        text('anomaly-lse-reading', '<p>LSE的异常样本中，前几个观测相对集中，另有一个较远观测。真位置下的点列与参考坐标匹配较差，右移位置能拉开下端对数间距，使点列更接近直线。准则因此选中靠近最小观测的位置，但随之增大的回归斜率取倒数后，形状明显降低，尺度也由缩小的距离恢复为较低值。</p><p>WMLE的异常样本改变了下端距离、对数距离和幂加权距离，两条方程的共同交点移向较高位置、较低形状。将返回参数代回，残差仍接近零。这里不是方程没有解对，而是这些样本统计量本身支持了偏离真值的参数。</p><p><em>复用报告2图7、12。LSE为W(2,1000,500)、n=7第18、19组；WMLE为W(5,100,500)、n=7第3、11组。保留历史实现及参数条件，只解释形成路径。</em></p><h4>数值求解未落实规则，也能形成异常返回</h4>'),
        image('anomaly-solver', 'R00_报告2_MLE_stop.png', '报告2图17：旧MLE近零停点仍存在提高似然的方向'),
        text('anomaly-solver-reading', '<p>旧MLE的第37组在近零位置停止，优化器标记收敛；其他起点的返回结果又因形状不满足接受条件被剔除，最终只剩这个候选。但图中向右仍可提高似然，说明搜索停止及候选接受没有实现预期的最优选择。近零位置进一步压缩对数跨度，形成较大的形状估计。</p><p><em>报告2图17，W(2,1000,3000)、n=7第37、38组，采用旧MLE。Study04已更新求解器，此例用于区分计算来源，不认定新版仍有同一缺陷。</em></p><p>前两例应研究估计准则对样本结构的响应；后一例应改进求解与候选检查。异常表现相近，形成环节不同，改进方向也不同。</p>'))]
    u33.update(mode='content', state='modify')

    for u in board['units']:
        if u['id'] in {'mechanism-high-beta', 'mechanism-n', 'mechanism-boundary', 'manuscript-outline', 'chapter-4', 'mechanism-n-background'}:
            continue
        assert u == next(x for x in before['units'] if x['id'] == u['id'])
    next(u for u in board['units'] if u['id'] == 'chapter-4')['options'][0]['blocks'] = [text('mechanism-chapter-opening', '<p>以下分别解释三类现象：样本减少时方法的不同响应、高形状条件下的参数偏移与边界聚集，以及明显异常估计的形成。解释沿样本信息、选参判据和参数恢复展开。</p>')]
    next(u for u in board['units'] if u['id'] == 'manuscript-outline')['title'] = '报告下（方法对比）v2.1 待审'
    board.update(revision=before['revision'] + 1, manuscript_version='2.1', manuscript_date='2026-10-23', review_phase='chapter3-mechanism-candidates', review_complete=False)
    board.setdefault('chapter3_evidence', {})['mechanism_candidates_sources'] = source_map
    board['chapter3_evidence']['fixed_position_control'] = '结果呈现/分析数据/第三章固定真位置对照.csv'
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'revision': board['revision'], 'choices': {'3.1': 3, '3.2': 3}, 'source_v2.0_unchanged': hashlib.sha256((STUDY/'报告下（方法对比）-v2.0.md').read_bytes()).hexdigest() == board['source_sha256']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
