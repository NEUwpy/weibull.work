"""横向机制地图：五条路线、方法联系与跨机制估计过程。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET
from 数学排版 import normalize_markup

ROOT = Path(__file__).resolve().parent
SOURCE = '../04-方法分类与沿袭关系工作稿.md'
doc = ET.Element('mxfile', host='app.diagrams.net', version='26.0.9')
diagram = ET.SubElement(doc, 'diagram', id='complete-method-map-v20', name='估计路线与方法关系')
WIDTH, HEIGHT = 4800, 2100
model = ET.SubElement(diagram, 'mxGraphModel', math='1', page='1', pageWidth=str(WIDTH), pageHeight=str(HEIGHT), background='#ffffff')
root = ET.SubElement(model, 'root')
ET.SubElement(root, 'mxCell', id='0')
ET.SubElement(root, 'mxCell', id='1', parent='0')
boxes = {}
relations = []
paths = []
colors = dict(like='#AB4D3D', dist='#286D99', stat='#26745A', post='#785499', learn='#A5621F')

# 按原文段落定位，生成时重算当前行号；正文增删不会让旧行号静默指错。
EVIDENCE_TERMS = {
    'e-mle-cw':['- **Cohen–Whitten MMLE：'],
    'e-jac-wmle':['| Jacquelin（1993）→'],
    'e-wmle-correct':['| Cousineau WMLE →'],
    'e-smith-kr':['**Smith→Kundu–Raqab：'],
    'e-kr-dmmle':['| Kundu–Raqab构造 ＋ Firth'],
    'e-firth-dmmle':['| Kundu–Raqab构造 ＋ Firth','Firth（1993）讨论'],
    'e-mle-cmle':['- **Cheng–Iles CMLE：'],
    'e-white-soman':['- **White（1969）→'],
    'e-lipson-park':['- **Lipson–Sheth（1973）→'],
    'e-soman-park':['即使使用同一分数并得到同一位置','这是**固定坐标下两种OLS'],
    'e-mps-qmp':['其中有比“共同构造”更具体的作者说明：'],
    'e-gm-svr':['**GM−噪声SVR有两个明确借用环节。'],
    'e-cran-pwm':['**Cran的Weibull moments不是常规幂矩','这里M为Greenwood'],
    'e-pwm-lmom':['**PWM↔L矩是线性转换'],
    'e-lmom-tlmom':['**PWM↔L矩是线性转换'],
    'e-lspf-lpf':['- **2013 LSPF→2015 LPF：'],
    'e-lspf-mvlue':['**LSPF的位置修正关系→Sugiyama'],
    'e-mvleh-extended':['**MVLE-H（2020）→2022扩展'],
    'e-lspf-yang':['- **Nagatsuka等LSPF（2013）的位置修正关系→'],
    'e-wmle-mvleh':['**MVLE-H（2020）→2022扩展'],
    'e-lspf-likelihood':['- **2013 LSPF：W变换后使用联合密度。'],
    'e-lpf-likelihood':['- **2013 LSPF→2015 LPF：'],
    'e-park-mle2':['| Park（2017；2018补存在性论证）'],
    'e-mle2-park':['| Park（2017；2018补存在性论证）'],
    'e-mvlue-early':['**2019位置MVLUE→2025初始失效期迭代'],
    'e-mle-mixed':['**Cousineau比较文自身也提出组合'],
    'e-wmle-mixed':['**Cousineau比较文自身也提出组合'],
    'e-mps-mixed':['**Cousineau比较文自身也提出组合'],
    'e-green-teimouri':['**Green（1994）→Teimouri'],
    'e-mle-bayes':['**Green（1994）→Teimouri'],
}
source_lines=(ROOT/SOURCE).read_text(encoding='utf-8').splitlines()

def provenance(key):
    matched=[]
    sections=[]
    for needle in EVIDENCE_TERMS[key]:
        hits=[i for i,line in enumerate(source_lines,1) if line.startswith(needle)]
        if len(hits)!=1:raise ValueError(f'{key}: evidence locator {needle!r} has {len(hits)} hits')
        line=hits[0];matched.append(str(line))
        section=next((v.lstrip('# ').strip() for v in reversed(source_lines[:line]) if v.startswith('##')), '')
        if section not in sections:sections.append(section)
    return ','.join(matched),'；'.join(sections)

def node(key, text, x, y, w, h, color='#334155', fill='#ffffff', size=31, bold=False, role='method', current=False):
    style = f'html=1;whiteSpace=wrap;rounded=1;arcSize=10;strokeColor={color};fillColor={fill};fontColor=#243449;fontFamily=Times New Roman;fontSize={size};spacing=12;align=center;verticalAlign=middle;strokeWidth=2;'
    if role == 'label': style += 'strokeColor=none;fillColor=none;'
    if bold: style += 'fontStyle=1;'
    if current: style += 'strokeColor=#AF8120;fillColor=#FFF6D5;strokeWidth=3;'
    cell = ET.SubElement(root, 'mxCell', id=key, value=normalize_markup(text), vertex='1', parent='1', style=style, renderRole=role)
    ET.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width=str(w), height=str(h), **{'as': 'geometry'})
    boxes[key] = (x, y, w, h)
    return cell

def port(key, side, along=.5):
    x,y,w,h=boxes[key]
    return {'left':(x,y+h*along),'right':(x+w,y+h*along),'top':(x+w*along,y),'bottom':(x+w*along,y+h)}[side]

def edge(key, src, dst, label, kind='inherit', color='#475569', start='right', end='left', via=(), at=None, evidence='', exit_at=.5, entry_at=.5):
    pos=lambda side,along:{'left':(0,along),'right':(1,along),'top':(along,0),'bottom':(along,1)}[side]
    sx,sy=pos(start,exit_at);tx,ty=pos(end,entry_at)
    style=f'html=1;rounded=0;strokeWidth=3;strokeColor={color};fontColor={color};fontFamily=Times New Roman;fontSize=28;labelBackgroundColor=#ffffff;exitX={sx};exitY={sy};entryX={tx};entryY={ty};exitPerimeter=0;entryPerimeter=0;'
    style += 'endArrow=none;' if kind=='math' else 'endArrow=open;' if kind in ('process','mechanism') else 'endArrow=block;endFill=1;'
    if kind=='math':style+='dashed=1;dashPattern=7 5;'
    if kind=='borrow':style+='dashed=1;dashPattern=10 4 2 4;strokeWidth=3.5;'
    if kind in ('process','mechanism'):style+='strokeWidth=2;'
    attrs=dict(id=key,value=normalize_markup(label),edge='1',parent='1',source=src,target=dst,style=style,relationKind=kind)
    if evidence:
        lines,section=provenance(key)
        attrs['evidence']=f'{SOURCE}:{lines}'
        attrs['evidenceSection']=section
        evidence=f'{section}；当前行{lines}'
    cell=ET.SubElement(root,'mxCell',**attrs)
    geo=ET.SubElement(cell,'mxGeometry',relative='1',**{'as':'geometry'})
    path=[port(src,start,exit_at),*via,port(dst,end,entry_at)]
    paths.append((key,src,dst,path))
    if via:
        points=ET.SubElement(geo,'Array',**{'as':'points'})
        for x,y in via:ET.SubElement(points,'mxPoint',x=str(x),y=str(y))
    if at:
        lx,ly=at;cell.set('labelX',str(lx));cell.set('labelY',str(ly))
        lengths=[math.dist(a,b) for a,b in zip(path,path[1:])];total=sum(lengths);walk=0;best=None
        for a,b,length in zip(path,path[1:],lengths):
            if not length:continue
            t=max(0,min(1,((lx-a[0])*(b[0]-a[0])+(ly-a[1])*(b[1]-a[1]))/length**2))
            px,py=a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])
            candidate=(math.dist((lx,ly),(px,py)),walk+t*length,px,py)
            if best is None or candidate[0]<best[0]:best=candidate
            walk+=length
        if best and total:
            geo.set('x',str(2*best[1]/total-1));geo.set('y','0')
            ET.SubElement(geo,'mxPoint',x=str(lx-best[2]),y=str(ly-best[3]),**{'as':'offset'})
    if evidence:relations.append((key,src,dst,kind,label,evidence))

USAGE = {
    'mle':'L1 原观测；L2 最大化', 'cw':'L2 方程＋S2 辅助关系',
    'jacquelin':'L2 方程代数构造', 'wmle':'L2 三权重方程',
    'smith':'L1 修改输入；L2 最大化', 'wmle-correct':'L2 后接形状修正',
    'kr':'L1 删最小值；L2 最大化', 'firth':'L2 得分修改',
    'cmle':'L1 单项概率替代', 'dmmle':'L1 数据修改＋L2 得分修正',
    'white':'D1 概率图；D2 回归', 'soman':'D1 分数；D2 定位与回归',
    'lipson':'D1 概率图；D2 定位', 'park':'D2 相关定位＋回归',
    'mps':'D1 概率间距；D2 乘积', 'qmp':'D1 分组；D2 分组概率',
    'mdm':'D1 反推尺度；D2 一致性', 'yang':'D2 回归＋S2 期望修正',
    'gm':'D1 变换；D2 灰色关系', 'gm-svr':'D2 当前样本的回归',
    'cran':'S1 生存积分；S2/S3 恢复', 'pwm':'S1 加权矩；S2/S3 匹配',
    'w-mean':'S1 不变量；S2 均值关系', 'lmom':'S1 线性矩；S2/S3 匹配',
    'quantile':'S1 分位统计；S2/S3 反演', 'tlmom':'S1 内部次序量；S2/S3 匹配',
    'mvlue':'S1 次序量；S2 条件协方差', 'mvleh':'S1 线性量；S2/S3 组合',
    'mvleh-extended':'S2 选权＋临时形状策略',
}

def method(key,text,x,y,w=480,h=125,route='like',current=False,size=31):
    cell=node(key,text,x,y,w,h,color=colors[route],size=size,current=current)
    if key in USAGE:cell.set('mechanismUse',USAGE[key])
    return cell

def mechanism(key,text,x,y,w,color,h=145):
    cell=node(key,text,x,y,w,h,color=colors[color],size=31,bold=True,role='principle')
    cell.set('mechanismId',key)
    return cell

def open_route(key,title,y,width=700,x=40,fill='#ffffff'):
    node('band-'+key,'',x,y,width,60,color='none',fill=fill,role='background')
    node('heading-'+key,title,x+15,y+3,width-30,54,color=colors[key],size=37,bold=True,role='label')

node('title','三参数 Weibull 参数估计方法路线图',50,16,4700,70,size=49,bold=True,role='label')
node('legend','实心箭头：沿袭／修正　　虚线：数学联系　　点划线：局部借用／组合　　空心箭头：估计过程　　金色：七种比较实现',50,94,4700,44,size=29,role='label')

# 三条经典路线从左侧核心机制展开，方法分支以横向短链延续。
open_route('like','① 似然构造与优化',150,fill='#FFF1EC')
mechanism('L1',r'L1 概率模型<br>\(L(\theta\mid D)\)',60,280,280,'like',150)
mechanism('L2',r'L2 最大化／修正<br>\(\hat{\theta}\)',420,280,280,'like',150)
edge('flow-L1-L2','L1','L2','',kind='mechanism',color=colors['like'])

method('mle','MLE<br>原始观测联合似然',850,230,570,current=True)
method('cw','Cohen–Whitten MMLE<br>位置／矩关系替换',1620,230,570)
method('cmle','CMLE<br>最小值处采用区间概率',2390,230,570)
method('firth','Firth 得分修正<br>加入偏差修正项',3160,230,570)
method('dmmle','DMMLE（2025）<br>数据修改＋得分修正',3930,230,570)
method('jacquelin','Jacquelin（1993）<br>二参数代数构造',850,435,570)
method('wmle','Cousineau WMLE<br>三权重估计方程',1620,435,570,current=True)
method('wmle-correct','杨小玉等（2024）<br>WMLE 形状偏差修正',2390,435,570)
method('smith','Smith（1985）<br>最小值替代构造',3160,435,570)
method('kr','K–R MMLE（2009）<br>最小值定位＋删点',3930,435,570,current=True)
edge('e-mle-cw','mle','cw','替换部分<br>得分方程','borrow',colors['like'],evidence=True)
edge('e-mle-cmle','mle','cmle','最小值密度 → 区间概率','borrow',colors['like'],'top','top',via=[(1135,210),(2675,210)],at=(2210,210),evidence=True)
edge('e-jac-wmle','jacquelin','wmle','三参数<br>三权重','inherit',colors['like'],evidence=True)
edge('e-wmle-correct','wmle','wmle-correct','随样本量<br>修正形状','inherit',colors['like'],evidence=True)
edge('e-smith-kr','smith','kr','共同最小值<br>场景适配','inherit',colors['like'],evidence=True)
edge('e-kr-dmmle','kr','dmmle','保留数据<br>修改似然','borrow',colors['like'],'top','bottom',at=(4585,395),evidence=True)
edge('e-firth-dmmle','firth','dmmle','偏差<br>修正项','borrow',colors['like'],evidence=True)
edge('use-L2-mle','L2','mle','',kind='mechanism',color=colors['like'],via=[(805,355),(805,292.5)])

open_route('dist','② 分布关系匹配',600,fill='#EBF5FC')
mechanism('D1','D1 分布表示<br>概率图／F',60,730,180,'dist')
mechanism('D2','D2 匹配准则<br>残差／概率',290,730,180,'dist')
mechanism('D3','D3 参数确定<br>拟合／恢复',520,730,180,'dist')
edge('flow-D1-D2','D1','D2','',kind='mechanism',color=colors['dist'])
edge('flow-D2-D3','D2','D3','',kind='mechanism',color=colors['dist'])
method('white','White（1969）<br>概率图分数与回归',850,670,route='dist')
method('soman','Soman LSE（1992）<br>White 回归＋位置评分',1510,670,route='dist',current=True)
method('lipson','Lipson–Sheth<br>概率图相关性定位',2170,670,route='dist')
method('park','Park LRE（2017）<br>相关定位＋回归',2830,670,route='dist',current=True)
method('park-mle2','Park Proposed+MLE2<br>相关定位 γ → MLE',3490,670,route='dist')
method('mle2','二参数 MLE<br>平移后恢复 β、η',4150,670)
method('mdm','MDM<br>反推尺度的一致性',850,875,route='dist',current=True)
method('mps','MPS<br>相邻 CDF 概率间距',1510,875,route='dist')
method('qmp','QMP<br>分位数组概率与计数',2170,875,route='dist')
method('gm','灰色位置估计<br>GM 确定 γ̂',2830,875,route='dist')
method('gm-svr','GM–SVR（2021）<br>当前样本 ε-SVR 拟合',3490,875,route='dist')
method('yang','Yang 迭代（2023）<br>回归 ↔ 最小值修正',4150,875,route='dist')
edge('e-white-soman','white','soman','接入未知<br>位置参数','inherit',colors['dist'],evidence=True)
edge('e-lipson-park','lipson','park','相关系数<br>最大化','inherit',colors['dist'],evidence=True)
edge('e-soman-park','soman','park',r'同分数、同 \(\gamma\)：\(\hat{\beta}_{\mathrm{Park}}=r^2\hat{\beta}_{\mathrm{White}}\)','math',colors['dist'],'bottom','bottom',via=[(1750,835),(3070,835)],at=(2440,835),evidence=True)
edge('e-park-mle2','park','park-mle2','相关定位<br>提供 γ̂','borrow','#C96A20',evidence=True)
edge('e-mle2-park','mle2','park-mle2','恢复<br>β、η','borrow','#C96A20','left','right',evidence=True)
edge('e-mps-qmp','mps','qmp','次序量作<br>分位数；计数 1<br>MPS 特例','math',colors['dist'],evidence=True)
edge('e-gm-svr','gm','gm-svr','GM 定 γ<br>SVR 求 β、η','borrow',colors['dist'],evidence=True)
edge('use-D3-white','D3','white','',kind='mechanism',color=colors['dist'],via=[(805,802.5),(805,732.5)])

open_route('stat','③ 统计特征关系匹配与反演',1060,fill='#EAF6EE')
mechanism('S1','S1 统计特征<br>矩／次序量',60,1190,180,'stat')
mechanism('S2','S2 理论关系<br>特征 ↔ 参数',290,1190,180,'stat')
mechanism('S3','S3 参数识别<br>匹配／反演',520,1190,180,'stat')
edge('flow-S1-S2','S1','S2','',kind='mechanism',color=colors['stat'])
edge('flow-S2-S3','S2','S3','',kind='mechanism',color=colors['stat'])
method('cran','MM：Cran（1988）<br>Weibull moments 显式恢复',850,1120,route='stat',current=True)
method('pwm','PWM<br>概率加权矩',1510,1120,route='stat')
method('lmom','L 矩（1990）<br>次序量的线性组合',2170,1120,route='stat')
method('tlmom','TL 矩（2003）<br>内部次序量',2830,1120,route='stat')
method('mvleh','MVLE-H（2020）<br>倒数形状的线性组合',3490,1120,route='stat')
method('mvleh-extended','MVLE-H 扩展（2022）<br>n 与临时 β 确定超参数',4150,1120,route='stat')
method('w-mean','W 均值匹配（2003）<br>标准化后匹配期望',850,1335,route='stat')
method('quantile','分位数／枢轴反演<br>统计关系 → 参数',1510,1335,route='stat')
method('mvlue','位置 MVLUE（2019）<br>给定 β、η：协方差选权',2170,1335,route='stat')
method('early-iter','初始失效期迭代（2025）<br>MVLUE ↔ 二参数恢复',2830,1335,route='stat')
method('mixed','Cousineau Mixed 各版本<br>形状估计 → 均值、最小值期望 → η̂、γ̂',3490,1335,1140,route='stat')
edge('e-cran-pwm','cran','pwm','生存积分<br>对应 PWM','math',colors['stat'],evidence=True)
edge('e-pwm-lmom','pwm','lmom','同阶数<br>同估计规则','math',colors['stat'],evidence=True)
edge('e-lmom-tlmom','lmom','tlmom','内部次序量<br>替代端部','inherit',colors['stat'],evidence=True)
edge('e-mvleh-extended','mvleh','mvleh-extended','扩展<br>超参数','inherit',colors['stat'],evidence=True)
edge('e-mvlue-early','mvlue','early-iter','位置代入<br>交替更新','borrow','#C96A20',evidence=True)
edge('e-wmle-mvleh','wmle','mvleh-extended','WMLE 临时形状策略','borrow','#C96A20','top','right',via=[(1905,410),(4720,410),(4720,1182.5)],at=(4400,410),evidence=True)
edge('e-mle-mixed','mle','mixed','MLE 形状','borrow','#B47744','bottom','top',via=[(1135,390),(770,390),(770,1300),(3718,1300)],at=(770,1030),entry_at=.2,evidence=True)
edge('e-mps-mixed','mps','mixed','MPS 形状','borrow','#B47744','bottom','top',via=[(1750,1030),(2070,1030),(2070,1270),(4060,1270)],at=(1900,1030),entry_at=.5,evidence=True)
edge('e-wmle-mixed','wmle','mixed','WMLE 形状','borrow','#B47744','bottom','top',via=[(1905,600),(4760,600),(4760,1290),(4402,1290)],at=(4470,600),entry_at=.8,evidence=True)
edge('use-S3-cran','S3','cran','',kind='mechanism',color=colors['stat'],via=[(805,1262.5),(805,1182.5)])

# 两条横向短流程保留各自的似然与参数恢复步骤。
method('lspf','LSPF（2013）<br>不变统计量似然',60,1520,430,95,route='stat')
node('lspf-eliminate',r'消去位置、尺度<br>\(W_i=\frac{x_{(i)}-x_{(1)}}{x_{(n)}-x_{(1)}}\)',670,1505,1000,125,color=colors['stat'],role='process')
node('lspf-like',r'L1＋L2｜最大化 W 的联合密度<br>\(\hat{\beta}=\arg\max_\beta L_W(\beta)\)',1900,1505,1000,125,color=colors['like'],role='process')
node('lspf-restore','S2＋S3｜最小值期望修正 γ̂<br>按原文方程回代 η̂',3130,1505,1170,125,color=colors['stat'],role='process')
method('lpf','LPF（2015）<br>去位置统计量似然',60,1680,430,95,route='like')
node('lpf-eliminate',r'消去位置，保留尺度<br>\(V_i=x_{(i)}-x_{(1)}\)',670,1665,1000,125,color=colors['stat'],role='process')
node('lpf-like','L1＋L2｜最大化 V 的联合密度<br>联合确定 β̂、η̂',1900,1665,1000,125,color=colors['like'],role='process')
node('lpf-restore','L2｜形状代入似然方程 (9)、(10)<br>恢复 η̂、γ̂',3130,1665,1170,125,color=colors['like'],role='process')
for prefix in ('lspf','lpf'):
    edge('flow-'+prefix+'-input',prefix,prefix+'-eliminate','',kind='process',color='#64748B')
    edge('flow-'+prefix+'-restore',prefix+'-like',prefix+'-restore','',kind='process',color='#64748B')
edge('e-lspf-likelihood','lspf-eliminate','lspf-like','统计量似然','process',colors['like'],evidence=True)
edge('e-lpf-likelihood','lpf-eliminate','lpf-like','统计量似然','process',colors['like'],evidence=True)
edge('e-lspf-lpf','lspf','lpf','尺度保留；2 → 1','inherit',colors['stat'],'bottom','top',at=(275,1647),evidence=True)
edge('e-lspf-mvlue','lspf-restore','mvlue','最小值修正 → 多次序量组合','borrow',colors['stat'],'top','bottom',via=[(3715,1478),(2410,1478)],at=(3090,1478),evidence=True)
edge('e-lspf-yang','lspf-restore','yang','最小值期望位置修正','borrow','#C96A20','right','right',via=[(4670,1567.5),(4670,937.5)],at=(4490,1567.5),evidence=True)

open_route('post','④ 贝叶斯后验推断',1820,2180,40,'#F1EAF7')
mechanism('B1',r'B1 后验构造<br>\(p(\theta\mid D)\propto L(\theta\mid D)\pi(\theta)\)',60,1885,900,'post',110)
mechanism('B2','B2 后验决策<br>均值／中位数／MAP → 参数估计',1290,1885,930,'post',110)
edge('flow-B1-B2','B1','B2','',kind='mechanism',color=colors['post'])
method('green','Green Bayes（1994）<br>先验与后验；Gibbs 计算',60,2000,900,95,route='post',size=29)
method('teimouri','Teimouri 后验方案<br>位置更新采用 MH',1290,2000,930,95,route='post',size=29)
edge('e-green-teimouri','green','teimouri','模型承接<br>位置抽样修改','inherit',colors['post'],evidence=True)
edge('use-B1-green','B1','green','',kind='mechanism',color=colors['post'],start='bottom',end='top')
edge('e-mle-bayes','mle','B1','样本似然＋先验','math',colors['post'],'bottom','left',via=[(1135,375),(745,375),(745,575),(20,575),(20,1940)],at=(190,1030),evidence=True)

open_route('learn','⑤ 学习型参数映射',1820,2260,2480,'#FBF0E2')
mechanism('N1',r'N1 带标签的多组样本训练<br>\(\{(T(D_j),\theta_j)\}\longrightarrow h_\varphi\)',2500,1885,970,'learn',110)
mechanism('N2',r'N2 新样本应用<br>\(\hat{\theta}=h_\varphi(T(D))\)',3750,1885,970,'learn',110)
edge('flow-N1-N2','N1','N2','固定映射',kind='mechanism',color=colors['learn'],at=(3610,1940))
method('ann','ANN／BPNN<br>训练映射 → 新样本三参数',2500,2000,970,95,route='learn',size=29)
node('solver','PSO／SA／DE<br>搜索当前样本的既定目标',3750,2000,970,95,size=29,role='process')
edge('use-N1-ann','N1','ann','',kind='mechanism',color=colors['learn'],start='bottom',end='top')

# 生成时校验画幅、节点边界与既有证据集合；SVG 预览由统一入口另行生成。
assert WIDTH*7 == HEIGHT*16
assert len(relations)==30, len(relations)
assert {r[0] for r in relations}==set(EVIDENCE_TERMS)
assert sum(r[3]=='process' for r in relations)==2
for key,(x,y,w,h) in boxes.items():
    assert 0 <= x and 0 <= y and x+w <= WIDTH and y+h <= HEIGHT, (key,boxes[key])
for key,src,dst,path in paths:
    for x,y in path:
        assert 0 <= x <= WIDTH and 0 <= y <= HEIGHT, (key,x,y)
    for endpoint,box in ((path[0],boxes[src]),(path[-1],boxes[dst])):
        px,py=endpoint;x,y,w,h=box
        assert x <= px <= x+w and y <= py <= y+h, (key,endpoint,box)
        assert px in (x,x+w) or py in (y,y+h), (key,endpoint,box)
    assert all(a[0]==b[0] or a[1]==b[1] for a,b in zip(path,path[1:])), (key,path)
ET.indent(doc, space='  ')
target=ROOT/'06-完整机理地图-估计路线与方法关系.drawio'
with target.open('w',encoding='utf-8',newline='\n') as output:
    ET.ElementTree(doc).write(output,encoding='unicode',xml_declaration=True)
print(f'generated {WIDTH}x{HEIGHT} horizontal route map: {len(boxes)} nodes, 28 method relations + 2 internal mechanism connections; all 30 evidence IDs retained')
