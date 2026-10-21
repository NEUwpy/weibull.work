"""用可编辑观测点、密度曲线和评分截面讲清似然信息处理流程。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET

from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / '07-似然估计路线-信息处理流程.drawio'
RED = '#AA5041'
BLUE = '#337695'
GREEN = '#357A63'
GRAY = '#6B7B8D'
d = Diagram('likelihood-visual-flow-v11', '似然估计：四步可视信息处理流程', 2400, 1100)


def dot(key, x, y, *, color=RED, radius=6):
    d.box(key, '', x-radius, y-radius, radius*2, radius*2,
          color=color, fill=color, size=1, extra='ellipse;')


def step(key, number, title, x, y, fill):
    d.panel(key, x, y, 540, 675, fill=fill)
    d.text(key+'-title', f'{number} {title}', x+20, y+18, 500, 55, size=28, bold=True)


d.text('title', '似然估计｜固定观测，比较不同参数下整组样本的密度贡献', 45, 20, 2310, 65, size=36, bold=True)
d.text('subtitle', r'独立完整样本；\(\theta=(\beta,\eta,\gamma)\)，\(\beta>0,\eta>0,\gamma<x_{(1)}\)。图中的曲线和参数截面均为原理示意。', 50, 100, 2300, 48, size=25)

step('step1', '①', '固定样本，提出候选参数', 35, 180, '#F3F7FB')
step('step2', '②', '读取各观测处的候选密度', 635, 180, '#FFF7F3')
step('step3', '③', '合成整组观测的贡献评分', 1235, 180, '#FFF8F0')
step('step4', '④', '比较评分，确定参数候选', 1835, 180, '#F2F8F4')

# ① 寿命点固定不动；候选模型只改变这些点在密度曲线上的高度。
d.text('observed-label', '已经观测到的寿命', 75, 285, 460, 45, size=27, bold=True)
d.line('data-axis', [(85, 445), (535, 445)], color=GRAY, width=2, arrow='block')
obs = [2.1, 3.3, 5.6, 8.2]
for i, (x, lab) in enumerate(zip(obs, [r'\(x_{(1)}\)', r'\(x_{(2)}\)', r'\(x_{(i)}\)', r'\(x_{(n)}\)'])):
    px = 95+x*48
    d.line(f'data-tick-{i}', [(px,432),(px,458)], color=BLUE, width=2)
    dot(f'data-point-{i}', px, 410, color=BLUE, radius=8)
    d.text(f'data-label-{i}', lab, px-48, 470, 96, 42, size=23, align='center')
d.text('data-axis-label', r'寿命 \(x\)', 415, 520, 125, 38, size=24)
d.box('candidate-a', r'候选 \(A\)<br>\(\theta_A=(\beta_A,\eta_A,\gamma_A)\)', 85, 590, 440, 100, color=RED, fill='#FFF1EB', size=25)
d.box('candidate-b', r'候选 \(B\)<br>\(\theta_B=(\beta_B,\eta_B,\gamma_B)\)', 85, 710, 440, 100, color=BLUE, fill='#EFF7FB', size=25)
d.text('data-fixed', '观测位置相同；<br>候选模型可以不同', 75, 335, 460, 65, size=25)

# ② 候选参数不同，对相同观测得到的贡献不同。虚线读取 A 曲线高度。
px0, py0, xs, ys = 690, 535, 43, 950
d.line('density-x', [(675,py0),(1130,py0)], color=GRAY, arrow='block')
d.line('density-y', [(px0,545),(px0,310)], color=GRAY, arrow='block')
d.text('density-y-label', r'\(f_\theta(x)\)', 695, 270, 135, 38, size=24)
d.text('density-x-label', r'寿命 \(x\)', 1030, 610, 130, 38, size=24)

def density(x, beta, eta, gamma):
    y=x-gamma
    return beta/eta*(y/eta)**(beta-1)*math.exp(-(y/eta)**beta) if y>0 else 0.

pars = [('a',2.25,4.5,.8,RED),('b',3.3,5.8,1.0,BLUE)]
for name,beta,eta,gamma,color in pars:
    pts=[(px0+x*xs, py0-density(x,beta,eta,gamma)*ys) for x in [j*.08 for j in range(121)]]
    d.line('density-curve-'+name, pts, color=color, width=3.5)
for i, (x,lab) in enumerate(zip(obs,[r'\(x_{(1)}\)',r'\(x_{(2)}\)',r'\(x_{(i)}\)',r'\(x_{(n)}\)'])):
    px,py=px0+x*xs,py0-density(x,*pars[0][1:4])*ys
    d.line(f'height-{i}', [(px,py0),(px,py)], color=RED, width=2, dashed=True)
    dot(f'height-point-{i}',px,py,color=RED)
    d.text(f'height-label-{i}',lab,px-43,545,86,38,size=23,align='center')
d.line('legend-a', [(690,660),(745,660)], color=RED, width=3.5)
d.text('legend-a-text',r'候选 \(A\)',760,640,300,42,size=25,color=RED)
d.line('legend-b', [(690,710),(745,710)], color=BLUE, width=3.5)
d.text('legend-b-text',r'候选 \(B\)',760,690,300,42,size=25,color=BLUE)
d.text('read-height', r'同一观测 \(x_i\)，在不同 \(\theta\) 下<br>得到不同的 \(f_\theta(x_i)\)', 665, 740, 480, 70, size=24, align='center')

# ③ 单点贡献像拼块一样汇合；原理是联合密度，取对数只是等价改写。
d.text('combine-heading', r'对同一个候选 \(\theta\)，<br>把全部观测贡献放进同一目标', 1270, 280, 470, 65, size=25)
tiles=[('f1',r'\(f_\theta(x_{(1)})\)',1275,370),('f2',r'\(f_\theta(x_{(2)})\)',1530,370),('fi',r'\(f_\theta(x_{(i)})\)',1275,500),('fn',r'\(f_\theta(x_{(n)})\)',1530,500)]
for key,label,x,y in tiles:
    d.box(key,label,x,y,180,80,color=RED,fill='#FFF0E8',size=28)
for i,(x,y) in enumerate([(1465,388),(1465,455),(1465,518)]):
    d.text('multiply-'+str(i),r'\(\times\)',x,y,56,45,size=29,bold=True,align='center')
d.line('contribution-bracket',[(1285,600),(1285,615),(1705,615),(1705,600)],color=RED,width=2.5)
d.box('joint-score',r'联合似然<br>\(L(\theta)=\prod_{i=1}^{n}f_\theta(x_i)\)',1280,640,450,100,color=RED,fill='#FFFFFF',size=28,bold=True)
d.line('combine-to-score',[(1505,615),(1505,640)],color=RED,width=2.5,arrow='block')
d.text('log-score',r'也可相加：\(\ell(\theta)=\ln L(\theta)\)<br>\(\ell(\theta)=\sum_{i=1}^{n}\ln f_\theta(x_i)\)',1265,750,480,95,size=25,align='center')

# ④ 多维参数搜索以一条示意截面呈现；峰是内点候选，不暗示普遍全局存在。
sx0, sy0, sw, sh = 1890,555,390,205
d.line('score-x',[(sx0-18,sy0),(sx0+sw+28,sy0)],color=GRAY,arrow='block')
d.line('score-y',[(sx0,sy0+8),(sx0,sy0-sh-18)],color=GRAY,arrow='block')
d.text('score-y-label',r'\(\ell(\theta)\)',1898,280,100,40,size=25)
def score_height(t):
    return .12 + .85*math.exp(-((t-.62)/.34)**2)
d.line('likelihood-section',[(sx0+t*sw,sy0-score_height(t)*sh) for t in [i/100 for i in range(101)]],color=GREEN,width=4)
for key,t,label in [('theta-a',.14,r'\(\theta_A\)'),('theta-b',.38,r'\(\theta_B\)'),('theta-peak',.62,r'\(\widehat\theta\)')]:
    xx,yy=sx0+t*sw,sy0-score_height(t)*sh
    d.line(key+'-guide',[(xx,sy0),(xx,yy)],color=GREEN,dashed=True)
    dot(key+'-point',xx,yy,color=GREEN,radius=6)
    d.text(key+'-label',label,xx-42,565,84,40,size=25,align='center')
d.text('local-peak','局部峰候选',2080,300,235,43,size=25,color=GREEN,align='center')
d.text('score-axis-label','候选参数（示意截面）',1885,610,420,38,size=24,align='center')
d.box('estimate',r'\(\widehat\theta=(\widehat\beta,\widehat\eta,\widehat\gamma)\)',1915,655,360,80,color=GREEN,fill='#E6F3EB',size=28,bold=True)
d.line('peak-to-estimate',[(2132,356),(2340,356),(2340,695),(2275,695)],color=GREEN,width=2.5,arrow='block')
d.text('implementation',r'数值实现：搜索评分或求解<br>内点得分方程 \(U(\theta)=0\)<br>比较目标值与边界响应。',1870,750,470,95,size=23)

# 稳定步骤箭头把图像串成过程；数值循环与基本原理分开标示。
d.line('step1-to-step2',[(587,535),(623,535)],color=RED,width=4,arrow='block')
d.line('step2-to-step3',[(1187,535),(1223,535)],color=RED,width=4,arrow='block')
d.text('all-contributions','把整组贡献送入评分',660,815,490,35,size=23,color=RED,align='center')
d.line('step3-to-step4',[(1787,535),(1823,535)],color=RED,width=4,arrow='block')
d.text('interfaces','方法差异的作用点：① 数据与位置处理　② 单点密度贡献　③ 联合目标　④ 得分方程与求解',65,905,2270,55,size=27,bold=True)
d.text('method-locations','例如：K–R改①；CMLE改②；罚似然改③；WMLE、Cohen–Whitten与DMMLE在相应得分关系上改④。',65,975,2270,55,size=24)
d.save(TARGET)

cells=ET.parse(TARGET).findall('.//mxCell')
ids=[c.get('id') for c in cells]
assert len(ids)==len(set(ids))
for cell in cells:
    if cell.get('edge')=='1':
        assert cell.get('source') in ids and cell.get('target') in ids
print(f'generated {TARGET.name}: {len(cells)} editable cells; XML and edge endpoints valid')
