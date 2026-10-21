"""似然的统计构造、最大化原则与计算实现：横向四步可视流程。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET

from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / '07-似然估计路线-信息处理流程.drawio'
RED, BLUE, GREEN, GRAY = '#AA5041', '#337695', '#357A63', '#6B7B8D'
d = Diagram('likelihood-visual-flow-v11', '似然估计：模型、似然、最大化与计算实现', 2400, 1100)


def dot(key, x, y, *, color=RED, radius=6):
    d.box(key, '', x-radius, y-radius, radius*2, radius*2,
          color=color, fill=color, size=1, extra='ellipse;')


def step(key, number, title, x, fill):
    d.panel(key, x, 180, 540, 675, fill=fill)
    d.text(key+'-title', f'{number} {title}', x+20, 198, 500, 55, size=28, bold=True)


d.text('title', '似然估计｜构造固定样本的似然函数，以最大化原则确定参数', 45, 20, 2310, 65, size=36, bold=True)
d.text('subtitle', r'独立同分布完整样本 \(D\)；\(\theta=(\beta,\eta,\gamma)\)，\(\beta>0,\eta>0,\gamma<x_{(1)}\)。曲线仅作原理示意。', 50, 100, 2300, 48, size=25)
step('step1', '①', '给定分布模型与固定样本', 35, '#F3F7FB')
step('step2', '②', '构造样本的似然函数', 635, '#FFF7F3')
step('step3', '③', '最大化整组样本的似然', 1235, '#F2F8F4')
step('step4', '④', '计算实现：求解与核验', 1835, '#F3F4F6')

# ① 相同观测位置与两条候选密度；下方的候选卡给曲线赋予参数含义。
d.text('observed-label', r'三参数 Weibull 模型 \(f(x;\theta)\)', 75, 275, 460, 45, size=25, bold=True)
obs = [2.1, 3.3, 5.6, 8.2]
labels = [r'\(x_{(1)}\)', r'\(x_{(2)}\)', r'\(x_{(i)}\)', r'\(x_{(n)}\)']
px0, py0, xs, ys = 85, 510, 43, 850
d.line('density-x', [(75,py0),(535,py0)], color=GRAY, arrow='block')
d.line('density-y', [(px0,520),(px0,323)], color=GRAY, arrow='block')
d.text('density-y-label', r'\(f(x;\theta)\)', 90, 315, 145, 38, size=24)
d.text('density-x-label', r'寿命 \(x\)', 420, 555, 130, 38, size=24)


def density(x, beta, eta, gamma):
    y=x-gamma
    return beta/eta*(y/eta)**(beta-1)*math.exp(-(y/eta)**beta) if y>0 else 0.


pars = [('a',2.25,4.5,.8,RED),('b',3.3,5.8,1.0,BLUE)]
for name,beta,eta,gamma,color in pars:
    pts=[(px0+x*xs,py0-density(x,beta,eta,gamma)*ys) for x in [j*.08 for j in range(121)]]
    d.line('density-curve-'+name,pts,color=color,width=3.5)
for i,(x,label) in enumerate(zip(obs,labels)):
    px,py=px0+x*xs,py0-density(x,*pars[0][1:4])*ys
    d.line(f'height-{i}',[(px,py0),(px,py)],color=RED,width=2,dashed=True)
    dot(f'height-point-{i}',px,py,color=RED)
    d.line(f'data-tick-{i}',[(px,py0-6),(px,py0+8)],color=BLUE,width=2)
    dot(f'data-point-{i}',px,py0,color=BLUE,radius=5)
    d.text(f'data-label-{i}',label,px-43,520,86,38,size=23,align='center')
d.text('data-fixed', r'样本 \(D\) 固定；候选 \(\theta\) 改变密度曲线', 75, 600, 460, 45, size=24)
d.line('legend-a',[(95,700),(135,700)],color=RED,width=3.5)
d.text('legend-a-text',r'候选 \(A\)',145,680,125,42,size=24,color=RED)
d.box('candidate-a',r'\(\theta_A=(\beta_A,\eta_A,\gamma_A)\)',270,665,255,70,color=RED,fill='#FFF1EB',size=24)
d.line('legend-b',[(95,800),(135,800)],color=BLUE,width=3.5)
d.text('legend-b-text',r'候选 \(B\)',145,780,125,42,size=24,color=BLUE)
d.box('candidate-b',r'\(\theta_B=(\beta_B,\eta_B,\gamma_B)\)',270,765,255,70,color=BLUE,fill='#EFF7FB',size=24)

# ② 独立观测的密度乘积成为固定 D 的参数函数。
d.text('combine-heading', r'独立观测的密度相乘，<br>得到固定样本 \(D\) 的联合似然', 670, 280, 470, 65, size=25)
tiles=[('f1',r'\(f(x_{(1)};\theta)\)',675,370),('f2',r'\(f(x_{(2)};\theta)\)',930,370),('fi',r'\(f(x_{(i)};\theta)\)',675,500),('fn',r'\(f(x_{(n)};\theta)\)',930,500)]
for key,label,x,y in tiles:
    d.box(key,label,x,y,180,80,color=RED,fill='#FFF0E8',size=28)
for i,(x,y) in enumerate([(865,388),(865,455),(865,518)]):
    d.text('multiply-'+str(i),r'\(\times\)',x,y,56,45,size=29,bold=True,align='center')
d.line('contribution-bracket',[(685,600),(685,615),(1105,615),(1105,600)],color=RED,width=2.5)
d.box('joint-score',r'似然函数<br>\(L(\theta;D)=\prod_{i=1}^{n} f(x_i;\theta)\)',680,640,450,105,color=RED,fill='#FFFFFF',size=28,bold=True)
d.line('combine-to-score',[(905,615),(905,640)],color=RED,width=2.5,arrow='block')
d.text('log-score',r'固定 \(D\)，将 \(L(\theta;D)\)<br>看作参数 \(\theta\) 的函数',665,760,480,75,size=25,align='center')

# ③ 先给出统计原则，再用参数轴曲线示意最大化关系；不以驻点定义MLE。
d.box('maximum',r'最大值存在时<br>\(\widehat\theta_{\mathrm{MLE}}\in\operatorname*{arg\,max}_{\theta\in\Theta}L(\theta;D)\)',1270,275,470,110,color=GREEN,fill='#E6F3EB',size=27,bold=True)
sx0,sy0,sw,sh=1290,640,390,180
d.line('score-x',[(sx0-18,sy0),(sx0+sw+28,sy0)],color=GRAY,arrow='block')
d.line('score-y',[(sx0,sy0+8),(sx0,sy0-sh-18)],color=GRAY,arrow='block')
d.text('score-y-label',r'\(L(\theta;D)\)',1298,400,180,40,size=25)


def score_height(t):
    return .12+.85*math.exp(-((t-.62)/.34)**2)


d.line('likelihood-section',[(sx0+t*sw,sy0-score_height(t)*sh) for t in [i/100 for i in range(101)]],color=GREEN,width=4)
for key,t,label in [('theta-a',.14,r'\(\theta_A\)'),('theta-b',.38,r'\(\theta_B\)'),('theta-peak',.62,r'\(\theta^{\star}\)')]:
    xx,yy=sx0+t*sw,sy0-score_height(t)*sh
    d.line(key+'-guide',[(xx,sy0),(xx,yy)],color=GREEN,dashed=True)
    dot(key+'-point',xx,yy,color=GREEN,radius=6)
    d.text(key+'-label',label,xx-42,650,84,40,size=25,align='center')
d.text('local-peak','最大化关系示意',1480,410,235,43,size=25,color=GREEN,align='center')
d.text('score-axis-label',r'候选参数 \(\theta\)（原理示意）',1285,695,420,38,size=24,align='center')
d.box('estimate',r'\(\widehat\theta_{\mathrm{MLE}}=(\widehat\beta,\widehat\eta,\widehat\gamma)\)',1280,755,430,65,color=GREEN,fill='#E6F3EB',size=27,bold=True)
d.line('peak-to-estimate',[(1531.8,465.4),(1735,465.4),(1735,787.5),(1710,787.5)],color=GREEN,width=2.5,arrow='block')

# ④ 这一栏执行既定原则：等价改写、求候选、核验目标与边界。
d.text('implementation', '对③确定的统计目标进行计算', 1870, 270, 470, 45, size=25, bold=True, color=GRAY)
d.box('log-transform',r'取对数：保持最大化关系<br>\(\ell(\theta;D)=\ln L(\theta;D)\)<br>\(=\sum_{i=1}^{n}\ln f(x_i;\theta)\)',1870,340,470,135,color=GRAY,fill='#FFFFFF',size=25)
d.box('score-equations',r'解析或数值计算候选<br>直接优化 \(\ell\)，或求解<br>\(U(\theta)=\nabla_\theta\ell(\theta;D)=0\)',1870,525,470,130,color=GRAY,fill='#FFFFFF',size=25)
d.box('verification',r'核验候选<br>比较目标值、参数域 \(\Theta\) 与支持边界<br>MLE 须满足③的最大化原则',1870,705,470,120,color=GRAY,fill='#FFFFFF',size=24)
d.edge('log-to-equations','log-transform','score-equations','选择计算路径',color=GRAY,start='bottom',end='top',at=(2105,500))
d.edge('equations-to-verification','score-equations','verification','检查候选及边界响应',color=GRAY,start='bottom',end='top',at=(2105,680))

# 只有一行步骤；统计构造与求解器变化在下方明确分开。
d.line('step1-to-step2',[(587,535),(623,535)],color=RED,width=4,arrow='block')
d.line('step2-to-step3',[(1187,535),(1223,535)],color=RED,width=4,arrow='block')
d.line('step3-to-step4',[(1787,535),(1823,535)],color=GRAY,width=4,arrow='block')
d.text('interfaces','统计构造改动：K–R改①数据／位置；CMLE改②似然项；罚似然改③目标；WMLE等另改估计方程。',65,905,2270,55,size=27,bold=True)
d.text('method-locations','纯求解器变化：保持同一似然目标或同一估计方程，更换搜索或求根程序；对应④的计算实现层。',65,975,2270,55,size=24)
d.save(TARGET)

cells=ET.parse(TARGET).findall('.//mxCell')
ids=[c.get('id') for c in cells]
assert len(ids)==len(set(ids))
for cell in cells:
    if cell.get('edge')=='1':
        assert cell.get('source') in ids and cell.get('target') in ids
    if cell.get('vertex')=='1':
        geom=cell.find('mxGeometry')
        x,y,w,h=(float(geom.get(k,'0')) for k in ('x','y','width','height'))
        assert 0<=x<=x+w<=2400 and 0<=y<=y+h<=1100,cell.get('id')
print(f'generated {TARGET.name}: {len(cells)} editable cells; XML, edge endpoints, and canvas bounds valid')
