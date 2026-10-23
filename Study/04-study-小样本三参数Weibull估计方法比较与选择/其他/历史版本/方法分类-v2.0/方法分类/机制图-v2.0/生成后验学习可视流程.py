"""后验推断与学习映射：横向曲线、网络及固定映射流程。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
PURPLE, BLUE, GREEN, ORANGE = '#785499', '#2D6D91', '#347B68', '#AE6C25'
WIDTH, HEIGHT = 3200, 1400
STAGES = [50, 1125, 2200]


def chart(d, key, x, y, w, h, xlabel, ylabel):
    d.line(key+'-x', [(x,y+h),(x+w,y+h)], color='#8090A0', arrow='block')
    d.line(key+'-y', [(x,y+h),(x,y)], color='#8090A0', arrow='block')
    d.text(key+'-xl', xlabel, x+w-270, y+h+10, 280, 45, size=26, align='right')
    d.text(key+'-yl', ylabel, x-5, y-55, w, 50, size=26)


def curve(d, key, values, x, y, w, h, color):
    maximum = max(values)
    points = [(x+i*w/(len(values)-1),y+h-v/maximum*h) for i,v in enumerate(values)]
    d.line(key, points, color=color, width=4)
    return points


def base(key, title, panel_y, panel_height):
    d = Diagram(key, title, WIDTH, HEIGHT)
    for i,x in enumerate(STAGES,1):
        d.panel(f'step-{i}', x, panel_y, 950, panel_height, fill='#F8F9FC')
    for i in [1,2]:
        d.edge(f'flow-{i}', f'step-{i}', f'step-{i+1}', color='#617487', width=3.5)
    return d


def posterior():
    d = base('posterior-information-flow', '后验推断｜似然与先验 → 联合后验 → 后验决策', 150, 1180)
    for key,label,x in [('s1','① B1 似然与先验',70),('s2','② B1 后验构造',1145),('s3','③ B2 后验决策',2220)]:
        d.text(key, label, x, 175, 910, 70, size=32, bold=True)
    xx = [.03+.97*i/100 for i in range(101)]
    like = [math.exp(-.5*(math.log(v/.39)/.48)**2)/v for v in xx]
    prior = [.35+math.exp(-.5*((v-.62)/.33)**2) for v in xx]
    post = [a*b for a,b in zip(like,prior)]
    mean = sum(x*p for x,p in zip(xx,post))/sum(post)
    variance = sum(p*(x-mean)**2 for x,p in zip(xx,post))/sum(post)
    chart(d, 'support', 140, 370, 770, 480, r'候选参数 \(\theta\)', '相对支持')
    curve(d, 'likelihood', like, 140, 370, 770, 480, BLUE)
    curve(d, 'prior', prior, 140, 370, 770, 480, PURPLE)
    for key,y,color,label in [('like',1010,BLUE,r'似然 \(L(\theta\mid D)\)'),('prior',1120,PURPLE,r'先验 \(\pi(\theta)\)')]:
        d.line(key+'-legend', [(130,y),(200,y)], color=color, width=4)
        d.text(key+'-label', label, 225, y-35, 700, 70, size=31)

    chart(d, 'post', 1215, 370, 770, 480, r'参数 \(\theta\)', '后验密度')
    maximum = max(post)
    for i in range(0,len(post),3):
        height = post[i]/maximum*470
        d.box(f'area-{i}', '', 1215+i*770/100, 850-height, 15, height, fill='#E9DDF3', color='none', role='background')
    curve(d, 'posterior', post, 1215, 370, 770, 480, PURPLE)
    d.text('posterior-product', r'\(p(\theta\mid D)\propto L(\theta\mid D)\pi(\theta)\)', 1160, 990, 880, 100, size=32, bold=True, align='center')
    d.text('posterior-normalize', r'\(\int p(\theta\mid D)\,d\theta=1\)', 1160, 1130, 880, 80, size=31, align='center')

    chart(d, 'risk', 2290, 370, 770, 480, r'候选估计 \(a\)', '后验期望损失')
    risks = [(v-mean)**2+variance for v in xx]
    curve(d, 'average-risk', risks, 2290, 370, 770, 480, GREEN)
    px = 2290+(mean-.03)/.97*770
    py = 850-variance/max(risks)*480
    d.line('chosen-guide', [(px,850),(px,py)], color=GREEN, dashed=True)
    d.box('chosen', '', px-9, py-9, 18, 18, fill=GREEN, color=GREEN, extra='shape=ellipse;')
    d.text('risk-rule', r'\(\widehat\theta=\operatorname*{arg\,min}_a\mathbb E[\ell(a,\theta)\mid D]\)', 2230, 965, 890, 110, size=31, align='center')
    d.text('squared-loss', '平方损失 → 后验均值', 2240, 1090, 870, 60, size=29)
    d.text('absolute-loss', '绝对损失 → 后验中位数', 2240, 1165, 870, 60, size=29)
    d.text('map-rule', 'MAP → 后验众数', 2240, 1240, 870, 60, size=29)
    d.save(ROOT/'10-后验推断路线-信息处理流程.drawio')


def learning():
    d = base('learning-information-flow', '学习映射｜带标签样本 → 映射预测 → 损失训练', 170, 690)
    d.text('training-phase', 'N1 训练', 60, 110, 500, 50, size=29, bold=True, color=ORANGE)
    for key,label,x in [('s1','① 样本表示',70),('s2','② 映射预测',1145),('s3','③ 损失与更新',2220)]:
        d.text(key, label, x, 185, 910, 65, size=32, bold=True)
    d.text('training-pairs', r'\((D_j,\theta_j),\quad j=1,\ldots,m\)', 80, 270, 890, 65, size=30, align='center')
    d.text('training-prediction', r'\(\widehat\theta_j=h_\varphi[T(D_j)]\)', 1155, 270, 890, 65, size=31, align='center')
    chart(d, 'features', 140, 425, 770, 255, '特征维度', r'\(T(D_j)\)')
    vals = [.12,.18,.23,.30,.36,.43,.52,.64,.80,.96]
    for i,v in enumerate(vals):
        d.box(f'feature-{i}', '', 165+i*72, 680-v*240, 38, v*240, color=BLUE, fill='#A9C9DD')
    d.text('feature-mapping', '排序值／分位数／统计量', 95, 760, 860, 60, size=29, align='center')

    layers = [[(1275,410),(1275,490),(1275,570)],[(1600,380),(1600,450),(1600,520),(1600,590)],[(1925,410),(1925,490),(1925,570)]]
    for layer in range(2):
        for i,a in enumerate(layers[layer]):
            for j,b in enumerate(layers[layer+1]):
                d.line(f'connection-{layer}-{i}-{j}', [a,b], color='#CBB69C', width=1.8)
    for layer,centers in enumerate(layers):
        for i,(cx,cy) in enumerate(centers):
            circle = [(cx+20*math.cos(2*math.pi*k/24),cy+20*math.sin(2*math.pi*k/24)) for k in range(25)]
            d.line(f'neuron-{layer}-{i}', circle, color=ORANGE, width=3)
    d.text('feature-network', '特征', 1200, 610, 150, 45, size=26, align='center')
    d.text('weights-network', r'权重 \(\varphi\)', 1490, 610, 220, 45, size=26, align='center')
    d.text('output-network', '参数', 1850, 610, 150, 45, size=26, align='center')
    for i,(label,true,pred) in enumerate([(r'\(\beta\)',65,48),(r'\(\eta\)',85,70),(r'\(\gamma\)',55,76)]):
        x = 1350+200*i
        d.box(f'true-{i}', '', x, 760-true, 30, true, fill='#93A0AC', color='none')
        d.box(f'pred-{i}', '', x+40, 760-pred, 30, pred, fill='#C99144', color='none')
        d.text(f'parameter-{i}', label, x-5, 765, 90, 40, size=27, align='center')
    d.text('compare', '灰：真值　橙：预测', 1170, 810, 860, 40, size=25, align='center')

    chart(d, 'loss', 2290, 425, 770, 255, '权重更新次数', '预测损失')
    values = [.78*math.exp(-i/25)+.1+.025*math.sin(i*.32) for i in range(101)]
    curve(d, 'training-loss', values, 2290, 425, 770, 255, ORANGE)
    d.text('loss-formula', r'\(\varphi^{*}=\operatorname*{arg\,min}_{\varphi}\frac1m\sum_{j=1}^{m}\ell(\widehat\theta_j,\theta_j)\)', 2230, 760, 890, 85, size=29, align='center')
    d.edge('update-cycle', 'step-3', 'step-2', r'更新 \(\varphi\)', color=ORANGE, kind='feedback', start='bottom', end='bottom', via=[(2675,940),(1600,940)], at=(2110,940))

    d.text('deployment', 'N2 固定映射', 60, 1010, 800, 55, size=30, bold=True, color=BLUE)
    for i,(x,value) in enumerate([
        (50,r'新样本<br>\(D_{\mathrm{new}}\rightarrow T(D_{\mathrm{new}})\)'),
        (1125,r'固定估计函数<br>\(g_{\varphi^*}\)'),
        (2200,r'参数估计<br>\(\widehat\theta_{\mathrm{new}}=g_{\varphi^*}[T(D_{\mathrm{new}})]\)<br>\(\widehat\theta=(\widehat\beta,\widehat\eta,\widehat\gamma)\)'),
    ],1):
        d.box(f'deploy-{i}', value, x, 1100, 950, 240, color=BLUE, fill='#F0F6FB', size=30)
    for i in [1,2]:
        d.edge(f'deploy-flow-{i}', f'deploy-{i}', f'deploy-{i+1}', color=BLUE, width=3)
    d.save(ROOT/'11-学习映射路线-信息处理流程.drawio')


def validate():
    for name in ['10-后验推断路线-信息处理流程.drawio','11-学习映射路线-信息处理流程.drawio']:
        root = ET.parse(ROOT/name).getroot()
        cells = root.findall('.//mxCell')
        ids = [c.get('id') for c in cells]
        assert len(ids) == len(set(ids)), name
        model = root.find('.//mxGraphModel')
        w,h = float(model.get('pageWidth')),float(model.get('pageHeight'))
        assert (w,h) == (WIDTH,HEIGHT) and h/w == 7/16, name
        for c in cells:
            if c.get('edge') == '1':
                assert c.get('source') in ids and c.get('target') in ids
            if c.get('vertex') == '1':
                g = c.find('mxGeometry')
                x,y,cw,ch = [float(g.get(k,0)) for k in ['x','y','width','height']]
                assert min(x,y) >= 0 and x+cw <= w and y+ch <= h, (name,c.get('id'))
            for p in c.findall('./mxGeometry/Array/mxPoint'):
                assert 0 <= float(p.get('x')) <= w and 0 <= float(p.get('y')) <= h, (name,c.get('id'))
        print(f'{name}: {len(cells)} cells; 3200x1400; XML, IDs, endpoints and bounds OK')


if __name__ == '__main__':
    posterior()
    learning()
    validate()
