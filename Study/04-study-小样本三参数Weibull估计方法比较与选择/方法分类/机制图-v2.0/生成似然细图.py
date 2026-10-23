"""横向似然机制图：密度贡献 → 联合目标 → 求解，并列展开改动接口。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '01-似然估计路线-机制图.drawio'
d = Diagram('likelihood-mechanism-v20-wide', '似然构造、求解与改动接口', 3200, 1400)
RED, BLUE, GREEN, ORANGE = '#A94F40', '#2D6D91', '#347B68', '#B07530'
d.text('title', '似然估计｜密度贡献 → 联合目标 → 参数求解', 45, 20, 3110, 60, size=38, bold=True)
d.text('support', r'\(\theta=(\beta,\eta,\gamma),\quad\beta>0,\quad\eta>0,\quad\gamma<x_{(1)},\quad y_i=x_i-\gamma>0\)', 50, 85, 3090, 45, size=26)

d.panel('density-panel', 40, 155, 995, 585, fill='#FFF8F5')
d.panel('equation-panel', 1070, 155, 970, 585, fill='#F5F8FC')
d.panel('solution-panel', 2075, 155, 1085, 585, fill='#F2F8F5')
d.text('density-heading', '① 固定观测，读取密度贡献', 65, 173, 935, 50, size=30, bold=True, color=RED)
d.text('sample', r'\(x_{(1)},x_{(2)},\ldots,x_{(n)}\)', 75, 235, 900, 40, size=26)
d.line('plot-x', [(95, 515), (955, 515)], color='#66788B', arrow='block')
d.line('plot-y', [(110, 525), (110, 300)], color='#66788B', arrow='block')
d.text('plot-y-label', r'\(f_\theta(x)\)', 120, 285, 160, 40, size=24)
d.text('plot-x-label', r'\(x\)', 930, 525, 60, 40, size=24)
d.text('plot-gamma', r'\(\gamma\)', 85, 525, 60, 40, size=24)
shape, scale = 2.25, 4.5

def density(z):
    return shape / scale * (z / scale) ** (shape - 1) * math.exp(-(z / scale) ** shape) if z > 0 else 0.

d.line('candidate-density', [(110 + z * 80, 515 - density(z) * 990) for z in [i * .10 for i in range(101)]], color=RED, width=4)
for i, z in enumerate([1.10, 2.55, 4.65, 7.15], start=1):
    xx, yy = 110 + z * 80, 515 - density(z) * 990
    d.line(f'density-guide-{i}', [(xx, 515), (xx, yy)], color=BLUE, width=2, dashed=True)
    d.box(f'density-dot-{i}', '', xx-5, yy-5, 10, 10, color=BLUE, fill=BLUE, size=1, extra='ellipse;')
    label = [r'\(x_{(1)}\)', r'\(x_{(2)}\)', r'\(x_{(i)}\)', r'\(x_{(n)}\)'][i-1]
    d.text(f'density-x-{i}', label, xx-55, 535, 110, 40, size=23, align='center')
d.text('density-formula', r'\(f_\theta(x_i)=\frac{\beta}{\eta}\left(\frac{y_i}{\eta}\right)^{\beta-1}\exp\!\left[-\left(\frac{y_i}{\eta}\right)^\beta\right]\)', 75, 610, 915, 95, size=28, bold=True)

d.text('equation-heading', '② 相乘，再取对数', 1095, 173, 910, 50, size=30, bold=True, color=BLUE)
d.box('minimum-factor', r'\(f_\theta(x_{(1)})\)', 1100, 270, 280, 95, color=ORANGE, fill='#FFF3DC', size=28)
d.box('remaining-factors', r'\(\times\prod_{i=2}^{n}f_\theta(x_{(i)})\)', 1410, 270, 380, 95, color=RED, size=28)
d.box('joint', r'\(L(\theta)\)', 1840, 270, 165, 95, color=RED, size=30, bold=True)
d.edge('density-product', 'remaining-factors', 'joint', color=RED)
d.box('loglik', r'\(\ell(\theta)=\ln L(\theta)\)<br>\(=n\ln\beta-n\beta\ln\eta\)<br>\(\quad+(\beta-1)\sum_{i=1}^{n}\ln y_i\)<br>\(\quad-\sum_{i=1}^{n}\left(\frac{y_i}{\eta}\right)^\beta\)', 1100, 440, 905, 250, color=BLUE, size=29, bold=True)
d.edge('joint-to-log', 'joint', 'loglik', r'\(\ln\)', color=RED, start='bottom', end='top', via=[(1922,400),(1552,400)], at=(1730,400))

d.text('solution-heading', '③ 内点方程与剖面求解', 2100, 173, 1025, 50, size=30, bold=True, color=GREEN)
d.box('score', r'\(U(\theta)=\nabla_\theta\ell(\theta)\)<br>\(U_\beta=0,\quad U_\eta=0,\quad U_\gamma=0\)', 2110, 260, 1015, 115, color=BLUE, size=28)
d.box('profile', r'\(U_\eta=0\ \Longrightarrow\ \widehat\eta(\beta,\gamma)=\left[\frac{1}{n}\sum_{i=1}^{n}(x_i-\gamma)^\beta\right]^{\frac{1}{\beta}}\)<br>求 \(\beta,\gamma\)，比较剖面 \(\ell\)', 2110, 440, 1015, 140, color=BLUE, size=28)
d.box('estimate', r'\(\widehat\theta=(\widehat\beta,\widehat\eta,\widehat\gamma)\)', 2320, 635, 600, 65, color=GREEN, fill='#EAF5EE', size=29, bold=True)
d.edge('log-to-score', 'loglik', 'score', r'\(\nabla_\theta\)', color=BLUE, start='right', end='left', via=[(2056,565),(2056,317)], at=(2056,410))
d.edge('score-eliminate', 'score', 'profile', '消去尺度', color=BLUE, start='bottom', end='top', at=(2617,405))
d.edge('profile-estimate', 'profile', 'estimate', '求解／比较', color=GREEN, start='bottom', end='top', at=(2617,609))

d.panel('data-patch', 40, 815, 995, 540, fill='#F2F8F5', color='#C6DDD2')
d.panel('equation-patch', 1070, 815, 970, 540, fill='#F5F7FC', color='#CED8EA')
d.panel('objective-patch', 2075, 815, 1085, 540, fill='#FFF8F0', color='#E3D3BC')
d.text('data-patch-title', '改数据｜K–R → DMMLE', 65, 832, 935, 45, size=29, bold=True, color=GREEN)
d.box('kr-minimum', r'\(x_{(1)}\ \longrightarrow\ \widehat\gamma=x_{(1)}\)', 75, 895, 405, 70, color=GREEN, fill='#E8F2ED', size=25)
d.box('kr-retained', r'保留 \(x_{(2)},\ldots,x_{(n)}\)', 535, 895, 460, 70, color=GREEN, size=25)
d.text('kr-data', r'\(y_i^*=x_{(i)}-x_{(1)}>0,\quad i=2,\ldots,n,\quad q=n-1\)', 75, 990, 920, 65, size=26, align='center')
d.box('kr-likelihood', r'\(\ell_{\mathrm{KR}}(\beta,\eta)=\sum_{i=2}^{n}\ln f_2(y_i^*;\beta,\eta)\)', 75, 1080, 920, 90, color=GREEN, size=28)
d.box('dmmle', r'DMMLE：\(U_{\mathrm{KR}}=\frac{\partial\ell_{\mathrm{KR}}}{\partial(\beta,\eta)}\)<br>\(U_{\mathrm{KR}}+A_{\mathrm{Firth}}=0\)', 75, 1225, 920, 105, color=GREEN, fill='#EAF5EE', size=27)
d.edge('kr-shift', 'kr-retained', 'kr-likelihood', '平移、删点', color=GREEN, start='right', end='right', via=[(1010,930),(1010,1125)], at=(1010,1040))
d.edge('kr-score-adjust', 'kr-likelihood', 'dmmle', '得分修正', color=GREEN, start='bottom', end='top', at=(535,1198))

d.text('equation-patch-title', '改方程｜WMLE · Cohen–Whitten', 1095, 832, 910, 45, size=29, bold=True, color=BLUE)
d.box('wmle-equations', r'WMLE：\(S(r)=\sum_i y_i^r,\quad H(r)=\sum_i y_i^r\ln y_i\)<br>\(\frac{J_2}{\beta}+\overline{\ln y}-\frac{H(\beta)}{S(\beta)}=0\)<br>\(\overline{y^{-1}}\,\frac{S(\beta)}{S(\beta-1)}=J_3,\quad\eta^\beta=\frac{S(\beta)}{nJ_1}\)', 1100, 895, 905, 195, color=BLUE, size=27)
d.text('weights', r'\(J_1=J_1(n),\quad J_2=J_2(n),\quad J_3=J_3(n,\beta)\)', 1100, 1095, 905, 45, size=25, align='center')
d.box('cw-replacement', r'Cohen–Whitten：保留 \(U_\beta=U_\eta=0\)<br>MMLE-II 以最小值期望替换 \(U_\gamma=0\)<br>\(x_{(1)}=\gamma+\eta n^{-\frac{1}{\beta}}\Gamma\!\left(1+\frac{1}{\beta}\right)\)', 1100, 1165, 905, 165, color=BLUE, fill='#EEF2FA', size=26)

d.text('objective-patch-title', '改目标｜CMLE · 罚似然', 2100, 832, 1025, 45, size=29, bold=True, color=ORANGE)
d.box('cmle-interval', r'CMLE：\(f_\theta(x_{(1)})\longrightarrow\Delta F_1\)<br>\(\Delta F_1=F_\theta(x_{(1)}+h)-F_\theta(x_{(1)})\)', 2110, 895, 1015, 120, color=ORANGE, size=27)
d.box('cmle-target', r'\(\ell_{\mathrm{CMLE}}=\ln\Delta F_1+\sum_{i=2}^{n}\ln f_\theta(x_{(i)})\)', 2110, 1050, 1015, 80, color=ORANGE, fill='#FFF3E2', size=28)
d.edge('cmle-replace', 'cmle-interval', 'cmle-target', color=ORANGE, start='bottom', end='top')
d.box('penalty', r'罚似然：\(\ell_{\mathrm{pen}}(\theta)=\ell(\theta)+\ln p(\gamma)\)<br>Hall–Wang：\(p(\gamma)=\frac{x_{(1)}-\gamma}{x_{(2)}-\gamma}\)', 2110, 1180, 1015, 145, color=ORANGE, size=27)

d.edge('data-interface', 'sample', 'kr-minimum', color=GREEN, kind='borrow', start='left', end='left', via=[(20,255),(20,930)], evidence='../04-方法分类与沿袭关系工作稿.md:53,59,70')
d.edge('score-interface', 'score', 'wmle-equations', color=BLUE, kind='borrow', start='right', end='right', via=[(3175,317),(3175,790),(2055,790),(2055,992)], evidence='../04-方法分类与沿袭关系工作稿.md:58,61,63')
d.edge('minimum-interface', 'minimum-factor', 'cmle-interval', color=ORANGE, kind='borrow', start='left', end='left', via=[(1050,317),(1050,775),(2055,775),(2055,955)], evidence='../04-方法分类与沿袭关系工作稿.md:60')
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
print(f'generated {OUT.name}: {len(cells)} editable cells; XML, endpoints and 16:7 canvas valid')
