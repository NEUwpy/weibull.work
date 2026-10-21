"""从三参数Weibull密度构造似然，并展示有限内点的剖面求解链。"""
from pathlib import Path
import xml.etree.ElementTree as ET
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / '07-似然估计路线-信息处理流程.drawio'
RED, BLUE, GREEN, GRAY = '#AA5041', '#337695', '#357A63', '#6B7B8D'
WIDTH, HEIGHT = 3400, 1320
d = Diagram('likelihood-visual-flow-v11', '似然估计：构造函数、推导方程、剖面求解', WIDTH, HEIGHT)

def card(key, number, title, x, w, fill):
    d.panel(key, x, 190, w, 875, fill=fill)
    d.text(key+'-title', f'{number} {title}', x+18, 207, w-36, 65, size=30, bold=True)

def down(key, x, y1, y2, color=GRAY):
    d.line(key, [(x,y1),(x,y2)], color=color, width=3, arrow='block')

d.text('title', '似然估计｜由分布密度构造似然函数，再推导方程求参数', 45, 20, 3310, 70, size=40, bold=True)
d.text('subtitle', r'独立同分布完整样本 \(D=(x_1,\ldots,x_n)\)，\(\theta=(\beta,\eta,\gamma)\)；以下以有限内点的剖面求解为例。', 50, 110, 3300, 48, size=28)
card('step1','①','写出模型与样本',30,540,'#F3F7FB')
card('step2','②','构造联合似然',630,590,'#FFF7F3')
card('step3','③','转成可求解的目标',1280,620,'#F2F8F4')
card('step4','④','内层：给定位置求形状、尺度',1960,730,'#F3F7FB')
card('step5','⑤','外层：求位置并核验',2750,620,'#F3F4F6')

# ① 观测只代入模型，不比较候选曲线。
d.text('data-heading', '一组观测寿命',65,305,470,45,size=27,bold=True)
d.line('data-axis',[(85,420),(520,420)],color=BLUE,width=3,arrow='block')
for i,(x,label) in enumerate([(115,r'\(x_{(1)}\)'),(210,r'\(x_{(2)}\)'),(355,r'\(x_{(i)}\)'),(465,r'\(x_{(n)}\)')]):
    d.box('sample-'+str(i),'',x-6,414,12,12,color=BLUE,fill=BLUE,size=1,extra='ellipse;')
    d.text('sample-label-'+str(i),label,x-46,445,92,44,size=26,align='center')
d.box('shift',r'令 \(y_i=x_i-\gamma>0\)',70,515,460,85,color=BLUE,fill='#FFFFFF',size=29)
d.text('density-heading','三参数 Weibull 密度',65,655,470,45,size=27,bold=True)
d.box('density',r'\(f(x_i;\theta)=\frac{\beta}{\eta}\left(\frac{y_i}{\eta}\right)^{\beta-1}\)<br>\(\qquad\times\exp\!\left[-\left(\frac{y_i}{\eta}\right)^\beta\right]\)',65,720,470,185,color=BLUE,fill='#FFFFFF',size=29)
d.text('support',r'\(\beta>0,\quad\eta>0,\quad\gamma<x_{(1)}\)',65,945,470,65,size=27,align='center')

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
d.box('shape-equation',r'代回 \(\frac{\partial\ell}{\partial\beta}=0\)，数值求形状<br><br>\(\frac1\beta+\frac1n\sum_{i=1}^{n}\ln y_i\)<br>\(-\frac{\sum_{i=1}^{n}y_i^\beta\ln y_i}{\sum_{i=1}^{n}y_i^\beta}=0\)',1990,660,670,210,color=BLUE,fill='#FFFFFF',size=28)
down('shape-to-conditional',2325,885,925,BLUE)
d.box('conditional-estimates',r'得到 \(\widehat\beta(\gamma)\)，<br>再恢复 \(\widehat\eta(\gamma)\)',1990,940,670,90,color=BLUE,fill='#EAF3F8',size=28,bold=True)

# ⑤ 剖面值进入外层位置搜索，虚线回到内层；最后进行域和边界核验。
d.text('profile-heading', '把内层解代回对数似然',2780,305,560,50,size=28,bold=True,color=GRAY)
d.box('profile-likelihood',r'\(\ell_p(\gamma)=\ell\bigl(\widehat\beta(\gamma),\widehat\eta(\gamma),\gamma;D\bigr)\)',2780,390,560,100,color=GRAY,fill='#FFFFFF',size=27)
down('profile-to-location',3060,505,545)
d.box('location-search',r'外层求 \(\gamma\)<br>按预先约定的参数域或局部极大规则，<br>搜索剖面对数似然；检查支持边界。',2780,560,560,150,color=GRAY,fill='#FFFFFF',size=27)
down('location-to-result',3060,725,765)
d.box('result',r'\((\widehat\beta,\widehat\eta,\widehat\gamma)\)<br>核验参数域、最大化要求和边界行为',2780,780,560,125,color=GREEN,fill='#E6F3EB',size=28,bold=True)
d.text('no-root-guarantee','方程根不自动等于最大似然估计；<br>不能把无界情形当作有限全局解。',2780,945,560,85,size=26,align='center')
d.line('location-loop',[(2780,635),(2720,635),(2720,1120),(1930,1120),(1930,342),(1990,342)],color=GRAY,width=3,arrow='block',dashed=True)
d.text('location-loop-label',r'更新 \(\gamma\)，重算内层',2370,1080,330,40,size=24,color=GRAY,align='center')

for i,(x1,x2) in enumerate([(585,615),(1235,1265),(1915,1945),(2705,2735)]):
    d.line('main-flow-'+str(i),[(x1,620),(x2,620)],color=RED if i<2 else BLUE,width=4,arrow='block')
d.text('method-locations','后续方法的改动位置：①样本与位置处理；②似然项；③目标修正；④估计方程；④—⑤既定目标的求解程序。',55,1170,3290,55,size=28,bold=True)
d.text('scope-note',r'本图展示原始 MLE 的构造与一种求解组织方式。无约束三参数似然可能无界；计算前需明确参数域或有限局部极大约定。',55,1240,3290,50,size=27)
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
