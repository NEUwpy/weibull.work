"""机制组成路线，方法按所用环节接入；沿袭证据与方法内部过程分开。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET
from 数学排版 import normalize_markup

ROOT = Path(__file__).resolve().parent
SOURCE = '../04-方法分类与沿袭关系工作稿.md'
doc = ET.Element('mxfile', host='app.diagrams.net', version='26.0.9')
diagram = ET.SubElement(doc, 'diagram', id='complete-method-map-v20', name='估计路线与方法关系')
model = ET.SubElement(diagram, 'mxGraphModel', math='1', page='1', pageWidth='3000', pageHeight='3130', background='#ffffff')
root = ET.SubElement(model, 'root')
ET.SubElement(root, 'mxCell', id='0')
ET.SubElement(root, 'mxCell', id='1', parent='0')
boxes = {}
relations = []
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

def node(key, text, x, y, w, h, color='#334155', fill='#ffffff', size=23, bold=False, role='method', current=False):
    style = f'html=1;whiteSpace=wrap;rounded=1;arcSize=10;strokeColor={color};fillColor={fill};fontColor=#243449;fontFamily=Times New Roman;fontSize={size};spacing=12;align=center;verticalAlign=middle;strokeWidth=2;'
    if role == 'label': style += 'strokeColor=none;fillColor=none;'
    if bold: style += 'fontStyle=1;'
    if current: style += 'strokeColor=#AF8120;fillColor=#FFF6D5;strokeWidth=3;'
    cell = ET.SubElement(root, 'mxCell', id=key, value=normalize_markup(text), vertex='1', parent='1', style=style, renderRole=role)
    ET.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width=str(w), height=str(h), **{'as': 'geometry'})
    boxes[key] = (x, y, w, h)
    return cell

def port(key, side):
    x,y,w,h=boxes[key]
    return {'left':(x,y+h/2),'right':(x+w,y+h/2),'top':(x+w/2,y),'bottom':(x+w/2,y+h)}[side]

def edge(key, src, dst, label, kind='inherit', color='#475569', start='right', end='left', via=(), at=None, evidence=''):
    pos={'left':(0,.5),'right':(1,.5),'top':(.5,0),'bottom':(.5,1)}
    sx,sy=pos[start];tx,ty=pos[end]
    style=f'html=1;rounded=0;strokeWidth=3;strokeColor={color};fontColor={color};fontFamily=Times New Roman;fontSize=20;labelBackgroundColor=#ffffff;exitX={sx};exitY={sy};entryX={tx};entryY={ty};exitPerimeter=0;entryPerimeter=0;'
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
    path=[port(src,start),*via,port(dst,end)]
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

def method(key,text,x,y,w=270,h=125,route='like',current=False):
    usage=USAGE.get(key)
    if usage:text += f'<br>〔{usage}〕'
    cell=node(key,text,x,y,w,h,color=colors[route],size=23,current=current)
    if usage:cell.set('mechanismUse',usage)
    return cell

def mechanism(key,text,x,y,w,color):
    cell=node(key,text,x,y,w,110,color=colors[color],fill='#ffffff',size=24,bold=True,role='principle')
    cell.set('mechanismId',key)
    return cell

def open_route(key,title,x,w,fill):
    # 只有标题底带，没有将方法围起来的分类边界。
    node('band-'+key,'',x,220,w,76,color='none',fill=fill,role='background')
    node('heading-'+key,title,x+15,229,w-30,58,color=colors[key],size=30,bold=True,role='label')

node('title','三参数 Weibull 参数估计方法路线图｜核心机制、构造改动与方法联系',45,20,2910,64,size=39,bold=True,role='label')
node('subtitle','同一寿命样本 \\(D=\\{x_1,\\ldots,x_n\\}\\)，经不同的统计对象与参数确定原则，得到 \\(\\hat{\\theta}=(\\hat{\\beta},\\hat{\\eta},\\hat{\\gamma})\\)。',45,91,2910,48,size=27,role='label')
node('legend','实心箭头：沿袭／修正　　虚线：有条件的数学联系　　点划线实心箭头：局部借用／组合　　金色：七种比较实现',45,147,2910,36,size=23,role='label')
node('process-legend','细线空心箭头：估计过程／机制接入，不表示历史沿袭；节点中的 L／D／S 等标识说明所用环节。同一方法可以连接多条路线。',45,186,2910,34,size=22,role='label')

open_route('like','① 似然构造与优化',40,940,'#FFF1EC')
open_route('dist','② 分布关系匹配',1020,940,'#EBF5FC')
open_route('stat','③ 统计特征关系匹配与反演',2000,960,'#EAF6EE')
mechanism('L1','L1 似然构造<br>观测／统计量的概率模型',75,315,370,'like')
mechanism('L2','L2 最大化／相应修正<br>联合似然或得分方程',565,315,370,'like')
edge('flow-L1-L2','L1','L2','',kind='mechanism',color=colors['like'])
mechanism('D1','D1 分布表示<br>概率图／间距／尺度',1050,315,260,'dist')
mechanism('D2','D2 匹配准则<br>残差／概率结构',1360,315,260,'dist')
mechanism('D3','D3 参数确定<br>拟合／恢复',1670,315,260,'dist')
edge('flow-D1-D2','D1','D2','',kind='mechanism',color=colors['dist'])
edge('flow-D2-D3','D2','D3','',kind='mechanism',color=colors['dist'])
mechanism('S1','S1 统计特征<br>矩／分位数／次序量',2030,315,270,'stat')
mechanism('S2','S2 理论关系<br>特征与参数相联系',2340,315,270,'stat')
mechanism('S3','S3 参数识别<br>匹配／反演／恢复',2650,315,280,'stat')
edge('flow-S1-S2','S1','S2','',kind='mechanism',color=colors['stat'])
edge('flow-S2-S3','S2','S3','',kind='mechanism',color=colors['stat'])
node('like-guide','从 L1 或 L2 改动，形成不同似然与方程构造；修正方程不必是原始似然的最大化。',75,440,860,52,size=20,role='label')
node('dist-guide','保留“表示 → 准则 → 参数”的骨架；具体方法选用的表示与准则不同。',1050,440,880,52,size=20,role='label')
node('stat-guide','由选定特征与理论关系识别参数；“构造了统计量”本身不决定这一路线。',2030,440,900,52,size=20,role='label')

# 似然方法：平行的改动分支分别保留自己的来源。
method('mle','MLE<br>原始观测联合似然',85,510,250,current=True)
method('cw','Cohen–Whitten MMLE<br>位置／矩关系替换',585,510,310)
method('jacquelin','Jacquelin（1993）<br>二参数代数推导',85,735,250)
method('wmle','Cousineau WMLE<br>估计方程引入三权重',585,735,310,current=True)
method('smith','Smith（1985）<br>最小值替代构造',85,960,250)
method('wmle-correct','杨小玉等（2024）<br>WMLE 形状偏差修正',585,960,310)
method('kr','K–R MMLE（2009）<br>最小值定位＋删点',85,1185,250,current=True)
method('firth','Firth 得分修正<br>偏差修正项',585,1185,310)
method('cmle','CMLE<br>最小值处改用区间概率',85,1410,250)
method('dmmle','DMMLE（2025）<br>数据修改＋得分修正',585,1410,310)
edge('e-mle-cw','mle','cw','替换部分得分方程','borrow',colors['like'],at=(460,535),evidence=True)
edge('e-jac-wmle','jacquelin','wmle','扩展至三参数／三权重','inherit',colors['like'],at=(460,759),evidence=True)
edge('e-wmle-correct','wmle','wmle-correct','样本量相关的形状修正','inherit',colors['like'],'bottom','top',at=(740,893),evidence=True)
edge('e-smith-kr','smith','kr','场景适配：共同最小值','inherit',colors['like'],'bottom','top',at=(230,1116),evidence=True)
edge('e-kr-dmmle','kr','dmmle','保留数据修改似然','borrow',colors['like'],'right','left',via=[(455,1230),(455,1455)],at=(445,1350),evidence=True)
edge('e-firth-dmmle','firth','dmmle','加入偏差修正项','borrow',colors['like'],'bottom','top',at=(740,1342),evidence=True)
edge('e-mle-cmle','mle','cmle','替换最小值密度项','borrow',colors['like'],'left','left',via=[(57,555),(57,1455)],at=(210,1340),evidence=True)
node('like-note','L1 的输入也可是不变统计量；<br>LSPF／LPF 的完整跨路线过程见下方。',85,1570,810,95,size=24,role='label')

# 分布方法：White、相关性定位、间距和尺度一致性是不同分支。
method('white','White（1969）<br>概率图分数与回归',1060,510,250,route='dist')
method('soman','Soman LSE（1992）<br>White 回归＋位置评分',1590,510,310,route='dist',current=True)
method('lipson','Lipson–Sheth<br>概率图相关性定位',1060,735,250,route='dist')
method('park','Park LRE（2017）<br>相关定位＋分数对寿命回归',1590,735,310,route='dist',current=True)
method('mps','MPS<br>相邻 CDF 概率间距',1060,960,250,route='dist')
method('qmp','QMP<br>分位数组概率与计数',1590,960,310,route='dist')
method('mdm','MDM<br>各观测反推尺度的一致性',1060,1185,250,175,route='dist',current=True)
method('yang','Yang 迭代（2023）<br>回归 ↔ 最小值期望修正',1590,1185,310,route='dist')
method('gm','灰色位置估计<br>由 GM 得到 γ̂',1060,1410,250,route='dist')
method('gm-svr','GM–SVR（2021）<br>当前样本的 ε-SVR 拟合',1590,1410,310,route='dist')
edge('e-white-soman','white','soman','White 构造接入未知位置','inherit',colors['dist'],at=(1450,535),evidence=True)
edge('e-lipson-park','lipson','park','视觉比较 → 相关系数最大化','inherit',colors['dist'],at=(1450,759),evidence=True)
edge('e-soman-park','soman','park','同分数、同 \\(\\gamma\\) 时的方向关系<br>\\(\\hat{\\beta}_{\\mathrm{Park}}=r^2\\hat{\\beta}_{\\mathrm{White}}\\)<br>两文分数各异；分数与方向共同定估计','math',colors['dist'],'bottom','top',at=(1730,685),evidence=True)
edge('e-mps-qmp','mps','qmp','次序统计量作分位数<br>且每组计数 1：MPS 特例','math',colors['dist'],at=(1450,985),evidence=True)
edge('e-gm-svr','gm','gm-svr','GM 定位置，SVR 恢复 β、η','borrow',colors['dist'],at=(1450,1433),evidence=True)
node('dist-note','残差、CDF 间距和尺度差异，各自定义不同的匹配判据。',1055,1600,875,94,size=24,role='label')

# 统计构造：矩变换、不变统计量和条件线性估计分别成链。
method('cran','MM：Cran（1988）<br>Weibull moments 显式恢复',2050,510,260,175,route='stat',current=True)
method('pwm','PWM<br>概率加权矩',2580,510,310,route='stat')
method('w-mean','W 均值匹配（2003）<br>标准化后匹配期望',2050,735,260,route='stat')
method('lmom','L 矩（1990）<br>次序统计量线性组合',2580,735,310,route='stat')
method('quantile','分位数／枢轴反演<br>由统计关系确定参数',2050,960,260,route='stat')
method('tlmom','TL 矩（2003）<br>内部次序统计量替代端部',2580,960,310,route='stat')
method('mvlue','位置 MVLUE（2019）<br>给定 β、η 的协方差选权',2050,1185,260,175,route='stat')
method('mvleh','MVLE-H（2020）<br>倒数形状的线性组合',2580,1185,310,route='stat')
method('mvleh-extended','MVLE-H 扩展（2022）<br>超参数依赖 n 与临时 β',2580,1430,310,route='stat')
node('stat-note','统计特征可继续接理论关系，也可接联合密度。<br>用什么准则确定参数，需继续追踪；见下方 LSPF／LPF。',2040,1580,870,95,size=23,role='label')
edge('e-cran-pwm','cran','pwm','生存积分与 PWM 泛函对应','math',colors['stat'],at=(2440,535),evidence=True)
edge('e-pwm-lmom','pwm','lmom','同阶数、同估计规则下线性转换','math',colors['stat'],'bottom','top',at=(2735,668),evidence=True)
edge('e-lmom-tlmom','lmom','tlmom','内部次序量替代端部量','inherit',colors['stat'],'bottom','top',at=(2735,893),evidence=True)
edge('e-mvleh-extended','mvleh','mvleh-extended','扩展超参数的确定方式','inherit',colors['stat'],'bottom','top',at=(2735,1366),evidence=True)
edge('e-wmle-mvleh','wmle','mvleh-extended','借用 WMLE 的临时形状策略','borrow','#C96A20','right','right',via=[(947,790),(947,1710),(2940,1710),(2940,1485)],at=(1720,1710),evidence=True)

# 同一方法跨机制的完整过程：不是新的类别，也不作为历史关系计数。
node('cross-title','追踪完整过程｜LSPF 跨接期望关系；LPF 延续似然方程',45,2050,2400,54,size=31,bold=True,role='label')
node('cross-note','消元构造不决定估计路线。两者先使用统计量似然，后续分别核对：LSPF 接最小值期望修正，LPF 接原文似然方程。',45,2108,2400,42,size=23,role='label')
method('lspf','LSPF（2013）<br>不变统计量似然与参数恢复',80,2190,350,125,route='stat')
node('lspf-eliminate','构造策略：消去位置、尺度<br>\\(W_i=(x_{(i)}-x_{(1)})/(x_{(n)}-x_{(1)})\\)<br>两个端部分量固定，保留内部 W',540,2170,640,165,color=colors['stat'],size=23,role='process')
node('lspf-like','L1＋L2：构造并最大化 W 的联合密度<br>由统计量似然确定形状 β<br>不是 W 均值匹配，也不是 MPS',1365,2170,650,165,color=colors['like'],size=24,role='process')
node('lspf-restore','S2＋S3：最小值期望关系<br>据此作位置修正<br>尺度再按原文方程回代',2200,2170,690,165,color=colors['stat'],size=24,role='process')
method('lpf','LPF（2015）<br>去位置统计量似然＋似然方程',80,2430,350,125,route='like')
node('lpf-eliminate','构造策略：只消去位置<br>\\(V_i=x_{(i)}-x_{(1)}\\)<br>一个分量固定，保留尺度信息',540,2410,640,165,color='#64748B',size=23,role='process')
node('lpf-like','L1＋L2：构造并最大化 V 的联合密度<br>先联合估计尺度 η 与形状 β<br>数据间距的密度不是 CDF 间距乘积',1365,2410,650,165,color=colors['like'],size=24,role='process')
node('lpf-restore','L2：代入形状估计<br>解原文似然方程(9)、(10)恢复 η、γ<br>恢复步骤本身不等于 S3',2200,2410,690,165,color=colors['like'],size=24,role='process')
for prefix in ('lspf','lpf'):
    edge('flow-'+prefix+'-input',prefix,prefix+'-eliminate','',kind='process',color='#64748B')
    edge('flow-'+prefix+'-restore',prefix+'-like',prefix+'-restore','',kind='process',color='#64748B')
# 这两个既有证据 ID 由泛化数学联系细化为方法内部过程，不再像沿袭线。
edge('e-lspf-likelihood','lspf-eliminate','lspf-like','统计量进入概率模型','process',colors['like'],at=(1272,2147),evidence=True)
edge('e-lpf-likelihood','lpf-eliminate','lpf-like','统计量进入概率模型','process',colors['like'],at=(1272,2387),evidence=True)
edge('e-lspf-lpf','lspf','lpf','保留尺度信息；退化分量 2 → 1','inherit',colors['stat'],'bottom','top',at=(260,2375),evidence=True)
edge('e-lspf-mvlue','lspf-restore','mvlue','最小值修正扩为多次序量组合','borrow',colors['stat'],'top','left',via=[(2545,2010),(1975,2010),(1975,1247)],at=(2160,2010),evidence=True)
edge('e-lspf-yang','lspf-restore','yang','借用最小值期望位置修正','borrow','#C96A20','right','right',via=[(2980,2252),(2980,1100),(1940,1100),(1940,1240)],at=(2470,1100),evidence=True)

# 具体组合方法：入边指向被借用的参数步骤。
node('hybrid-title','其他跨路线组合｜写明取哪个参数、接哪一条机制',45,1750,2910,48,size=28,bold=True,role='label')
method('park-mle2','Park Proposed+MLE2<br>D2 相关定位 γ → L1/L2 二参数 MLE',70,1875,670,115,route='dist')
method('mle2','二参数 MLE<br>L1/L2 平移后恢复 β、η',800,1875,280,115)
method('mixed','Cousineau Mixed 各版本<br>L2／D2 提供形状估计<br>S2/S3 以均值、最小值期望恢复 η、γ',1170,1875,740,115,route='stat')
method('early-iter','初始失效期迭代（2025）<br>S2/S3 位置 MVLUE ↔ 平移后二参数恢复',2240,1875,650,115,route='stat')
edge('e-park-mle2','park','park-mle2','取相关性位置估计','borrow','#C96A20','left','top',via=[(1515,790),(1515,1685),(455,1685),(455,1825),(405,1825)],at=(675,1685),evidence=True)
edge('e-mle2-park','mle2','park-mle2','恢复 β、η','borrow','#C96A20','left','right',at=(770,1830),evidence=True)
edge('e-mvlue-early','mvlue','early-iter','代入位置估计，交替更新','borrow','#C96A20','right','top',via=[(2335,1247),(2335,1660),(2965,1660),(2965,1820),(2565,1820)],at=(2730,1820),evidence=True)
edge('e-mle-mixed','mle','mixed','MLE 形状','borrow','#B47744','bottom','top',via=[(210,665),(365,665),(365,1800),(1310,1800)],at=(940,1800),evidence=True)
edge('e-wmle-mixed','wmle','mixed','WMLE 形状','borrow','#B47744','bottom','top',via=[(740,890),(915,890),(915,1825),(1540,1825)],at=(1450,1825),evidence=True)
edge('e-mps-mixed','mps','mixed','MPS 形状','borrow','#B47744','bottom','top',via=[(1185,1105),(1335,1105),(1335,1850),(1770,1850)],at=(1770,1850),evidence=True)

# 后验与学习仍由机制链展开，不设容纳方法的封闭分类区。
node('band-post','',40,2660,1420,76,color='none',fill='#F1EAF7',role='background')
node('post-heading','④ 贝叶斯后验推断',65,2670,1370,55,size=31,bold=True,role='label')
mechanism('B1','B1 后验构造<br>\\(p(\\theta\\mid D)\\propto L(\\theta\\mid D)\\pi(\\theta)\\)',75,2760,600,'post')
mechanism('B2','B2 后验决策<br>均值／中位数／MAP → 参数估计',825,2760,600,'post')
edge('flow-B1-B2','B1','B2','',kind='mechanism',color=colors['post'])
method('green','Green Bayes（1994）<br>B1 先验与后验；Gibbs 计算',85,2935,530,110,route='post')
method('teimouri','Teimouri 后验方案<br>B1 模型承接；位置更新改用 MH',875,2935,530,110,route='post')
edge('e-green-teimouri','green','teimouri','模型承接＋位置抽样修改','inherit',colors['post'],at=(745,2990),evidence=True)
edge('e-mle-bayes','mle','B1','共享样本似然；引入先验与后验决策','math',colors['post'],'left','left',via=[(20,565),(20,2815)],at=(330,2620),evidence=True)
node('post-note','似然提供样本贡献；抽样、积分等用于计算后验，估计输出还取决于决策规则。',75,3063,1350,50,size=22,role='label')
node('band-learn','',1510,2660,1450,76,color='none',fill='#FBF0E2',role='background')
node('learn-heading','⑤ 学习型参数映射',1535,2670,1400,55,size=31,bold=True,role='label')
mechanism('N1','N1 多组带标签样本训练<br>\\(\\{(T(D_j),\\theta_j)\\}\\) → 学习 \\(h_{\\varphi}\\)',1545,2760,605,'learn')
mechanism('N2','N2 新样本应用固定映射<br>\\(\\hat{\\theta}=h_{\\varphi}(T(D))\\)',2305,2760,605,'learn')
edge('flow-N1-N2','N1','N2','固定已学映射',kind='mechanism',color=colors['learn'],at=(2230,2733))
method('ann','ANN／BPNN<br>N1 学习估计函数 → N2 输出三参数',1545,2935,605,110,route='learn')
node('solver-note','PSO／SA／DE：搜索当前样本的既定目标<br>GM–SVR：拟合当前样本的概率图<br>作用位置分别说明，不等同于 N1 训练',2305,2935,605,110,size=22,role='label')
node('learn-note','特征可借用 S1 等构造；多组样本训练估计函数，与逐样本匹配理论特征关系有区别。',1545,3063,1365,50,size=22,role='label')

# 少量接入线示范“由机制展开方法”，其余方法按节点内同一机制标识阅读。
# 细线为空心箭头，无文献证据计数；它们不声称历史发展。
edge('use-L1-mle','L1','mle','',kind='mechanism',color=colors['like'],start='left',end='left',via=[(62,370),(62,572.5)])
edge('use-L2-cw','L2','cw','',kind='mechanism',color=colors['like'],start='right',end='right',via=[(960,370),(960,572.5)])
edge('use-D1-white','D1','white','',kind='mechanism',color=colors['dist'],start='left',end='left',via=[(1035,370),(1035,572.5)])
edge('use-D3-soman','D3','soman','',kind='mechanism',color=colors['dist'],start='right',end='right',via=[(1950,370),(1950,572.5)])
edge('use-S1-cran','S1','cran','',kind='mechanism',color=colors['stat'],start='left',end='left',via=[(2010,370),(2010,572.5)])
edge('use-S3-pwm','S3','pwm','',kind='mechanism',color=colors['stat'],start='right',end='right',via=[(2950,370),(2950,572.5)])
edge('use-B1-green','B1','green','',kind='mechanism',color=colors['post'],start='bottom',end='top',via=[(375,2910),(350,2910)])
edge('use-N1-ann','N1','ann','',kind='mechanism',color=colors['learn'],start='bottom',end='top')

ET.indent(doc, space='  ')
target=ROOT/'06-完整机理地图-估计路线与方法关系.drawio'
ET.ElementTree(doc).write(target,encoding='utf-8',xml_declaration=True)
assert len(relations)==30, len(relations)
assert {r[0] for r in relations}==set(EVIDENCE_TERMS)
print(f'generated route map: {len(boxes)} nodes, 28 method relations + 2 internal mechanism explanations; all 30 evidence IDs retained')
