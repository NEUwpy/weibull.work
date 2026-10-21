'分布匹配与统计关系反演的机制细图，独立于总览地图。'
from pathlib import Path
import math
import xml.etree.ElementTree as ET

from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
BLUE, GREEN, ORANGE, GREY = '#286D99', '#26745A', '#B47744', '#64748B'


def heading(d, key, label, x, y, w, color=BLUE):
    d.text(key, label, x, y, w, 55, size=29, bold=True, color=color)


def point(d, key, x, y, color=BLUE, r=5):
    d.box(key, '', x-r, y-r, 2*r, 2*r, fill=color, color=color,
          role='point', extra='shape=ellipse;')


def axis(d, key, x, y, w, h, xlabel, ylabel):
    d.line(key+'-x', [(x, y+h), (x+w, y+h)], color=GREY, arrow='block')
    d.line(key+'-y', [(x, y+h), (x, y)], color=GREY, arrow='block')
    d.text(key+'-xl', xlabel, x+w-60, y+h+3, 100, 40, size=23)
    d.text(key+'-yl', ylabel, x-30, y-45, 100, 40, size=23)


def regression_demo(d, key, x, y, direction, color):
    '同一组人为示意点；分别画水平和竖直的最小二乘残差。'
    us = [.12, .28, .43, .61, .78, .91]
    zs = [.15, .12, .53, .48, .91, .78]
    um, zm = sum(us)/6, sum(zs)/6
    su = sum((u-um)**2 for u in us)
    sz = sum((z-zm)**2 for z in zs)
    suz = sum((u-um)*(z-zm) for u,z in zip(us,zs))
    w,h = 310,230
    axis(d,key,x,y,w,h,'\\(u\\)','\\(z\\)')
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


def distribution():
    d=Diagram('distribution-mechanism-detail','分布匹配：变换、残差、概率间距与尺度一致性',2000,1900)
    heading(d,'title','分布匹配：同一条 Weibull 分布关系，怎样变成不同的估计依据？',45,25,1920)
    d.text('subtitle','形状 \\(\\beta\\) · 尺度 \\(\\eta\\) · 位置 \\(\\gamma\\)；排序寿命 \\(x_{(1)}<\\cdots<x_{(n)}\\)，候选位置 \\(\\gamma<x_{(1)}\\)',45,80,1920,45,size=24)
    d.panel('identity-bg',45,145,1910,180,fill='#F1F7FB')
    d.text('cdf','\\(F(x;\\theta)=1-\\exp\\left[-\\left(\\frac{x-\\gamma}{\\eta}\\right)^\\beta\\right]\\)',70,162,690,65,size=29,bold=True)
    d.text('coordinates','\\(p_i\\longrightarrow q_i=-\\ln(1-p_i)\\longrightarrow z_i=\\ln q_i\\)<br>\\(x_{(i)}\\longrightarrow u_i(\\gamma)=\\ln(x_{(i)}-\\gamma)\\)',795,160,1110,85,size=27)
    d.text('identity','概率图关系：\\(z_i\\approx\\beta u_i(\\gamma)-\\beta\\ln\\eta\\)\u3000\u3000⇄\u3000\u3000逐点反推尺度：\\(\\eta_i=\\frac{x_{(i)}-\\gamma}{q_i^{\\frac{1}{\\beta}}}\\)',70,250,1840,80,size=27,bold=True)

    d.panel('regression-bg',45,360,1910,720,fill='#F8FAFC')
    heading(d,'regression-title','A\u3000概率图：分数、位置与回归方向，分别改变哪一步？',70,376,1850)
    d.line('regression-divider',[(1000,446),(1000,990)],color='#D7E2EB',width=2)
    heading(d,'white-title','White → Soman：对数寿命 \\(u\\) 对分数 \\(z\\) 回归',75,440,900)
    d.text('white-score','White：\\(z_i=\\mathbb{E}[Z_{(i:n)}]\\)，\\(Z\\) 的密度 \\(h(z)=\\exp(z-e^z)\\)<br>两参数时 \\(\\gamma=0\\)；Soman 主分支将其接到候选 \\(\\gamma\\) 上',80,500,875,82,size=24)
    regression_demo(d,'white-plot',110,640,'horizontal',BLUE)
    d.text('white-fit','\\(u_i=a+bz_i+e_i\\)<br>\\(\\min_{a,b}\\sum_{i=1}^n(u_i-a-bz_i)^2\\)<br><br>\\(\\widehat{\\beta}=\\frac{1}{b}\\)<br>\\(\\widehat{\\eta}=\\exp(a)\\)',455,622,470,235,size=27)
    d.text('white-distance','水平残差：在同一 \\(z\\) 上比较 \\(u\\)<br>示意点用于解释距离方向',85,905,875,70,size=23)
    d.text('soman-gamma','Soman 选位置：最大化 \\(F(\\gamma)=\\frac{(n-2)\\mathrm{SST}_u}{(n-1)\\mathrm{SSE}_u}\\)<br>每换一个 \\(\\gamma\\)，重新计算 \\(u\\)、回归与评分',80,980,880,100,size=24)

    heading(d,'park-title','Park Proposed+Plot：分数 \\(z\\) 对对数寿命 \\(u\\) 回归',1020,440,900)
    d.text('park-score','\\(p_i=\\begin{cases}\\frac{i-\\tfrac{3}{8}}{n+\\tfrac{1}{4}},&n\\leq10,\\\\\\frac{i-\\tfrac{1}{2}}{n},&n\\geq11.\\end{cases}\\)<br>再取 \\(z_i=\\ln[-\\ln(1-p_i)]\\)',1020,500,900,130,size=24)
    regression_demo(d,'park-plot',1060,640,'vertical',GREEN)
    d.text('park-fit','\\(z_i=a+bu_i+e_i\\)<br>\\(\\min_{a,b}\\sum_{i=1}^n(z_i-a-bu_i)^2\\)<br><br>\\(\\widehat{\\beta}=b\\)<br>\\(\\widehat{\\eta}=\\exp\\left(-\\frac{a}{b}\\right)\\)',1400,622,470,235,size=27)
    d.text('park-distance','竖直残差：在同一 \\(u\\) 上比较 \\(z\\)<br>同一组示意点，换了被最小化的距离',1020,905,900,70,size=23)
    d.text('park-gamma','Park 选位置：\\(\\widehat{\\gamma}=\\operatorname*{arg\\,max}_{0\\leq\\gamma<x_{(1)}}\\;\\operatorname{corr}[u(\\gamma),z]\\)<br>定位后可接上述回归，也可接平移样本的二参数 MLE',1020,980,900,100,size=24)
    d.text('direction-identity','固定同一组 \\(z\\)、同一 \\(\\gamma\\) 时：\\(\\widehat{\\beta}_{z\\mid u}=r^2\\widehat{\\beta}_{u\\mid z}\\)。实际 White 与 Park 还使用不同分数。',70,1090,1870,50,size=24,bold=True)

    d.panel('mps-bg',45,1180,680,630,fill='#F1F7FB')
    heading(d,'mps-title','B\u3000MPS：把观测映到 CDF 纵轴',65,1195,640)
    axis(d,'cdf-axis',110,1330,400,210,'\\(x\\)','\\(F\\)')
    curve=[(.02,.02),(.15,.05),(.28,.15),(.40,.35),(.55,.58),(.70,.78),(.85,.91),(.97,.96)]
    d.line('cdf-curve',[(110+400*x,1330+210*(1-f)) for x,f in curve],color=BLUE,width=3)
    for i,(x,f) in enumerate(curve[1:-1]):
        point(d,'cdf-p'+str(i),110+400*x,1330+210*(1-f),BLUE)
        d.line('cdf-proj'+str(i),[(110+400*x,1330+210*(1-f)),(545,1330+210*(1-f))],dashed=True,color='#A8BAC7')
    d.line('spacing',[(560,1330+210*(1-.35)),(560,1330+210*(1-.58))],color=ORANGE,width=5)
    d.text('spacing-label','\\(D_i\\)',565,1410,90,45,size=27,bold=True,color=ORANGE)
    d.text('cdf-demo','CDF 曲线与观测位置为原理示意',85,1580,610,45,size=23)
    d.text('mps-equations','\\(F_i=F(x_{(i)};\\theta),\\quad F_0=0,\\quad F_{n+1}=1\\)<br>\\(D_i=F_i-F_{i-1}\\)<br>\\(\\widehat{\\theta}=\\operatorname*{arg\\,max}_{\\theta}\\sum_{i=1}^{n+1}\\ln D_i\\)<br>候选 \\(\\theta\\) 改变每个概率区间的长度',70,1620,620,180,size=25)

    d.panel('mdm-bg',765,1180,1190,630,fill='#F2F8F4')
    heading(d,'mdm-title','C\u3000MDM：每个点都能反推 \\(\\eta\\)，让这些尺度尽量一致',785,1195,1145,GREEN)
    d.text('mdm-input','\\(p_i=\\frac{i-0.3}{n+0.4},\\qquad\\eta_i(\\beta,\\gamma)=\\frac{x_{(i)}-\\gamma}{[-\\ln(1-p_i)]^{\\frac{1}{\\beta}}}\\)',790,1245,1130,80,size=25)
    d.text('mdm-conditional-title','① 固定 \\(\\gamma\\)，只沿 \\(\\beta\\) 压缩尺度离散',785,1330,540,45,size=25,bold=True,color=GREEN)
    d.text('mdm-conditional','\\(s_\\eta=\\operatorname{std}(\\eta_1,\\ldots,\\eta_n)\\)<br>\\(\\beta^*(\\gamma)=\\operatorname*{arg\\,min}_{\\beta}\\;s_\\eta(\\beta,\\gamma)\\)<br>当前求解域 \\(\\beta\\in[0.1,15]\\)<br>\\(s^*(\\gamma)=s_\\eta[\\beta^*(\\gamma),\\gamma]\\)',790,1380,530,185,size=26)
    d.text('mdm-gradient-title','② 随 \\(\\gamma\\) 得到廓线，再按梯度定位',1365,1330,545,45,size=25,bold=True,color=GREEN)
    axis(d,'gradient-axis',1415,1420,400,125,'\\(\\gamma\\)','\\(g(\\gamma)\\)')
    d.line('gradient-curve',[(1415,1540),(1480,1535),(1540,1520),(1600,1493),(1660,1458),(1720,1398)],color=GREEN,width=3)
    d.line('gradient-threshold',[(1415,1475),(1815,1475)],dashed=True,color=ORANGE,width=2.5)
    point(d,'gradient-cross',1630,1475,ORANGE,6)
    d.text('gradient-delta','\\(\\delta\\)',1820,1450,60,45,size=27,color=ORANGE)
    d.text('gradient-caption','\\(g(\\gamma)=\\frac{ds^*(\\gamma)}{d\\gamma}\\)；曲线为原理示意',1365,1580,545,45,size=23)
    d.text('mdm-location','位置规则：\\(g(\\widehat{\\gamma})=\\delta\\)（MDM-0.1 取 \\(\\delta=0.1\\)）；\\(g(0)\\geq\\delta\\) 时，\\(\\widehat{\\gamma}=0\\)',790,1640,1130,55,size=25,bold=True)
    d.text('mdm-recover','③ \\(\\widehat{\\beta}=\\beta^*(\\widehat{\\gamma}),\\qquad\\widehat{\\eta}=\\frac{1}{n}\\sum_{i=1}^n\\eta_i(\\widehat{\\beta},\\widehat{\\gamma})\\)<br>形状来自条件最小差异；位置来自梯度规则；尺度来自伪尺度均值。',790,1700,1130,100,size=25)
    d.text('distribution-footer','其他拟合对象：CDF-WLSE 比较 \\(\\sum_{i=1}^n w_i(F_i-p_i)^2\\)；密度拟合比较经验密度与参数密度。它们改变的是被比较的量。',55,1820,1890,70,size=23)
    d.save(ROOT/'02-分布匹配路线-机制图.drawio')


def statistics():
    d=Diagram('statistics-mechanism-detail','统计关系反演：提取统计量、消元与参数恢复',2000,2610)
    heading(d,'title','统计特征关系匹配与反演｜S1 特征 → S2 理论关系 → S3 识别参数',45,25,1920,GREEN)
    d.text('identity','模型依赖：\\(X=\\gamma+\\eta Y\\)，\\(Y\\) 的分布只由 \\(\\beta\\) 决定。差值消去 \\(\\gamma\\)，标准化比值进一步消去 \\(\\eta\\)。',45,88,1910,55,size=27)

    d.panel('moment-bg',45,175,1910,470,fill='#F2F8F4')
    heading(d,'moment-title','A\u3000常规矩示例：选偏度、方差与均值，匹配理论关系',65,190,1870,GREEN)
    d.box('sample-moments','从样本提取<br>\\(\\bar{x}=\\frac{1}{n}\\sum_{i=1}^n x_i\\)<br>\\(m_2=\\frac{1}{n}\\sum_{i=1}^n(x_i-\\bar{x})^2\\)<br>\\(m_3=\\frac{1}{n}\\sum_{i=1}^n(x_i-\\bar{x})^3\\)<br>样本偏度 \\(g_1=\\frac{m_3}{m_2^{3/2}}\\)',80,285,460,220,fill='#FFFFFF',color=GREEN,size=26)
    d.box('shape-equation','总体关系消去 \\(\\gamma\\)、\\(\\eta\\)<br>\\(G_k(\\beta)=\\Gamma\\left(1+\\frac{k}{\\beta}\\right)\\)<br>\\(A_2=G_2-G_1^2\\)<br>\\(A_3=G_3-3G_1G_2+2G_1^3\\)<br>解 \\(g_1=\\frac{A_3}{A_2^{3/2}}\\) 得 \\(\\widehat{\\beta}\\)',620,285,640,220,fill='#FFFFFF',color=GREEN,size=26)
    d.box('moment-recover','参数恢复<br>\\(\\widehat{\\eta}=\\sqrt{\\frac{m_2}{A_2(\\widehat{\\beta})}}\\)<br>\\(\\widehat{\\gamma}=\\bar{x}-\\widehat{\\eta}G_1(\\widehat{\\beta})\\)<br><br>先 \\(\\beta\\)，再 \\(\\eta\\)，再 \\(\\gamma\\)',1340,285,540,220,fill='#FFFFFF',color=GREEN,size=27)
    d.edge('sample-to-equation','sample-moments','shape-equation',color=GREEN)
    d.edge('shape-to-recover','shape-equation','moment-recover',color=GREEN)
    d.text('moment-explanation','中心化去掉位置；三阶中心矩与方差的 \\(\\frac{3}{2}\\) 次方相除，尺度 \\(\\eta^3\\) 抵消；最后用未标准化的量恢复 \\(\\eta\\)、\\(\\gamma\\)。',75,552,1830,65,size=25)

    d.panel('cran-bg',45,685,935,700,fill='#F8FAFC')
    heading(d,'cran-title','B1\u3000Cran：把幂矩改成生存曲线的积分',65,700,895,GREEN)
    d.text('cran-theory','非负位置 \\(\\gamma\\geq0\\) 时<br>\\(\\bar{\\mu}_k=\\int_0^\\infty[1-F(x)]^k\\,dx\\)<br>\\(=\\gamma+\\eta\\Gamma\\left(1+\\frac{1}{\\beta}\\right)k^{-\\frac{1}{\\beta}}\\)',75,770,870,150,size=27)
    d.text('cran-sample','样本阶梯积分（\\(x_{(0)}=0\\)）<br>\\(\\bar{m}_k=\\sum_{r=0}^{n-1}\\left(1-\\frac{r}{n}\\right)^k[x_{(r+1)}-x_{(r)}]\\)<br>提取 \\(k=1,2,4\\)；\\(\\bar{m}_1=\\bar{x}\\)',75,925,870,140,size=26)
    d.box('cran-differences','\\(d_{12}=\\bar{m}_1-\\bar{m}_2,\\quad d_{24}=\\bar{m}_2-\\bar{m}_4\\)<br>总体 \\(\\frac{d_{12}}{d_{24}}=2^{\\frac{1}{\\beta}}\\)<br>差值消 \\(\\gamma\\)，再作比值消 \\(\\eta\\)',80,1080,835,135,fill='#F2F8F4',color=GREEN,size=25)
    d.text('cran-recover','\\(\\widehat{\\beta}=\\frac{\\ln2}{\\ln d_{12}-\\ln d_{24}}\\)<br>\\(\\widehat{\\gamma}=\\frac{\\bar{m}_1\\bar{m}_4-\\bar{m}_2^2}{\\bar{m}_1+\\bar{m}_4-2\\bar{m}_2}\\)<br>\\(\\widehat{\\eta}=\\frac{\\bar{m}_1-\\widehat{\\gamma}}{\\Gamma(1+\\frac{1}{\\widehat{\\beta}})}\\)',75,1220,875,160,size=25)

    d.panel('l-moments-bg',1020,685,935,700,fill='#F8FAFC')
    heading(d,'lm-title','B2\u3000PWM → L矩 → TL矩：改造样本权重',1040,700,895,GREEN)
    d.text('pwm','PWM：\\(b_r=\\mathbb{E}[XF(X)^r]\\)<br>\\(\\widehat{b}_r=\\frac{1}{n}\\sum_{i=1}^n\\frac{\\binom{i-1}{r}}{\\binom{n-1}{r}}x_{(i)}\\)<br>秩权重将样本排序信息压缩成若干个量<br>\\(\\bar{\\mu}_k=k\\mathbb{E}\\{X[1-F(X)]^{k-1}\\}\\)：与 Cran 有泛函联系',1040,770,880,180,size=24)
    d.box('lm-conversion','L矩由同组 PWM 线性转换<br>\\(\\lambda_1=b_0\\)<br>\\(\\lambda_2=2b_1-b_0\\)<br>\\(\\lambda_3=6b_2-6b_1+b_0\\)',1055,965,850,145,fill='#F2F8F4',color=GREEN,size=26)
    d.text('lm-recover','\\(\\lambda_1=\\gamma+\\eta a_1(\\beta),\\quad\\lambda_r=\\eta a_r(\\beta)\\ (r\\geq2)\\)<br>\\(\\frac{\\lambda_3}{\\lambda_2}\\) 定 \\(\\beta\\) → \\(\\lambda_2\\) 定 \\(\\eta\\) → \\(\\lambda_1\\) 定 \\(\\gamma\\)',1040,1120,880,90,size=25)
    d.text('tl-moments','TL矩：改用概念样本内部次序量<br>例如 \\(\\lambda_1^{(1,1)}=\\mathbb{E}[X_{(2:3)}]\\)<br>\\(\\lambda_2^{(1,1)}=\\frac{1}{2}\\mathbb{E}[X_{(3:4)}-X_{(2:4)}]\\)<br>端部处理改变权重与理论关系，再作样本—总体匹配。',1040,1225,880,150,size=24)

    d.panel('invariant-bg',45,1425,1910,755,fill='#F5F7FA')
    heading(d,'invariant-title','C\u3000不变统计量对照：构造、似然与后续参数恢复分别辨认',65,1440,1870,GREEN)
    d.line('invariant-divider',[(1000,1515),(1000,2060)],color='#D5E4DB',width=2)
    heading(d,'w-title','LSPF：\\(W\\) 同时消去位置与尺度',75,1515,885,GREEN)
    d.text('w-cancel','\\(W_i=\\frac{X_{(i)}-X_{(1)}}{X_{(n)}-X_{(1)}}=\\frac{Y_{(i)}-Y_{(1)}}{Y_{(n)}-Y_{(1)}}\\)<br>\\(W_1=0,\\quad W_n=1\\)；内部 \\(n-2\\) 个量只依赖 \\(\\beta\\)',80,1580,880,135,size=26)
    d.box('w-density','\\(\\widehat{\\beta}_W=\\operatorname*{arg\\,max}_{\\beta}\\;f_W(w_2,\\ldots,w_{n-1};\\beta)\\)<br>这里使用统计量联合密度',80,1728,850,100,fill='#FFF7F3',color='#AB4D3D',size=26)
    d.text('w-recover','代入 \\(\\widehat{\\beta}_W\\)，记 \\(b=\\widehat{\\beta}_W\\)<br>\\(\\eta_{\\mathrm{init}}=\\left[\\frac{1}{n}\\sum_{i=1}^n(x_i-x_{(1)})^b\\right]^{\\frac{1}{b}}\\)<br>\\(\\widehat{\\gamma}_W=x_{(1)}-\\eta_{\\mathrm{init}}\\Gamma(1+\\frac{1}{b})n^{-\\frac{1}{b}}\\)<br>\\(\\widehat{\\eta}_W=\\left[\\frac{1}{n}\\sum_{i=1}^n(x_i-\\widehat{\\gamma}_W)^b\\right]^{\\frac{1}{b}}\\)',80,1840,880,215,size=25)
    d.edge('w-statistic-density','w-cancel','w-density',start='bottom',end='top',color=GREEN,width=2)
    d.edge('w-density-recovery','w-density','w-recover',start='bottom',end='top',color=GREEN,width=2)
    d.text('w-mean','同一 \\(W\\) 也可匹配 \\(\\mathbb{E}_\\beta[\\bar{W}]\\) 来估 \\(\\beta\\)；<br>换成联合密度，改变的是确定参数的原则。',80,2070,880,70,size=23)

    heading(d,'v-title','LPF：\\(V\\) 只消去位置，尺度仍在',1020,1515,895,GREEN)
    d.text('v-cancel','\\(V_i=X_{(i)}-X_{(1)}=\\eta(Y_{(i)}-Y_{(1)})\\)<br>\\(V_1=0\\)；其余 \\(n-1\\) 个量仍依赖 \\(\\eta\\)、\\(\\beta\\)<br>少一个恒定分量，并保留绝对间距大小',1025,1580,880,125,size=26)
    d.box('v-density','\\((\\widehat{\\eta}_{V0},\\widehat{\\beta}_V)=\\operatorname*{arg\\,max}_{\\eta,\\beta}\\;f_V(v_2,\\ldots,v_n;\\eta,\\beta)\\)<br>下一阶段保留 \\(\\widehat{\\beta}_V\\)，重新恢复 \\(\\eta\\)、\\(\\gamma\\)',1025,1728,870,140,fill='#FFF7F3',color='#AB4D3D',size=26)
    d.text('v-recover','L2 代入形状估计，固定 \\(b=\\widehat{\\beta}_V\\)，令 \\(y_i=x_i-\\gamma\\)；解原文似然方程<br>\\(\\frac{\\sum_{i=1}^n y_i^b\\ln y_i}{\\sum_{i=1}^n y_i^b}-\\frac{1}{n}\\sum_{i=1}^n\\ln y_i=\\frac{1}{b}\\)<br>得到 \\(\\widehat{\\gamma}_V\\) 后：\\(\\widehat{\\eta}_V=\\left[\\frac{1}{n}\\sum_{i=1}^n(x_i-\\widehat{\\gamma}_V)^b\\right]^{\\frac{1}{b}}\\)',1025,1880,880,210,size=25)
    d.edge('v-statistic-density','v-cancel','v-density',start='bottom',end='top',color=GREEN,width=2)
    d.edge('v-density-recovery','v-density','v-recover',start='bottom',end='top',color=GREEN,width=2)
    d.text('v-meaning','数据间距的联合密度保留相关结构。<br>LPF保留形状后，仍解原文似然方程。',1025,2100,880,70,size=23)

    d.panel('mvlue-bg',45,2205,1910,340,fill='#F8FAFC')
    heading(d,'mvlue-title','D\u3000条件位置 MVLUE：已知 \\(\\beta\\)、\\(\\eta\\) 时，把无偏位置估计按协方差组合',65,2220,1860,GREEN)
    d.text('mvlue-statistics','\\(T_i=X_{(i)}-\\eta\\mathbb{E}_\\beta[Y_{(i)}],\\quad\\mathbb{E}[T_i]=\\gamma\\)<br>尤其 \\(T_1=X_{(1)}-\\eta\\Gamma(1+\\frac{1}{\\beta})n^{-\\frac{1}{\\beta}}\\)<br>取 \\(S=\\operatorname{Cov}(T)\\)，在 \\(\\mathbf{1}^{\\mathsf{T}}c=1\\) 下最小化 \\(c^{\\mathsf{T}}Sc\\)',75,2290,1030,155,size=26)
    d.box('mvlue-weights','\\(c=\\frac{S^{-1}\\mathbf{1}}{\\mathbf{1}^{\\mathsf{T}}S^{-1}\\mathbf{1}}\\)<br>\\(\\widehat{\\gamma}=\\sum_{i=1}^n c_iT_i\\)',1200,2295,680,140,fill='#F2F8F4',color=GREEN,size=29)
    d.text('mvlue-plugin','与二参数估计组合时：临时 \\(\\widetilde{\\beta},\\widetilde{\\eta}\\) → 代入 \\(T_i\\) 与 \\(S\\) 的理论系数 → 更新 \\(\\gamma\\) → 平移样本并重估 \\(\\beta\\)、\\(\\eta\\)。',75,2470,1810,55,size=25)
    d.text('footer','公式依据：Newby 矩构造；Cran（1988）；Hosking（1990）、Elamir–Seheult（2003）；LPF 原文 §2.1–2.2；位置 MVLUE 原文式(7)–(18)。',55,2535,1890,55,size=23)
    d.save(ROOT/'03-统计关系反演路线-机制图.drawio')


def validate():
    for name in ['02-分布匹配路线-机制图.drawio','03-统计关系反演路线-机制图.drawio']:
        root=ET.parse(ROOT/name).getroot()
        cells=root.findall('.//mxCell');ids=[c.attrib['id'] for c in cells]
        assert len(ids)==len(set(ids)),name
        ids=set(ids)
        for c in cells:
            if c.get('edge')=='1':
                assert c.get('source') in ids and c.get('target') in ids,c.attrib
        model=root.find('.//mxGraphModel')
        w,h=float(model.get('pageWidth')),float(model.get('pageHeight'))
        for c in cells:
            if c.get('vertex')!='1':continue
            g=c.find('mxGeometry');x,y=float(g.get('x')),float(g.get('y'))
            cw,ch=float(g.get('width')),float(g.get('height'))
            assert x>=0 and y>=0 and x+cw<=w and y+ch<=h,(name,c.get('id'))
        print(f'{name}: {len(cells)} cells; endpoints, IDs and canvas bounds OK')


if __name__=='__main__':
    distribution()
    statistics()
    validate()
