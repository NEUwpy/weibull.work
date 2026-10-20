"""基于已定骨架发散表达形式；复用review-html，不生成新讲稿或新估计。"""
from pathlib import Path
import hashlib, html, json, runpy, shutil, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent.parent
ROOT=STUDY/'reviewbyhtml/方法对比'
SKILL=Path.home()/'.codex/skills/review-html'
sys.path.insert(0,str(SKILL/'scripts'))
from math_html import render_html_batch

LABELS=['MDM','LSE','LRE','WMLE','MLE','K–R','MM']
COLORS=['#0072B2','#009E73','#CC79A7','#D55E00','#444444','#56B4E9','#E69F00']
BETAS=[1.5,2.,2.5,3.,3.5,4.,4.5,5.]
NS=[50,20,15,10,7]

def markup(text):return html.escape(str(text))
def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th>'+markup(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+markup(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'

def text_block(key,text):return dict(id=key,kind='text',html='<p>'+text+'</p>')
def visual(key,content):return dict(id=key,kind='visual',html=content)

def asset(source):
    target=ROOT/'assets'/source.name
    if not target.exists() or target.read_bytes()!=source.read_bytes():shutil.copy2(source,target)
    return 'assets/'+target.name

def picture(key,source,alt):return dict(id=key,kind='image',src=asset(source),alt=alt)

def option(letter,title,blocks,advantage,omission):
    return dict(id=letter,label=letter+' · '+title,blocks=blocks+[
        text_block('what','<strong>能讲清：</strong>'+advantage),
        text_block('tradeoff','<strong>会省略／还要补：</strong>'+omission)])

def existing(model,group,index):
    item=model['figures'][group][index]
    return [picture('preview',HERE/'图'/item['file'],item['label']),text_block('scope',markup(item['caption']))]

def context(uid,title,body):
    return dict(id=uid,title=title,mode='content',state='open',selected=None,
                options=[dict(id='current',label='骨架与问题',blocks=[text_block('skeleton',body)])])

def choices(uid,title,opts,context_line):
    return dict(id=uid,title=title,mode='choices',inline=True,state='open',selected=None,
                context=context_line,options=opts)

def new_previews(model):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    directory=ROOT/'assets'
    rmse=np.array(model['stats']['common']['rmse']);ratio=np.array(model['ratios'])
    # Fixed design-domain endpoints and n=20 illustrate the form; not selected extrema.
    fig,axs=plt.subplots(2,3,figsize=(12,6.4),layout='constrained')
    for row,j in enumerate([0,7]):
        for p,ax in enumerate(axs[row]):
            x=rmse[p,1,j]/(BETAS[j] if p==0 else 1000)
            ax.scatter(x,range(7),c=COLORS,s=30,zorder=3)
            ax.set_yticks(range(7),LABELS);ax.invert_yaxis();ax.set_xscale('log')
            ax.set_xlabel(['β','η','γ'][p]+' normalized RMSE (log)');ax.set_title(f'β={BETAS[j]:g}, n=20');ax.grid(axis='x',alpha=.14)
    point=directory/'发散_同条件七法点图.png';fig.savefig(point,dpi=150,bbox_inches='tight');plt.close(fig)
    fig,axs=plt.subplots(2,3,figsize=(12,6.7),layout='constrained')
    for row,j in enumerate([0,7]):
        for p,ax in enumerate(axs[row]):
            for m in range(7):ax.plot(ratio[p,:,j,m],range(5),marker='o',ms=3,color=COLORS[m],label=LABELS[m])
            ax.set_xscale('log');ax.set_yticks(range(5),NS);ax.invert_yaxis()
            ax.set_ylabel('n');ax.set_xlabel(['β','η','γ'][p]+' RMSE / min (log)');ax.set_title(f'β={BETAS[j]:g}');ax.grid(axis='x',alpha=.14)
    handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,ncol=7,frameon=False,loc='outside lower center')
    trajectory=directory/'发散_五档样本量轨迹.png';fig.savefig(trajectory,dpi=150,bbox_inches='tight');plt.close(fig)
    return point,trajectory

def flow(items):
    return '<div style="display:grid;gap:8px;text-align:center">'+'<div style="color:#759581">↓</div>'.join('<div style="border:1px solid #b9cdbd;border-radius:7px;padding:12px;background:#f5f8f4">'+x+'</div>' for x in items)+'</div>'

def build():
    p=ROOT/'board.json';board=json.loads(p.read_text(encoding='utf-8'))
    feedback_path=ROOT/'feedback.json'
    if feedback_path.exists():
        feedback=json.loads(feedback_path.read_text(encoding='utf-8'))
        if feedback.get('board_revision')==board['revision'] and not board.get('last_applied_submission'):
            raise RuntimeError('当前轮次有待处理反馈，请先resume并处理，不覆盖。')
    if board.get('stage') in ['presentation-divergence','selected-presentation']:
        print(json.dumps(dict(status='EXISTS',revision=board['revision'],root=str(ROOT)),ensure_ascii=False));return
    model=json.loads((HERE.parent/'分析数据/比较论证-v0.4.json').read_text(encoding='utf-8'))
    for rel,digest in model['sources'].items():assert hashlib.sha256((STUDY/rel).read_bytes()).hexdigest()==digest
    (ROOT/'assets').mkdir(exist_ok=True);point,trajectory=new_previews(model)
    units=[context('text-b002','本轮：沿骨架发散表达，不写成稿',
        '骨架保留为<strong>整体差异 → 条件变化 → 误差与代价 → 典型解释 → 选择启示</strong>。下面只讨论每处怎样表达、能讲清什么，以及会遗漏什么；没有预写讲稿，也没有预选要得到的结论。候选可以组合，选中先记方向，仍可继续扩展。'),
        context('evidence-base','共用素材与口径',
        '已有七种方法、8个β×5个n、每条件1200次的结果。预览主要复用这些数据；形状、尺度、位置分开。主要精度预览用七法共同有效样本，返回率用全部尝试；单个条件图只演示表达结构，不代替全域证据。')]
    units.append(context('text-b003','1　整体差异在哪些地方值得看',
        '<strong>本处要讲清：</strong>七种方法在相同条件下究竟相差多少；是大多数方法分开，还是某个极端方法拉开了量程？<br>这里先辨认整体格局，变化规律放到下一处。'))
    rows=[[s['method']]+[f'{n}/40' for n in s['near'][:3]] for s in model['summaries']]
    units.append(choices('figure-global','这里可以怎样让听众先看到全貌',[
        option('A','中间差异与极端差异分开画',existing(model,'global',0),
            '一张区域图同时看中间方法和最差方法离参照多远；先定位值得继续查的n、β区域。',
            '图中没有具体方法身份，要接一个方法表。每面板色标独立，不能只凭深浅跨面板比大小。'),
        option('B','七法全条件误差比表',existing(model,'global',1),
            '七种方法、40个条件、三个参数全部在场，可追到具体方法和坐标。',
            '内容密，讲述需要引导；适合材料全景，PPT需局部放大或逐步揭示。'),
        option('C','同条件七法点图',[
            picture('preview',point,'七种方法在同条件下的误差点图'),
            text_block('scope','示意取n=20及β域两端1.5、5；不是按差异最大筛出的条件。三列为三个参数，七法全部显示，横轴为标准化RMSE，对数刻度。')],
            '方法名称与误差距离直接对应，容易看清是整体分开还是一法突出。',
            '两个切片不能代表40个条件；若采用，要补全域检查，示例条件也可再换。'),
        option('D','概览表：各法接近参照的覆盖面',[
            visual('coverage-table',table(['方法','形状','尺度','位置'],rows)),
            text_block('scope','数字为RMSE不超过本条件最小值1.10倍的条件数；共同有效口径。10%只是一种显示刻度，可讨论5%或20%，不作为工程合格线。')],
            '不依靠极端最大值，先看各方法在多大范围内接近参照，以及三个参数是否一致。',
            '会丢掉这些条件位于哪里，也压缩了优势幅度；需要一张条件图承接。')],
        '四种形式分别强调区域、完整对应、直观距离和覆盖面。先比较各自读图效果，不要求这一轮定唯一主图。'))
    units.append(context('text-b013','2　差距怎样随n和β一起改变',
        '<strong>本处要讲清：</strong>同样减少样本，各方法的相对距离怎样变化；不同β下，这种变化是否一致？<br>保留全部七法作为比较底座，下面尝试不同的信息展开顺序。'))
    rose=STUDY/'结果呈现/图片/16_RMSE玫瑰图_β5_样本量序列.png'
    units.append(choices('figure-change','这里可以怎样表达“变化”',[
        option('A','完整轨迹：每个方法一行',existing(model,'change',0),
            '五档n、八个β及七种方法都保留，可检查规律在哪些条件下成立、哪里有反例。',
            '面板较多，听众需要来回比；更适合查证，讲述时需要聚焦少数有依据的观察。'),
        option('B','端点变化：距离变近还是变远',existing(model,'change',1),
            '把n=50到7的相对变化压成一个倍数，容易比较方向和β差异。',
            '看不到20、15、10的中间过程；端点变化不能被称作单调趋势。'),
        option('C','玫瑰图逐档展开',[
            picture('preview',rose,'β=5时n从50到7的现有RMSE玫瑰图'),
            text_block('scope','沿用现有样式；当前主视图是六法、β=5，n=50→20→15→10→7。采用时需配七法完整范围及其他β的核对。')],
            '适合作为口头报告的逐步出现画面：方法轮廓在同一刻度下怎样变化。',
            '不同β要另看；扇形比较容易受视觉面积影响，MM的完整量级也需要补上。'),
        option('D','固定β，沿纵向走过五档n',[
            picture('preview',trajectory,'β域两端的七法样本量轨迹'),
            text_block('scope','示意取β=1.5和5；n纵向、三参数横向，七法均保留。横轴为同条件相对距离，对数刻度。')],
            '同一条方法轨迹随n向下走；两种β并排理解，便于比较样本量响应是否相同。',
            '只展示β域两端；若采纳此种结构，再决定怎样补中间六个β。')],
        '这里的分歧在展开顺序：先看全域、先压缩端点、先逐档展示，或先固定β。'))
    units.append(context('text-b023','3　差距体现为怎样的误差和代价',
        '<strong>本处要讲清：</strong>前面看到的差距，究竟对应持续偏移、重复波动、极端输出，还是没有返回有效估计？<br>分布形式和风险形式分别发散，可以各取一种，也可以批注要求组合。'))
    bias=np.array(model['stats']['common']['bias']);sd=np.array(model['stats']['common']['sd']);rmse=np.array(model['stats']['common']['rmse'])
    stats_rows=[[m]+[f'{a[0,0,7,k]/5:.3f}' for a in [bias,sd,rmse]] for k,m in enumerate(LABELS)]
    distribution=STUDY/'结果呈现/图片/01_估计值分布_β5.png'
    units.append(choices('figure-error','3a　偏移与波动可以怎样表达',[
        option('A','中位数与分位区间带',existing(model,'error',0),
            '中心位置与主体宽度较容易对照，画面简洁，适合讲偏移与波动的区别。',
            '只显示中心90%，不能靠它判断极端估计；需要误差指标或尾部图。'),
        option('B','完整绝对误差累积曲线',existing(model,'error',1),
            '可以问“误差小于这个数的比例是多少”，同时看到主体和极端尾部。',
            '绝对误差丢掉高估／低估方向，曲线重叠时也难分辨。'),
        option('C','现有估计值分布图',[
            picture('preview',distribution,'β=5下现有估计值分布图'),
            text_block('scope','复用已有分布图：n纵向、三个参数横向；真值、估计分布和中心位置同图。图像使用既定显示窗口，窗外有效值仍进入统计。')],
            '沿用Research00式直觉：估计落在哪，集中还是分散，距真值多远。',
            '信息密、画面长；显示窗外的尾部必须另看。'),
        option('D','小表只对照这三种性质',[
            visual('bias-sd-table',table(['方法','相对Bias','相对SD','相对RMSE'],stats_rows)),
            text_block('scope','β=5、n=50，七法共同有效集合；三项均除以真β。只是表格式预览，不扩展为全条件指标清单。')],
            '数值关系明确，便于解释偏移小、波动小、总误差小各指什么。',
            '缺少分布形状和逐次估计直觉；讲述不能变成逐行报数。')],
        '先比较哪种形式更容易让你看懂“集中”和“接近真值”的区别。'))
    audit=model['audit'];rates=STUDY/'结果呈现/图片/06_有效率.png';risk=STUDY/'结果呈现/图片/07_形状异常频率.png'
    units.append(choices('figure-tail','3b　尾部与返回问题可以怎样表达',[
        option('A','平方误差的累积贡献',existing(model,'tail',0),
            '直接回答较大RMSE是否被少量记录主导，七法在同一条件下都能看。',
            '这是影响大小，不是发生频率；示例由全域筛查得到，还需说明其代表范围。'),
        option('B','全条件发生频率与有效率',[
            picture('risk-map',risk,'七法形状异常频率'),picture('return-map',rates,'七法有效率'),
            text_block('scope','两张图分开表达：有效但形状明显偏离，以及是否返回有效估计。异常阈值沿用β̂≤β/3或β̂≥3β，异常率以有效数为分母，有效率以1200次为分母。')],
            '能看问题在哪些条件反复出现，而不是只被一条极端记录吸引。',
            '频率不说明损失有多大；阈值要能说明，0次发生也仍是本批观察。'),
        option('C','比较集合怎样改变判断的对照表',[
            visual('subset-audit',table(['β=5，n=7：B1','次数','RMSE'],[
                ['MLE自身有效',audit['mle_count'],f"{audit['mle_rmse']:.2f}"],
                ['MDM自身有效',1200,f"{audit['mdm_own']:.2f}"],
                ['MDM在相同817份样本',817,f"{audit['mdm_on_mle']:.2f}"]])),
            text_block('scope','这个案例解释整体寿命表的口径问题：自身有效口径下MLE在18/40条件最低，共同有效口径下为0/40。这里没有给失败填虚构误差。')],
            '可以简洁说明“成功结果误差较小”为什么要和返回情况一起看。',
            '主要解释评价口径，不是异常机制；若讲得太长会挤占方法差异本身。')],
        '贡献、频率、成功筛选回答不同问题；这里允许你用批注指定组合，不要求三选一就覆盖所有风险。'))
    units.append(context('text-b035','4　典型解释怎样接回方法构造',
        '<strong>本处要讲清：</strong>从整体结果提出的一个现象，怎样用方法步骤解释得简明？<br>K–R来自形状与位置表现不一致的线索；MM来自极端输出影响RMSE的线索。先比较解释对象与讲法，不要求两个都讲。'))
    kr_flow=flow(['<strong>K–R定位动作</strong><br>$\\hat\\gamma=X_{(1)}$',
                  '<strong>有限样本的最小值仍离起点有距离</strong>',
                  '<strong>位置出现正偏移</strong><br>随n、β改变，距离缩小的速度也不同'])
    mm_flow=flow(['<strong>已有矩差之比</strong><br>1.00005226',
                  '<strong>取对数后很接近零</strong><br>约0.00005225',
                  '<strong>用它作分母恢复形状</strong><br>β̂约13265'])
    units.append(choices('figure-mechanism','这里可以怎样把解释说简单',[
        option('A','K–R理论曲线叠实测点',existing(model,'mechanism',0),
            '把构造的定量后果和模拟观察接起来，可核对n、β怎样共同影响偏移。',
            '需要先交代样本最小值定位及理论Bias公式，会比口头直觉多一步。'),
        option('B','K–R动作—距离—偏移的三步图',[
            visual('kr-chain',kr_flow),
            text_block('formula','若需要，再补公式 $E(\\hat\\gamma-\\gamma)=\\eta\\Gamma(1+1/\\beta)n^{-1/\\beta}$；本轮先看这条解释链是否容易理解。')],
            '用很少的文字回到方法的定位动作，容易接上第一部分。',
            '直觉链不展示实测支持；可以配一两个数，或与方案A组合。'),
        option('C','MM的小差别被放大：数值三步图',[
            visual('mm-chain',mm_flow),
            text_block('formula','对应Cran恢复式 $\\hat\\beta=\\ln 2/\\ln[(m_1-m_2)/(m_2-m_4)]$。数值来自β=5、n=15的样本289，仅解释该条记录。')],
            '把近奇异恢复转成一条易看的算术链，解释为什么少量输出可能非常大。',
            '没有同时解释发生频率；不能把一条恒等关系扩大成所有异常的原因。'),
        option('D','两类问题一张对照表',[
            visual('mechanisms',table(['现象','对应步骤','可以怎样说','还缺什么'],[
                ['持续偏移','K–R用最小值定位','最小值还没靠近真实起点','形状、尺度的后续恢复仍要单看'],
                ['极端输出','MM由矩差比恢复形状','两个量太接近，分母很小','频率和其他异常来源']]))],
            '把偏移与极端输出放回不同构造环节，前后两部分容易衔接。',
            '每个案例解释较浅；若篇幅只够一个，仍需选主例。')],
        '这里的候选既有图形形式的差异，也有解释线索的差异；可以只保留一种线索继续发散。'))
    units.append(context('text-b044','5　比较怎样转为选择启示',
        '<strong>本处要讲清：</strong>方法差异对什么选择有用，需要知道哪些信息，以及参数目标换成寿命目标后应怎样重新判断？<br>这里先试表达形式，尚不写推荐规则或自动选法结论。'))
    decision=flow(['<strong>先明确使用目标</strong><br>形状／尺度／位置，还是B1等寿命量？',
                   '<strong>已知n，β范围有多大依据？</strong><br>有范围：在子域比较；未知：先给定参考域',
                   '<strong>再看精度与风险要求</strong><br>平均误差、偏移、返回情况、异常影响',
                   '<strong>形成候选并验证选择规则</strong><br>当前不填“自动最优方法”'])
    units.append(choices('figure-life','这里可以怎样表达实际选择的意义',[
        option('A','条件表：候选名称与差距一起看',existing(model,'life',0),
            '保留你觉得有意思的n×β表格形式，同时显示第一、第二候选相差多少。',
            '真β在实际使用时未知；微小差距仍须核对不确定性，不能把地图直接当可用选择器。'),
        option('B','工程精度曲线：返回且满足要求的比例',existing(model,'life',1),
            '从“谁的RMSE小”换成“给定精度要求，有多少次可用”，把返回情况纳入同一分母。',
            '当前只示意β=5的两档n；工程容限没有预定，需要先讨论关心哪种要求。'),
        option('C','信息—目标—候选的决策草图',[
            visual('decision-flow',decision)],
            '把比较与实际使用接起来，明确先有信息与需求，再形成候选。',
            '这是选择思路，尚未给出可执行并验证的规则；后续AI研究可从这里接出。')],
        '三种方向分别强调条件地图、工程可用比例和选择过程。可以选一个主画面，再备注另一种作补充。'))
    units.append(context('closing-slot','收尾位置先保留',
        'AI辅助选法与weibull.work仍放在结尾。当前只保留<strong>已有比较 → 利用具体样本信息的下一步研究 → 网站方法入口</strong>这条衔接，不预写寒暄或完整口述。'))
    blocks=[b for u in units for o in u['options'] for b in o['blocks'] if 'html' in b]
    for b,markup_ in zip(blocks,render_html_batch([b['html'] for b in blocks])):b['html']=markup_
    board.update(title='方法对比：沿骨架发散表达方式',document=True,revision=board['revision']+1,
                 stage='presentation-divergence',units=units,review_complete=False,
                 source='../表达方式发散.md')
    for key in ['processing','submitted','last_applied_submission','completed_at']:
        board.pop(key,None)
    p.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_markdown(board)
    print(json.dumps(dict(status='READY',revision=board['revision'],units=len(units),
        alternatives=sum(len(u['options']) for u in units if u['mode']=='choices')),ensure_ascii=False))

def write_markdown(board):
    intro='本轮确认内容已整理为[报告下（方法对比）v0.4](../../报告下（方法对比）-v0.4.md)；本文件保留HTML审阅内容镜像。' if board.get('review_complete') else '当前是内容与图表表达的审阅镜像；正式选择、批注与下一步以审阅页提交为准。'
    out=['# '+board['title'],'',intro,'']
    for u in board['units']:
        out.extend(['## '+u['title'],''])
        if u.get('context'):out.extend([u['context'],''])
        if u['mode']=='choices' and u.get('selected'):
            chosen=next(o for o in u['options'] if o['id']==u['selected'])
            out.extend(['**当前方向：'+chosen['label']+'**（保留其他候选）',''])
        for o in u['options']:
            if u['mode']=='choices':out.extend(['### '+o['label'],''])
            for b in o['blocks']:
                if b['kind']=='gallery':
                    for slide in b['images']:
                        out.extend(['### '+slide.get('label',slide['id']),'',f'![{slide.get("alt","")}]({(ROOT/slide["src"]).as_posix()})',''])
                else:out.extend([f'![{b.get("alt","")}]({(ROOT/b["src"]).as_posix()})' if b['kind']=='image' else b['html'],''])
    (HERE/'表达方式发散.md').write_text('\n'.join(out),encoding='utf-8')

def reuse_research00():
    """处理第二轮批注，直接接入Research00原图，不重算或重绘。"""
    board_path=ROOT/'board.json'
    board=json.loads(board_path.read_text(encoding='utf-8'))
    assert board['revision']==6
    assert board.get('last_applied_submission_id')=='cc7f25a7-c140-45df-9dfc-c001ef50f5a8'
    before={u['id']:json.dumps(u,ensure_ascii=False,sort_keys=True) for u in board['units']}
    research=STUDY.parent.parent/'Research/00-方法对比'
    feedback=json.loads((ROOT/'feedback.json').read_text(encoding='utf-8'))
    unit=next(u for u in board['units'] if u['id']=='text-b035')
    block=unit['options'][0]['blocks'][0]
    note=next(u for u in feedback['units'] if u['unit_id']=='text-b035')['annotations'][0]
    assert block['id']==note['block_id']
    assert hashlib.sha256(block['html'].encode()).hexdigest()==note['block_hash']
    assert note['quote'] in block['html']
    sources={}
    def original(key,folder,filename,alt):
        source=research/'交付/结果'/folder/filename
        target=ROOT/'assets'/('R00_'+filename)
        shutil.copy2(source,target)
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
        sources[source.relative_to(research).as_posix()]=digest
        return dict(id=key,kind='image',src='assets/'+target.name,alt=alt)
    for filename in ['报告1：小样本情况下高形状参数的估计偏移.md','报告2：小样本情况下的明显异常估计.md']:
        sources[filename]=hashlib.sha256((research/filename).read_bytes()).hexdigest()
    block['html']=(
        '<p><strong>本处要讲清：</strong>前面看到的偏移与异常，已有研究怎样解释？'
        '<br>直接复用Research00两份报告：报告1解释高β、小样本下的起点信息不足、参数补偿与逐法偏移；'
        '报告2沿正常／异常样本的估计过程，区分方法准则偏好的偏离组合与计算造成的异常。'
        '<br>下面放入现成图与简述，继续比较本报告适合摘哪一段；原有简化链和本轮MM案例也保留。</p>')
    mechanisms=next(u for u in board['units'] if u['id']=='figure-mechanism')
    opts={o['id']:o for o in mechanisms['options']}
    opts['A'].update(label='A · 复用报告1：K–R的三参数偏移过程',blocks=[
        original('preview','报告1','图15_MMLE定位与形状尺度.png','Research00报告1图15：MMLE定位与形状尺度'),
        text_block('scope','来源：Research00报告1第2.6节、图15。原图保留β=2与5、n=7的50组估计和第3组展开，不重绘。K–R先取最小值定位，再拟合保留距离；高β例的位置偏高，随后形状和尺度偏低。'),
        text_block('what','<strong>能讲清：</strong>把本轮分布图中的有规律偏移接回具体估计步骤，从位置一直讲到形状和尺度，复用原报告的解释。'),
        text_block('tradeoff','<strong>会省略／还要补：</strong>这是一种方法的典型过程；原图属于Research00历史案例，不能并入本轮1200次统计。六格较满，采用后可再决定保留哪些面板。')])
    opts['D'].update(label='D · 复用报告2：准则偏好与计算停点分开看',blocks=[
        original('criterion-case','报告2','配对情形_MLE_high.png','Research00报告2图15：较高似然与形状高估'),
        text_block('criterion-caption','来源：报告2第2.1.5节（1）、图15，W(2,100,500)、n=15。第36组的零位置候选比真位置条件拟合的对数似然约高0.68，同时形状估计达到23.54。此例说明：偏离真值的组合也可能得到方法准则的支持。'),
        original('solver-case','报告2','配对情形_MLE_stop.png','Research00报告2图17：旧求解器的近零停点'),
        text_block('solver-caption','来源：同节（3）、图17，W(2,1000,3000)、n=7。旧程序第37组停在近零位置，形状约13.10；改看γ=3000的条件候选，形状约2.17，对数似然从−50.3247升至−49.9405。该例定位的是旧搜索与停止问题。'),
        text_block('what','<strong>能讲清：</strong>异常结果要分两种情况看：准则本身偏好的偏离组合，以及程序尚未找到更好候选。两幅原图都已有正常样本作对照。'),
        text_block('tradeoff','<strong>会省略／还要补：</strong>先比较这两幅原图，采用后可只展开其中一幅，另一幅一句带过。本轮MLE已经更新求解器；旧停点不能证明新程序仍有同样缺陷，旧异常次数也不并入当前频率。')])
    if not any(o['id']=='E' for o in mechanisms['options']):
        mechanisms['options'].append(option('E','复用报告1：先用样本与分布解释共同背景',[
            original('sample-origin','报告1','图2_样本与真实起点.png','Research00报告1图2：样本与真实起点'),
            text_block('sample-caption','来源：报告1第2章、图2，β=2与5，n=7、15、30，每格50组；下排为样本最小值的理论密度。先让人看到：高β、样本较少时，最小观测往往仍离真实起点较远。'),
            original('compensation','报告1','图2_样本与分布相容.png','Research00报告1图3：不同参数组合在观测区间内相近'),
            text_block('scope','接原报告图3：W(5,1000,500)与W(2,500,1000)参数相差明显，在这组观测覆盖的中部区间却有相近曲线。这是为说明局部相容性设置的两个分布，并非两种方法的估计对比；黑点来自原β=5、n=7第31组。')],
            '先讲“样本没把起点约束住，参数之间又能补偿”，再接前面各法的偏移和波动；不必先展开某个方法的方程。',
            '共同背景不能解释每种方法最终偏向哪里；需要再接一句具体规则，或与A组合。先展示原图供选，选定后才精简面板，不另做一套实验。'))
    mechanisms['context']='A、D、E直接复用Research00图与解释；B保留简化链，C保留本轮MM案例。比较解释的入口和详略，仍不预选。'
    blocks=[b for u in [unit,mechanisms] for o in u['options'] for b in o['blocks'] if 'html' in b]
    for b,markup_ in zip(blocks,render_html_batch([b['html'] for b in blocks])):b['html']=markup_
    changed=[u['id'] for u in board['units'] if json.dumps(u,ensure_ascii=False,sort_keys=True)!=before[u['id']]]
    assert changed==['text-b035','figure-mechanism']
    board_path.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_markdown(board)
    (HERE.parent/'分析数据/Research00素材复用核对.json').write_text(json.dumps(dict(
        revision=6,submission_id=feedback['submission_id'],changed_units=changed,
        original_images_unchanged=True,new_estimates=0,sources=sources),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(revision=6,changed_units=changed,original_pngs_copied=5,new_estimates=0),ensure_ascii=False))


def remove_mm_case():
    board_path=ROOT/'board.json'
    board=json.loads(board_path.read_text(encoding='utf-8'))
    assert board['revision']==8
    assert board.get('last_applied_submission_id')=='31623669-9373-400f-8478-17efae9172dd'
    feedback=json.loads((ROOT/'feedback.json').read_text(encoding='utf-8'))
    unit=next(u for u in board['units'] if u['id']=='text-b035')
    block=unit['options'][0]['blocks'][0]
    note=next(u for u in feedback['units'] if u['unit_id']=='text-b035')['annotations'][0]
    assert hashlib.sha256(block['html'].encode()).hexdigest()==note['block_hash']
    assert note['quote'] in block['html']
    block['html']=(
        '<p><strong>本处要讲清：</strong>前面看到的偏移与异常，已有研究怎样解释？'
        '<br>复用Research00两份报告：报告1解释高β、小样本下的起点信息不足、参数补偿与逐法偏移；'
        '报告2沿正常／异常样本的估计过程，区分方法准则偏好的偏离组合与计算造成的异常。'
        '<br>从现有案例中选取：先看共同背景，再沿方法过程追踪参数偏移；求解问题用报告2的原案例说明。</p>')
    mechanism=next(u for u in board['units'] if u['id']=='figure-mechanism')
    assert next(o for o in mechanism['options'] if o['id']=='C')['label'].startswith('C · MM')
    mechanism['options']=[o for o in mechanism['options'] if o['id']!='C']
    mechanism['context']='E可交代小n、大β的共同背景；A用方法过程与偏差传递解释具体案例，D说明准则偏好与计算停点的区别，B保留简化讲法。候选字母沿用上一轮。'
    board_path.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_markdown(board)
    print(json.dumps(dict(revision=8,removed_explanation='figure-mechanism/C',
                         comparison_data_unchanged=True),ensure_ascii=False))


def prune_options():
    """按用户要求撤下弃用方案，所选内容恢复普通展示。"""
    board_path=ROOT/'board.json'
    board=json.loads(board_path.read_text(encoding='utf-8'))
    assert board['revision']==8 and not board.get('processing')
    titles={
        'figure-global':'整体差距：直接读百分比',
        'figure-change':'差距变化：六法线性玫瑰图与MM数值',
        'figure-error':'偏移与波动：两档n的估计值分布',
        'figure-tail':'异常与返回：全条件发生频率与有效率',
        'figure-mechanism':'解释：共同背景与方法过程',
        'figure-life':'选择启示：候选方法与差距的条件表'}
    removed={}
    for unit in board['units']:
        if unit.get('mode')!='choices':continue
        chosen=next(o for o in unit['options'] if o['id']==unit['selected'])
        kept={chosen['id']}
        if unit['id']=='figure-mechanism':
            background=next(o for o in unit['options'] if o['id']=='E')
            kept.add('E')
            background_blocks=[dict(b,id='background-'+b['id']) for b in background['blocks']
                               if b['id'] not in ['what','tradeoff']]
            chosen['blocks']=[text_block('background-heading','<strong>共同背景：小n、大β</strong>')]+background_blocks+[
                text_block('process-heading','<strong>沿方法过程追踪偏差传递</strong>')]+chosen['blocks']
        removed[unit['id']]=[o['id'] for o in unit['options'] if o['id'] not in kept]
        unit.update(mode='content',state='converged',title=titles[unit['id']],options=[chosen])
        for key in ['context','inline']:unit.pop(key,None)
    opening=next(u for u in board['units'] if u['id']=='text-b002')
    opening['title']='当前表达：沿骨架继续审阅'
    opening['options'][0]['blocks'][0]['html']=(
        '<p>骨架保留为<strong>整体差异 → 条件变化 → 误差与代价 → 典型解释 → 选择启示</strong>。'
        '下面只展示当前选定的方向，继续讨论图怎样讲清问题，尚未扩写成完整讲稿；可直接在文字和图下批注。</p>')
    explanation=next(u for u in board['units'] if u['id']=='text-b035')
    explanation['options'][0]['blocks'][0]['html']=(
        '<p><strong>本处要讲清：</strong>前面看到的偏移与异常，已有研究怎样解释？'
        '<br>复用Research00报告1、2：先用起点信息不足与参数补偿说明小n、大β的共同背景，'
        '再沿定位、形状确定、尺度恢复三个环节，展示系统偏移与明显异常怎样形成。</p>')
    board.update(title='方法对比：当前表达与批注',revision=9,processing=True,stage='selected-presentation',review_complete=False)
    board_path.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_markdown(board)
    print(json.dumps(dict(revision=9,removed_options=removed,choices_remaining=0,
                         history_preserved=True),ensure_ascii=False))


if __name__=='__main__':
    if sys.argv[1:]==['--reuse-research00']:reuse_research00()
    elif sys.argv[1:]==['--remove-mm-case']:remove_mm_case()
    elif sys.argv[1:]==['--prune-options']:prune_options()
    elif not sys.argv[1:]:build()
    else:raise SystemExit('可选参数：--reuse-research00、--remove-mm-case、--prune-options')
