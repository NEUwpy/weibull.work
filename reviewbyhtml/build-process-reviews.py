"""Review artifacts only: read frozen runs, never implement an estimator.

Invoke one method first (MLE), verify it, then prepare remaining methods.
Existing feedback stays at its original task root. This is a deliberate
editorial revision of the review scope, not a recurring content generator.
"""
from pathlib import Path
import copy
import hashlib
import html
import json
import re
import subprocess
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
SKILL = Path('C:/Users/36089/.codex/skills/review-html')
sys.path.insert(0, str(SKILL / 'scripts'))
from math_html import render_html_batch
plt.rcParams.update({'font.family':['Microsoft YaHei','DejaVu Sans'],'svg.fonttype':'none',
                     'font.size':17,'axes.spines.top':False,'axes.spines.right':False,
                     'axes.edgecolor':'#cbd5e1','text.color':'#213930',
                     'axes.labelcolor':'#334155','xtick.color':'#64748b','ytick.color':'#64748b'})

CONFIG = {
 'mle':dict(name='极大似然估计 MLE',
  story='不断尝试位置γ；每到一个位置，都求对应的形状β和尺度η。再比较合格候选的似然，确定最终三参数。',
  stages=['读入并检查样本','尝试位置 γ','求该位置下的 β、η','比较位置候选','给出估计与边界说明'],loop=True,
  program='保留现有“步骤—源码—公式”三栏。步骤按估计任务组织，并在主线中显出位置搜索与条件求解的循环。归一化、稳定求和及旁录留在对应步骤内部，不再变成需要用户选择的流程。',
  assessment='当前源码、公式已有对应；但左侧六步偏线性，循环关系主要藏在文字里。建议保留六步和三栏，在步骤概览补明“换一个位置，就重复条件形状和尺度求解”。',
  layout='先用“剖面对数似然＋位置得分”回答位置为什么取这里，两图共用位置γ的阅读位置；随后展开选中位置的形状方程，最后由尺度公式连到结果。桌面前两图并排，手机依次上下排。',
  figures={
   'profile-likelihood':('位置为什么选这里','保留。主图展示位置变化时的剖面似然，标出所有被接受的有限候选和最终点。','它是函数形态图，线上的点按γ排列，不是算法沿这条线迭代。'),
   'location-score':('这个峰是否满足判据','保留并与似然主图配对。默认看清最终点左右的正负变化，全范围作为补充。','当前右端的陡降仍会压扁零点附近；建议让默认视窗服务于判据解释。'),
   'conditional-shape-equation':('在选中位置，形状怎样确定','放在位置判据之后，标题直接写明固定的γ值。保留零点与β=1边界的区别。','曲线含同一方程的辅助采样，用来解释方程，不称为迭代轨迹。')},
  conclusion='建议沿用当前三类图，调整主次和联动，让“定位置—说明形状—恢复尺度”成为一条可读主线；无需为了形式统一改写估计规则。'),
 'wmle':dict(name='加权极大似然估计 WMLE',
  story='用权重修正的两个方程共同确定形状与位置；比较可接受的根，再按加权尺度公式恢复η。',
  stages=['读入样本与权重','尝试位置 γ','求形状方程 T₁=0','找位置方程 T₂=0','比较根并恢复尺度'],loop=True,
  program='保留步骤—源码—公式三栏；主线突出两个加权方程如何共同确定结果。权重表的查找与数值处理放在相应步骤内部。',
  assessment='当前已经记录条件方程、候选根和尺度恢复，但容易被通用“优化曲线”的外观带偏。说明应明确WMLE这里是在解加权方程，不是照搬MLE的似然峰选择。',
  layout='主图以位置方程T₂的过零说明γ；紧接着显示同一位置下T₁的过零说明β，接受候选用表紧邻两图。最后给出J₁加权尺度恢复。边界近似直接随结果说明。',
  figures={
   'weighted-location-equation':('位置方程怎样确定位置','作为主图，显示条件T₁=0后的T₂曲线、零线与所选位置。','主图要看清根；候选选择另列小表，不用一个孤立点撑一整幅图。'),
   'conditional-shape-equation':('形状方程怎样与位置配合','放在位置图旁或其后，固定同一γ，标明T₁=0对应的β。','两图要让读者知道它们属于同一组方程，而不是两个互不相干的结果。'),
   'candidate-residuals':('有多个根时采用哪个','用候选表，保留β、γ、两个残差及最终选择标记。','仅有一个根时仍是小表；根的接受与选择规则由我核对，不逐项让你决定数值阈值。')},
  conclusion='建议采用“两个方程＋候选表＋尺度恢复”的专属表达，保持与MLE清楚区分。'),
 'mdm':dict(name='最小差异法 MDM',
  story='固定位置γ时，让各观测反算出的伪尺度尽量一致；再按最小差异曲线的梯度与偏移δ确定位置，伪尺度均值给出η。',
  stages=['样本与绘图概率','固定 γ，寻找最小差异 β','改变 γ，考察最小差异梯度','按偏移 δ 定位','伪尺度均值给出 η'],loop=True,
  program='保留原有三栏，并以条件形状寻优、位置偏移判据、尺度恢复作为主线。梯度差分和搜索保护留在对应步骤内说明。',
  assessment='已有审定要求保留原MDM双图及联动；当前计算页仍调用通用过程图，尚不能算原双图已恢复。此次评审继续以原两幅图的用途和联动为基准。',
  layout='沿用你认可的“形状参数寻优＋位置参数判据”两幅图及联动。选择位置时，形状图对应这个位置；最终点连到β、γ及伪尺度均值η。零位置处理、普通交点、右端外推用结果状态解释。',
  figures={
   'shape-discrepancy':('这个位置下，形状为什么取这里','沿用原形状寻优图：横轴β、纵轴伪尺度标准差，标出条件最小点。','当前记录只显示最终位置的少量求值，不能据此声称位置联动已经恢复。'),
   'location-criterion':('位置与偏移有什么关系','沿用原位置判据图：横轴γ，显示实际梯度与δ的交点或边界处理。','右端外推不画成已验证交点；保留已确认的返回口径，同时让图忠实说明结果来源。')},
  conclusion='建议恢复原两图的表达与必要联动，保留已经确认的算法口径；不把MDM硬套进其他方法的通用图式。'),
 'lse':dict(name='最小二乘估计 LSE',
  story='尝试不同位置γ，对数寿命与White顺序统计量期望作回归；选择F比最大的候选，再由回归斜率和截距恢复形状与尺度。',
  stages=['读入排序样本','White 顺序统计量期望','逐位置回归并比较 F','选定位置下的回归','斜率、截距恢复参数'],loop=True,
  program='按“构造回归量—比较位置—恢复参数”组织三栏。积分和缓存属于顺序统计量期望的实现，主界面不将它们扩展成独立选择。',
  assessment='两幅现图已覆盖位置判据和最终回归，方向基本正确。主要应加强两图的同次计算关系，以及回归斜率与形状参数并不相同这一点。',
  layout='先看F(γ)选中位置，再看该位置的White回归。图中直接写清X是顺序统计量期望、Y是ln(t−γ)，斜率a=1/β，截距b=lnη；图后把a、b变成β、η。',
  figures={
   'f-location':('F比如何确定位置','保留位置主图，突出F峰与选中γ，不让近支撑端的密集点淹没峰。','曲线是各位置的函数求值，不能称作F随迭代收敛。'),
   'white-regression':('回归怎样给出形状与尺度','保留散点与回归线，直接标注斜率取倒数得到β、截距取指数得到η。','它与LRE的回归方向及横坐标不同，不能共用含糊的“线性拟合”说明。')},
  conclusion='建议保留两图，只加强“F定位置—White回归定形状和尺度”的衔接与符号解释。'),
 'lre':dict(name='线性回归估计 LRE',
  story='按Park绘图概率形成概率图，选择相关系数最大的γ；在这个位置的概率图上回归，斜率得到β、截距恢复η。',
  stages=['样本与 Park 绘图概率','逐位置计算相关系数','选定相关系数最大的 γ','最终位置的概率图回归','恢复形状与尺度'],loop=True,
  program='保留三栏；把绘图概率、相关系数定位和概率图回归串成一条主线，不将边界搜索和退化保护拆成多条平行方法。',
  assessment='现图的相关系数判据与概率图回归相互对应，基本结构可保留。需要让读者看出不是在已知位置上普通拟合，也不能把高相关当成模型已经通过统计检验。',
  layout='相关系数ρ(γ)为位置主图；选中点对应下方的概率图散点和直线。直线斜率β、截距与尺度η的关系直接附在图上。',
  figures={
   'correlation-location':('位置是怎样选出来的','保留ρ随γ的变化及选中峰；让峰附近差异可见。','ρ高表示这里线性相关更强，不等于三参数Weibull模型检验已通过。'),
   'park-probability-regression':('这条直线怎样给出参数','保留概率图散点和拟合线，明确X=ln(t−γ)、Y=ln[−ln(1−p)]。','这里斜率就是β；与LSE中a=1/β的规则要在表达上区分。')},
  conclusion='建议保留两图，突出“先定位，再回归”，并把概率图量与参数恢复写在一起。'),
 'mm':dict(name='矩估计 MM',
  story='由经验生存函数的面积形成三个Weibull矩；检查这些矩能否给出可采纳解，再用显式公式求参数，并说明位置处理前后的变化。',
  stages=['经验生存函数','面积形成三个 Weibull 矩','检查矩的可采纳性','显式公式求三参数','说明位置修正与最终结果'],loop=False,
  program='采用“样本—矩—可采纳性—显式求参”的三栏流程。MM没有形状寻优轨迹，不为统一外观而加入搜索动画。',
  assessment='现有生存函数图和矩差图已能说明输入量；但若没有把面积、矩和最终参数连起来，读者仍不知道图与估计有什么关系。位置修正前后也需要直接可见。',
  layout='以经验生存阶梯及其幂次面积为主图，接三个矩的数值和可采纳性关系，再用公式流向β、η、γ。最终结果旁列出位置处理前后值；不把它伪装成迭代优化。',
  figures={
   'weibull-moments':('样本怎样形成矩','保留阶梯函数，显示S、S²、S⁴及面积对应的三个矩。','台阶与面积是关键，不画平滑拟合线来替代经验生存函数。'),
   'moment-admissibility':('这些矩能否求参','以简短关系图或数值比较展示两组矩差均为正且有序。','两点散点图的信息较少；建议与矩数值及求参公式放在一起。')},
  conclusion='建议从“矩如何由样本得到”出发，形成面积到参数的可读链条；不要求MM长得像MLE。'),
 'mmle':dict(name='修正极大似然估计 MMLE',
  story='原样本最小值确定γ，删除其中一个最小观测；对保留距离迭代求β，再恢复η。',
  stages=['原样本最小值定 γ','删除一个最小观测','保留距离迭代求 β','满足停止判据','由保留样本恢复 η'],loop=True,
  program='程序流程显示最小值、单次删除、形状不动点迭代和尺度恢复。需要讲清这里的循环是形状迭代，不是位置搜索。',
  assessment='MMLE现有后端记录与程序流程可核对，但计算过程页面仍未开放。以下运行图是同一现行实现的记录重绘，用于审阅未来呈现，不代表已在网站上线。',
  layout='先以样本示意明确哪个观测给出γ、哪个观测被删除；随后展示β随实际迭代步的变化及停止判据，最后给出η。未计算的拟合优度不得呈现为有效R²。',
  figures={
   'shape-fixed-point':('形状迭代怎样接近最终值','使用真实迭代序号和β值，显示最终接受点。','这才是实际迭代图；不要把它与其他方法按参数排序的函数图混为一谈。'),
   'shape-step':('为什么在这一轮停止','紧邻形状图展示相邻β变化量与停止线。','达到数值停止条件不等于已证明一般情形都收敛；迭代失败要按失败呈现。')},
  conclusion='建议以“最小值及删除—形状迭代—尺度恢复”呈现。此次只评审展示方案，不改变MMLE开放状态。'),
}

def esc(text): return html.escape(str(text))
def text_block(ident, markup): return dict(id=ident,kind='text',html=markup)
def unit(ident,title,markup=None,blocks=None):
    return dict(id=ident,title=title,mode='content',options=[dict(id=ident+'-content',label=title,blocks=blocks or [text_block(ident+'-body',markup)])])
def image(ident,src,alt): return dict(id=ident,kind='image',src='assets/'+src,alt=alt)
def paragraph(label,text): return f'<p><strong>{label}</strong>{text}</p>'

def flow_svg(config, target):
    stages=config['stages']; height=125+len(stages)*88
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 {height}" role="img" aria-label="建议的呈现主线">',
      '<rect width="620" height="100%" fill="#f8faf9" rx="18"/><defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#527a67"/></marker></defs>',
      '<text x="310" y="43" text-anchor="middle" fill="#64748b" font-family="Microsoft YaHei,sans-serif" font-size="22">建议的阅读主线 · 尚未修改网站</text>']
    for i,label in enumerate(stages):
        y=70+i*88
        parts += [f'<rect x="70" y="{y}" width="480" height="62" rx="12" fill="{("#e0eee5" if i in (1,2) else "white")}" stroke="#c4d4ca"/>',
          f'<text x="310" y="{y+39}" text-anchor="middle" font-family="Microsoft YaHei,sans-serif" font-size="30" fill="#203d30">{esc(label)}</text>']
        if i<len(stages)-1: parts += [f'<path d="M310,{y+64}v19" fill="none" stroke="#527a67" stroke-width="2" marker-end="url(#arrow)"/>']
    if config['loop']:
        # A reading aid, not a replacement for an executable control-flow graph.
        msg='搜索与条件计算重复进行' if 'MMLE' not in config['name'] else '形状迭代重复进行'
        parts += [f'<text x="310" y="{height-22}" text-anchor="middle" fill="#64748b" font-family="Microsoft YaHei,sans-serif" font-size="22">{msg}</text>']
    parts.append('</svg>'); target.write_text(''.join(parts),encoding='utf-8')

def make_plot(chart, target, method):
    fig,ax=plt.subplots(figsize=(7.6,4.7),dpi=150)
    fig.patch.set_facecolor('#fbfdfb');ax.set_facecolor('#fbfdfb')
    colors=['#2563eb','#7c3aed','#059669','#475569']
    for i,series in enumerate(chart['series']):
        points=series['points']
        if not points: continue
        x=[p['x'] for p in points]; y=[p['y'] for p in points]
        if series['kind']=='line':
            ax.plot(x,y,color=colors[i%len(colors)],lw=2,
                    drawstyle='steps-post' if series.get('interpolation')=='stepAfter' else 'default',label=series['label'])
        else: ax.scatter(x,y,color=colors[i%len(colors)],s=20,label=series['label'],zorder=4)
    for r in chart.get('references',[]):
        (ax.axhline if r['axis']=='y' else ax.axvline)(r['value'],color='#94a3b8',ls='--',lw=1)
    selected=chart.get('selected',[])
    if selected:
        p=selected[0]
        ax.scatter([p['x']],[p['y']],s=70,c='#b7791f',edgecolors='white',zorder=6)
        # Focus on a readable vicinity using only values in the saved run.
        all_x=sorted(set(p['x'] for s in chart['series'] for p in s['points']))
        if chart['id'] in ['profile-likelihood','location-score','weighted-location-equation','f-location','correlation-location'] and len(all_x)>10:
            center=p['x']; span=max(all_x)-min(all_x)
            width=span*.04
            left,right=max(min(all_x),center-width),min(max(all_x),center+width)
            visible=[q['y'] for s in chart['series'] for q in s['points'] if left<=q['x']<=right]
            visible += [p['y']] + [r['value'] for r in chart.get('references',[]) if r['axis']=='y']
            if len(visible)>2:
                lo,hi=min(visible),max(visible); pad=(hi-lo)*.13 or 1e-6
                ax.set(xlim=(left,right),ylim=(lo-pad,hi+pad))
        ax.annotate(f"{p.get('label','选中点')}\n({p['x']:.6g}, {p['y']:.6g})",xy=(p['x'],p['y']),xytext=(12,18),textcoords='offset points',fontsize=13,color='#875c16')
    ax.set_xlabel(chart['x']['label'],fontsize=17)
    ax.set_ylabel(chart['y']['label'],fontsize=16)
    ax.tick_params(labelsize=13)
    ax.grid(axis='y',alpha=.18)
    ax.legend(loc='best',fontsize=11,frameon=False)
    if chart['id']=='shape-step': ax.set_yscale('log')
    fig.tight_layout(pad=1.3); fig.savefig(target); plt.close(fig)
    target.write_text('\n'.join(line.rstrip() for line in target.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')

def previous_review(board, assets):
    path=assets/'prior-algorithm-review.json'
    if path.exists(): return
    path.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>此前原文核对</title><style>body{max-width:900px;margin:32px auto;padding:20px;font:18px/1.9 system-ui;color:#213930}h2{font-size:23px}pre{overflow:auto;font-size:14px}img{max-width:100%}table{border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #ddd}math{overflow:auto}</style><h1>此前原文与实现核对</h1><p>保留供查阅；当前审阅以程序和计算过程的整体呈现为主。这里不接收提交，也不代表任何未定方案已被采纳。</p>']
    for u in board['units']:
        parts.append('<h2>'+esc(u['title'])+'</h2>')
        for option in u['options']:
            if u['mode']=='choices': parts.append('<h3>'+esc(option['label'])+'</h3>')
            for b in option['blocks']:
                if 'html' in b: parts.append(b['html'].replace('href="assets/','href="'))
                if b['kind']=='image': parts.append(f'<img src="{esc(b["src"].removeprefix("assets/"))}" alt="{esc(b.get("alt",""))}">')
    parts.append('</html>');(assets/'prior-algorithm-review.html').write_text(''.join(parts),encoding='utf-8')

def main(method):
    config=CONFIG[method]; root=ROOT/('method-'+method);assets=root/'assets'
    board_path=root/'board.json';old=json.loads(board_path.read_text(encoding='utf-8'))
    if any(u['id']=='presentation-summary' for u in old['units']): raise SystemExit('Already revised; edit the existing review instead of rebuilding')
    previous_review(old,assets)
    run=json.loads((assets/'process-run.json').read_text(encoding='utf-8'));trace=run['calculation']
    result=run['result'];flow=run['flow']; units=[]
    intro=paragraph('建议主线：',config['story'])+paragraph('本次把关内容：','程序怎样分阶段、计算怎样讲清楚、图怎样配合。以下为核查后的呈现建议；实现细节由我处理，不需要逐项选择。')
    if method=='mmle': intro+=paragraph('现状：','计算过程页未开放，以下仅为呈现建议与后端核对记录。')
    units.append(unit('identity','1 整体呈现',intro))
    flow_svg(config,assets/'proposed-reading-flow.svg')
    units.append(unit('presentation-summary','2 建议采用的阅读主线',blocks=[
        image('reading-flow','proposed-reading-flow.svg','建议的阅读主线，尚未应用到网站'),
        text_block('summary-assessment',paragraph('我的判断：',config['conclusion']))]))
    blocks=[text_block('program-assessment',paragraph('当前判断：',config['assessment'])+paragraph('建议呈现：',config['program']))]
    if (assets/'current-process.png').exists():
        if (assets/'current-process-search.png').exists():
            blocks.append(dict(id='program-current',kind='gallery',aspect_ratio=1.3,images=[dict(id='conditional',label='当前网站：条件形状求解',src='assets/current-process.png',alt='当前网站程序流程第二步'),dict(id='location',label='当前网站：位置搜索',src='assets/current-process-search.png',alt='当前网站程序流程第四步')]))
        else: blocks.append(image('program-current','current-process.png','当前网站程序流程截图'))
    blocks.append(text_block('program-order','<p>当前网站步骤：'+ ' → '.join(esc(s['name']) for s in flow['steps']) + '。</p>'))
    units.append(unit('program-presentation','3 程序流程怎样呈现',blocks=blocks))
    value_text='，'.join(f'{label}={result[key]:.7g}' for key,label in [('beta_hat','β̂'),('eta_hat','η̂'),('gamma_hat','γ̂')])
    intro=paragraph('建议顺序：',config['layout'])+f'<p>下图沿用一组固定输入：{esc(run["case"]["label"])}，n={len(run["case"]["observations"])}；结果 {value_text}。</p>'
    blocks=[text_block('calculation-layout',intro)]
    if (assets/'current-calculation.png').exists(): blocks.append(image('calculation-current','current-calculation.png','当前网站计算过程截图；点击可放大'))
    units.append(unit('calculation-presentation','4 计算过程与图的主次',blocks=blocks))
    charts={c['id']:c for c in trace['charts']}
    for i,(chart_id,(purpose,suggestion,caveat)) in enumerate(config['figures'].items(),1):
        chart=charts[chart_id]
        markup=paragraph('这幅图要回答：',purpose+'。')+paragraph('建议：',suggestion)+paragraph('核查意见：',caveat)
        blocks=[text_block('chart-'+chart_id+'-assessment',markup)]
        actual_index=list(charts).index(chart_id)+1
        if (assets/f'current-chart-{actual_index}.png').exists():
            blocks.append(image('current-'+chart_id,f'current-chart-{actual_index}.png','当前网站：'+chart['title']))
        if chart_id=='candidate-residuals':
            rows=[]
            for series in chart['series']:
                for p in series['points']:
                    rows.append('<tr>'+''.join(f'<td>{p.get(k,0):.6g}</td>' for k in ['beta','gamma','t1','t2'])+'</tr>')
            blocks.append(dict(id='candidate-values',kind='visual',html='<table><thead><tr><th>β</th><th>γ</th><th>T₁</th><th>T₂</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'))
        else:
            filename='record-'+chart_id+'.svg';make_plot(chart,assets/filename,method)
            blocks.append(image('record-'+chart_id,filename,'同一次运行记录重绘：'+chart['title']))
            blocks.append(text_block('record-'+chart_id+'-caption','<p style="color:#64748b;font-size:14px">记录重绘，供核对图意与建议阅读范围；不是网站改后截图。点值来自同一现行方法运行，未另造估计器。</p>'))
        units.append(unit('figure-'+chart_id,f'4.{i} {purpose}',blocks=blocks))
    recover=''.join('<p><strong>'+esc(s['title'])+'</strong>：'+', '.join(esc(v['label'])+'='+f'{v["value"]:.7g}' for v in s['values'])+'</p>' for s in trace.get('recovery',[]))
    units.append(unit('result-link','5 图怎样连到最终结果',recover+paragraph('呈现要求：','图中选中点、公式中的量、最终三参数要来自同一次计算。更改输入后明确更新状态；无可采纳结果时，图与结果一起说明原因。')+paragraph('我的处理范围：','源码对应、数值记录、坐标、单位及边界标记由我核对；只有会改变估计规则或成功口径的改动，另行讨论。')))
    if method=='mdm':
        units.append(unit('prior-decisions','6 已确认的口径', '<p>保留Bernard默认近似秩、连续数值求解、现有右端返回及成功口径。恢复原双图及必要联动；外推如实标明。此前选择及记录继续保留，不重新要求决定。</p>'))
    units.append(unit('sources','核查依据', '<p><a href="assets/process-evidence.html" target="_blank" rel="noopener">逐步源码、公式与本次计算记录</a> · <a href="assets/prior-algorithm-review.html" target="_blank" rel="noopener">此前原文与实现核对</a></p><p>本轮仅更新审阅载体；网站算法、页面与开放状态均未修改。你的意见将落实到本方法网站的程序流程、计算过程和过程图呈现。</p>'))
    board=copy.deepcopy(old);board.update(title=config['name']+' · 流程与图的呈现评审',revision=old['revision']+1,units=units)
    board['archive_plan']=f'按最终确认的宏观呈现意见，更新本方法网站的程序流程说明、计算过程编排和过程图组件；底层一致性与浏览器验收由Agent完成。保留同一方法实现，不改变算法规则或方法开放状态；如需改变估计结果或成功口径，先另行讨论。将审定及落实结果写入 D:/weibull/docs/method-reviews/{method}.md，保留现有有效决定及原始意见，Git本地保存；不部署、不自动推送。'
    board.pop('review_complete',None);board.pop('completed_at',None);board.pop('archive_pending',None)
    html_blocks=[b for u in units for o in u['options'] for b in o['blocks'] if 'html' in b]
    for block,compiled in zip(html_blocks,render_html_batch([b['html'] for b in html_blocks])): block['html']=compiled
    board_path.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    evidence=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>流程核查依据</title><style>body{max-width:1000px;margin:32px auto;padding:20px;font:17px/1.8 system-ui;color:#213930}pre{overflow:auto;background:#f1f5f2;padding:16px;font-size:14px}math{display:block;overflow:auto}h2{font-size:24px}table{border-collapse:collapse}td,th{padding:8px}</style><h1>'+esc(config['name'])+' · 核查依据</h1><p>读取时间 '+esc(run['checked_at'])+'。以下从网站当前流程API及现行方法运行记录取得；本页仅供查证。</p><p><a href="process-run.json">完整输入、结果、绘图点及源码身份</a> · <a href="prior-algorithm-review.html">此前原文核对</a></p>']
    files={s['path']:s for s in flow['sources']}
    for s in flow['steps']:
        evidence+=['<h2>'+esc(s['name'])+'</h2><p>'+esc(s['description'])+'</p><p>\\['+s['formula']['expression']+'\\]</p>']
        for ref in s['sources']:
            lines=files[ref['file']]['lines']
            code='\n'.join(f'{n+1:>4} {lines[n]}'.rstrip() for n in range(ref['start'],ref['end']))
            evidence += ['<p>'+esc(ref['file'])+f' L{ref["start"]+1}–{ref["end"]}</p><pre><code>'+esc(code)+'</code></pre>']
    evidence+=['</html>'];compiled=render_html_batch([''.join(evidence)])[0]
    (assets/'process-evidence.html').write_text(compiled,encoding='utf-8')
    subprocess.run([sys.executable,str(SKILL/'scripts/review.py'),'render','--root',str(root)],check=True,capture_output=True)
    print(json.dumps(dict(method=method,revision=board['revision'],sections=len(units)),ensure_ascii=False))

if __name__=='__main__':
    for method in sys.argv[1:] or ['mle']: main(method)
