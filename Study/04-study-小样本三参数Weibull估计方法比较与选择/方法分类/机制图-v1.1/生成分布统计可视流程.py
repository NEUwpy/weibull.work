"""用原生 draw.io 图形讲解分布匹配与统计反演的代表性信息处理过程。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
BLUE, GREEN, ORANGE, GREY = '#286D99', '#26745A', '#B47744', '#718297'
SAMPLE = [42., 57., 69., 77., 86., 99., 122.]


def dot(d, key, x, y, color=BLUE, r=6, hollow=False):
    d.box(key, '', x-r, y-r, 2*r, 2*r, fill='#FFFFFF' if hollow else color,
          color=color, role='point', extra='shape=ellipse;strokeWidth=2;')


def text(d, key, value, x, y, w, h=50, size=25, bold=False):
    return d.text(key, value, x, y, w, h, size=size, bold=bold)


def stage(d, key, title, x, y, fill):
    d.panel(key+'-bg', x, y, 900, 430, fill=fill, color='#DEE6EC')
    text(d, key+'-heading', title, x+20, y+10, 860, 60, 29, True)


def axes(d, key, x, y, w, h, xlabel, ylabel, xmin=0, xmax=1, ymin=0, ymax=1):
    d.line(key+'-x', [(x, y+h), (x+w, y+h)], color=GREY, arrow='block')
    d.line(key+'-y', [(x, y+h), (x, y)], color=GREY, arrow='block')
    text(d, key+'-xl', xlabel, x+w-110, y+h+4, 145, 45, 23)
    text(d, key+'-yl', ylabel, x-30, y-42, 180, 45, 23)
    return lambda a,b: (x+w*(a-xmin)/(xmax-xmin),y+h*(1-(b-ymin)/(ymax-ymin)))


def curve(d, key, coords, color=BLUE, width=3.5, dashed=False):
    d.line(key, list(coords), color=color, width=width, dashed=dashed)


def connect_stages(d, color):
    d.line('step-1-2', [(960,425),(1030,425)], color=color, width=3.5, arrow='block')
    d.line('step-2-3', [(1500,645),(1500,697),(500,697),(500,730)], color=color, width=3.5, arrow='block')
    d.line('step-3-4', [(960,955),(1030,955)], color=color, width=3.5, arrow='block')


def legend(d,key,x,y,label,color):
    d.line(key+'-line',[(x,y+20),(x+40,y+20)],color=color,width=4)
    text(d,key+'-label',label,x+50,y-5,180,50,24)


def cdf(x,beta,eta,gamma=0):
    return 0 if x<=gamma else -math.expm1(-((x-gamma)/eta)**beta)


def distribution():
    d=Diagram('visual-distribution-flow','分布匹配：由样本概率点到匹配准则',2000,1460)
    text(d,'title','分布匹配｜把样本分布画出来，再让模型与它对齐',45,20,1910,70,35,True)
    text(d,'subtitle','以 CDF 平方差为讲解骨架：①②构造比较对象，③把偏离量化，④以整组差异判断参数。',45,105,1910,60,26)
    stage(d,'empirical','① 由排序寿命构造样本概率点',50,205,'#F1F7FB')
    stage(d,'candidate','② 把候选分布放到同一坐标中',1050,205,'#F1F7FB')
    stage(d,'difference','③ 看每个点偏了多少，再合起来',50,735,'#F8FAFC')
    stage(d,'criterion','④ 选择整组偏离较小的候选',1050,735,'#F2F8F4')
    connect_stages(d,BLUE)
    xs=[.18,.32,.41,.49,.57,.68,.88]
    n=len(xs);ps=[(i-.3)/(n+.4) for i in range(1,n+1)]
    fa=[cdf(x,1.0,.65) for x in xs]
    fb=[cdf(x,2.0,.62) for x in xs]
    qa=sum((f-p)**2 for f,p in zip(fa,ps));qb=sum((f-p)**2 for f,p in zip(fb,ps))
    p1=axes(d,'sample-probability',105,340,450,205,'寿命 \\(x\\)','概率',xmax=1)
    for i,(x,p) in enumerate(zip(xs,ps)):
        dot(d,'sample-point-'+str(i),*p1(x,p),BLUE)
    text(d,'sample-meaning','寿命越大，<br>对应的累积概率越高。<br><br>一组观测变成一组<br>可与理论分布比较的点。',615,325,300,220,25)
    text(d,'probability-ranks','\\(x_{(i)}\\longleftrightarrow p_i\\)\u3000此处用 \\(p_i=\\frac{i-0.3}{n+0.4}\\)',90,565,820,65,24)

    p2=axes(d,'candidate-probability',1105,340,450,205,'寿命 \\(x\\)','概率',xmax=1)
    grid=[i/80 for i in range(81)]
    curve(d,'cdf-a',[p2(x,cdf(x,1.0,.65)) for x in grid],ORANGE)
    curve(d,'cdf-b',[p2(x,cdf(x,2.0,.62)) for x in grid],GREEN)
    for i,(x,p) in enumerate(zip(xs,ps)):
        dot(d,'candidate-point-'+str(i),*p2(x,p),BLUE)
    for i in [0,3,5]:
        d.line('candidate-residual-'+str(i),[p2(xs[i],ps[i]),p2(xs[i],fa[i])],color=ORANGE,width=3,dashed=True)
    legend(d,'a-legend',1610,330,'候选 \\(A\\)',ORANGE)
    legend(d,'b-legend',1610,390,'候选 \\(B\\)',GREEN)
    text(d,'model-changes','改变 \\(\\beta\\)、\\(\\eta\\)、\\(\\gamma\\)<br>会改变曲线的<br>弯曲、伸展和位置。',1615,455,295,130,25)
    text(d,'cdf-object','同一组样本点保持固定；比较 \\(F_\\theta(x_{(i)})\\) 与 \\(p_i\\) 的距离。',1085,580,825,45,24)

    text(d,'residual-axis-title','每个观测的概率偏离绝对值',90,815,510,45,24)
    left,top,barw,scale=135,880,390,390/.27
    d.line('residual-zero',[(left,top-12),(left,top+210)],color=GREY,width=2)
    for i,(a,b,p) in enumerate(zip(fa,fb,ps)):
        yy=top+i*29
        text(d,f'obs-{i}',rf'\({i+1}\)',80,yy-15,50,40,23)
        d.box(f'residual-a-{i}','',left,yy,max(2,abs(a-p)*scale),8,fill=ORANGE,color=ORANGE,role='background')
        d.box(f'residual-b-{i}','',left,yy+10,max(2,abs(b-p)*scale),8,fill=GREEN,color=GREEN,role='background')
    text(d,'residual-formula','逐点偏离<br>\\(e_i(\\theta)=F_\\theta(x_{(i)})-p_i\\)<br><br>平方后相加<br>\\(D(\\theta)=\\sum_{i=1}^n e_i(\\theta)^2\\)',580,835,350,260,26)
    text(d,'residual-purpose','每个观测贡献一个差异；评分同时考虑整组观测。',90,1115,815,45,24)

    scoremax=max(qa,qb)*1.35
    p4=axes(d,'total-score',1125,875,430,210,'候选','总平方差 \\(D\\)',xmin=0,xmax=3,ymax=scoremax)
    for key,x,q,color in [('a',.75,qa,ORANGE),('b',2.,qb,GREEN)]:
        bx,by=p4(x,q);base=p4(x,0)[1]
        d.box('score-'+key,'',bx-55,by,110,base-by,fill=color,color=color,role='background')
        text(d,'score-label-'+key,rf'\({key.upper()}\)',bx-40,base+5,80,45,25,True)
        text(d,'score-value-'+key,rf'\({q:.3f}\)',bx-65,by-45,130,45,24)
    text(d,'selected-rule','比较总差异<br>\\(D(B)<D(A)\\)<br><br>这组示意候选中，<br>\\(B\\) 与样本更一致。',1620,850,295,225,27,True)
    text(d,'criterion-objective','参数确定原则：最小化 \\(D(\\theta)\\)。连续求解时据此更新候选参数。',1085,1115,830,45,24)

    d.line('interface-divider',[(50,1225),(1950,1225)],color='#DEE6EC',width=2)
    text(d,'interfaces-title','后续讲方法差异时，对照这些步骤',55,1237,1890,55,27,True)
    text(d,'plot-interface','①②换坐标：概率图改用对数寿命与分数，③④再区分回归方向和位置评分。',55,1300,1890,50,24)
    text(d,'mps-interface','③换对象：MPS比较相邻 CDF 概率间距，并最大化其对数和。',55,1345,1890,50,24)
    text(d,'mdm-interface','②③④换构造：MDM用伪尺度的条件最小离散曲线，再按梯度阈值\\(\\delta\\)定位，最后取尺度均值。',55,1390,1890,50,24)
    text(d,'demo-note','原理示意：7个玩具观测、两组候选参数；图中条长与评分由这些点计算。',55,164,1890,40,23)
    d.save(ROOT/'08-分布匹配路线-信息处理流程.drawio')


def skewness(beta):
    g1,g2,g3=[math.gamma(1+k/beta) for k in (1,2,3)]
    a2=g2-g1*g1
    return (g3-3*g1*g2+2*g1**3)/a2**1.5


def density_y(y,beta):
    return 0 if y<=0 else beta*y**(beta-1)*math.exp(-y**beta)


def statistics():
    d=Diagram('visual-statistics-flow','统计关系反演：用统计特征消元并恢复参数',2000,1510)
    text(d,'title','统计关系反演｜先压缩出特征，再利用理论关系拆开未知参数',45,20,1910,70,35,True)
    text(d,'subtitle','以常规矩法为讲解骨架：①提取特征，②消去位置尺度，③反解形状，④恢复原量纲。',45,105,1910,60,26)
    text(d,'demo-note','原理示意：7个玩具观测；图中的平移、拉伸和理论曲线用于解释处理过程。',55,164,1890,40,23)
    stage(d,'features','① 把一组寿命压缩成分布特征',50,205,'#F2F8F4')
    stage(d,'cancel','② 用中心化和比值消去位置、尺度',1050,205,'#F2F8F4')
    stage(d,'solve','③ 用形状的理论关系寻找交点',50,735,'#F8FAFC')
    stage(d,'recover','④ 用方差与均值恢复尺度、位置',1050,735,'#F2F8F4')
    connect_stages(d,GREEN)
    n=len(SAMPLE);mean=sum(SAMPLE)/n
    m2=sum((x-mean)**2 for x in SAMPLE)/n;m3=sum((x-mean)**3 for x in SAMPLE)/n
    sd=math.sqrt(m2);sample_skew=m3/sd**3
    lo,hi=.7,7.
    for _ in range(100):
        mid=(lo+hi)/2
        if skewness(mid)>sample_skew:lo=mid
        else:hi=mid
    bh=(lo+hi)/2
    ey=math.gamma(1+1/bh);sdy=math.sqrt(math.gamma(1+2/bh)-ey**2)
    eh=sd/sdy;gh=mean-eh*ey
    p1=axes(d,'histogram',105,340,460,205,'寿命 \\(x\\)','频数',xmin=30,xmax=140,ymax=3)
    for i,(lower,upper) in enumerate([(35,55),(55,75),(75,95),(95,115),(115,135)]):
        count=sum(lower<=x<upper for x in SAMPLE)
        bx,by=p1(lower,count);right,base=p1(upper,0)
        d.box('hist-'+str(i),'',bx+3,by,right-bx-6,base-by,fill='#B6D9CB',color=GREEN,role='background')
    curve(d,'histogram-mean',[p1(mean,0),p1(mean,2.65)],ORANGE,2.5,True)
    text(d,'mean-marker','均值',p1(mean,0)[0]-40,550,100,45,23)
    text(d,'observed-features','位置：均值 \\(\\bar{x}\\)<br><br>散布：方差 \\(m_2\\)<br><br>不对称：偏度 \\(\\widehat{g}\\)',625,325,280,245,27)
    text(d,'sample-moment-def','由观测计算：\\(m_k=\\frac{1}{n}\\sum_{i=1}^n(x_i-\\bar{x})^k\\)，此处取 \\(k=2,3\\)。',90,565,820,65,24)

    # 两组有确定仿射关系的数据在标准化后逐点重合。
    moved=[18+1.35*x for x in SAMPLE]
    for key,vals,yy,color,label in [('raw',SAMPLE,365,BLUE,'原样本'),('affine',moved,450,ORANGE,'平移并拉伸后')]:
        d.line(key+'-baseline',[(1110,yy),(1590,yy)],color=GREY,width=1.8,arrow='block')
        for i,x in enumerate(vals):dot(d,key+'-'+str(i),1110+480*x/200,yy,color,5)
        text(d,key+'-label',label,1100,yy-55,470,45,23)
    d.line('standardized-baseline',[(1110,560),(1590,560)],color=GREY,width=1.8,arrow='block')
    for i,x in enumerate(SAMPLE):
        xx=1110+480*((x-mean)/sd+2)/4
        dot(d,'standardized-affine-'+str(i),xx,560,ORANGE,8,True)
        dot(d,'standardized-raw-'+str(i),xx,560,BLUE,4)
    text(d,'overlap-label','各自中心化并标准化后：逐点重合',1100,502,495,45,23)
    text(d,'cancel-description','平移不改变<br>中心化后的偏差。<br><br>比值消去\\(\\eta^3\\)：<br>\\(\\widehat{g}=\\frac{m_3}{m_2^{3/2}}\\)',1640,320,265,230,25)
    text(d,'cancel-object','标准化后的偏度只保留分布形状的信息。',1085,585,825,45,24)

    p3=axes(d,'shape-relation',110,875,455,210,'形状 \\(\\beta\\)','理论偏度',xmin=.7,xmax=6,ymin=-.5,ymax=3.5)
    bs=[.7+i*(6-.7)/120 for i in range(121)]
    curve(d,'shape-curve',[p3(b,skewness(b)) for b in bs],GREEN)
    curve(d,'sample-skew-line',[p3(.7,sample_skew),p3(6,sample_skew)],ORANGE,2.5,True)
    curve(d,'shape-root-line',[p3(bh,-.5),p3(bh,sample_skew)],BLUE,2.5,True)
    dot(d,'shape-root',*p3(bh,sample_skew),BLUE,7)
    text(d,'shape-root-label','\\(\\widehat{\\beta}\\)',p3(bh,-.5)[0]-30,1090,80,45,25,True)
    text(d,'skew-target','样本给出水平线 \\(\\widehat{g}\\)<br>模型给出曲线 \\(g(\\beta)\\)<br><br>在交点处：<br>\\(g(\\widehat{\\beta})=\\widehat{g}\\)<br>由此确定形状。',625,825,285,270,26)
    text(d,'shape-purpose','用一个只含\\(\\beta\\)的关系求根，不再同时处理三个未知量。',90,1115,820,45,24)

    p4a=axes(d,'unit-y',1110,840,450,90,'标准 \\(Y\\)','密度',xmin=0,xmax=2.5,ymax=2)
    grid=[i*2.5/100 for i in range(101)]
    curve(d,'unit-y-density',[p4a(y,density_y(y,bh)) for y in grid],BLUE)
    curve(d,'unit-y-mean',[p4a(ey,0),p4a(ey,1.5)],ORANGE,2,True)
    text(d,'affine-verb','乘 \\(\\eta\\) 拉伸，再加 \\(\\gamma\\) 平移',1120,955,430,45,25,True)
    d.line('affine-arrow',[(1325,1000),(1325,1020)],color=GREEN,width=3,arrow='block')
    p4b=axes(d,'restored-x',1110,1030,450,75,'寿命 \\(X\\)','密度',xmin=20,xmax=170,ymax=.025)
    gridx=[20+i*150/100 for i in range(101)]
    curve(d,'restored-x-density',[p4b(x,density_y((x-gh)/eh,bh)/eh) for x in gridx],GREEN)
    curve(d,'restored-x-mean',[p4b(mean,0),p4b(mean,.021)],ORANGE,2,True)
    text(d,'restore-rules','形状固定为 \\(\\widehat{\\beta}\\) 后<br><br>\\(\\widehat{\\eta}=\\frac{\\sqrt{m_2}}{\\operatorname{sd}_{\\widehat{\\beta}}(Y)}\\)<br><br>\\(\\widehat{\\gamma}=\\bar{x}-\\widehat{\\eta}\\mathbb{E}_{\\widehat{\\beta}}[Y]\\)',1620,815,295,290,26)
    text(d,'recover-purpose','方差定伸展；均值定平移。',1085,1115,490,45,24)

    d.line('interface-divider',[(50,1225),(1950,1225)],color='#DEE6EC',width=2)
    text(d,'interfaces-title','后续讲方法差异时，对照这些步骤',55,1237,1890,55,27,True)
    text(d,'cran-interface','①②换统计量：Cran改用生存积分矩；\\(\\gamma\\geq0\\)时由矩差比反解。PWM／L矩／TL矩改排序权重。',55,1300,1890,50,24)
    text(d,'wv-interface','②③换消元与准则：\\(W\\)消\\(\\gamma\\)、\\(\\eta\\)后以联合密度估\\(\\beta\\)；\\(V\\)只消\\(\\gamma\\)，先联合估\\(\\eta\\)、\\(\\beta\\)，再保留\\(\\beta\\)恢复其余参数。',55,1350,1890,50,24)
    text(d,'linear-interface','③④换成条件选权：给定\\(\\beta\\)、\\(\\eta\\)构造无偏位置量，再按协方差组合；未知时另以临时估计代入。',55,1400,1890,50,24)
    text(d,'notation','这里\\(Y\\)为尺度1、位置0的Weibull变量；平移、正尺度变换保持偏度不变。',55,1450,1890,45,23)
    d.save(ROOT/'09-统计关系反演路线-信息处理流程.drawio')


def validate():
    for name in ['08-分布匹配路线-信息处理流程.drawio','09-统计关系反演路线-信息处理流程.drawio']:
        root=ET.parse(ROOT/name).getroot();cells=root.findall('.//mxCell')
        ids=[c.get('id') for c in cells];assert len(ids)==len(set(ids))
        model=root.find('.//mxGraphModel');w,h=float(model.get('pageWidth')),float(model.get('pageHeight'))
        for c in cells:
            if c.get('edge')=='1':assert c.get('source') in ids and c.get('target') in ids
            if c.get('vertex')=='1':
                g=c.find('mxGeometry');x,y,cw,ch=[float(g.get(k,0)) for k in ['x','y','width','height']]
                assert min(x,y)>=0 and x+cw<=w and y+ch<=h,(name,c.get('id'))
        print(f'{name}: {len(cells)} cells; XML, IDs, endpoints and bounds OK')


if __name__=='__main__':
    distribution()
    statistics()
    validate()
