"""分布与统计路线方法差异：共同步骤＋可编辑的小图。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
BLUE, GREEN, RED, ORANGE, GREY = '#286D99', '#26745A', '#AB4D3D', '#B47744', '#64748B'


def heading(d, key, label, x, y, w, color=BLUE):
    d.text(key, label, x, y, w, 55, size=29, bold=True, color=color)


def point(d, key, x, y, color=BLUE, r=5):
    d.box(key, '', x-r, y-r, 2*r, 2*r, fill=color, color=color, role='point', extra='shape=ellipse;')


def axis(d, key, x, y, w, h, xlabel, ylabel):
    d.line(key+'-x', [(x, y+h), (x+w, y+h)], color=GREY, arrow='block')
    d.line(key+'-y', [(x, y+h), (x, y)], color=GREY, arrow='block')
    d.text(key+'-xl', xlabel, x+w-60, y+h+4, 100, 42, size=24)
    d.text(key+'-yl', ylabel, x-20, y-45, 150, 42, size=24)


def common_steps(d, prefix, labels, color):
    for i, (title, detail) in enumerate(labels):
        d.box(prefix+str(i+1), title+'<br>'+detail, 40+i*1095, 25, 930, 135,
              color=color, fill='#F1F7FB' if color==BLUE else '#F2F8F4', size=30, bold=True)
    for i in (1, 2):
        d.edge(prefix+f'-{i}-{i+1}', prefix+str(i), prefix+str(i+1), color=color)


def regression_demo(d, key, x, y, direction, color):
    us = [.12, .28, .43, .61, .78, .91]
    zs = [.15, .12, .53, .48, .91, .78]
    um, zm = sum(us)/6, sum(zs)/6
    su = sum((u-um)**2 for u in us)
    sz = sum((z-zm)**2 for z in zs)
    suz = sum((u-um)*(z-zm) for u,z in zip(us,zs))
    w,h = 310,230
    axis(d,key,x,y,w,h,r'\(u\)',r'\(z\)')
    if direction == 'horizontal':
        b=suz/sz; a=um-b*zm
        d.line(key+'-fit',[(x+w*(a+b*.02),y+h*(1-.02)),(x+w*(a+b*.97),y+h*(1-.97))],color=color,width=3)
        targets=[(a+b*z,z) for z in zs]
    else:
        b=suz/su; a=zm-b*um
        d.line(key+'-fit',[(x+w*.02,y+h*(1-a-b*.02)),(x+w*.97,y+h*(1-a-b*.97))],color=color,width=3)
        targets=[(u,a+b*u) for u in us]
    for i,((u,z),(ut,zt)) in enumerate(zip(zip(us,zs),targets)):
        d.line(key+f'-res{i}',[(x+w*u,y+h*(1-z)),(x+w*ut,y+h*(1-zt))],color=ORANGE,width=3,dashed=True)
        point(d,key+f'-p{i}',x+w*u,y+h*(1-z),color)


def profile(d, key, x, y, w, h, ylabel, color):
    axis(d,key,x,y,w,h,r'\(\gamma\)',ylabel)
    values=[.12,.24,.44,.67,.86,.98,.94,.75,.46,.18]
    pts=[(x+w*i/(len(values)-1),y+h*(1-v)) for i,v in enumerate(values)]
    d.line(key+'-curve',pts,color=color,width=3)
    px,py=pts[5]
    point(d,key+'-max',px,py,ORANGE,6)
    d.line(key+'-drop',[(px,py),(px,y+h)],color=ORANGE,dashed=True)
    d.text(key+'-estimate',r'\(\widehat\gamma\)',px-40,y+h+4,85,45,size=25,color=ORANGE)


def distribution():
    d=Diagram('distribution-mechanism-wide','分布匹配方法的构造差异',3200,1400)
    common_steps(d,'D',[
        ('D1 分布表示',r'\(p_i\ \leftrightarrow\ F(x_{(i)};\theta)\)'),
        ('D2 匹配准则','残差／概率间距／尺度差异'),
        ('D3 参数确定','求解目标／关系 → 参数估计'),
    ],BLUE)
    d.text('coordinates',r'\(u_i=\ln(x_{(i)}-\gamma),\quad z_i=\ln[-\ln(1-p_i)]\)',50,180,1800,60,size=28)
    d.text('identity',r'\(z_i\approx\beta u_i-\beta\ln\eta\)',1900,180,1230,60,size=29,align='center')
    for key,x,w,fill in [('white-bg',40,770,'#F8FAFC'),('park-bg',835,770,'#F2F8F4'),('mps-bg',1630,630,'#F1F7FB'),('mdm-bg',2285,875,'#F2F8F4')]:
        d.panel(key,x,265,w,1090,fill=fill)

    heading(d,'white-title',r'White → Soman｜\(u\) 对 \(z\) 回归',65,280,720)
    d.text('white-score',r'\(z_i=\mathbb E[Z_{(i:n)}]\)<br>White：\(\gamma=0\)；Soman：候选 \(\gamma\)',65,355,720,95,size=26)
    regression_demo(d,'white-plot',85,500,'horizontal',BLUE)
    d.text('white-fit',r'\(u_i=a+bz_i+e_i\)<br>\(\min\sum_i e_i^2\)<br>\(\widehat\beta=1/b,\quad\widehat\eta=e^a\)',425,490,360,200,size=27)
    d.text('white-residual',r'水平残差 \(u_i-a-bz_i\)',65,785,720,50,size=27,align='center',color=BLUE)
    profile(d,'soman-profile',100,910,600,150,r'\(F(\gamma)\)',BLUE)
    d.box('soman-gamma',r'Soman：\(\widehat\gamma=\arg\max_{\gamma<x_{(1)}}F(\gamma)\)<br>\(F(\gamma)=\frac{(n-2)\mathrm{SST}_u}{(n-1)\mathrm{SSE}_u}\)',75,1150,700,115,color=BLUE,size=27)
    d.text('direction-identity',r'同一 \(z,\gamma\)：\(\widehat\beta_{z\mid u}=r^2\widehat\beta_{u\mid z}\)',65,1280,720,60,size=25,align='center')

    heading(d,'park-title',r'Park Proposed+Plot｜\(z\) 对 \(u\) 回归',860,280,720,GREEN)
    d.text('park-score',r'\(p_i=\begin{cases}\frac{i-3/8}{n+1/4},&n\leq10,\\\frac{i-1/2}{n},&n\geq11.\end{cases}\)',860,350,720,110,size=26)
    regression_demo(d,'park-plot',880,500,'vertical',GREEN)
    d.text('park-fit',r'\(z_i=a+bu_i+e_i\)<br>\(\min\sum_i e_i^2\)<br>\(\widehat\beta=b,\quad\widehat\eta=e^{-a/b}\)',1220,490,360,200,size=27)
    d.text('park-residual',r'竖直残差 \(z_i-a-bu_i\)',860,785,720,50,size=27,align='center',color=GREEN)
    profile(d,'park-profile',895,910,600,150,r'\(r(\gamma)\)',GREEN)
    d.box('park-gamma',r'Park：\(\widehat\gamma=\arg\max_{0\leq\gamma<x_{(1)}}\operatorname{corr}[u(\gamma),z]\)',870,1150,700,90,color=GREEN,size=27)
    d.box('park-recovery',r'\(\widehat\gamma\) → 回归恢复 \(\beta,\eta\)<br>或 → 平移后二参数 MLE',870,1255,700,90,color=GREEN,fill='#EAF4ED',size=25)
    d.edge('park-position-fit','park-gamma','park-recovery',color=GREEN,start='bottom',end='top')

    heading(d,'mps-title','MPS｜概率间距',1655,280,580)
    axis(d,'cdf-axis',1695,430,360,240,r'\(x\)',r'\(F\)')
    curve=[(.02,.02),(.15,.05),(.28,.15),(.40,.35),(.55,.58),(.70,.78),(.85,.91),(.97,.96)]
    d.line('cdf-curve',[(1695+360*x,430+240*(1-f)) for x,f in curve],color=BLUE,width=3)
    levels=[0]+[f for _,f in curve[1:-1]]+[1]
    for i,(x,f) in enumerate(curve[1:-1]):
        point(d,'cdf-p'+str(i),1695+360*x,430+240*(1-f),BLUE)
        d.line('cdf-proj'+str(i),[(1695+360*x,430+240*(1-f)),(2110,430+240*(1-f))],dashed=True,color='#A8BAC7')
    for i,(a,b) in enumerate(zip(levels,levels[1:])):
        d.line('cdf-gap'+str(i),[(2130,430+240*(1-a)),(2130,430+240*(1-b))],color=ORANGE if i==3 else BLUE,width=6)
        d.line('cdf-tick'+str(i),[(2120,430+240*(1-a)),(2140,430+240*(1-a))],color=GREY)
    d.text('spacing-label',r'\(D_i\)',2140,540,90,50,size=28,bold=True,color=ORANGE)
    d.text('mps-endpoints',r'\(F_i=F(x_{(i)};\theta)\)<br>\(F_0=0,\quad F_{n+1}=1\)',1660,725,570,90,size=26,align='center')
    d.box('mps-equations',r'\(D_i=F_i-F_{i-1}\)<br>\(\widehat\theta=\arg\max_\theta\sum_{i=1}^{n+1}\ln D_i\)',1660,835,570,170,color=BLUE,size=28)
    d.box('cdf-wlse',r'CDF-WLSE<br>\(\min_\theta\sum_iw_i(F_i-p_i)^2\)',1660,1150,570,145,color=BLUE,fill='#F8FAFC',size=27)

    heading(d,'mdm-title','MDM｜压缩逐点尺度差异',2310,280,825,GREEN)
    d.text('mdm-input',r'\(p_i=\frac{i-0.3}{n+0.4},\quad\eta_i=\frac{x_{(i)}-\gamma}{[-\ln(1-p_i)]^{1/\beta}}\)',2310,355,825,90,size=28)
    d.text('mdm-spread-before','候选形状',2310,465,170,50,size=26,color=GREY)
    d.text('mdm-spread-after',r'条件形状 \(\beta^*(\gamma)\)',2310,625,270,50,size=26,color=GREEN)
    d.line('mdm-before-axis',[(2470,520),(3090,520)],color=GREY,arrow='block')
    d.line('mdm-after-axis',[(2470,680),(3090,680)],color=GREY,arrow='block')
    before=[.04,.19,.37,.57,.80,.94];after=[.37,.41,.45,.49,.53,.57]
    for i,(a,b) in enumerate(zip(before,after)):
        d.line('mdm-compress'+str(i),[(2470+600*a,520),(2470+600*b,680)],color='#C8DACF',width=2)
        point(d,'mdm-before'+str(i),2470+600*a,520,GREY,6)
        point(d,'mdm-after'+str(i),2470+600*b,680,GREEN,6)
    d.text('mdm-scale-axis',r'\(\eta_i\)',3095,650,65,50,size=27)
    d.text('mdm-conditional',r'\(\beta^*(\gamma)=\arg\min_{\beta\in[0.1,15]}s_\eta(\beta,\gamma)\)<br>\(s_\eta=\operatorname{std}(\eta_1,\ldots,\eta_n)\)',2310,740,825,100,size=28,align='center')
    axis(d,'gradient-axis',2370,935,550,125,r'\(\gamma\)',r'\(g(\gamma)\)')
    d.line('gradient-curve',[(2370,1055),(2460,1050),(2540,1035),(2625,1010),(2710,972),(2790,913)],color=GREEN,width=3)
    d.line('gradient-threshold',[(2370,990),(2920,990)],dashed=True,color=ORANGE,width=2.5)
    point(d,'gradient-cross',2670,990,ORANGE,6)
    d.text('gradient-delta',r'\(\delta\)',2930,965,70,45,size=28,color=ORANGE)
    d.text('mdm-location',r'\(g(\gamma)=ds^*(\gamma)/d\gamma,\quad g(\widehat\gamma)=\delta\)<br>\(\delta=0.1,\quad g(0)\geq\delta\Rightarrow\widehat\gamma=0\)',2310,1120,825,100,size=27)
    d.box('mdm-recover',r'\(\widehat\beta=\beta^*(\widehat\gamma),\quad\widehat\eta=\frac1n\sum_i\eta_i(\widehat\beta,\widehat\gamma)\)',2320,1260,805,75,color=GREEN,fill='#EAF4ED',size=28)
    d.save(ROOT/'02-分布匹配路线-机制图.drawio')


def sample_strip(d, key, x, y, w, values, color=GREEN):
    d.line(key+'-line',[(x,y),(x+w,y)],color='#B8C6BD',width=2)
    for i,t in enumerate(values):point(d,key+str(i),x+w*t,y,color,6)


def density_peak(d,key,x,y,w,h):
    axis(d,key,x,y,w,h,r'\(\beta\)',r'\(L_W\)')
    pts=[(x+w*i/40,y+h*(1-math.exp(-((i/40-.56)/.19)**2))) for i in range(41)]
    d.line(key+'-curve',pts,color=RED,width=3)
    px=x+w*.56
    d.line(key+'-drop',[(px,y),(px,y+h)],color=ORANGE,dashed=True)
    point(d,key+'-peak',px,y,ORANGE,6)
    d.text(key+'-hat',r'\(\widehat\beta_W\)',px-50,y+h+3,110,45,size=25,color=ORANGE)


def statistics():
    d=Diagram('statistics-mechanism-wide','统计关系方法的特征与恢复差异',3200,1400)
    common_steps(d,'S',[
        ('S1 样本特征','矩／次序量／统计量'),
        ('S2 理论关系',r'样本特征 ↔ \((\beta,\eta,\gamma)\)'),
        ('S3 参数识别','匹配／消元／反演'),
    ],GREEN)
    d.text('identity',r'\(X=\gamma+\eta Y,\quad Y\sim\mathrm{Weibull}(\beta,1,0)\)',50,180,3100,60,size=29,align='center')
    xs=[40,670,1300,1930,2560]
    for key,x in zip(['moment-bg','cran-bg','l-moments-bg','w-bg','v-bg'],xs):
        d.panel(key,x,255,600,825,fill='#F2F8F4' if key=='moment-bg' else '#F8FAFC')

    heading(d,'moment-title','常规矩｜均值、散布与偏度',60,270,560,GREEN)
    vals=[.04,.08,.14,.20,.27,.35,.52,.91]
    sample_strip(d,'moment-sample',100,435,470,vals)
    mean=sum(vals)/len(vals)
    d.line('moment-mean',[(100+470*mean,355),(100+470*mean,490)],color=ORANGE,width=3,dashed=True)
    d.text('moment-mean-label',r'\(\bar x\)',100+470*mean-40,330,90,50,size=27,color=ORANGE)
    # 中心距用连接同一均值与各样本点的线段呈现。
    for i,v in enumerate(vals):
        yy=455+i*9
        d.line('moment-deviation'+str(i),[(100+470*mean,yy),(100+470*v,yy)],color='#B9D7C7',width=3)
    d.text('moment-features',r'\(\bar x,\quad m_2,\quad g_1=m_3/m_2^{3/2}\)',65,550,550,65,size=27,align='center')
    # Weibull理论偏度：样本偏度的水平线与G(beta)交点确定形状。
    def skew(beta):
        g1,g2,g3=[math.gamma(1+k/beta) for k in (1,2,3)]
        return (g3-3*g1*g2+2*g1**3)/(g2-g1*g1)**1.5
    bx,by,bw,bh=110,715,440,180
    axis(d,'skew-axis',bx,by,bw,bh,r'\(\beta\)',r'\(G(\beta)\)')
    grid=[.8+5.2*i/60 for i in range(61)]
    lo,hi=-.5,skew(.8)
    coord=lambda b,g:(bx+bw*(b-.8)/5.2,by+bh*(1-(g-lo)/(hi-lo)))
    d.line('skew-curve',[coord(b,skew(b)) for b in grid],color=GREEN,width=3)
    m2=sum((v-mean)**2 for v in vals)/len(vals)
    sample_g1=(sum((v-mean)**3 for v in vals)/len(vals))/m2**1.5
    lower,upper=.8,6.
    for _ in range(60):
        middle=(lower+upper)/2
        if skew(middle)>sample_g1:lower=middle
        else:upper=middle
    target=(lower+upper)/2;px,py=coord(target,sample_g1)
    d.line('sample-skewness',[(bx,py),(bx+bw,py)],color=ORANGE,dashed=True)
    d.line('skew-shape-drop',[(px,py),(px,by+bh)],color=ORANGE,dashed=True)
    point(d,'skew-intersection',px,py,ORANGE,6)
    d.text('sample-skew-label',r'\(g_1\)',515,py-30,75,50,size=27,color=ORANGE)
    d.text('skew-shape-label',r'\(\widehat\beta\)',px-40,by+bh+4,90,45,size=27,color=ORANGE)
    d.text('moment-shape',r'\(g_1=G(\widehat\beta)\)',65,955,550,50,size=28,align='center')
    d.text('moment-recover',r'\(m_2\rightarrow\widehat\eta,\quad\bar x\rightarrow\widehat\gamma\)',65,1010,550,50,size=28,align='center')

    heading(d,'cran-title','Cran｜生存曲线下面积',690,270,560,GREEN)
    d.text('cran-condition',r'\(\gamma\geq0,\quad k=1,2,4\)',695,335,550,45,size=27,align='center')
    cx,cy,cw,ch=720,435,460,200
    axis(d,'survival-axis',cx,cy,cw,ch,r'\(x\)',r'\([1-F(x)]^k\)')
    for k,fill in [(1,'#DFEEE5'),(2,'#B9DCC9'),(4,'#85BFA3')]:
        curve=[]
        for i in range(61):
            t=i/60;surv=1 if t<=.12 else math.exp(-((t-.12)/.48)**2)
            curve.append((cx+cw*t,cy+ch*(1-surv**k)))
        d.polygon('cran-area-'+str(k),[(cx,cy+ch),*curve,(cx+cw,cy+ch)],fill=fill)
        d.line('cran-survival-'+str(k),curve,color=GREEN,width=2.5)
        j={1:43,2:34,4:27}[k]
        tx,ty=curve[j]
        d.text('cran-k-'+str(k),r'\(k='+str(k)+r'\)',tx+5,ty-40,90,45,size=25,color=GREEN)
    d.text('cran-integral',r'\(\bar\mu_k=\int_0^\infty[1-F(x)]^k\,dx\)',695,675,550,65,size=27,align='center')
    # 三条从同一原点起算的面积条，端点之间的差即d12与d24。
    barx=790
    mu={k:.12+.48*math.gamma(1.5)*k**-.5 for k in (1,2,4)}
    lengths={k:390*mu[k]/mu[1] for k in mu}
    for i,k in enumerate((1,2,4)):
        yy=785+i*58
        d.text('cran-m'+str(k),r'\(\bar m_'+str(k)+r'\)',695,yy-12,90,45,size=26)
        d.box('cran-area-bar'+str(k),'',barx,yy,lengths[k],22,fill=['#DFEEE5','#B9DCC9','#85BFA3'][i],color=GREEN,role='bar')
    d.line('cran-d12',[(barx+lengths[2],777),(barx+lengths[1],777)],color=ORANGE,width=6)
    d.text('cran-d12-label',r'\(d_{12}\)',1085,735,100,45,size=25,color=ORANGE)
    d.line('cran-d24',[(barx+lengths[4],835),(barx+lengths[2],835)],color=ORANGE,width=6)
    d.text('cran-d24-label',r'\(d_{24}\)',990,795,100,45,size=25,color=ORANGE)
    d.text('cran-differences',r'\(\frac{d_{12}}{d_{24}}=2^{1/\beta}\)',695,945,550,65,size=29,align='center')
    d.text('cran-recover',r'差比 → \(\widehat\beta\) → \(\widehat\eta,\widehat\gamma\)',695,1010,550,50,size=28,align='center')

    heading(d,'lm-title','PWM → L矩 → TL矩',1320,270,560,GREEN)
    ranks=[i/7 for i in range(8)]
    sample_strip(d,'rank-sample',1380,390,440,ranks)
    d.text('rank-first',r'\(x_{(1)}\)',1335,335,130,45,size=26)
    d.text('rank-last',r'\(x_{(n)}\)',1745,335,130,45,size=26)
    d.text('pwm-weights-title',r'PWM：\(r=1\) 的秩权重',1325,440,550,45,size=27)
    for i,t in enumerate(ranks):
        hh=105*t
        if hh:d.box('pwm-weight'+str(i),'',1380+i*57,615-hh,30,hh,fill='#8DBEA4',color=GREEN,role='bar')
        else:point(d,'pwm-zero'+str(i),1395+i*57,615,GREY,5)
    d.line('pwm-baseline',[(1360,615),(1830,615)],color=GREY)
    d.text('pwm-formula',r'\(b_r=\mathbb E[XF(X)^r]\)',1325,635,550,60,size=28,align='center')
    d.text('lm-weights-title','L矩：有符号线性组合',1325,710,550,45,size=27)
    d.line('lm-baseline',[(1360,830),(1830,830)],color=GREY)
    for i,v in enumerate([2*t-1 for t in ranks]):
        hh=abs(v)*70
        d.box('lm-weight'+str(i),'',1380+i*57,830-hh if v>0 else 830,30,hh,fill=GREEN if v>0 else '#B8C9D8',color=GREEN if v>0 else BLUE,role='bar')
    d.text('lm-formula',r'\(\lambda_2=2b_1-b_0\)',1325,905,550,50,size=27,align='center')
    d.text('tl-weights-title','TL一阶(1,1)：端部权重为0',1325,965,550,45,size=27)
    d.line('tl-baseline',[(1360,1050),(1830,1050)],color=GREY)
    for i,v in enumerate([i*(7-i)/12 for i in range(8)]):
        if v:
            d.box('tl-weight'+str(i),'',1380+i*57,1050-v*42,30,v*42,fill='#8DBEA4',color=GREEN,role='bar')
        else:
            point(d,'tl-zero'+str(i),1395+i*57,1050,GREY,5)

    raw=[.12,.20,.33,.48,.67,.92]
    for prefix,x,title in [('w',1930,'LSPF｜消去位置、尺度'),('v',2560,'LPF｜消去位置')]:
        heading(d,prefix+'-title',title,x+20,270,560,GREEN)
        d.text(prefix+'-input-label',r'次序量 \(X_{(i)}\)',x+25,335,550,45,size=26)
        sample_strip(d,prefix+'-raw',x+70,405,460,raw)
        transformed=[(v-raw[0])/(raw[-1]-raw[0]) for v in raw] if prefix=='w' else [v-raw[0] for v in raw]
        for i,(a,b) in enumerate(zip(raw,transformed)):
            d.line(prefix+'-transform'+str(i),[(x+70+460*a,405),(x+70+460*b,515)],color='#BAD8CA',width=2)
        sample_strip(d,prefix+'-transformed',x+70,515,460,transformed)
        d.text(prefix+'-zero','0',x+45,525,65,40,size=25)
        d.text(prefix+'-last','1' if prefix=='w' else r'\(V_n\)',x+70+460*transformed[-1]-50,525,100,40,size=25)
    d.text('w-formula',r'\(W_i=\frac{X_{(i)}-X_{(1)}}{X_{(n)}-X_{(1)}}\)',1955,590,550,80,size=28,align='center')
    d.text('v-formula',r'\(V_i=X_{(i)}-X_{(1)}\)',2585,590,550,80,size=28,align='center')
    density_peak(d,'w-density',2005,745,420,150)
    d.text('w-maximize',r'\(\widehat\beta_W=\arg\max_\beta L_W(\beta)\)',1955,950,550,50,size=27,align='center')
    d.text('w-recover',r'最小值期望修正 \(\gamma\) → 回代 \(\eta\)',1955,1010,550,50,size=27,align='center')
    # V联合密度有beta、eta两个自变量；同心等值线标出联合峰。
    axis(d,'v-density-axis',2635,735,440,180,r'\(\beta\)',r'\(\eta\)')
    for i,(ww,hh) in enumerate([(375,155),(270,110),(165,65)]):
        d.box('v-density-contour'+str(i),'',2850-ww/2,820-hh/2,ww,hh,
              fill=['#FFF6F2','#F7DDD4','#EDC3B5'][i],color=RED,role='contour',extra='shape=ellipse;')
    point(d,'v-density-peak',2850,820,ORANGE,7)
    d.text('v-density-label',r'\(L_V(\beta,\eta)\)',2690,675,420,50,size=27,align='center',color=RED)
    d.text('v-maximize',r'\((\widehat\beta_V,\widehat\eta_{V0})=\arg\max_{\beta,\eta}L_V\)',2585,950,550,50,size=26,align='center')
    d.text('v-recover',r'固定 \(\widehat\beta_V\) → 似然方程 → \(\widehat\gamma,\widehat\eta\)',2585,1010,550,50,size=26,align='center')

    d.panel('mvlue-bg',40,1110,3120,245,fill='#F2F8F4')
    heading(d,'mvlue-title',r'条件位置 MVLUE｜给定 \(\beta,\eta\)',65,1120,1090,GREEN)
    d.text('mvlue-statistics',r'\(T_i=X_{(i)}-\eta\mathbb E_\beta[Y_{(i)}]\)<br>\(\mathbb E[T_i]=\gamma\)',65,1200,1030,105,size=29)
    d.text('mvlue-weight-title','多估计组合权重',1150,1135,550,45,size=27,align='center')
    for i,v in enumerate([1,.65,.35,.15]):
        d.box('mvlue-weight'+str(i),'',1210+i*125,1280-v*70,65,v*70,fill='#8DBEA4',color=GREEN,role='bar')
        d.text('mvlue-ci'+str(i),r'\(c_'+str(i+1)+r'\)',1195+i*125,1285,95,45,size=26,align='center')
    d.line('mvlue-baseline',[(1185,1280),(1685,1280)],color=GREY)
    d.text('mvlue-covariance',r'\(S=\operatorname{Cov}(T)\)<br>\(\min_c c^{\mathsf T}Sc\)<br>\(\mathbf1^{\mathsf T}c=1\)',1790,1185,600,145,size=28,align='center')
    d.box('mvlue-result',r'\(\widehat\gamma=\sum_i c_iT_i\)',2500,1200,600,100,color=GREEN,size=31)
    d.line('mvlue-output',[(2385,1250),(2480,1250)],color=GREEN,arrow='block')
    d.save(ROOT/'03-统计关系反演路线-机制图.drawio')


def validate():
    for name in ['02-分布匹配路线-机制图.drawio','03-统计关系反演路线-机制图.drawio']:
        root=ET.parse(ROOT/name).getroot()
        cells=root.findall('.//mxCell'); ids=[c.get('id') for c in cells]
        assert len(ids)==len(set(ids)),name
        assert 'title' not in ids and 'legend' not in ids
        model=root.find('.//mxGraphModel')
        assert (model.get('pageWidth'),model.get('pageHeight'))==('3200','1400')
        for c in cells:
            if c.get('edge')=='1':
                assert c.get('source') in ids and c.get('target') in ids,c.attrib
            if c.get('vertex')=='1':
                g=c.find('mxGeometry');x,y,w,h=[float(g.get(k)) for k in ('x','y','width','height')]
                assert 0<=x<=x+w<=3200 and 0<=y<=y+h<=1400,(name,c.get('id'),x,y,w,h)
        print(f'{name}: {len(cells)} native cells; IDs, endpoints, no total title/legend and 16:7 bounds OK')


if __name__=='__main__':
    distribution()
    statistics()
    validate()
