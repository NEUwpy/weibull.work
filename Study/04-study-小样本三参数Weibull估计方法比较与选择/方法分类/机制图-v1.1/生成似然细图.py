"""似然路线内部的密度贡献、方程求解与改动作用点。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET

from 细图绘制 import Diagram


ROOT = Path(__file__).resolve().parent
OUT = ROOT / '01-似然估计路线-机制图.drawio'
d = Diagram('likelihood-mechanism-v10', '似然估计：从密度贡献到方程与改动作用点', 1800, 2110)
RED = '#A94F40'
BLUE = '#2D6D91'
GREEN = '#347B68'
ORANGE = '#B07530'
INK = '#243449'

d.text('title', '似然估计｜让全部观测的密度贡献共同确定参数', 45, 22, 1710, 58, size=36, bold=True)
d.text('subtitle', '完整独立寿命样本；θ=(β, η, γ)，β>0、η>0；原始连续密度的共同支撑为 γ<x₍₁₎。', 50, 88, 1700, 46, size=25)

# 一条候选密度曲线，读出固定观测处的高度；曲线是可编辑的原生折线。
d.panel('density-panel', 40, 150, 1720, 470, fill='#FFF8F5')
d.text('density-heading', '① 固定观测，改变候选参数，观测处的密度随之改变', 65, 170, 1660, 48, size=28, bold=True)
d.text('sample', '排序样本  x₍₁₎，x₍₂₎，…，x₍ₙ₎', 80, 228, 560, 42, size=25)
d.line('plot-x', [(95, 500), (655, 500)], color='#66788B', arrow='block')
d.line('plot-y', [(110, 510), (110, 285)], color='#66788B', arrow='block')
d.text('plot-y-label', 'fθ(x)', 120, 275, 120, 36, size=23)
d.text('plot-x-label', '寿命 x', 572, 509, 100, 35, size=23)
d.text('plot-gamma', 'γ', 91, 509, 45, 35, size=23)
shape, scale = 2.25, 4.5
def density(z):
    return shape / scale * (z / scale) ** (shape - 1) * math.exp(-(z / scale) ** shape) if z > 0 else 0.
points = [(110 + z * 51, 500 - density(z) * 990) for z in [i * .10 for i in range(101)]]
d.line('candidate-density', points, color=RED, width=4)
for i, z in enumerate([1.10, 2.55, 4.65, 7.15], start=1):
    xx, yy = 110 + z * 51, 500 - density(z) * 990
    d.line(f'density-guide-{i}', [(xx, 500), (xx, yy)], color=BLUE, width=2, dashed=True)
    d.box(f'density-dot-{i}', '', xx-5, yy-5, 10, 10, color=BLUE, fill=BLUE, size=1, extra='ellipse;')
    label = ['x₍₁₎', 'x₍₂₎', 'x₍ᵢ₎', 'x₍ₙ₎'][i-1]
    d.text(f'density-x-{i}', label, xx-50, 519, 100, 40, size=22, align='center')
d.text('density-height', '竖线高度给出各观测的 fθ(xᵢ)', 135, 570, 500, 34, size=23)
d.text('density-formula', 'yᵢ=xᵢ−γ>0<br>fθ(xᵢ)=(β/η)(yᵢ/η)^(β−1) exp[−(yᵢ/η)^β]', 700, 232, 1015, 120, size=28, bold=True)
d.text('schematic-caption', '左图为密度贡献的原理示意', 705, 357, 1010, 38, size=23, color='#66788B')
d.box('minimum-factor', 'fθ(x₍₁₎)<br>最小观测的贡献', 720, 425, 280, 108, color=ORANGE, fill='#FFF3DC', size=25)
d.box('remaining-factors', '×  ∏ᵢ₌₂ⁿ fθ(x₍ᵢ₎)<br>其余观测的贡献', 1040, 425, 390, 108, color=RED, size=25)
d.box('joint', 'L(θ)<br>联合似然', 1490, 425, 220, 108, color=RED, fill='#FFFFFF', size=27, bold=True)
d.edge('density-product', 'remaining-factors', 'joint', '', color=RED)

# 似然代数与求解：每个箭头都有确切数学含义。
d.panel('equation-panel', 40, 655, 1720, 425, fill='#F5F8FC')
d.text('equation-heading', '② 取对数，把密度乘积转成可求导的参数函数', 65, 674, 1660, 48, size=28, bold=True)
d.box('loglik', 'ℓ(θ)=ln L(θ)=n lnβ − nβ lnη + (β−1) Σᵢ ln yᵢ − Σᵢ(yᵢ/η)^β', 85, 738, 1630, 82, color=BLUE, size=29, bold=True)
d.box('score', '得分向量  U(θ)=∇θ ℓ(θ)<br>内点驻点满足<br>Uβ=0，Uη=0，Uγ=0', 85, 884, 465, 145, color=BLUE, size=25)
d.box('profile', '先由尺度方程消去 η<br>η̂(β,γ)=[Σᵢ(xᵢ−γ)^β/n]^(1/β)<br>再求 β、γ 或比较剖面 ℓ', 640, 884, 570, 145, color=BLUE, size=25)
d.box('estimate', '候选参数 θ̂=(β̂,η̂,γ̂)<br>比较目标值，检查支撑、<br>局部峰及边界响应', 1310, 884, 405, 145, color=GREEN, fill='#EEF8F3', size=25)
d.edge('joint-to-log', 'joint', 'loglik', '取对数：乘积变为求和', color=RED, start='bottom', end='right', via=[(1742,533),(1742,779)], at=(1485,640))
d.edge('log-to-score', 'loglik', 'score', '对参数求偏导', color=BLUE, start='bottom', end='top', via=[(900,852),(317,852)], at=(450,849))
d.edge('score-eliminate', 'score', 'profile', 'Uη=0', color=BLUE, at=(595,953))
d.edge('profile-estimate', 'profile', 'estimate', '求解／比较', color=BLUE, at=(1255,953))

# 三个可辨别的原型接口。不是方法名单，而是数据与公式的具体变更。
d.text('modification-heading', '③ 后续构造改变的是哪一个计算对象？', 55, 1097, 1680, 48, size=29, bold=True)
d.panel('data-patch', 40, 1180, 535, 790, fill='#F2F8F5', color='#C6DDD2')
d.panel('equation-patch', 605, 1180, 570, 790, fill='#F5F7FC', color='#CED8EA')
d.panel('objective-patch', 1205, 1180, 555, 790, fill='#FFF8F0', color='#E3D3BC')
d.text('data-patch-title', '改数据与位置处理', 62, 1200, 485, 45, size=28, bold=True, color=GREEN)
d.text('equation-patch-title', '改求解方程', 628, 1200, 520, 45, size=28, bold=True, color=BLUE)
d.text('objective-patch-title', '改最小值项或目标函数', 1228, 1200, 505, 45, size=28, bold=True, color=ORANGE)

# K–R：将位置固定在原最小值；被删除观测从修改数据目标中退出。
d.text('kr-title', 'K–R：最小值定位、删除该点', 65, 1258, 480, 45, size=25, bold=True)
d.box('kr-minimum', 'x₍₁₎<br>用于 γ̂=x₍₁₎', 70, 1320, 190, 90, color=GREEN, fill='#E8F2ED', size=24)
d.box('kr-retained', 'x₍₂₎，…，x₍ₙ₎<br>保留并作平移', 310, 1320, 220, 90, color=GREEN, size=24)
d.line('kr-delete-mark', [(74,1339),(111,1376)], color=ORANGE, width=3)
d.text('kr-data', 'yᵢ*=x₍ᵢ₎−x₍₁₎>0，i=2,…,n<br>有效样本数 q=n−1', 70, 1440, 460, 80, size=24, align='center')
d.box('kr-likelihood', '修改数据目标<br>ℓKR(β,η)=Σᵢ₌₂ⁿ ln f₂(yᵢ*;β,η)<br>只对保留的正距离估 β、η', 70, 1555, 460, 130, color=GREEN, size=24)
d.edge('kr-shift', 'kr-retained', 'kr-likelihood', '平移、删点后组成目标', color=GREEN, start='right', end='top', via=[(550,1365),(550,1535),(300,1535)], at=(302,1535))
d.box('dmmle', 'DMMLE：在修改数据得分上加修正<br>UKR=∂ℓKR/∂(β,η)<br>求解  UKR + AFirth = 0', 70, 1760, 460, 155, color=GREEN, fill='#EAF5EE', size=25)
d.edge('kr-score-adjust', 'kr-likelihood', 'dmmle', '求导后加入偏差修正项', color=GREEN, start='bottom', end='top', at=(300,1725))

# WMLE：展示三个权重具体嵌入的三个方程；J3随临时形状更新。
d.box('wmle-equations', 'WMLE：权重进入形状／位置方程<br>S(r)=Σᵢ yᵢʳ，H(r)=Σᵢ yᵢʳ ln yᵢ<br>J₂/β + 平均ln y − H(β)/S(β) = 0<br>平均(1/y) · S(β)/S(β−1) = J₃<br>η^β = S(β)/(nJ₁)', 635, 1290, 510, 255, color=BLUE, size=23)
d.text('weights', 'J₁、J₂由 n 确定；J₃依赖 n 与 β<br>联立更新 β、γ，再恢复 η', 642, 1550, 495, 82, size=24, align='center')
d.box('cw-replacement', 'Cohen–Whitten：保留 Uβ=0、Uη=0<br>把 Uγ=0 换成另一统计关系<br>例：MMLE-II 使用最小值期望', 635, 1690, 510, 118, color=BLUE, size=24)
d.box('cw-minimum-expectation', 'x₍₁₎ = γ + η n^(−1/β) Γ(1+1/β)<br>与保留的两条似然方程联立', 635, 1840, 510, 91, color=BLUE, fill='#EEF2FA', size=24)
d.edge('cw-substitute', 'cw-replacement', 'cw-minimum-expectation', '', color=BLUE, start='bottom', end='top')

# CMLE：显式保留原最小值的区间概率；罚似然在目标层增加因子。
d.box('cmle-interval', 'CMLE：将最小值密度贡献改为区间概率<br>fθ(x₍₁₎)  →  Fθ(x₍₁₎+h)−Fθ(x₍₁₎)<br>其余观测仍贡献各自的密度', 1235, 1290, 495, 165, color=ORANGE, size=24)
d.box('cmle-target', 'ℓCMLE = ln[Fθ(x₍₁₎+h)−Fθ(x₍₁₎)]<br>+ Σᵢ₌₂ⁿ ln fθ(x₍ᵢ₎)<br>区间宽度 h 参与边界处理', 1235, 1495, 495, 142, color=ORANGE, fill='#FFF3E2', size=24)
d.edge('cmle-replace', 'cmle-interval', 'cmle-target', '替换后重组目标', color=ORANGE, start='bottom', end='top', at=(1482,1474))
d.box('penalty', '罚似然：给目标增加经验因子<br>ℓpen(θ)=ℓ(θ)+ln p(γ)<br>Hall–Wang：p(γ)=(x₍₁₎−γ)/(x₍₂₎−γ)', 1235, 1730, 495, 170, color=ORANGE, size=24)
d.text('penalty-result', '重新比较带惩罚的参数目标', 1245, 1910, 475, 38, size=24, align='center')

# 将修改指到确切数学接口；绕行通道不穿过正文公式。
d.edge('data-interface', 'sample', 'kr-minimum', '', color=GREEN, kind='borrow', start='left', end='left', via=[(18,249),(18,1365)], evidence='../04-方法分类与沿袭关系工作稿.md:53,59,70')
d.edge('score-interface', 'score', 'wmle-equations', '修改得分的代数方程', color=BLUE, kind='borrow', start='bottom', end='top', via=[(317,1100),(890,1100)], at=(890,1154), evidence='../04-方法分类与沿袭关系工作稿.md:58,61,63')
d.edge('minimum-interface', 'minimum-factor', 'cmle-interval', '替换最小观测项', color=ORANGE, kind='borrow', start='bottom', end='right', via=[(860,600),(1782,600),(1782,1372)], at=(1550,1154), evidence='../04-方法分类与沿袭关系工作稿.md:60')
d.text('source-note', '公式依据：Cousineau（2009）式(2)–(3)；Cohen–Whitten（1982）MMLE-II；Cheng–Iles（1987）式(10)；Hall–Wang（2005）式(2.4)–(2.5)。', 55, 2010, 1690, 60, size=23, color='#66788B')
d.save(OUT)

# 输出结构检查：对象、端点和支撑表述均在图源中保留。
tree = ET.parse(OUT)
cells = tree.findall('.//mxCell')
ids = [c.get('id') for c in cells]
assert len(ids) == len(set(ids))
for cell in cells:
    if cell.get('edge') == '1':
        assert cell.get('source') in ids and cell.get('target') in ids
print(f'generated {OUT.name}: {len(cells)} editable cells, {sum(c.get("edge") == "1" for c in cells)} edges; XML and endpoints valid')
