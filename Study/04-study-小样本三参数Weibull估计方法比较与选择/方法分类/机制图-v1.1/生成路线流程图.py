"""五条路线的信息处理流程，先于机制细图阅读。"""
from pathlib import Path
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
RED, BLUE, GREEN, PURPLE, ORANGE = '#A94F40', '#2D6D91', '#347B68', '#785499', '#AE6C25'


def canvas(key, title, subtitle, height):
    d = Diagram(key, title, 1800, height)
    d.text('title', title, 45, 20, 1710, 60, size=35, bold=True)
    d.text('subtitle', subtitle, 45, 95, 1710, 55, size=25)
    return d


def likelihood():
    d = canvas('likelihood-information-flow', '似然估计｜固定样本，比较不同参数下的联合贡献',
               '观测先变为密度贡献，再组成似然；确定参数的依据是似然目标或由其导出的方程。', 650)
    items = [
        ('data', '输入寿命样本 D\n保留各观测 xᵢ', 55, 270),
        ('density', '给定候选 θ=(β,η,γ)\n计算观测处的 fθ(xᵢ)\n并落实模型支持域', 395, 300),
        ('joint', '组合全部观测贡献\nL(θ)=∏ᵢ fθ(xᵢ)\n取对数得到 ℓ(θ)', 765, 300),
        ('rule', '据似然确定参数\n最大化 ℓ(θ)\n或求解、修正得分方程', 1135, 300),
        ('estimate', '输出估计\nβ̂、η̂、γ̂', 1505, 240),
    ]
    for key, text, x, w in items:
        d.box(key, text.replace('\n', '<br>'), x, 225, w, 155,
              color=RED, fill='#FFF7F3' if key != 'estimate' else '#F4E8E2', size=25, bold=key == 'estimate')
    for a, b in zip(items, items[1:]):
        d.edge(a[0]+'-'+b[0], a[0], b[0], color=RED, width=3)
    d.edge('numeric-loop', 'rule', 'density', '需要数值求解时：更新候选参数，再计算相应贡献',
           color=RED, kind='feedback', start='bottom', end='bottom',
           via=[(1285, 490), (545, 490)], at=(915, 490))
    d.text('meaning', '数据、密度项、目标或方程发生修改时，变化进入对应的计算环节。', 60, 560, 1680, 45, size=25)
    d.save(ROOT / '07-似然估计路线-信息处理流程.drawio')


def branched(key, title, subtitle, branch_rows, output, color, name, footer):
    d = canvas(key, title, subtitle, 900)
    d.box('data', '输入寿命样本 D<br>提取所需观测', 50, 380, 240, 150, color=color, size=25)
    d.box('representation', '选取这类方法使用的<br>样本表示与理论关系', 360, 380, 260, 150,
          color=color, fill='#F1F7FA', size=25)
    d.edge('data-representation', 'data', 'representation', color=color, width=3)
    for i, (y, info, rule) in enumerate(branch_rows):
        d.box(f'info-{i}', info, 730, y, 300, 155, color=color, fill='#F6F9FB', size=24)
        d.box(f'rule-{i}', rule, 1110, y, 330, 155, color=color, fill='#FFFFFF', size=24)
        d.edge(f'branch-{i}', 'representation', f'info-{i}', color=color,
               via=[(675, 455), (675, y+77.5)])
        d.edge(f'rule-edge-{i}', f'info-{i}', f'rule-{i}', color=color, width=3)
    d.box('estimate', output, 1520, 380, 230, 155, color=color, fill='#EAF4EE', size=25, bold=True)
    for i, (y, _, _) in enumerate(branch_rows):
        d.edge(f'recover-{i}', f'rule-{i}', 'estimate', color=color,
               via=[(1480, y+77.5), (1480, 457.5)])
    d.text('meaning', footer, 55, 795, 1690, 65, size=25)
    d.save(ROOT / name)


def distribution():
    branched('distribution-information-flow', '分布匹配｜把样本写成分布关系，按对应的匹配规则求解',
             '不同分支选取不同的比较对象；比较对象决定参数评分和恢复过程。', [
        (200, '概率图表示<br>绘图分数 zᵢ<br>对数寿命 uᵢ(γ)',
         '回归与位置定位<br>按残差、相关性或位置评分<br>确定位置、斜率与截距'),
        (400, 'CDF 表示<br>经验概率与 Fθ(x₍ᵢ₎)<br>或相邻 CDF 概率间距',
         '分布差异或间距评分<br>最小化相应分布差异<br>或最大化间距目标'),
        (600, '伪尺度表示<br>各观测反推 ηᵢ(β,γ)<br>计算这些尺度的离散程度',
         'MDM 分步确定参数<br>给定 γ，条件确定 β<br>按梯度阈值 δ 定位 γ<br>伪尺度均值恢复 η'),
    ], '按相应关系恢复<br>β̂、η̂、γ̂', BLUE,
             '08-分布匹配路线-信息处理流程.drawio',
             '回归、分布距离、概率间距与伪尺度一致性，分别给出具体的匹配依据。')


def statistics():
    branched('statistics-information-flow', '统计关系反演｜提取统计量，再由参数关系逐步确定未知量',
             '先明确统计量保留哪些参数信息，再选择匹配、统计量似然或条件线性组合。', [
        (200, '矩／分位数等统计量<br>接入总体参数关系<br>通过差值、比值等消元',
         '反演统计关系<br>显式反解或解匹配方程<br>再用剩余关系恢复参数'),
        (400, '不变统计量 W／V<br>W 消去位置与尺度<br>V 只消去位置',
         '最大化统计量联合密度<br>W 定 β；V 初始定 η、β<br>保留 β，再恢复其余参数'),
        (600, '条件位置统计量<br>给定 β、η 构造无偏量<br>未知时用临时参数代入',
         '按条件协方差选权<br>线性组合得到 γ̂<br>代入时与参数恢复迭代'),
    ], '结合已知、代入<br>及恢复的参数<br>组成三参数估计', GREEN,
             '09-统计关系反演路线-信息处理流程.drawio',
             '显式恢复直接给出结果；参数尚未知时，可把条件估计与其他参数的恢复步骤组合迭代。')


def posterior():
    d = canvas('posterior-information-flow', '后验推断｜样本与先验形成后验，再按所选规则给出估计',
               '联合后验确定参数的不确定性；输出规则决定需要计算哪一个后验量。', 730)
    items = [
        ('sample', '输入观测 D<br>形成样本似然 L(θ|D)', 55, 285),
        ('posterior', '结合参数先验与支持域<br>p(θ|D) ∝ L(θ|D)π(θ)', 420, 330),
        ('decision', '选择后验输出规则<br>均值／逐参数中位数<br>或联合 MAP', 830, 285),
        ('compute', '计算所选后验量<br>积分、抽样、近似<br>或密度峰优化', 1195, 285),
        ('estimate', '得到参数估计<br>β̂、η̂、γ̂', 1560, 190),
    ]
    for key, text, x, w in items:
        d.box(key, text, x, 240, w, 150, color=PURPLE,
              fill='#F8F3FB' if key != 'estimate' else '#EEE2F6', size=25, bold=key == 'estimate')
    for a, b in zip(items, items[1:]):
        d.edge(a[0]+'-'+b[0], a[0], b[0], color=PURPLE, width=3)
    d.box('prior', '已有信息与参数范围<br>先验 π(θ) 及允许域', 435, 500, 300, 105,
          color=PURPLE, fill='#FFFFFF', size=25)
    d.edge('prior-joint', 'prior', 'posterior', color=PURPLE, start='top', end='bottom')
    d.text('rules', '后验均值取期望；逐参数中位数取边缘分位数；MAP取联合后验密度的峰。', 55, 650, 1690, 45, size=25)
    d.save(ROOT / '10-后验推断路线-信息处理流程.drawio')


def learning():
    d = canvas('learning-information-flow', '学习映射｜先用多组样本训练，再对新样本执行固定映射',
               '训练时通过参数标签学习估计函数；使用时沿用相同特征表示与已训练权重。', 1090)
    d.panel('train-panel', 35, 155, 1730, 445, fill='#FCF6EE')
    d.text('train-title', '训练：样本和参数标签共同确定映射', 60, 170, 1670, 55, size=28, bold=True)
    items = [
        ('data', '多组训练样本 Dⱼ<br>及对应参数 θⱼ<br>来自模拟或标注', 55, 300),
        ('features', '提取统一特征<br>T(Dⱼ)', 425, 250),
        ('mapping', '用当前映射预测<br>θ̂ⱼ=hφ(T(Dⱼ))', 745, 280),
        ('loss', '预测与真值对照<br>计算参数预测损失 ℒ(φ)', 1095, 290),
        ('update', '按损失更新权重 φ<br>继续下一轮训练', 1455, 280),
    ]
    for key, text, x, w in items:
        d.box(key, text, x, 285, w, 125, color=ORANGE, size=24)
    for a, b in zip(items, items[1:]):
        d.edge(a[0]+'-'+b[0], a[0], b[0], color=ORANGE, width=3)
    d.edge('truth-to-loss', 'data', 'loss', '对应的参数标签 θⱼ', color=ORANGE,
           start='bottom', end='bottom', via=[(205, 465), (1240, 465)], at=(640, 465))
    d.edge('training-loop', 'update', 'mapping', '更新映射，再预测', color=ORANGE, kind='feedback',
           start='top', end='top', via=[(1595, 250), (885, 250)], at=(1240, 250))
    d.box('freeze', '训练结束，固定 φ*', 1405, 505, 330, 65, color=ORANGE, fill='#FFF0DA', size=25, bold=True)
    d.edge('freeze-trained', 'update', 'freeze', color=ORANGE, start='bottom', end='top',
           via=[(1595, 480), (1570, 480)])
    d.panel('use-panel', 35, 700, 1730, 300, fill='#F0F8F3')
    d.text('use-title', '使用：当前新样本只经过一次固定映射', 60, 715, 1670, 55, size=28, bold=True)
    use = [('new-data', '输入新样本 D', 55, 300), ('new-feature', '沿用同一特征 T(D)', 445, 300),
           ('fixed', '执行固定映射 hφ*', 835, 355), ('estimate', '输出 β̂、η̂、γ̂', 1280, 455)]
    for key, text, x, w in use:
        d.box(key, text, x, 825, w, 105, color=GREEN, fill='#FFFFFF', size=27, bold=key == 'estimate')
    for a, b in zip(use, use[1:]):
        d.edge(a[0]+'-'+b[0], a[0], b[0], color=GREEN, width=3)
    d.edge('transfer', 'freeze', 'fixed', '带入已训练权重', color=ORANGE, start='bottom', end='top',
           via=[(1570, 655), (1012.5, 655)], at=(1260, 655))
    d.text('scope', '这里的映射直接输出参数；学习中间权重或修正量时，再接入相应统计估计器。', 55, 1020, 1690, 45, size=25)
    d.save(ROOT / '11-学习映射路线-信息处理流程.drawio')


if __name__ == '__main__':
    likelihood()
    distribution()
    statistics()
    posterior()
    learning()
    print('generated five information-processing flowcharts')
