"""似然路线细图：短机制链与数据、方程、目标三处改动。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '01-似然估计路线-机制图.drawio'
RED, BLUE, GREEN, ORANGE = '#A94F40', '#2D6D91', '#347B68', '#B07530'
GRAY, INK = '#A4ADB8', '#66788B'
d = Diagram('likelihood-mechanism-v20-wide', '似然构造、求解与改动接口', 3200, 1400)


def dot(key, x, y, color, radius=7, fill=None):
    d.box(key, '', x-radius, y-radius, radius*2, radius*2,
          color=color, fill=fill or color, size=1, extra='ellipse;')


def axis(key, x, y, w, h, xlabel='', ylabel=''):
    d.line(key+'-x', [(x, y), (x+w, y)], color=INK, arrow='block', width=1.8)
    d.line(key+'-y', [(x, y), (x, y-h)], color=INK, arrow='block', width=1.8)
    if xlabel:
        d.text(key+'-xl', xlabel, x+w-45, y+10, 95, 40, size=24)
    if ylabel:
        d.text(key+'-yl', ylabel, x+5, y-h-28, 210, 45, size=25)


def curve(key, x, y, w, h, fn, color, dashed=False):
    d.line(key, [(x+w*t/80, y-h*fn(t/80)) for t in range(81)],
           color=color, width=3.5, dashed=dashed)


def weibull(t):
    z = t*9
    return 2.25/4.5*(z/4.5)**1.25*math.exp(-(z/4.5)**2.25)*5.8 if z > 0 else 0


# 共同机制只占上部：同一批点 → 密度贡献 → 联合目标 → 最大化。
d.panel('core-strip', 40, 35, 3120, 345, fill='#FAFBFC')
d.text('sample-heading', '① 观测', 65, 55, 400, 48, size=31, bold=True, color=RED)
d.line('sample-axis', [(95, 240), (475, 240)], color=INK, width=2, arrow='block')
for i, xx in enumerate([130, 195, 285, 405]):
    dot(f'sample-dot-{i}', xx, 240, BLUE)
    d.text(f'sample-label-{i}', [r'\(x_{(1)}\)', r'\(x_{(2)}\)', r'\(x_{(i)}\)', r'\(x_{(n)}\)'][i],
           xx-55, 260, 110, 42, size=24, align='center')
d.text('sample-symbol', r'\(D=\{x_1,\ldots,x_n\}\)', 90, 125, 380, 50, size=27)

d.text('density-heading', '② 密度贡献', 600, 55, 670, 48, size=31, bold=True, color=RED)
axis('density', 625, 285, 600, 145, r'\(x\)', r'\(f_\theta(x)\)')
curve('density-curve', 625, 285, 565, 145, weibull, RED)
for i, t in enumerate([.12, .28, .52, .80]):
    xx, yy = 625+565*t, 285-145*weibull(t)
    d.line(f'density-guide-{i}', [(xx,285),(xx,yy)], color=BLUE, dashed=True)
    dot(f'density-dot-{i}', xx, yy, BLUE, 5)
d.text('density-values', r'\(f_\theta(x_1),\ldots,f_\theta(x_n)\)', 650, 315, 550, 40, size=26, align='center')

d.text('product-heading', '③ 联合目标', 1385, 55, 670, 48, size=31, bold=True, color=BLUE)
d.box('product', r'\(L(\theta)=\prod_{i=1}^{n}f_\theta(x_i)\)', 1390, 145, 675, 85,
      color=BLUE, fill='#F3F7FC', size=32, bold=True)
d.text('log', r'\(\ell(\theta)=\ln L(\theta)\)', 1410, 265, 635, 52, size=30, align='center')

d.text('maximize-heading', '④ 最大化', 2235, 55, 850, 48, size=31, bold=True, color=GREEN)
axis('maximum', 2280, 300, 570, 165, r'\(\theta\)', r'\(\ell(\theta)\)')
curve('maximum-curve', 2280, 300, 525, 165, lambda t: .88-2.5*(t-.55)**2, GREEN)
d.line('maximum-guide', [(2569,300),(2569,155)], color=GREEN, dashed=True)
dot('maximum-dot', 2569, 155, GREEN, 7)
d.text('estimate', r'\(\widehat\theta\)', 2855, 187, 210, 80, size=38, bold=True, color=GREEN, align='center')
for key, a, b in [('sample-density',500,575),('density-product',1280,1355),('product-max',2110,2205)]:
    d.line(key, [(a,215),(b,215)], color=INK, width=3, arrow='block')

# 三处改动用独立的可编辑小图说明；不把公式清单当作机制图。
d.panel('data-panel', 40, 445, 1000, 915, fill='#F3F8F5', color='#C6DDD2')
d.panel('equation-panel', 1100, 445, 1000, 915, fill='#F4F7FC', color='#CED8EA')
d.panel('target-panel', 2160, 445, 1000, 915, fill='#FFF8F0', color='#E3D3BC')
d.text('data-title', '改数据', 65, 465, 930, 50, size=34, bold=True, color=GREEN)
d.text('equation-title', '改方程', 1125, 465, 930, 50, size=34, bold=True, color=BLUE)
d.text('target-title', '改目标', 2185, 465, 930, 50, size=34, bold=True, color=ORANGE)

# K–R：最小值决定平移与删点，保留差值进入二参数似然。
d.text('kr-title', 'K–R', 75, 530, 900, 45, size=30, bold=True, color=GREEN)
d.line('raw-axis', [(120,645),(960,645)], color=INK, arrow='block')
raw = [190, 310, 465, 650, 870]
for i, xx in enumerate(raw):
    dot(f'raw-{i}', xx, 645, GRAY if i==0 else GREEN, 8, '#FFFFFF' if i==0 else GREEN)
d.line('drop-first-a', [(177,632),(203,658)], color=RED, width=3)
d.line('drop-first-b', [(177,658),(203,632)], color=RED, width=3)
d.text('minimum-label', r'\(x_{(1)}\)', 135, 665, 110, 42, size=25, align='center')
d.text('retained-label', r'\(x_{(2)},\ldots,x_{(n)}\)', 370, 665, 490, 42, size=26, align='center')
d.line('translate-arrow', [(555,720),(555,775)], color=GREEN, width=3, arrow='block')
d.text('translate-label', r'\(-x_{(1)}\)', 575, 723, 230, 45, size=27, color=GREEN)
d.line('shift-axis', [(120,835),(960,835)], color=INK, arrow='block')
d.text('origin', '0', 105, 848, 60, 40, size=24)
for i, xx in enumerate([240,395,580,800]):
    dot(f'shifted-{i}', xx, 835, GREEN, 8)
d.text('shifted-label', r'\(y_i^*=x_{(i)}-x_{(1)},\quad i=2,\ldots,n\)', 155, 865, 800, 50, size=27, align='center')
d.box('kr-output', r'\(\widehat\gamma=x_{(1)}\)　→　二参数似然', 100, 945, 880, 75,
      color=GREEN, fill='#EAF4EE', size=28)

d.text('dmmle-title', 'DMMLE · Firth得分修正', 75, 1080, 900, 48, size=29, bold=True, color=GREEN)
d.box('kr-score', r'\(U_{\mathrm{KR}}\)', 110, 1190, 225, 80, color=GREEN, size=30)
d.text('plus', '+', 345, 1205, 55, 50, size=33, align='center')
d.box('firth-term', r'\(A_{\mathrm{Firth}}\)', 415, 1190, 260, 80, color=ORANGE, fill='#FFF2DE', size=30)
d.line('adjusted-to-root', [(710,1230),(795,1230)], color=GREEN, arrow='block', width=3)
d.text('adjusted-zero', r'\(=0\)', 810, 1195, 150, 70, size=35, bold=True, color=GREEN)

# WMLE：改变三个估计方程中的系数，而非重新给观测点配任意权。
d.text('wmle-title', 'WMLE', 1135, 530, 910, 45, size=30, bold=True, color=BLUE)
for i, (label, hh) in enumerate([(r'\(J_1\)',94),(r'\(J_2\)',65),(r'\(J_3\)',126)]):
    xx = 1260+i*280
    d.box(f'coefficient-base-{i}', '', xx, 720-100, 65, 100, color=GRAY, fill='#D9DEE5', size=1, extra='rounded=0;')
    d.box(f'coefficient-new-{i}', '', xx+76, 720-hh, 65, hh, color=BLUE, fill='#91BBD4', size=1, extra='rounded=0;')
    d.text(f'coefficient-label-{i}', label, xx-10, 738, 170, 45, size=27, align='center')
d.text('coefficient-base-label', '原系数', 1190, 790, 360, 40, size=24, color=INK)
d.text('coefficient-new-label', '修正系数', 1585, 790, 380, 40, size=24, color=BLUE)
d.text('coefficient-functions', r'\(J_1(n),\quad J_2(n),\quad J_3(n,\beta)\)', 1150, 845, 890, 52, size=28, align='center')
d.line('wmle-reweight', [(1595,915),(1595,960)], color=BLUE, arrow='block', width=3)
for i, label in enumerate([r'\(\widetilde U_\beta=0\)',r'\(\widetilde U_\eta=0\)',r'\(\widetilde U_\gamma=0\)']):
    d.box(f'wmle-equation-{i}', label, 1140+i*310, 980, 290, 70, color=BLUE, size=28)

# Cohen–Whitten只替换位置方程，形状、尺度方程保留。
d.text('cw-title', 'Cohen–Whitten · MMLE-II', 1135, 1100, 910, 45, size=29, bold=True, color=BLUE)
d.line('minimum-law-axis', [(1160,1300),(1460,1300)], color=INK, arrow='block')
curve('minimum-law', 1160, 1300, 270, 110, weibull, BLUE)
d.line('minimum-expectation', [(1280,1300),(1280,1185)], color=BLUE, dashed=True)
dot('observed-minimum', 1280, 1300, BLUE, 6)
d.text('minimum-law-label', r'\(f_{X_{(1)}}\)', 1165, 1150, 245, 45, size=25, color=BLUE)
d.text('observed-minimum-label', r'\(x_{(1)}\)', 1215, 1308, 160, 40, size=24, align='center')
d.text('cw-retained', r'保留 \(U_\beta=U_\eta=0\)', 1490, 1150, 550, 48, size=27, align='center')
d.text('cw-replace', r'替换 \(U_\gamma=0\) ↓', 1490, 1205, 550, 45, size=26, color=BLUE, align='center')
d.box('cw-minimum', r'\(x_{(1)}=\mathbb E_\theta[X_{(1)}]\)', 1490, 1260, 550, 65,
      color=BLUE, fill='#EAF1FA', size=28)

# CMLE：以区间概率面积替换最小观测的一点密度贡献。
d.text('cmle-title', 'CMLE', 2195, 530, 910, 45, size=30, bold=True, color=ORANGE)
axis('interval', 2235, 835, 830, 220, r'\(x\)', r'\(f_\theta(x)\)')
lo, hi = .24, .47
area = [(2235+790*lo,835)] + [(2235+790*t/80,835-220*weibull(t/80)) for t in range(round(lo*80),round(hi*80)+1)] + [(2235+790*hi,835)]
d.polygon('interval-area', area, fill='#F1CCA0', opacity=.85)
curve('interval-density', 2235, 835, 790, 220, weibull, ORANGE)
for name,t in [('left',lo),('right',hi)]:
    d.line('interval-'+name, [(2235+790*t,835),(2235+790*t,835-220*weibull(t))], color=ORANGE, dashed=True)
d.text('interval-left-label', r'\(x_{(1)}\)', 2235+790*lo-80, 850, 160, 44, size=25, align='center')
d.text('interval-right-label', r'\(x_{(1)}+h\)', 2235+790*hi-65, 850, 230, 44, size=25, align='center')
d.text('interval-area-label', r'\(\Delta F_1\)', 2430, 755, 180, 48, size=29, bold=True, color=ORANGE, align='center')
d.text('interval-probability', r'\(f_\theta(x_{(1)})\ \longrightarrow\ \Delta F_1\)', 2220, 920, 890, 50, size=29, align='center')

# Hall–Wang罚因子改变边界附近目标形状，估计仍由目标极值给出。
d.text('penalty-title', 'Hall–Wang · 罚似然', 2195, 1000, 910, 45, size=29, bold=True, color=ORANGE)
axis('penalty', 2240, 1270, 560, 165, r'\(\gamma\)', r'\(\ell\)')
def penalty_example(t, adjusted=False):
    xs, beta, eta = [2,3,4,6,8], .6, 3
    gamma = -.5+2.5*min(t,.9999)
    ll = len(xs)*math.log(beta)-len(xs)*beta*math.log(eta)
    ll += (beta-1)*sum(math.log(x-gamma) for x in xs)-sum(((x-gamma)/eta)**beta for x in xs)
    if adjusted:
        ll += math.log((xs[0]-gamma)/(xs[1]-gamma))
    return (ll+17)/10
curve('ordinary-objective', 2240, 1270, 520, 165, penalty_example, GRAY)
curve('penalized-objective', 2240, 1270, 520, 165, lambda t:penalty_example(t,True), ORANGE)
d.line('support-boundary', [(2760,1270),(2760,1100)], color=INK, dashed=True)
d.text('boundary-label', r'\(x_{(1)}\)', 2680, 1280, 160, 45, size=24, align='center')
d.text('penalty-expression', r'\(\ell+\ln p(\gamma)\)<br>\(p(\gamma)=\dfrac{x_{(1)}-\gamma}{x_{(2)}-\gamma}\)', 2820, 1110, 300, 150,
       size=27, color=ORANGE, align='center')
d.save(OUT)

cells = ET.parse(OUT).findall('.//mxCell')
ids = [c.get('id') for c in cells]
assert len(ids) == len(set(ids))
for cell in cells:
    if cell.get('edge') == '1':
        assert cell.get('source') in ids and cell.get('target') in ids
    if cell.get('vertex') == '1':
        g = cell.find('mxGeometry')
        x, y, w, h = [float(g.get(k)) for k in ('x', 'y', 'width', 'height')]
        assert 0 <= x <= x+w <= 3200 and 0 <= y <= y+h <= 1400, cell.get('id')
print(f'{OUT.name}: {len(cells)} native cells; XML, endpoints and 16:7 bounds OK')
