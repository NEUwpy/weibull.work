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
d = Diagram('likelihood-visual-flow-v11', '似然估计：四步可视信息处理流程', 2000, 1530)


def dot(key, x, y, *, color=RED, radius=6):
    d.box(key, '', x-radius, y-radius, radius*2, radius*2,
          color=color, fill=color, size=1, extra='ellipse;')


def step(key, number, title, x, y, fill):
    d.panel(key, x, y, 900, 520, fill=fill)
    d.text(key+'-title', f'{number} {title}', x+25, y+18, 850, 55, size=30, bold=True)


d.text('title', '似然估计｜固定观测，比较不同参数下整组样本的密度贡献', 45, 20, 1910, 65, size=36, bold=True)
d.text('subtitle', '独立完整样本；θ=(β,η,γ)，β>0、η>0、γ<x₍₁₎。图中的曲线和参数截面均为原理示意。', 50, 100, 1900, 48, size=25)

step('step1', '①', '固定样本，提出候选参数', 40, 180, '#F3F7FB')
step('step2', '②', '在每个观测处读出候选密度', 1060, 180, '#FFF7F3')
step('step3', '③', '将全部密度贡献组成同一评分', 40, 825, '#FFF8F0')
step('step4', '④', '比较评分，确定参数候选', 1060, 825, '#F2F8F4')

# ① 寿命点固定不动；候选模型只改变这些点在密度曲线上的高度。
d.text('observed-label', '已经观测到的寿命', 80, 280, 810, 45, size=27, bold=True)
d.line('data-axis', [(100, 435), (865, 435)], color=GRAY, width=2, arrow='block')
obs = [2.1, 3.3, 5.6, 8.2]
for i, (x, lab) in enumerate(zip(obs, ['x₍₁₎', 'x₍₂₎', 'x₍ᵢ₎', 'x₍ₙ₎'])):
    px = 125+x*76
    d.line(f'data-tick-{i}', [(px,422),(px,448)], color=BLUE, width=2)
    dot(f'data-point-{i}', px, 400, color=BLUE, radius=8)
    d.text(f'data-label-{i}', lab, px-52, 455, 104, 42, size=25, align='center')
d.text('data-axis-label', '寿命 x', 777, 491, 130, 38, size=24)
d.box('candidate-a', '候选 A<br>θA=(βA,ηA,γA)', 95, 565, 330, 95, color=RED, fill='#FFF1EB', size=26)
d.box('candidate-b', '候选 B<br>θB=(βB,ηB,γB)', 550, 565, 330, 95, color=BLUE, fill='#EFF7FB', size=26)
d.text('data-fixed', '观测位置相同；候选模型可以不同', 95, 340, 780, 45, size=26)

# ② 候选参数不同，对相同观测得到的贡献不同。虚线读取 A 曲线高度。
px0, py0, xs, ys = 1135, 525, 61, 1200
d.line('density-x', [(1117,py0),(1904,py0)], color=GRAY, arrow='block')
d.line('density-y', [(px0,535),(px0,292)], color=GRAY, arrow='block')
d.text('density-y-label', 'fθ(x)', 1145, 282, 135, 38, size=24)
d.text('density-x-label', '寿命 x', 1795, 574, 130, 38, size=24)

def density(x, beta, eta, gamma):
    y=x-gamma
    return beta/eta*(y/eta)**(beta-1)*math.exp(-(y/eta)**beta) if y>0 else 0.

pars = [('a',2.25,4.5,.8,RED),('b',3.3,5.8,1.0,BLUE)]
for name,beta,eta,gamma,color in pars:
    pts=[(px0+x*xs, py0-density(x,beta,eta,gamma)*ys) for x in [j*.08 for j in range(154)]]
    d.line('density-curve-'+name, pts, color=color, width=3.5)
for i, (x,lab) in enumerate(zip(obs,['x₍₁₎','x₍₂₎','x₍ᵢ₎','x₍ₙ₎'])):
    px,py=px0+x*xs,py0-density(x,*pars[0][1:4])*ys
    d.line(f'height-{i}', [(px,py0),(px,py)], color=RED, width=2, dashed=True)
    dot(f'height-point-{i}',px,py,color=RED)
    d.text(f'height-label-{i}',lab,px-47,533,94,38,size=23,align='center')
d.line('legend-a', [(1170,630),(1230,630)], color=RED, width=3.5)
d.text('legend-a-text','候选 A',1240,610,230,42,size=25,color=RED)
d.line('legend-b', [(1480,630),(1540,630)], color=BLUE, width=3.5)
d.text('legend-b-text','候选 B',1550,610,230,42,size=25,color=BLUE)
d.text('read-height', '同一观测 xᵢ，在不同 θ 下得到不同的 fθ(xᵢ)', 1100, 659, 820, 35, size=24, align='center')

# ③ 单点贡献像拼块一样汇合；原理是联合密度，取对数只是等价改写。
d.text('combine-heading', '对同一个候选 θ，把每个观测贡献都放进来', 80, 920, 820, 45, size=26)
tiles=[('f1','fθ(x₍₁₎)',90),('f2','fθ(x₍₂₎)',290),('fi','fθ(x₍ᵢ₎)',490),('fn','fθ(x₍ₙ₎)',690)]
for key,label,x in tiles:
    d.box(key,label,x,1005,160,100,color=RED,fill='#FFF0E8',size=28)
for i,x in enumerate([251,451,651]):
    d.text('multiply-'+str(i),'×',x,1032,36,45,size=31,bold=True,align='center')
d.line('contribution-bracket',[(110,1133),(110,1150),(830,1150),(830,1133)],color=RED,width=2.5)
d.box('joint-score','联合似然  L(θ)=∏ᵢ fθ(xᵢ)',185,1195,610,70,color=RED,fill='#FFFFFF',size=29,bold=True)
d.line('combine-to-score',[(490,1150),(490,1195)],color=RED,width=2.5,arrow='block')
d.text('log-score','也可相加：ℓ(θ)=ln L(θ)=Σᵢ ln fθ(xᵢ)',90,1280,790,50,size=26,align='center')

# ④ 多维参数搜索以一条示意截面呈现；峰是内点候选，不暗示普遍全局存在。
sx0, sy0, sw, sh = 1140,1190,565,205
d.line('score-x',[(sx0-18,sy0),(sx0+sw+28,sy0)],color=GRAY,arrow='block')
d.line('score-y',[(sx0,sy0+8),(sx0,sy0-sh-18)],color=GRAY,arrow='block')
d.text('score-y-label','ℓ(θ)',1148,956,100,40,size=25)
def score_height(t):
    return .12 + .85*math.exp(-((t-.62)/.34)**2)
d.line('likelihood-section',[(sx0+t*sw,sy0-score_height(t)*sh) for t in [i/100 for i in range(101)]],color=GREEN,width=4)
for key,t,label in [('theta-a',.14,'θA'),('theta-b',.38,'θB'),('theta-peak',.62,'θ̂')]:
    xx,yy=sx0+t*sw,sy0-score_height(t)*sh
    d.line(key+'-guide',[(xx,sy0),(xx,yy)],color=GREEN,dashed=True)
    dot(key+'-point',xx,yy,color=GREEN,radius=6)
    d.text(key+'-label',label,xx-42,1198,84,40,size=25,align='center')
d.text('local-peak','局部峰候选',1430,925,235,43,size=25,color=GREEN,align='center')
d.text('score-axis-label','候选参数（示意截面）',1260,1235,390,38,size=24,align='center')
d.box('estimate','θ̂<br>(β̂,η̂,γ̂)',1730,1005,200,140,color=GREEN,fill='#E6F3EB',size=27,bold=True)
d.line('peak-to-estimate',[(1490,995),(1710,995),(1710,1075),(1730,1075)],color=GREEN,width=2.5,arrow='block')
d.text('implementation','数值实现：搜索评分，或解内点得分方程 U(θ)=0<br>再比较目标值与边界响应。',1100,1280,820,64,size=23)

# 稳定步骤箭头把图像串成过程；数值循环与基本原理分开标示。
d.line('step1-to-step2',[(952,440),(1048,440)],color=RED,width=4,arrow='block')
d.line('step2-to-step3',[(1510,715),(1510,755),(490,755),(490,812)],color=RED,width=4,arrow='block')
d.text('all-contributions','把整组贡献送入评分',745,707,620,45,size=25,color=RED,align='center')
d.line('step3-to-step4',[(952,1090),(1048,1090)],color=RED,width=4,arrow='block')
d.text('interfaces','方法差异的作用点：① 数据与位置处理　② 单点密度贡献　③ 联合目标　④ 得分方程与求解',65,1390,1870,52,size=27,bold=True)
d.text('method-locations','例如：K–R改①；CMLE改②；罚似然改③；WMLE、Cohen–Whitten与DMMLE在相应得分关系上改④。',65,1450,1870,45,size=24)
d.save(TARGET)

cells=ET.parse(TARGET).findall('.//mxCell')
ids=[c.get('id') for c in cells]
assert len(ids)==len(set(ids))
for cell in cells:
    if cell.get('edge')=='1':
        assert cell.get('source') in ids and cell.get('target') in ids
print(f'generated {TARGET.name}: {len(cells)} editable cells; XML and edge endpoints valid')
