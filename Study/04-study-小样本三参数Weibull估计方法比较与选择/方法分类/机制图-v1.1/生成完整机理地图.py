"""从明确的方法对关系生成可编辑的 draw.io 方法地图。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET
from 数学排版 import normalize_markup

ROOT = Path(__file__).resolve().parent
SOURCE = '../04-方法分类与沿袭关系工作稿.md'
doc = ET.Element('mxfile', host='app.diagrams.net', version='26.0.9')
diagram = ET.SubElement(doc, 'diagram', id='complete-method-map-v10', name='方法机理与方法间关系')
model = ET.SubElement(diagram, 'mxGraphModel', math='1', page='1', pageWidth='3000', pageHeight='2550', background='#ffffff')
root = ET.SubElement(model, 'root')
ET.SubElement(root, 'mxCell', id='0')
ET.SubElement(root, 'mxCell', id='1', parent='0')
boxes = {}
relations = []
colors = dict(like='#AB4D3D', dist='#286D99', stat='#26745A', post='#785499', learn='#A5621F')

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
    style += 'endArrow=none;' if kind=='math' else 'endArrow=block;endFill=1;'
    if kind=='math':style+='dashed=1;dashPattern=7 5;'
    if kind=='borrow':style+='dashed=1;dashPattern=10 4 2 4;strokeWidth=3.5;'
    cell=ET.SubElement(root,'mxCell',id=key,value=normalize_markup(label),edge='1',parent='1',source=src,target=dst,style=style,relationKind=kind,evidence=f'{SOURCE}:{evidence}')
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
    relations.append((key,src,dst,kind,label,evidence))

def method(key,text,x,y,w=270,h=90,route='like',current=False):
    return node(key,text,x,y,w,h,color=colors[route],size=23,current=current)

node('title','三参数 Weibull 方法地图｜估计依据、方法原型与具体改进',45,20,2910,64,size=39,bold=True,role='label')
node('subtitle','同一寿命样本 \\(D=\\{x_1,\\ldots,x_n\\}\\)，经不同的统计对象与参数确定原则，得到 \\(\\hat{\\theta}=(\\hat{\\beta},\\hat{\\eta},\\hat{\\gamma})\\)。',45,91,2910,48,size=27,role='label')
node('legend','实线箭头：扩展／修正　　虚线：数学联系　　点划线箭头：局部借用／组合　　金色节点：本次比较的七种实现',45,147,2910,42,size=23,role='label')

panels=[('like',40,940,'① 似然估计','观测密度 → 联合似然 \\(L(\\theta)=\\prod_{i=1}^{n}f_{\\theta}(x_i)\\)<br>最大化 \\(L\\)，或求解、修正似然得分方程','#FFF8F5'),
        ('dist',1020,940,'② 分布匹配','经验分布／概率图／CDF 概率间距<br>选择残差、距离或尺度差异较小／间距评分较大的 θ','#F2F8FC'),
        ('stat',2000,960,'③ 统计关系反演','样本统计量 \\(T(D)\\) ↔ 理论关系 \\(T(\\theta)\\)<br>匹配、消元、反演；或按条件协方差组合统计量<br>不变统计量还可接统计量似然','#F2F9F5')]
for key,x,w,title,principle,fill in panels:
    node('bg-'+key,'',x,220,w,1535,color='#DFE6EB',fill=fill,role='background')
    node('heading-'+key,title,x+25,236,w-50,58,color=colors[key],size=32,bold=True,role='label')
    node('principle-'+key,principle,x+30,309,w-60,143,color=colors[key],fill='#ffffff',size=25,bold=True,role='principle')

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
edge('e-mle-cw','mle','cw','替换部分得分方程','borrow',colors['like'],at=(460,535),evidence='57-60')
edge('e-jac-wmle','jacquelin','wmle','扩展至三参数／三权重','inherit',colors['like'],at=(460,759),evidence='61,69')
edge('e-wmle-correct','wmle','wmle-correct','样本量相关的形状修正','inherit',colors['like'],'bottom','top',at=(740,893),evidence='71')
edge('e-smith-kr','smith','kr','场景适配：共同最小值','inherit',colors['like'],'bottom','top',at=(230,1116),evidence='53,59')
edge('e-kr-dmmle','kr','dmmle','保留数据修改似然','borrow',colors['like'],'right','left',via=[(455,1230),(455,1455)],at=(445,1350),evidence='70')
edge('e-firth-dmmle','firth','dmmle','加入偏差修正项','borrow',colors['like'],'bottom','top',at=(740,1342),evidence='70,74')
edge('e-mle-cmle','mle','cmle','替换最小值密度项','borrow',colors['like'],'left','left',via=[(57,555),(57,1455)],at=(210,1340),evidence='59,78')
method('stat-like','统计量似然<br>最大化变换统计量的联合密度',500,1580,400,110)

# 分布方法：White、相关性定位、间距和尺度一致性是不同分支。
method('white','White（1969）<br>概率图分数与回归',1060,510,250,route='dist')
method('soman','Soman LSE（1992）<br>White 回归＋位置评分',1590,510,310,route='dist',current=True)
method('lipson','Lipson–Sheth<br>概率图相关性定位',1060,735,250,route='dist')
method('park','Park LRE（2017）<br>相关定位＋分数对寿命回归',1590,735,310,route='dist',current=True)
method('mps','MPS<br>相邻 CDF 概率间距',1060,960,250,route='dist')
method('qmp','QMP<br>分位数组概率与计数',1590,960,310,route='dist')
method('mdm','MDM<br>各观测反推尺度的一致性',1060,1185,250,route='dist',current=True)
method('yang','Yang 迭代（2023）<br>回归 ↔ 最小值期望修正',1590,1185,310,route='dist')
method('gm','灰色位置估计<br>由 GM 得到 γ̂',1060,1410,250,route='dist')
method('gm-svr','GM–SVR（2021）<br>当前样本的 ε-SVR 拟合',1590,1410,310,route='dist')
edge('e-white-soman','white','soman','White 构造接入未知位置','inherit',colors['dist'],at=(1450,535),evidence='106-107,114')
edge('e-lipson-park','lipson','park','视觉比较 → 相关系数最大化','inherit',colors['dist'],at=(1450,759),evidence='116')
edge('e-soman-park','soman','park','同分数、同 \\(\\gamma\\) 时的方向关系<br>\\(\\hat{\\beta}_{\\mathrm{Park}}=r^2\\hat{\\beta}_{\\mathrm{White}}\\)<br>两文分数各异；分数与方向共同定估计','math',colors['dist'],'bottom','top',at=(1730,669),evidence='127-138')
edge('e-mps-qmp','mps','qmp','次序统计量作分位数<br>且每组计数 1：MPS 特例','math',colors['dist'],at=(1450,985),evidence='78-80')
edge('e-gm-svr','gm','gm-svr','GM 定位置，SVR 恢复 β、η','borrow',colors['dist'],at=(1450,1433),evidence='208')
node('dist-note','残差、CDF 间距和尺度差异，各自定义不同的匹配判据。',1055,1600,875,94,size=24,role='label')

# 统计构造：矩变换、不变统计量和条件线性估计分别成链。
method('cran','MM：Cran（1988）<br>Weibull moments 显式恢复',2050,510,260,route='stat',current=True)
method('pwm','PWM<br>概率加权矩',2580,510,310,route='stat')
method('w-mean','W 均值匹配（2003）<br>标准化后匹配期望',2050,735,260,route='stat')
method('lmom','L 矩（1990）<br>次序统计量线性组合',2580,735,310,route='stat')
method('quantile','分位数／枢轴反演<br>由统计关系确定参数',2050,960,260,route='stat')
method('tlmom','TL 矩（2003）<br>内部次序统计量替代端部',2580,960,310,route='stat')
method('lspf','LSPF（2013）<br>W 消去位置、尺度<br>最大化 W 联合密度',2050,1185,260,110,route='stat')
method('lpf','LPF（2015）<br>V 只消去位置<br>最大化 V 联合密度',2580,1185,310,110,route='stat')
method('mvlue','位置 MVLUE（2019）<br>给定 β、η 的协方差选权',2050,1430,260,120,route='stat')
method('mvleh','MVLE-H（2020）<br>倒数形状的线性组合',2580,1410,310,route='stat')
method('mvleh-extended','MVLE-H 扩展（2022）<br>超参数依赖 n 与临时 β',2580,1610,310,route='stat')
edge('e-cran-pwm','cran','pwm','生存积分与 PWM 泛函对应','math',colors['stat'],at=(2440,535),evidence='154-159')
edge('e-pwm-lmom','pwm','lmom','同阶数、同估计规则下线性转换','math',colors['stat'],'bottom','top',at=(2735,668),evidence='161')
edge('e-lmom-tlmom','lmom','tlmom','内部次序量替代端部量','inherit',colors['stat'],'bottom','top',at=(2735,893),evidence='161')
edge('e-lspf-lpf','lspf','lpf','保留尺度信息<br>退化分量：2 → 1','inherit',colors['stat'],at=(2440,1215),evidence='168-169')
edge('e-lspf-mvlue','lspf','mvlue','最小值修正扩为多次序量组合','borrow',colors['stat'],'bottom','top',at=(2180,1369),evidence='179')
edge('e-mvleh-extended','mvleh','mvleh-extended','扩展超参数的确定方式','inherit',colors['stat'],'bottom','top',at=(2735,1554),evidence='181')
edge('e-lspf-yang','lspf','yang','借用最小值期望位置修正','borrow','#C96A20','left','top',via=[(1977,1240),(1977,1100),(1745,1100)],at=(1935,1100),evidence='110,119')
edge('e-wmle-mvleh','wmle','mvleh-extended','借用 WMLE 的临时形状策略','borrow','#C96A20','right','right',via=[(947,780),(947,1790),(2925,1790),(2925,1655)],at=(2000,1790),evidence='181')
edge('e-lspf-likelihood','lspf','stat-like','LSPF：W 的联合密度最大化','math',colors['stat'],'bottom','right',via=[(2180,1330),(2340,1330),(2340,1720),(995,1720),(995,1635)],at=(1900,1720),evidence='168-169')
edge('e-lpf-likelihood','lpf','stat-like','LPF：V 的联合密度最大化','math',colors['stat'],'bottom','right',via=[(2735,1330),(2940,1330),(2940,1720),(995,1720),(995,1635)],at=(2640,1720),evidence='168-169')

# 具体组合方法：入边指向被借用的参数步骤。
node('hybrid-title','跨方法组合：衔接具体参数步骤',45,1830,650,48,size=28,bold=True,role='label')
method('park-mle2','Park Proposed+MLE2<br>相关定位 γ → 二参数 MLE 恢复 β、η',70,1950,670,115,route='dist')
method('mle2','二参数 MLE<br>平移后估计 β、η',800,1950,280,115)
method('mixed','Cousineau Mixed 各版本<br>取 MLE／WMLE／MPS 的 β̂<br>接均值与最小值期望恢复 η、γ',1170,1950,740,115,route='stat')
method('early-iter','初始失效期迭代（2025）<br>位置 MVLUE ↔ 平移后二参数恢复',2240,1950,650,115,route='stat')
edge('e-park-mle2','park','park-mle2','取相关性位置估计','borrow','#C96A20','left','top',via=[(1515,780),(1515,1740),(405,1740)],at=(670,1740),evidence='109')
edge('e-mle2-park','mle2','park-mle2','恢复 β、η','borrow','#C96A20','left','right',at=(770,1925),evidence='109')
edge('e-mvlue-early','mvlue','early-iter','代入位置估计，交替更新','borrow','#C96A20','bottom','top',via=[(2180,1870),(2565,1870)],at=(2475,1870),evidence='183')
edge('e-mle-mixed','mle','mixed','MLE 形状','borrow','#B47744','bottom','top',via=[(210,650),(365,650),(365,1905),(1310,1905)],at=(530,1905),evidence='191')
edge('e-wmle-mixed','wmle','mixed','WMLE 形状','borrow','#B47744','bottom','top',via=[(740,875),(915,875),(915,1880),(1540,1880)],at=(1100,1880),evidence='191')
edge('e-mps-mixed','mps','mixed','MPS 形状','borrow','#B47744','bottom','top',via=[(1185,1090),(1340,1090),(1340,1855),(1770,1855)],at=(1510,1855),evidence='191')

# 后验与学习各有独立的决定原则，计算工具留在方法节点内。
node('bg-post','',40,2140,1420,355,color='#E2DDEA',fill='#F7F3FA',role='background')
node('post-heading','④ 后验推断',65,2150,350,55,size=31,bold=True,role='label')
node('post-principle','\\(L(\\theta\\mid D)\\,\\pi(\\theta)\\longrightarrow p(\\theta\\mid D)\\)<br>按后验均值、中位数或 MAP 确定估计',75,2225,630,126,color=colors['post'],size=25,role='principle')
method('green','Green Bayes（1994）<br>先验＋Gibbs',785,2200,600,85,route='post')
method('teimouri','Teimouri 后验方案<br>承接模型，位置更新改用 MH',785,2390,600,85,route='post')
edge('e-green-teimouri','green','teimouri','模型承接＋位置抽样修改','inherit',colors['post'],'bottom','top',at=(1085,2340),evidence='222-224')
edge('e-mle-bayes','mle','green','共享样本似然；引入先验与后验决策','math',colors['post'],'left','top',via=[(20,555),(20,2115),(1085,2115)],at=(750,2115),evidence='220-230')
node('post-note','样本贡献由似然提供，先验与后验决策共同确定输出。',75,2380,630,90,size=23,role='label')
node('bg-learn','',1510,2140,1450,355,color='#E8DFD3',fill='#FCF7F0',role='background')
node('learn-heading','⑤ 学习映射',1535,2150,350,55,size=31,bold=True,role='label')
node('learn-principle','训练集 \\(\\{(T(D_j),\\theta_j)\\}\\) → 学习 \\(h_{\\varphi}\\)<br>新样本输入 \\(T(D)\\)，直接输出 \\(\\hat{\\theta}=h_{\\varphi}(T(D))\\)',1545,2225,650,126,color=colors['learn'],size=25,role='principle')
method('ann','ANN／BPNN<br>跨样本学习特征 → 三参数',2280,2225,600,126,route='learn')
node('learn-note','训练样本定义映射的学习范围，特征和损失决定估计函数。',1545,2380,650,90,size=23,role='label')
node('solver-note','PSO／SA／DE：搜索既定统计目标<br>GM–SVR：拟合当前样本的概率图关系',2280,2380,600,90,size=23,role='label')

ET.indent(doc, space='  ')
target=ROOT/'06-完整机理地图-五簇分类与方法关系.drawio'
ET.ElementTree(doc).write(target,encoding='utf-8',xml_declaration=True)
print(f'generated method map: {len(boxes)} nodes, {len(relations)} explicit method relations')
