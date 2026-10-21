"""从三参数Weibull密度构造似然，并展示有限内点的剖面求解链。"""
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy.optimize import brentq, minimize_scalar
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / '07-似然估计路线-信息处理流程.drawio'
RED, BLUE, GREEN, GRAY = '#AA5041', '#337695', '#357A63', '#6B7B8D'
WIDTH, HEIGHT = 3400, 1470
d = Diagram('likelihood-visual-flow-v11', '似然估计：构造函数、推导方程、剖面求解', WIDTH, HEIGHT)

def card(key, number, title, x, w, fill):
    d.panel(key, x, 190, w, 1015, fill=fill)
    d.text(key+'-title', f'{number} {title}', x+18, 207, w-36, 65, size=30, bold=True)

def down(key, x, y1, y2, color=GRAY):
    d.line(key, [(x,y1),(x,y2)], color=color, width=3, arrow='block')

# 同一固定模拟样本用于画求根与局部剖面曲线；不作方法性能比较。
sample = np.sort(2.+3.*np.random.default_rng(1).weibull(2.7,10))
def shape_score(beta, gamma):
    logs=np.log(sample-gamma)
    weights=np.exp(beta*(logs-logs.max()))
    return float(1/beta+logs.mean()-np.dot(weights,logs)/weights.sum())

def conditional(gamma):
    beta=brentq(lambda b:shape_score(b,gamma),.05,20.)
    eta=float(np.mean((sample-gamma)**beta)**(1/beta))
    ll=float(len(sample)*np.log(beta)-len(sample)*beta*np.log(eta)+(beta-1)*np.log(sample-gamma).sum()-(((sample-gamma)/eta)**beta).sum())
    return beta,eta,ll

def mark(key,x,y,color):
    d.box(key,'',x-6,y-6,12,12,color=color,fill=color,size=1)

d.text('title', '似然估计｜由分布密度构造似然函数，再推导方程求参数', 45, 20, 3310, 70, size=40, bold=True)
d.text('subtitle', r'独立同分布完整样本 \(D=(x_1,\ldots,x_n)\)，\(\theta=(\beta,\eta,\gamma)\)；以下以有限内点的剖面求解为例。', 50, 110, 3300, 48, size=28)
card('step1','①','写出模型与样本',30,540,'#F3F7FB')
card('step2','②','构造联合似然',630,590,'#FFF7F3')
card('step3','③','转成可求解的目标',1280,620,'#F2F8F4')
card('step4','④','内层：给定位置求形状、尺度',1960,730,'#F3F7FB')
card('step5','⑤','外层：求位置并核验',2750,620,'#F3F4F6')

# ① 单条模型曲线解释观测怎样进入密度，不比较A/B候选。
d.text('data-heading', '观测代入密度模型',65,305,470,45,size=27,bold=True)
dx=lambda x:95+(x-1.8)/6.5*420
def density(x):
    z=max((x-2.)/3.,0.)
    return 2.7/3.*z**1.7*np.exp(-z**2.7)
dy=lambda y:610-y*650
d.line('density-x',[(85,610),(530,610)],color=GRAY,width=2.5,arrow='block')
d.line('density-y',[(95,620),(95,385)],color=GRAY,width=2.5,arrow='block')
d.line('single-density',[(dx(x),dy(density(x))) for x in np.linspace(2.,8.1,120)],color=BLUE,width=4)
d.text('density-axis-label',r'\(f(x;\theta)\)',100,365,180,45,size=26)
d.text('lifetime-axis-label',r'寿命 \(x\)',400,660,135,45,size=25)
for i,index in enumerate([0,3,6,9]):
    x=float(sample[index]);xx=dx(x);yy=dy(density(x))
    d.line('observed-height-'+str(i),[(xx,610),(xx,yy)],color=RED,width=2,dashed=True)
    mark('observed-model-'+str(i),xx,yy,RED)
    mark('observed-data-'+str(i),xx,610,BLUE)
    d.text('observed-label-'+str(i),rf'\(x_{{({index+1})}}\)',xx-44,665 if i==1 else 620,88,40,size=24,align='center')
d.text('data-into-density',r'把 \(x_i\) 代入 \(f\)，形成各密度因子',65,725,470,50,size=26,align='center')
down('density-to-formula',300,790,830,BLUE)
d.box('shift',r'\(y_i=x_i-\gamma>0\)',70,840,460,70,color=BLUE,fill='#FFFFFF',size=28)
d.box('density',r'\(f(x_i;\theta)=\frac{\beta}{\eta}\left(\frac{y_i}{\eta}\right)^{\beta-1}\)<br>\(\qquad\times\exp\!\left[-\left(\frac{y_i}{\eta}\right)^\beta\right]\)',65,940,470,175,color=BLUE,fill='#FFFFFF',size=29)
d.text('support',r'\(\beta>0,\quad\eta>0,\quad\gamma<x_{(1)}\)',65,1130,470,55,size=26,align='center')

# ② 独立性把同一模型下的密度相乘，明确写出L本身。
d.text('independence', '独立观测 → 密度相乘',665,305,520,50,size=29,bold=True,color=RED)
for i,(x,label) in enumerate([(665,r'\(f(x_1;\theta)\)'),(880,r'\(\cdots\)'),(1035,r'\(f(x_n;\theta)\)')]):
    d.box('factor-'+str(i),label,x,405,150 if i!=1 else 90,85,color=RED,fill='#FFF0E8',size=27)
d.text('multiply-left',r'\(\times\)',815,425,65,45,size=29,align='center')
d.text('multiply-right',r'\(\times\)',970,425,65,45,size=29,align='center')
down('multiply-to-likelihood',925,510,570,RED)
d.box('joint-likelihood',r'\(L(\theta;D)=\prod_{i=1}^{n}f(x_i;\theta)\)<br><br>\(=\frac{\beta^n}{\eta^{n\beta}}\prod_{i=1}^{n}y_i^{\beta-1}\)<br><br>\(\quad\times\exp\!\left[-\sum_{i=1}^{n}\left(\frac{y_i}{\eta}\right)^\beta\right]\)',660,590,530,300,color=RED,fill='#FFFFFF',size=29)
d.text('likelihood-explanation',r'观测 \(x_i\) 已给定；<br>未知量 \(\beta,\eta,\gamma\) 留在函数中。',670,935,510,85,size=27,align='center')

# ③ 从乘积到对数和，不用峰形图或候选分数代替推导。
d.text('take-log','取对数：乘积变成求和',1310,305,560,50,size=29,bold=True,color=GREEN)
d.box('log-likelihood',r'\(\ell(\theta;D)=\ln L(\theta;D)\)<br><br>\(=n\ln\beta-n\beta\ln\eta\)<br><br>\(\quad+(\beta-1)\sum_{i=1}^{n}\ln y_i\)<br><br>\(\quad-\sum_{i=1}^{n}\left(\frac{y_i}{\eta}\right)^\beta\)',1310,395,560,305,color=GREEN,fill='#FFFFFF',size=29)
down('log-to-maximum',1590,720,770,GREEN)
d.box('maximum-principle',r'最大值存在时<br>\(\widehat\theta\in\operatorname*{arg\,max}_{\theta\in\Theta}\ell(\theta;D)\)',1310,790,560,120,color=GREEN,fill='#E6F3EB',size=29,bold=True)
d.text('derivative-intro',r'对参数求导，建立求解关系；<br>取对数不改变最大化解。',1315,945,550,80,size=27,align='center')

# ④ 展示消元和形状求根，不将求解留成一个黑箱。
d.box('fix-location',r'先给定 \(\gamma<x_{(1)}\)，得到 \(y_i\)',1990,305,670,75,color=BLUE,fill='#EAF3F8',size=28,bold=True)
down('location-to-scale',2325,395,435,BLUE)
d.box('scale-elimination',r'\(\frac{\partial\ell}{\partial\eta}=0\) → 尺度可解析消去<br>\(\widehat\eta(\beta,\gamma)=\left[\frac1n\sum_{i=1}^{n}y_i^\beta\right]^{1/\beta}\)',1990,450,670,140,color=BLUE,fill='#FFFFFF',size=28)
down('scale-to-shape',2325,605,645,BLUE)
d.box('shape-equation',r'代回 \(\frac{\partial\ell}{\partial\beta}=0\)，得 \(g(\beta;\gamma)=0\)<br>\(g=\frac1\beta+\frac1n\sum_{i=1}^{n}\ln y_i\)<br>\(\quad-\frac{\sum_{i=1}^{n}y_i^\beta\ln y_i}{\sum_{i=1}^{n}y_i^\beta}\)',1990,660,670,175,color=BLUE,fill='#FFFFFF',size=27)
fixed_gamma=2.2
root=conditional(fixed_gamma)[0]
bs=np.linspace(root*.55,root*1.6,90)
vals=[shape_score(b,fixed_gamma) for b in bs]
gx=lambda b:2040+(b-bs[0])/(bs[-1]-bs[0])*550
gy=lambda v:1095-(v-min(vals))/(max(vals)-min(vals))*185
zero=gy(0.)
d.line('shape-root-x',[(2020,zero),(2615,zero)],color=GRAY,width=2.3,arrow='block')
d.line('shape-root-y',[(2040,1105),(2040,890)],color=GRAY,width=2.3,arrow='block')
d.line('shape-root-curve',[(gx(b),gy(v)) for b,v in zip(bs,vals)],color=BLUE,width=4)
mark('shape-root-point',gx(root),zero,BLUE)
d.line('shape-root-guide',[(gx(root),zero),(gx(root),1105)],color=BLUE,dashed=True)
d.text('root-y-label',r'\(g(\beta;\gamma)\)',2050,855,220,40,size=25)
d.text('root-zero-label',r'\(0\)',1980,zero-20,60,40,size=25)
d.text('root-beta-label',r'\(\beta\)',2605,zero-45,60,45,size=27)
d.text('root-location-label',r'\(\widehat\beta(\gamma)\)',gx(root)-70,1100,140,45,size=25,align='center')
d.text('root-caption','数值求根：找到曲线与零线的交点',2025,1145,600,45,size=26,align='center')

# ⑤ 剖面值进入外层位置搜索，虚线回到内层；最后进行域和边界核验。
d.text('profile-heading', '把内层解代回对数似然',2780,305,560,50,size=28,bold=True,color=GRAY)
d.box('profile-likelihood',r'\(\ell_p(\gamma)=\ell\bigl(\widehat\beta(\gamma),\widehat\eta(\gamma),\gamma;D\bigr)\)',2780,390,560,100,color=GRAY,fill='#FFFFFF',size=27)
gs=np.linspace(2.15,2.805,95);lls=[conditional(g)[2] for g in gs]
peak=minimize_scalar(lambda g:-conditional(g)[2],bounds=(2.35,2.78),method='bounded').x
px=lambda g:2825+(g-gs[0])/(gs[-1]-gs[0])*460
py=lambda value:815-(value-min(lls))/(max(lls)-min(lls))*200
d.line('profile-x',[(2805,835),(3320,835)],color=GRAY,width=2.3,arrow='block')
d.line('profile-y',[(2825,845),(2825,565)],color=GRAY,width=2.3,arrow='block')
d.line('profile-curve',[(px(g),py(value)) for g,value in zip(gs,lls)],color=GREEN,width=4)
for i,(a,b) in enumerate([(2.3,2.4),(2.47,2.55)]):
    d.line('profile-update-'+str(i),[(px(g),py(conditional(g)[2])) for g in np.linspace(a,b,8)],color=RED,width=4,arrow='block')
mark('profile-peak',px(peak),py(conditional(peak)[2]),GREEN)
d.line('profile-peak-guide',[(px(peak),py(conditional(peak)[2])),(px(peak),835)],color=GREEN,dashed=True)
d.text('profile-axis-label',r'\(\ell_p(\gamma)\)',2830,535,180,45,size=26)
d.text('profile-gamma-label',r'\(\gamma\)',3300,840,55,45,size=27)
d.text('profile-peak-label',r'\(\widehat\gamma\)',px(peak)-45,840,90,45,size=26,align='center')
d.text('search-caption','沿剖面函数搜索有限局部峰',2810,890,510,45,size=26,align='center')
d.box('location-search',r'更新 \(\gamma\) → 重算④ → 继续搜索<br>按给定参数域或局部极大规则核验',2780,970,560,90,color=GRAY,fill='#FFFFFF',size=27)
down('location-to-result',3060,1070,1100)
d.box('result',r'恢复 \((\widehat\beta,\widehat\eta,\widehat\gamma)\)<br>核验目标与边界行为',2780,1110,560,80,color=GREEN,fill='#E6F3EB',size=27,bold=True)
d.line('location-loop',[(2780,1015),(2720,1015),(2720,1250),(1930,1250),(1930,342),(1990,342)],color=GRAY,width=3,arrow='block',dashed=True)
d.text('location-loop-label',r'更新 \(\gamma\)，重算内层',2370,1210,330,40,size=24,color=GRAY,align='center')

for i,(x1,x2) in enumerate([(585,615),(1235,1265),(1915,1945),(2705,2735)]):
    d.line('main-flow-'+str(i),[(x1,620),(x2,620)],color=RED if i<2 else BLUE,width=4,arrow='block')
d.text('method-locations','后续方法的改动位置：①样本与位置处理；②似然项；③目标修正；④估计方程；④—⑤既定目标的求解程序。',55,1300,3290,55,size=28,bold=True)
d.text('scope-note',r'同一模拟样本的示意曲线：观测代入、方程求根、有限局部峰搜索。无约束三参数似然可能无界，取解需核验参数域与边界。',55,1370,3290,50,size=27)
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
        assert 0<=x<=x+w<=WIDTH and 0<=y<=y+h<=HEIGHT,cell.get('id')
print(f'generated {TARGET.name}: {len(cells)} editable cells; XML, edge endpoints, and canvas bounds valid')
