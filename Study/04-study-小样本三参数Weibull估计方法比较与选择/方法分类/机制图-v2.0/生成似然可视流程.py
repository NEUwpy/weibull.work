"""似然原理的同一条构造链：固定数据、参数函数、逐点相乘、联合最大化。"""
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy.optimize import minimize_scalar
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / '07-似然估计路线-信息处理流程.drawio'
W,H=2850,1450
BLUE,GREEN,ORANGE,GRAY='#337695','#357A63','#BB693C','#6B7B8D'
COLORS=[BLUE,GREEN,ORANGE]
DATA=np.array([3.1,4.6,6.2])
ETA,GAMMA=3.,2.
B0=1.4
BS=np.linspace(.4,5.2,150)

def density(x,beta):
    z=np.maximum((np.asarray(x)-GAMMA)/ETA,0.)
    return beta/ETA*z**(beta-1)*np.exp(-z**beta)

def factors(beta):
    return density(DATA,beta)

def joint(beta):
    return float(np.prod(factors(beta)))

BEST=minimize_scalar(lambda b:-joint(b),bounds=(.4,5.2),method='bounded').x
d=Diagram('likelihood-visual-flow-v11','似然原理：固定观测、参数函数、联合最大化',W,H)

def dot(key,x,y,color,r=6):
    d.box(key,'',x-r,y-r,r*2,r*2,color=color,fill=color,size=1)

def panel(key,x,w,number,title,fill):
    d.panel(key,x,235,w,975,fill=fill)
    d.text(key+'-title',number+' '+title,x+20,250,w-40,60,size=32,bold=True)

d.text('title','似然原理｜固定样本，把各观测的参数函数相乘，再求联合最大值',45,20,2760,70,size=39,bold=True)
d.text('core',r'L1 固定样本，将观测因子构成参数的似然函数；L2 在同一似然函数上求最大值。',50,100,2750,55,size=29,bold=True)
d.text('slice-scope',r'图示用 \(D=(3.1,4.6,6.2)\)，固定 \(\eta_0=3,\gamma_0=2\)，只画 \(\beta\) 截面；蓝灰竖线均表示同一个 \(\beta_0=1.4\)。',50,170,2750,48,size=26)
panel('data-panel',30,690,'①','固定同一组观测', '#F3F7FB')
panel('factor-panel',790,870,'②','L1 将密度因子看作参数函数', '#F6F8FA')
panel('joint-panel',1730,1090,'③','L1 构造联合似然 → L2 最大化', '#F2F8F4')

# ① 横轴是寿命x；在同一beta0曲线上标出三个观测。
d.text('model-caption',r'已观测的 \(x_1,x_2,x_3\) 保持不变',65,345,620,50,size=28,bold=True)
xx=lambda x:100+(x-1.8)/(8.7-1.8)*545
yy=lambda f:740-f*1050
d.line('model-x',[(85,740),(670,740)],color=GRAY,width=2.6,arrow='block')
d.line('model-y',[(100,750),(100,440)],color=GRAY,width=2.6,arrow='block')
d.line('model-curve',[(xx(x),yy(density(x,B0))) for x in np.linspace(2.01,8.5,130)],color=GRAY,width=4)
d.text('model-y-label',r'\(f(x;\beta_0,\eta_0,\gamma_0)\)',105,410,470,45,size=27)
d.text('model-x-label',r'寿命 \(x\)',530,805,145,45,size=27)
for i,(x,color) in enumerate(zip(DATA,COLORS)):
    px,py=xx(x),yy(density(x,B0))
    d.line('observation-guide-'+str(i),[(px,740),(px,py)],color=color,width=2.5,dashed=True)
    dot('observation-'+str(i),px,740,color)
    dot('density-value-'+str(i),px,py,color)
    d.text('observation-label-'+str(i),rf'\(x_{i+1}\)',px-45,755,90,45,size=28,color=color,align='center')
d.box('same-model',r'同一个 Weibull 模型；\(z_i=(x_i-\gamma_0)/\eta_0\)<br>\(f(x_i;\beta,\eta_0,\gamma_0)=\frac{\beta}{\eta_0}z_i^{\beta-1}e^{-z_i^\beta}\)',65,880,620,170,color=GRAY,fill='#FFFFFF',size=28)
d.text('change-variable',r'固定 \(x_i\)，让 \(\beta\) 连续变化',65,1080,620,55,size=29,bold=True,align='center')
d.text('model-not-change-data','变化的是参数；三个观测始终不变。',70,1150,610,45,size=26,align='center')

# ② 三条函数共享同一beta范围、同一横坐标位置；不能分别最大化。
d.box('factor-definition',r'\(g_i(\beta)=f(x_i;\beta,\eta_0,\gamma_0)\)',825,335,800,90,color=GRAY,fill='#FFFFFF',size=30)
fx=lambda b:910+(b-BS[0])/(BS[-1]-BS[0])*640
parameter_x=fx(B0)
d.line('factor-common-guide',[(parameter_x,455),(parameter_x,1090)],color=GRAY,width=2.2,dashed=True)
for i,color in enumerate(COLORS):
    top=470+i*210
    bottom=top+150
    values=np.array([factors(b)[i] for b in BS])
    fmax=float(values.max())*1.08
    fy=lambda value:bottom-float(value)/fmax*125
    d.line('factor-axis-'+str(i),[(890,bottom),(1580,bottom)],color=GRAY,width=2.2,arrow='block')
    d.line('factor-y-'+str(i),[(910,bottom+5),(910,top-10)],color=GRAY,width=2.2,arrow='block')
    d.line('factor-curve-'+str(i),[(fx(b),fy(v)) for b,v in zip(BS,values)],color=color,width=4)
    dot('factor-same-beta-'+str(i),parameter_x,fy(factors(B0)[i]),color)
    d.text('factor-name-'+str(i),rf'\(g_{i+1}(\beta)\)',920,top-35,205,45,size=28,color=color)
    d.text('factor-beta-'+str(i),r'\(\beta\)',1560,bottom-5,60,45,size=28)
d.text('factor-beta-zero',r'\(\beta_0\)',parameter_x+15,1090,80,45,size=28,color=GRAY,align='center')
d.text('factor-shared-axis',r'三图共用同一 \(\beta\) 范围',1130,1140,490,45,size=26,align='center')

# ③ 乘的是同一beta下的三个函数值；所有beta的乘积组成整条L。
d.box('product',r'\(L(\beta;D,\eta_0,\gamma_0)=g_1(\beta)\,g_2(\beta)\,g_3(\beta)\)',1765,335,1020,95,color=GREEN,fill='#FFFFFF',size=30,bold=True)
d.text('pointwise-product',r'对每一个 \(\beta\) 相乘，形成整个似然函数',1775,455,1000,50,size=29,bold=True,color=GREEN,align='center')
lx=lambda b:1830+(b-BS[0])/(BS[-1]-BS[0])*870
likelihoods=np.array([joint(b) for b in BS])
scale=float(likelihoods.max())*1.12
ly=lambda value:920-value/scale*320
d.line('joint-x',[(1810,920),(2740,920)],color=GRAY,width=2.6,arrow='block')
d.line('joint-y',[(1830,930),(1830,550)],color=GRAY,width=2.6,arrow='block')
d.text('joint-y-label',r'\(L(\beta;D,\eta_0,\gamma_0)\)',1840,515,650,45,size=28)
d.line('joint-function',[(lx(b),ly(v)) for b,v in zip(BS,likelihoods)],color=GREEN,width=4.5)
d.line('joint-beta-zero',[(lx(B0),590),(lx(B0),920)],color=GRAY,width=2.2,dashed=True)
dot('joint-product-point',lx(B0),ly(joint(B0)),GRAY)
d.text('joint-beta-zero-label',r'\(\beta_0\)',lx(B0)+12,935,90,45,size=28,color=GRAY,align='center')
d.line('joint-maximum-guide',[(lx(BEST),ly(joint(BEST))),(lx(BEST),920)],color=GREEN,width=2.5,dashed=True)
dot('joint-maximum',lx(BEST),ly(joint(BEST)),GREEN,r=8)
d.text('joint-maximum-label',r'\(\beta^{\star}\)',lx(BEST)-50,935,100,45,size=29,color=GREEN,align='center')
# 同一联合函数上的连续最大化，与前面的乘积构造共享目标。
d.line('joint-search',[(lx(b),ly(joint(b))) for b in np.linspace(1.45,BEST-.10,15)],color=ORANGE,width=5,arrow='block')
d.text('maximization-label','在这个联合函数上求最大值',2250,555,490,50,size=27,color=GREEN,bold=True)
d.box('conditional-maximum',r'本图截面最大点<br>\(\beta^{\star}=\operatorname*{arg\,max}_{\beta>0}L(\beta;D,\eta_0,\gamma_0)\)',1770,1020,1010,130,color=GREEN,fill='#E6F3EB',size=29,bold=True)

# 水平主线与相同参数位置的取值—乘积连线。
d.line('data-to-factors',[(735,680),(775,680)],color=GRAY,width=4,arrow='block')
d.line('factors-to-product',[(1675,680),(1715,680)],color=GREEN,width=4,arrow='block')
d.text('multiply-label',r'\(\times\)',1670,605,60,55,size=30,align='center',color=GREEN)
d.line('point-product-link',[(parameter_x,1090),(parameter_x,1260),(lx(B0),1260),(lx(B0),ly(joint(B0)))],color=GRAY,width=2.4,arrow='block',dashed=True)
d.text('point-product-link-label',r'同一个 \(\beta_0\)：\(g_1(\beta_0)g_2(\beta_0)g_3(\beta_0)=L(\beta_0;D,\eta_0,\gamma_0)\)',1100,1215,850,40,size=25,color=GRAY,align='center')
d.text('three-parameter',r'有限最大值存在时，完整三参数估计满足 \(\widehat\theta\in\operatorname*{arg\,max}_{\theta\in\Theta}L(\theta;D)\)，\(\theta=(\beta,\eta,\gamma)\)；在三维参数域内处理同一个联合似然。',50,1310,2750,80,size=28,bold=True)
d.text('implementation',r'解析推导、得分方程或数值优化用于实现这个最大化。参数域、支持边界及有限解的存在性仍需核验。',50,1400,2750,45,size=26)
d.save(TARGET)

cells=ET.parse(TARGET).findall('.//mxCell');ids=[c.get('id') for c in cells]
assert len(ids)==len(set(ids))
for cell in cells:
    if cell.get('edge')=='1':assert cell.get('source') in ids and cell.get('target') in ids
    if cell.get('vertex')=='1':
        geo=cell.find('mxGeometry');x,y,w,h=(float(geo.get(k,'0')) for k in ('x','y','width','height'))
        assert 0<=x<=x+w<=W and 0<=y<=y+h<=H,cell.get('id')
assert abs(joint(B0)-np.prod(factors(B0)))<1e-14
assert .4<BEST<5.2
print(f'generated {TARGET.name}: {len(cells)} cells; same-sample pointwise product and canvas valid; conditional beta={BEST:.6f}')
