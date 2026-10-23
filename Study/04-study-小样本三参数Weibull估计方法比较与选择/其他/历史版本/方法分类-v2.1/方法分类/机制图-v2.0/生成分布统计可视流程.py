"""分布匹配与统计关系反演：图像化核心机制，具体方法分支见第二幅图。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
BLUE, GREEN, ORANGE, GREY = '#286D99', '#26745A', '#B47744', '#718297'
SAMPLE = [42., 57., 69., 77., 86., 99., 122.]
WIDTH, HEIGHT = 3200, 1400
STAGES = [50, 850, 1650, 2450]


def dot(d, key, x, y, color=BLUE, r=6, hollow=False):
    d.box(key, '', x-r, y-r, 2*r, 2*r, fill='#FFFFFF' if hollow else color,
          color=color, role='point', extra='shape=ellipse;strokeWidth=2;')


def text(d, key, value, x, y, w, h=50, size=27, bold=False):
    return d.text(key, value, x, y, w, h, size=size, bold=bold)


def stage(d, key, title, x, fill):
    d.panel(key+'-bg', x, 130, 700, 595, fill=fill, color='#DEE6EC')
    text(d, key+'-heading', title, x+20, 145, 660, 65, 31, True)


def axes(d, key, x, y, w, h, xlabel, ylabel, xmin=0, xmax=1, ymin=0, ymax=1):
    d.line(key+'-x', [(x, y+h), (x+w, y+h)], color=GREY, arrow='block')
    d.line(key+'-y', [(x, y+h), (x, y)], color=GREY, arrow='block')
    text(d, key+'-xl', xlabel, x+w-160, y+h+4, 200, 45, 24)
    text(d, key+'-yl', ylabel, x-20, y-48, 310, 45, 24)
    return lambda a,b: (x+w*(a-xmin)/(xmax-xmin), y+h*(1-(b-ymin)/(ymax-ymin)))


def curve(d, key, coords, color=BLUE, width=3.5, dashed=False):
    d.line(key, list(coords), color=color, width=width, dashed=dashed)


def connect_stages(d, color):
    for i, x in enumerate(STAGES[:-1], 1):
        d.line(f'step-{i}-{i+1}', [(x+710,425),(x+790,425)], color=color, width=3.5, arrow='block')


def legend(d, key, x, y, label, color):
    d.line(key+'-line', [(x,y+20),(x+40,y+20)], color=color, width=4)
    text(d, key+'-label', label, x+50, y-5, 180, 50, 25)


def expand_core(d):
    """Give the four-step example the whole wide page; keep glyphs and dots round."""
    scale=2.02
    for cell in d.root.findall('mxCell'):
        geo=cell.find('mxGeometry')
        if geo is None: continue
        if cell.get('vertex')=='1':
            y=float(geo.get('y','0'));h=float(geo.get('height','0'))
            role=cell.get('renderRole')
            if role in {'label','point'} or cell.get('value'):
                geo.set('y',str(65+(y+h/2-130)*scale-h/2))
            else:
                geo.set('y',str(65+(y-130)*scale));geo.set('height',str(h*scale))
        for point in geo.findall('./Array/mxPoint'):
            point.set('y',str(65+(float(point.get('y'))-130)*scale))
        if cell.get('labelY') is not None:
            cell.set('labelY',str(65+(float(cell.get('labelY'))-130)*scale))


def cdf(x, beta, eta, gamma=0):
    return 0 if x <= gamma else -math.expm1(-((x-gamma)/eta)**beta)


def distribution():
    d = Diagram('visual-distribution-flow', '分布匹配：表示、准则与定参', WIDTH, HEIGHT)
    stage(d, 'empirical', '① D1 样本概率点', STAGES[0], '#F1F7FB')
    stage(d, 'candidate', '② D1 候选分布', STAGES[1], '#F1F7FB')
    stage(d, 'difference', '③ D2 概率残差', STAGES[2], '#F8FAFC')
    stage(d, 'criterion', '④ D3 最小差异定参', STAGES[3], '#F2F8F4')
    connect_stages(d, BLUE)
    xs = [.18,.32,.41,.49,.57,.68,.88]
    n = len(xs)
    ps = [(i-.3)/(n+.4) for i in range(1,n+1)]
    fa = [cdf(x,1.0,.65) for x in xs]
    fb = [cdf(x,2.0,.62) for x in xs]
    qa = sum((f-p)**2 for f,p in zip(fa,ps))
    qb = sum((f-p)**2 for f,p in zip(fb,ps))
    p1 = axes(d, 'sample-probability', 125, 285, 530, 265, r'寿命 \(x\)', '概率')
    for i,(x,p) in enumerate(zip(xs,ps)):
        dot(d, f'sample-point-{i}', *p1(x,p), BLUE, 7)
    text(d, 'probability-ranks', r'\(x_{(i)}\longleftrightarrow p_i\)<br>\(p_i=\frac{i-0.3}{n+0.4}\)', 90, 610, 620, 100, 29)

    p2 = axes(d, 'candidate-probability', 925, 285, 530, 265, r'寿命 \(x\)', '概率')
    grid = [i/80 for i in range(81)]
    curve(d, 'cdf-a', [p2(x,cdf(x,1.0,.65)) for x in grid], ORANGE)
    curve(d, 'cdf-b', [p2(x,cdf(x,2.0,.62)) for x in grid], GREEN)
    for i,(x,p) in enumerate(zip(xs,ps)):
        dot(d, f'candidate-point-{i}', *p2(x,p), BLUE, 7)
    for i in [0,3,5]:
        d.line(f'candidate-residual-{i}', [p2(xs[i],ps[i]),p2(xs[i],fa[i])], color=ORANGE, width=3, dashed=True)
    legend(d, 'a-legend', 905, 610, r'候选 \(A\)', ORANGE)
    legend(d, 'b-legend', 1205, 610, r'候选 \(B\)', GREEN)
    text(d, 'cdf-object', r'\(F_\theta(x_{(i)})\)', 905, 665, 610, 50, 29)

    left, top, scale = 1745, 285, 500/.27
    d.line('residual-zero', [(left,top-10),(left,top+265)], color=GREY, width=2)
    for i,(a,b,p) in enumerate(zip(fa,fb,ps)):
        yy = top+i*38
        text(d, f'obs-{i}', rf'\({i+1}\)', 1680, yy-12, 50, 40, 24)
        d.box(f'residual-a-{i}', '', left, yy, max(2,abs(a-p)*scale), 11, fill=ORANGE, color=ORANGE, role='background')
        d.box(f'residual-b-{i}', '', left, yy+14, max(2,abs(b-p)*scale), 11, fill=GREEN, color=GREEN, role='background')
    text(d, 'residual-label', r'\(\lvert F_\theta(x_{(i)})-p_i\rvert\)', 1705, 565, 600, 45, 26)
    text(d, 'residual-formula', r'\(e_i(\theta)=F_\theta(x_{(i)})-p_i\)<br>\(D(\theta)=\sum_{i=1}^n e_i(\theta)^2\)', 1680, 620, 640, 95, 29)

    p4 = axes(d, 'total-score', 2525, 285, 530, 265, '候选', r'平方差 \(D\)', xmax=3, ymax=max(qa,qb)*1.35)
    for key,x,q,color in [('a',.75,qa,ORANGE),('b',2.,qb,GREEN)]:
        bx,by = p4(x,q)
        base = p4(x,0)[1]
        d.box('score-'+key, '', bx-62, by, 124, base-by, fill=color, color=color, role='background')
        text(d, 'score-label-'+key, rf'\({key.upper()}\)', bx-40, base+3, 80, 45, 27, True)
        text(d, 'score-value-'+key, rf'\({q:.3f}\)', bx-65, by-45, 130, 45, 26)
    text(d, 'selected-rule', r'\(D(B)<D(A)\)', 2490, 610, 620, 45, 29, True)
    text(d, 'criterion-objective', r'\(\widehat\theta=\operatorname*{arg\,min}_{\theta}D(\theta)\)', 2490, 655, 620, 65, 29)

    expand_core(d)
    d.save(ROOT/'08-分布匹配路线-信息处理流程.drawio')


def skewness(beta):
    g1,g2,g3 = [math.gamma(1+k/beta) for k in (1,2,3)]
    return (g3-3*g1*g2+2*g1**3)/(g2-g1*g1)**1.5


def density_y(y,beta):
    return 0 if y <= 0 else beta*y**(beta-1)*math.exp(-y**beta)


def statistics():
    d = Diagram('visual-statistics-flow', '统计关系反演：特征、理论关系与参数', WIDTH, HEIGHT)
    stage(d, 'features', '① S1 提取样本特征', STAGES[0], '#F2F8F4')
    stage(d, 'cancel', '② S2 消去位置与尺度', STAGES[1], '#F2F8F4')
    stage(d, 'solve', '③ S3 反解形状', STAGES[2], '#F8FAFC')
    stage(d, 'recover', '④ S3 恢复尺度与位置', STAGES[3], '#F2F8F4')
    connect_stages(d, GREEN)
    n = len(SAMPLE)
    mean = sum(SAMPLE)/n
    m2 = sum((x-mean)**2 for x in SAMPLE)/n
    m3 = sum((x-mean)**3 for x in SAMPLE)/n
    sd, sample_skew = math.sqrt(m2), m3/m2**1.5
    lo,hi = .7,7.
    for _ in range(100):
        mid = (lo+hi)/2
        if skewness(mid) > sample_skew:
            lo = mid
        else:
            hi = mid
    bh = (lo+hi)/2
    ey = math.gamma(1+1/bh)
    sdy = math.sqrt(math.gamma(1+2/bh)-ey**2)
    eh,gh = sd/sdy,mean-sd/sdy*ey
    p1 = axes(d, 'histogram', 125, 280, 530, 245, r'寿命 \(x\)', '频数', xmin=30, xmax=140, ymax=3)
    for i,(lower,upper) in enumerate([(35,55),(55,75),(75,95),(95,115),(115,135)]):
        count = sum(lower <= x < upper for x in SAMPLE)
        bx,by = p1(lower,count)
        right,base = p1(upper,0)
        d.box(f'hist-{i}', '', bx+3, by, right-bx-6, base-by, fill='#B6D9CB', color=GREEN, role='background')
    curve(d, 'histogram-mean', [p1(mean,0),p1(mean,2.65)], ORANGE, 2.5, True)
    text(d, 'mean-marker', r'\(\bar x\)', p1(mean,0)[0]-40, 535, 100, 45, 26)
    text(d, 'observed-features', r'\(\bar x,\quad m_2,\quad m_3\)<br>\(m_k=\frac1n\sum_i(x_i-\bar x)^k,\quad k=2,3\)', 90, 605, 620, 110, 28)

    moved = [18+1.35*x for x in SAMPLE]
    for key,vals,yy,color,label in [('raw',SAMPLE,305,BLUE,'原样本'),('affine',moved,415,ORANGE,'平移、拉伸')]:
        d.line(key+'-baseline', [(925,yy),(1455,yy)], color=GREY, width=1.8, arrow='block')
        for i,x in enumerate(vals):
            dot(d, f'{key}-{i}', 925+530*x/200, yy, color, 6)
        text(d, key+'-label', label, 905, yy-55, 620, 45, 25)
    d.line('standardized-baseline', [(925,540),(1455,540)], color=GREY, width=1.8, arrow='block')
    for i,x in enumerate(SAMPLE):
        xx = 925+530*((x-mean)/sd+2)/4
        dot(d, f'standardized-affine-{i}', xx, 540, ORANGE, 9, True)
        dot(d, f'standardized-raw-{i}', xx, 540, BLUE, 5)
    text(d, 'overlap-label', '中心化、标准化', 905, 475, 620, 45, 25)
    text(d, 'cancel-description', r'\(\widehat g=\frac{m_3}{m_2^{3/2}}\)<br>\(g(\beta)=\frac{\mathbb E[(Y-\mathbb EY)^3]}{\operatorname{Var}(Y)^{3/2}}\)', 905, 585, 620, 135, 28)

    p3 = axes(d, 'shape-relation', 1725, 285, 530, 265, r'形状 \(\beta\)', '偏度', xmin=.7, xmax=6, ymin=-.5, ymax=3.5)
    bs = [.7+i*(6-.7)/120 for i in range(121)]
    curve(d, 'shape-curve', [p3(b,skewness(b)) for b in bs], GREEN)
    curve(d, 'sample-skew-line', [p3(.7,sample_skew),p3(6,sample_skew)], ORANGE, 2.5, True)
    curve(d, 'shape-root-line', [p3(bh,-.5),p3(bh,sample_skew)], BLUE, 2.5, True)
    dot(d, 'shape-root', *p3(bh,sample_skew), BLUE, 8)
    text(d, 'shape-root-label', r'\(\widehat\beta\)', p3(bh,-.5)[0]-35, 558, 90, 50, 28, True)
    legend(d, 'shape-legend', 1680, 615, r'\(g(\beta)\)', GREEN)
    legend(d, 'skew-legend', 1980, 615, r'\(\widehat g\)', ORANGE)
    text(d, 'shape-equation', r'\(g(\widehat\beta)=\widehat g\)', 1680, 670, 630, 45, 29)

    p4a = axes(d, 'unit-y', 2525, 270, 530, 80, r'标准 \(Y\)', '密度', xmax=2.5, ymax=2)
    grid = [i*2.5/100 for i in range(101)]
    curve(d, 'unit-y-density', [p4a(y,density_y(y,bh)) for y in grid], BLUE)
    text(d, 'affine-relation', r'\(X=\gamma+\eta Y\)', 2490, 400, 620, 50, 30, True)
    d.line('affine-arrow', [(2790,450),(2790,475)], color=GREEN, width=3, arrow='block')
    p4b = axes(d, 'restored-x', 2525, 500, 530, 75, r'寿命 \(X\)', '密度', xmin=20, xmax=170, ymax=.025)
    gridx = [20+i*150/100 for i in range(101)]
    curve(d, 'restored-x-density', [p4b(x,density_y((x-gh)/eh,bh)/eh) for x in gridx], GREEN)
    text(d, 'restore-rules', r'\(\widehat\eta=\frac{\sqrt{m_2}}{\operatorname{sd}_{\widehat\beta}(Y)}\)<br>\(\widehat\gamma=\bar x-\widehat\eta\mathbb E_{\widehat\beta}[Y]\)', 2490, 620, 620, 100, 28)

    expand_core(d)
    d.save(ROOT/'09-统计关系反演路线-信息处理流程.drawio')


def validate():
    for name in ['08-分布匹配路线-信息处理流程.drawio','09-统计关系反演路线-信息处理流程.drawio']:
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
    distribution()
    statistics()
    validate()
