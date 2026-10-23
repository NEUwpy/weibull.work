"""后验与学习细图：上部短链，下部用决策、采样、近似与映射小图展开。"""
from pathlib import Path
import math
import random
import xml.etree.ElementTree as ET
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
PURPLE, ORANGE, GREEN = '#785499', '#AE6C25', '#2C7B61'
BLUE, RED, GRAY, INK = '#367B98', '#AC5B49', '#A4ADB8', '#66788B'


def dot(d, key, x, y, color, radius=6, fill=None):
    d.box(key, '', x-radius, y-radius, radius*2, radius*2,
          color=color, fill=fill or color, size=1, extra='ellipse;')


def axis(d, key, x, y, w, h, xlabel='', ylabel=''):
    d.line(key+'-x', [(x,y),(x+w,y)], color=INK, width=1.8, arrow='block')
    d.line(key+'-y', [(x,y),(x,y-h)], color=INK, width=1.8, arrow='block')
    if xlabel:
        d.text(key+'-xl', xlabel, x+w-50, y+10, 100, 42, size=24)
    if ylabel:
        d.text(key+'-yl', ylabel, x+5, y-h-32, 280, 48, size=24)


def curve(d, key, x, y, w, h, fn, color, dashed=False, lo=0, hi=1):
    d.line(key, [(x+w*(lo+(hi-lo)*i/80),y-h*fn(lo+(hi-lo)*i/80)) for i in range(81)],
           color=color, width=3.5, dashed=dashed)


def gaussian(t, mu=.5, sd=.16):
    return math.exp(-.5*((t-mu)/sd)**2)


def network(d, key, xs, ys, color, radius=13):
    for layer in range(len(xs)-1):
        for i, yy in enumerate(ys[layer]):
            for j, zz in enumerate(ys[layer+1]):
                d.line(f'{key}-connection-{layer}-{i}-{j}', [(xs[layer],yy),(xs[layer+1],zz)],
                       color='#C3CCD6', width=1.35)
    for layer, xx in enumerate(xs):
        for i, yy in enumerate(ys[layer]):
            dot(d, f'{key}-node-{layer}-{i}', xx, yy, color, radius, '#FFFFFF' if layer==0 else color)


def posterior():
    d = Diagram('posterior-detail-wide', '后验推断：构造、决策与计算', 3200, 1400)
    d.panel('core-strip',40,35,3120,345,fill='#FAF8FC')
    d.text('likelihood-heading','① 样本似然',65,55,410,48,size=31,bold=True,color=RED)
    curve(d,'likelihood-curve',100,285,350,145,lambda t:gaussian(t,.60,.17),RED)
    d.line('likelihood-axis',[(90,285),(475,285)],color=INK,arrow='block')
    d.text('likelihood-symbol',r'\(L(\theta\mid D)\)',95,303,380,48,size=29,align='center')
    d.text('multiply','×',485,174,65,70,size=42,align='center',color=PURPLE)
    d.text('prior-heading','先验',565,55,420,48,size=31,bold=True,color=PURPLE)
    curve(d,'prior-curve',595,285,350,145,lambda t:gaussian(t,.40,.24),PURPLE)
    d.line('prior-axis',[(580,285),(965,285)],color=INK,arrow='block')
    d.text('prior-symbol',r'\(\pi(\theta)\)',590,303,375,48,size=29,align='center')
    d.line('combine',[(1000,215),(1080,215)],color=PURPLE,width=3,arrow='block')
    d.text('posterior-heading','② 后验',1125,55,600,48,size=31,bold=True,color=PURPLE)
    curve(d,'posterior-curve',1190,285,460,155,lambda t:gaussian(t,.53,.14),PURPLE)
    d.line('posterior-axis',[(1175,285),(1680,285)],color=INK,arrow='block')
    d.text('posterior-symbol',r'\(p(\theta\mid D)\propto L(\theta\mid D)\pi(\theta)\)',1120,303,610,48,size=29,align='center')
    d.line('posterior-decision',[(1760,215),(1835,215)],color=PURPLE,width=3,arrow='block')
    d.text('decision-heading','③ 决策',1875,55,590,48,size=31,bold=True,color=PURPLE)
    d.box('decision-rule',r'后验期望损失最小<br>或联合密度峰',1880,145,570,155,
          color=PURPLE,fill='#F2EBF8',size=31)
    d.line('decision-output',[(2490,215),(2600,215)],color=PURPLE,width=3,arrow='block')
    d.text('output-heading','④ 估计',2650,55,450,48,size=31,bold=True,color=PURPLE)
    d.text('posterior-estimate',r'\(\widehat\theta\)<br>\((\widehat\beta,\widehat\eta,\widehat\gamma)\)',2650,150,450,140,
           size=36,bold=True,color=PURPLE,align='center')

    d.panel('decision-panel',40,445,1000,915,fill='#F8F5FC',color='#DDD0E7')
    d.panel('sampling-panel',1100,445,1000,915,fill='#F1F8F4',color='#C6DDD2')
    d.panel('laplace-panel',2160,445,1000,915,fill='#F1F7FA',color='#C8DDE7')
    d.text('decision-title','后验决策',65,465,930,50,size=34,bold=True,color=PURPLE)
    d.text('sampling-title','Gibbs / 条件抽样',1125,465,930,50,size=34,bold=True,color=GREEN)
    d.text('laplace-title','Laplace · 局部近似',2185,465,930,50,size=34,bold=True,color=BLUE)

    # 同一个右偏密度用于三个决策及Laplace图，风险最小点与峰位置一致。
    mode,sigma=.5,.35
    posterior_mu=math.log(mode)+sigma*sigma
    mean=math.exp(posterior_mu+.5*sigma*sigma)
    median=math.exp(posterior_mu)
    variance=(math.exp(sigma*sigma)-1)*math.exp(2*posterior_mu+sigma*sigma)
    def logp(t):
        u=.10+t
        return -math.log(u)-(math.log(u)-posterior_mu)**2/(2*sigma*sigma)
    peak=logp(.4)
    def normal_cdf(z):
        return .5*(1+math.erf(z/math.sqrt(2)))
    def absolute_risk(t):
        a=.1+t
        z=(math.log(a)-posterior_mu)/sigma
        return a*(2*normal_cdf(z)-1)-2*mean*normal_cdf(z-sigma)+mean
    # 平方、绝对损失分别选择均值和逐参数中位数；MAP取联合后验峰。
    axis(d,'square-risk',110,745,410,145,r'\(a\)',r'\(\mathbb E[(a-\theta_k)^2\mid D]\)')
    curve(d,'square-risk-curve',110,745,370,145,lambda t:2.2*(variance+(.1+t-mean)**2),PURPLE)
    dot(d,'square-risk-minimum',110+370*(mean-.1),745-145*2.2*variance,PURPLE,7)
    d.text('square-rule','平方损失',590,585,390,48,size=28,bold=True,color=PURPLE)
    d.text('mean',r'\(\widehat\theta_k=\mathbb E(\theta_k\mid D)\)',565,660,435,70,size=28,align='center')
    axis(d,'absolute-risk',110,1010,410,145,r'\(a\)',r'\(\mathbb E[|a-\theta_k|\mid D]\)')
    curve(d,'absolute-risk-curve',110,1010,370,145,lambda t:1.7*absolute_risk(t),PURPLE)
    dot(d,'absolute-risk-minimum',110+370*(median-.1),1010-145*1.7*absolute_risk(median-.1),PURPLE,7)
    d.text('absolute-rule','绝对损失',590,850,390,48,size=28,bold=True,color=PURPLE)
    d.text('median',r'\(\widehat\theta_k=\operatorname{median}(\theta_k\mid D)\)',550,925,450,70,size=27,align='center')
    axis(d,'map-density',110,1280,410,145,r'\(\theta\)',r'\(p(\theta\mid D)\)')
    curve(d,'map-density-curve',110,1280,370,145,lambda t:math.exp(logp(t)-peak),PURPLE)
    dot(d,'map-maximum',110+370*.4,1135,PURPLE,7)
    d.text('map-rule','MAP · 联合密度峰',580,1120,410,48,size=28,bold=True,color=PURPLE)
    d.text('map',r'\(\widehat\theta=\operatorname*{arg\,max}_\theta p(\theta\mid D)\)',545,1190,465,85,size=27,align='center')

    # 云图为(beta,gamma)投影；下方完整展示三个参数的轮流条件更新。
    axis(d,'sample-cloud',1180,965,790,360,r'\(\beta\)',r'\(\gamma\)')
    rng=random.Random(704)
    for i in range(90):
        u,v=rng.gauss(0,1),rng.gauss(0,1)
        xx,yy=1570+145*u,780-58*(.65*u+.76*v)
        if 1200 < xx < 1950 and 620 < yy < 945:
            dot(d,f'posterior-sample-{i}',xx,yy,'#8EBCA6',4)
    walk=[(1320,890),(1460,890),(1460,810),(1660,810),(1660,760),(1540,760),
          (1540,705),(1730,705),(1730,800),(1590,800),(1590,735),(1690,735)]
    d.line('coordinate-walk',walk,color=GREEN,width=2.8)
    for i,(xx,yy) in enumerate(walk):
        dot(d,f'walk-{i}',xx,yy,GREEN,5)
    d.text('projection-label',r'\((\beta,\gamma)\) 投影',1450,980,460,45,size=25,color=GREEN,align='center')
    for i,(label,conditional_mu) in enumerate([(r'\(\beta\mid\eta,\gamma,D\)',.43),(r'\(\eta\mid\beta,\gamma,D\)',.57),(r'\(\gamma\mid\beta,\eta,D\)',.48)]):
        xx=1165+i*300
        d.line(f'conditional-axis-{i}',[(xx,1180),(xx+235,1180)],color=INK,arrow='block')
        curve(d,f'conditional-{i}',xx+10,1180,210,105,lambda t,m=conditional_mu:gaussian(t,m,.16),GREEN)
        d.text(f'conditional-label-{i}',label,xx-15,1190,270,50,size=25,align='center')
        if i<2:
            d.line(f'conditional-next-{i}',[(xx+250,1125),(xx+285,1125)],color=GREEN,width=2.8,arrow='block')
    d.line('conditional-repeat',[(1920,1250),(1920,1270),(1280,1270),(1280,1245)],color=GREEN,width=2.5,arrow='block',dashed=True)
    d.text('posterior-summaries','后验样本 → 均值 / 中位数 / 区间',1160,1295,880,45,size=28,color=GREEN,align='center')

    # 同一参数坐标、同一峰高、同一局部曲率；标签全部位于绘图区之外。
    peak_t=mode-.1
    hessian=1/(sigma*sigma*mode*mode)
    def quadratic(t):
        return peak-.5*hessian*(t-peak_t)**2
    def log_height(t):
        return .90+.075*(logp(t)-peak)
    def quadratic_height(t):
        return .90+.075*(quadratic(t)-peak)
    def density_height(t):
        return math.exp(logp(t)-peak)
    def normal_height(t):
        return math.exp(quadratic(t)-peak)
    step=1e-5
    numerical_hessian=-(logp(peak_t+step)-2*logp(peak_t)+logp(peak_t-step))/(step*step)
    assert math.isclose(numerical_hessian,hessian,rel_tol=1e-5)
    assert math.isclose(logp(peak_t),peak,abs_tol=1e-12)
    assert math.isclose(density_height(peak_t),normal_height(peak_t),abs_tol=1e-12)
    assert logp(peak_t-step)<peak and logp(peak_t+step)<peak
    assert all(0<=log_height(i/80)<=1 and 0<=density_height(i/80)<=1+1e-12 for i in range(81))
    plot_x,plot_w=2235,770
    axis(d,'log-posterior',plot_x,820,810,225,r'\(\theta\)')
    d.text('log-posterior-yl',r'\(\log p(\theta\mid D)\)',plot_x+5,540,500,45,size=24)
    curve(d,'exact-logp',plot_x,820,plot_w,225,log_height,PURPLE)
    curve(d,'quadratic-logp',plot_x,820,plot_w,225,quadratic_height,BLUE,True,lo=.15,hi=.70)
    dot(d,'laplace-peak',plot_x+plot_w*peak_t,820-225*.9,BLUE,7)
    d.text('logp-legend','后验对数密度',2245,855,410,42,size=25,color=PURPLE)
    d.text('quadratic-legend','二次近似',2715,855,330,42,size=25,color=BLUE)
    axis(d,'laplace-density',plot_x,1210,810,210,r'\(\theta\)')
    d.text('laplace-density-yl',r'\(p(\theta\mid D)\)',plot_x+5,930,500,45,size=24)
    curve(d,'exact-posterior-density',plot_x,1210,plot_w,210,density_height,PURPLE)
    curve(d,'normal-approximation',plot_x,1210,plot_w,210,normal_height,BLUE,True)
    d.text('laplace-result',r'\(H=-\nabla^2\log p(\widehat\theta_{\rm MAP}\mid D),\quad\Sigma\approx H^{-1}\)',2200,1280,920,65,size=27,align='center',color=BLUE)
    d.save(ROOT/'04-后验推断路线-机制图.drawio')


def learning():
    d=Diagram('learning-detail-wide','学习映射：训练闭环与新样本使用',3200,1400)
    d.panel('core-strip',40,35,3120,345,fill='#FCF8F1')
    d.text('training-data-heading','① 多组带标签样本',65,55,620,48,size=31,bold=True,color=ORANGE)
    for row in range(4):
        yy=160+row*42
        for col in range(6):
            dot(d,f'training-observation-{row}-{col}',110+col*48+(row%2)*9,yy,ORANGE,4)
        d.text(f'training-parameter-{row}',r'\(\theta_'+str(row+1)+r'\)',450,yy-22,170,42,size=25,color=ORANGE,align='center')
    d.line('training-input',[(670,215),(745,215)],color=ORANGE,width=3,arrow='block')
    d.text('train-heading','② 训练映射',780,55,790,48,size=31,bold=True,color=ORANGE)
    network(d,'training-network',[850,1010,1170],[[175,245],[150,210,270],[175,245]],ORANGE,11)
    d.text('train-network-symbol',r'\(h_\varphi\)',905,295,225,45,size=28,color=ORANGE,align='center')
    d.line('prediction-loss',[(1205,210),(1270,210)],color=ORANGE,arrow='block',width=2.5)
    axis(d,'training-loss',1300,285,255,130,r'\(\varphi\)',r'\(\mathcal L\)')
    curve(d,'training-loss-curve',1300,285,215,130,lambda t:.14+2*(t-.60)**2,ORANGE)
    d.line('training-feedback',[(1420,315),(1420,345),(1010,345),(1010,290)],color=RED,dashed=True,arrow='block',width=2.5)
    d.line('freeze',[(1605,215),(1675,215)],color=ORANGE,width=3,arrow='block')
    d.text('fixed-heading','③ 固定',1705,55,350,48,size=31,bold=True,color=ORANGE)
    d.box('fixed-mapping',r'\(h_{\varphi^*}\)',1710,155,350,125,color=ORANGE,fill='#FFF0D9',size=36,bold=True)
    d.line('deploy',[(2090,215),(2160,215)],color=GREEN,width=3,arrow='block')
    d.text('new-sample-heading','④ 新样本估计',2195,55,900,48,size=31,bold=True,color=GREEN)
    d.text('new-data',r'\(D\)',2205,175,125,80,size=34,color=GREEN,align='center')
    d.line('new-feature',[(2340,215),(2400,215)],color=GREEN,width=2.5,arrow='block')
    d.text('new-features',r'\(T(D)\)',2410,175,205,80,size=32,color=GREEN,align='center')
    d.line('new-mapping',[(2630,215),(2690,215)],color=GREEN,width=2.5,arrow='block')
    d.text('new-mapped',r'\(h_{\varphi^*}\)',2700,175,210,80,size=32,color=GREEN,align='center')
    d.line('new-output',[(2920,215),(2970,215)],color=GREEN,width=2.5,arrow='block')
    d.text('new-estimate',r'\(\widehat\theta\)',2970,175,150,80,size=36,bold=True,color=GREEN,align='center')

    d.panel('direct-panel',40,445,1000,915,fill='#FCF6EE',color='#E5D4BA')
    d.panel('process-panel',1100,445,1000,915,fill='#F7F2FA',color='#D9CBE5')
    d.panel('search-panel',2160,445,1000,915,fill='#F2F6FA',color='#D0DCE7')
    d.text('direct-title','直接参数映射',65,465,930,50,size=34,bold=True,color=ORANGE)
    d.text('process-title','过程量 → 统计估计器',1125,465,930,50,size=34,bold=True,color=PURPLE)
    d.text('search-title','数值搜索 · PSO / SA',2185,465,930,50,size=34,bold=True,color=BLUE)

    # 一次固定网络映射，三个输出就是参数。
    d.line('direct-data-axis',[(110,675),(945,675)],color=INK,arrow='block')
    for i,t in enumerate([.08,.19,.31,.50,.68,.84]):
        dot(d,f'direct-observation-{i}',110+780*t,675,ORANGE,7)
    d.text('direct-data-label',r'\(D\)',110,580,300,55,size=30,color=ORANGE)
    d.line('direct-extraction',[(230,725),(230,785)],color=ORANGE,arrow='block',width=3)
    for i,length in enumerate([100,180,135,155,80]):
        d.box(f'direct-feature-{i}','',125,830+i*58,length,24,color='#DBB982',fill='#DBB982',size=1,extra='rounded=0;')
    d.text('direct-feature-label',r'\(T(D)\)',125,1150,210,55,size=29,color=ORANGE)
    network(d,'direct-network',[420,585,750],[[850,970,1090],[805,915,1025,1135],[850,970,1090]],ORANGE,15)
    d.line('features-network',[(325,975),(395,975)],color=ORANGE,arrow='block',width=3)
    for i,(yy,label) in enumerate([(850,r'\(\widehat\beta\)'),(970,r'\(\widehat\eta\)'),(1090,r'\(\widehat\gamma\)')]):
        d.line(f'direct-output-{i}',[(775,yy),(835,yy)],color=ORANGE,arrow='block',width=2.7)
        d.text(f'direct-parameter-{i}',label,850,yy-36,150,75,size=36,bold=True,color=ORANGE,align='center')
    d.text('direct-mapping-symbol',r'\(\widehat\theta=h_{\varphi^*}[T(D)]\)',145,1250,790,65,size=32,color=ORANGE,align='center')

    # 网络输出进入传统构造的过程量，参数由下方统计估计器恢复。
    for i,length in enumerate([100,165,125,145]):
        d.box(f'process-feature-{i}','',1165,620+i*48,length,21,color='#B79CCB',fill='#B79CCB',size=1,extra='rounded=0;')
    d.text('process-feature-label',r'\(T(D)\)',1150,830,220,50,size=28,color=PURPLE,align='center')
    network(d,'process-network',[1420,1570,1720],[[630,720,810],[600,680,760,840],[660,780]],PURPLE,12)
    d.line('process-feature-network',[(1345,720),(1390,720)],color=PURPLE,arrow='block',width=2.7)
    d.line('network-process-output',[(1745,720),(1810,720)],color=PURPLE,arrow='block',width=2.7)
    for i,hh in enumerate([100,165,125]):
        d.box(f'process-quantity-{i}','',1840+i*55,835-hh,34,hh,color=PURPLE,fill='#A98AC0',size=1,extra='rounded=0;')
    d.text('process-quantity-label','权重 / 修正量',1790,865,265,50,size=27,color=PURPLE,align='center')
    d.line('process-to-estimator',[(1920,935),(1920,980),(1530,980),(1530,1015)],color=PURPLE,width=3,arrow='block')
    d.text('statistical-estimator-title','统计估计器',1175,1020,500,48,size=29,bold=True,color=PURPLE)
    axis(d,'statistical-estimator',1195,1255,570,150,r'\(x\)',r'\(F\)')
    curve(d,'statistical-model',1195,1255,525,150,lambda t:1-math.exp(-3*t*t),PURPLE)
    for i,t in enumerate([.10,.27,.44,.62,.82]):
        dot(d,f'statistical-target-{i}',1195+525*t,1255-150*(1-math.exp(-3*t*t))+(i%2*2-1)*7,PURPLE,6,'#FFFFFF')
    d.line('statistical-output',[(1810,1180),(1880,1180)],color=PURPLE,arrow='block',width=3)
    d.text('hybrid-estimate',r'\(\widehat\theta\)',1890,1135,160,100,size=37,bold=True,color=PURPLE,align='center')

    # 搜索直接作用于指定目标；等高线、候选点和移动箭头说明求解角色。
    axis(d,'search',2240,1230,795,590,r'\(\theta_1\)',r'\(\theta_2\)')
    for i,(ww,hh) in enumerate([(700,430),(540,330),(370,225),(185,110)]):
        d.box(f'objective-contour-{i}','',2650-ww/2,920-hh/2,ww,hh,color='#86AFC4',fill='none',size=1,
              extra='ellipse;rotation=-20;strokeWidth=2.2;')
    swarm=[(2330,1120),(2420,760),(2505,1080),(2830,800),(2930,1040),(2760,1160),(2360,920),(2880,650)]
    moves=[(2480,1020),(2510,835),(2570,1000),(2740,850),(2800,990),(2700,1060),(2485,920),(2780,775)]
    for i,((xx,yy),(tx,ty)) in enumerate(zip(swarm,moves)):
        dot(d,f'swarm-{i}',xx,yy,BLUE,7)
        d.line(f'swarm-move-{i}',[(xx,yy),(tx,ty)],color=BLUE,arrow='block',width=2.3)
    dot(d,'search-optimum',2650,920,ORANGE,11)
    d.text('search-optimum-label',r'\(\widehat\theta\)',2680,925,190,60,size=31,bold=True,color=ORANGE)
    d.text('objective-label',r'\(Q(\theta;D)\)',2300,565,550,60,size=31,color=BLUE)
    d.text('search-result',r'\(\widehat\theta=\operatorname*{arg\,min}_\theta Q(\theta;D)\)',2230,1285,880,60,size=30,color=BLUE,align='center')
    d.save(ROOT/'05-学习映射路线-机制图.drawio')


def validate():
    for name in ['04-后验推断路线-机制图.drawio','05-学习映射路线-机制图.drawio']:
        root=ET.parse(ROOT/name).getroot()
        cells=root.findall('.//mxCell');ids=[c.get('id') for c in cells]
        assert len(ids)==len(set(ids)),name
        model=root.find('.//mxGraphModel')
        assert (model.get('pageWidth'),model.get('pageHeight'))==('3200','1400')
        for c in cells:
            if c.get('edge')=='1':
                assert c.get('source') in ids and c.get('target') in ids,c.attrib
            if c.get('vertex')=='1':
                g=c.find('mxGeometry');x,y,w,h=[float(g.get(k)) for k in ('x','y','width','height')]
                assert 0<=x<=x+w<=3200 and 0<=y<=y+h<=1400,(name,c.get('id'))
        print(f'{name}: {len(cells)} native cells; IDs, endpoints and 16:7 bounds OK')


if __name__=='__main__':
    posterior()
    learning()
    validate()
