"""分布匹配与统计关系反演：16:7 横向方法分支。"""
from pathlib import Path
import xml.etree.ElementTree as ET
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
BLUE, GREEN, ORANGE, GREY = '#286D99', '#26745A', '#B47744', '#64748B'

def heading(d, key, label, x, y, w, color=BLUE):
    d.text(key, label, x, y, w, 55, size=29, bold=True, color=color)

def point(d, key, x, y, color=BLUE, r=5):
    d.box(key, '', x-r, y-r, 2*r, 2*r, fill=color, color=color, role='point', extra='shape=ellipse;')

def axis(d, key, x, y, w, h, xlabel, ylabel):
    d.line(key+'-x', [(x, y+h), (x+w, y+h)], color=GREY, arrow='block')
    d.line(key+'-y', [(x, y+h), (x, y)], color=GREY, arrow='block')
    d.text(key+'-xl', xlabel, x+w-40, y+h+3, 75, 40, size=23)
    d.text(key+'-yl', ylabel, x-25, y-45, 110, 40, size=23)

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

def distribution():
    d=Diagram('distribution-mechanism-wide','分布匹配：概率图、概率间距与尺度一致性',3200,1400)
    d.text('title','分布匹配｜概率变换 → 残差、间距或尺度差异',45,20,3110,60,size=38,bold=True)
    d.text('support',r'\(x_{(1)}<\cdots<x_{(n)},\quad\beta>0,\quad\eta>0,\quad\gamma<x_{(1)}\)',50,88,3090,45,size=26)
    d.panel('identity-bg',40,155,3120,145,fill='#F1F7FB')
    d.text('cdf',r'\(F(x;\theta)=1-\exp\!\left[-\left(\frac{x-\gamma}{\eta}\right)^\beta\right]\)',65,178,950,95,size=29,bold=True)
    d.text('coordinates',r'\(p_i\rightarrow q_i=-\ln(1-p_i)\rightarrow z_i=\ln q_i\)<br>\(x_{(i)}\rightarrow u_i(\gamma)=\ln(x_{(i)}-\gamma)\)',1050,175,1015,100,size=27)
    d.text('identity',r'\(z_i\approx\beta u_i-\beta\ln\eta\)<br>\(\eta_i=\frac{x_{(i)}-\gamma}{q_i^{1/\beta}}\)',2120,175,985,100,size=29,bold=True)

    for key,x,w,fill in [('white-bg',40,770,'#F8FAFC'),('park-bg',835,770,'#F2F8F4'),('mps-bg',1630,630,'#F1F7FB'),('mdm-bg',2285,875,'#F2F8F4')]:
        d.panel(key,x,340,w,1015,fill=fill)
    heading(d,'white-title',r'White → Soman｜\(u\) 对 \(z\) 回归',65,360,720)
    d.text('white-score',r'\(z_i=\mathbb{E}[Z_{(i:n)}],\quad h(z)=\exp(z-e^z)\)<br>White：\(\gamma=0\)；Soman：候选 \(\gamma\)',65,435,720,110,size=25)
    regression_demo(d,'white-plot',85,620,'horizontal',BLUE)
    d.text('white-fit',r'\(u_i=a+bz_i+e_i\)<br>\(\min_{a,b}\sum_i(u_i-a-bz_i)^2\)<br>\(\widehat\beta=\frac{1}{b}\)<br>\(\widehat\eta=\exp(a)\)',425,605,360,260,size=26)
    d.text('white-distance',r'水平残差 \(u_i-a-bz_i\)',65,900,720,45,size=26,align='center',color=BLUE)
    d.box('soman-gamma',r'Soman：选位置<br>\(\widehat\gamma=\operatorname*{arg\,max}_{\gamma<x_{(1)}} F(\gamma)\)<br>\(F(\gamma)=\frac{(n-2)\mathrm{SST}_u}{(n-1)\mathrm{SSE}_u}\)',75,990,700,190,color=BLUE,size=27)
    d.text('direction-identity',r'同一 \(z,\gamma\)：<br>\(\widehat\beta_{z\mid u}=r^2\widehat\beta_{u\mid z}\)',75,1220,700,90,size=25,align='center')

    heading(d,'park-title',r'Park Proposed+Plot｜\(z\) 对 \(u\) 回归',860,360,720,GREEN)
    d.text('park-score',r'\(p_i=\begin{cases}\frac{i-\tfrac{3}{8}}{n+\tfrac{1}{4}},&n\leq10,\\\frac{i-\tfrac{1}{2}}{n},&n\geq11.\end{cases}\)<br>\(z_i=\ln[-\ln(1-p_i)]\)',860,435,720,140,size=25)
    regression_demo(d,'park-plot',880,620,'vertical',GREEN)
    d.text('park-fit',r'\(z_i=a+bu_i+e_i\)<br>\(\min_{a,b}\sum_i(z_i-a-bu_i)^2\)<br>\(\widehat\beta=b\)<br>\(\widehat\eta=\exp\!\left(-\frac{a}{b}\right)\)',1220,605,360,260,size=26)
    d.text('park-distance',r'竖直残差 \(z_i-a-bu_i\)',860,900,720,45,size=26,align='center',color=GREEN)
    d.box('park-gamma',r'Park：相关系数定位<br>\(\widehat\gamma=\operatorname*{arg\,max}_{0\leq\gamma<x_{(1)}}\operatorname{corr}[u(\gamma),z]\)',870,990,700,150,color=GREEN,size=27)
    d.box('park-recovery',r'\(\widehat\gamma\) → 回归恢复 \(\beta,\eta\)<br>或 → 平移样本的二参数 MLE',870,1210,700,100,color=GREEN,fill='#EAF4ED',size=25)
    d.edge('park-position-fit','park-gamma','park-recovery',color=GREEN,start='bottom',end='top')

    heading(d,'mps-title','MPS｜概率间距',1655,360,580)
    axis(d,'cdf-axis',1695,480,360,240,r'\(x\)',r'\(F\)')
    curve=[(.02,.02),(.15,.05),(.28,.15),(.40,.35),(.55,.58),(.70,.78),(.85,.91),(.97,.96)]
    d.line('cdf-curve',[(1695+360*x,480+240*(1-f)) for x,f in curve],color=BLUE,width=3)
    for i,(x,f) in enumerate(curve[1:-1]):
        point(d,'cdf-p'+str(i),1695+360*x,480+240*(1-f),BLUE)
        d.line('cdf-proj'+str(i),[(1695+360*x,480+240*(1-f)),(2100,480+240*(1-f))],dashed=True,color='#A8BAC7')
    d.line('spacing',[(2120,480+240*(1-.35)),(2120,480+240*(1-.58))],color=ORANGE,width=5)
    d.text('spacing-label',r'\(D_i\)',2130,580,90,45,size=27,bold=True,color=ORANGE)
    d.box('mps-equations',r'\(F_i=F(x_{(i)};\theta)\)<br>\(F_0=0,\quad F_{n+1}=1\)<br>\(D_i=F_i-F_{i-1}\)<br>\(\widehat\theta=\operatorname*{arg\,max}_{\theta}\sum_{i=1}^{n+1}\ln D_i\)',1660,825,570,235,color=BLUE,size=27)
    d.box('cdf-wlse',r'CDF-WLSE<br>\(\min_\theta\sum_{i=1}^{n}w_i(F_i-p_i)^2\)',1660,1140,570,100,color=BLUE,fill='#F8FAFC',size=25)
    d.text('density-fitting','密度拟合：经验密度 ↔ 参数密度',1660,1270,570,50,size=24,align='center')

    heading(d,'mdm-title','MDM｜压缩逐点尺度差异',2310,360,825,GREEN)
    d.text('mdm-input',r'\(p_i=\frac{i-0.3}{n+0.4}\)<br>\(\eta_i(\beta,\gamma)=\frac{x_{(i)}-\gamma}{[-\ln(1-p_i)]^{1/\beta}}\)',2310,435,825,130,size=28)
    d.box('mdm-conditional',r'① 固定 \(\gamma\)，求条件形状<br>\(s_\eta=\operatorname{std}(\eta_1,\ldots,\eta_n)\)<br>\(\beta^*(\gamma)=\operatorname*{arg\,min}_{\beta\in[0.1,15]}s_\eta(\beta,\gamma)\)<br>\(s^*(\gamma)=s_\eta[\beta^*(\gamma),\gamma]\)',2320,590,805,200,color=GREEN,size=26)
    axis(d,'gradient-axis',2370,875,550,125,r'\(\gamma\)',r'\(g(\gamma)\)')
    d.line('gradient-curve',[(2370,995),(2460,990),(2540,975),(2625,950),(2710,912),(2790,853)],color=GREEN,width=3)
    d.line('gradient-threshold',[(2370,930),(2920,930)],dashed=True,color=ORANGE,width=2.5)
    point(d,'gradient-cross',2670,930,ORANGE,6)
    d.text('gradient-delta',r'\(\delta\)',2930,905,70,45,size=27,color=ORANGE)
    d.text('mdm-location',r'② \(g(\gamma)=\frac{ds^*(\gamma)}{d\gamma},\quad g(\widehat\gamma)=\delta\)<br>MDM-0.1：\(\delta=0.1\)<br>\(g(0)\geq\delta\Rightarrow\widehat\gamma=0\)',2310,1050,825,125,size=26)
    d.box('mdm-recover',r'③ \(\widehat\beta=\beta^*(\widehat\gamma)\)<br>\(\widehat\eta=\frac{1}{n}\sum_i\eta_i(\widehat\beta,\widehat\gamma)\)',2320,1220,805,105,color=GREEN,fill='#EAF4ED',size=28)
    d.save(ROOT/'02-分布匹配路线-机制图.drawio')

def statistics():
    d=Diagram('statistics-mechanism-wide','统计关系反演：特征、消元与参数恢复',3200,1400)
    d.text('title','统计关系反演｜样本特征 → 消元关系 → 参数恢复',45,20,3110,60,size=38,bold=True)
    d.text('identity',r'\(X=\gamma+\eta Y,\quad Y\sim\mathrm{Weibull}(\beta,1,0)\)；差值消 \(\gamma\)，标准化比值消 \(\eta\)',50,88,3090,45,size=27)
    xs=[40,670,1300,1930,2560]
    for key,x in zip(['moment-bg','cran-bg','l-moments-bg','w-bg','v-bg'],xs):
        d.panel(key,x,165,600,875,fill='#F2F8F4' if key=='moment-bg' else '#F8FAFC')
    heading(d,'moment-title','A  常规矩',60,180,560,GREEN)
    d.box('sample-moments',r'\(\bar{x}=\frac{1}{n}\sum_i x_i\)<br>\(m_2=\frac{1}{n}\sum_i(x_i-\bar{x})^2\)<br>\(m_3=\frac{1}{n}\sum_i(x_i-\bar{x})^3\)<br>\(g_1=\frac{m_3}{m_2^{3/2}}\)',65,255,550,210,color=GREEN,size=26)
    d.box('shape-equation',r'\(G_k(\beta)=\Gamma\!\left(1+\frac{k}{\beta}\right)\)<br>\(A_2=G_2-G_1^2\)<br>\(A_3=G_3-3G_1G_2+2G_1^3\)<br>\(g_1=\frac{A_3}{A_2^{3/2}}\ \Rightarrow\ \widehat\beta\)',65,530,550,210,color=GREEN,size=26)
    d.box('moment-recover',r'\(\widehat\eta=\sqrt{\frac{m_2}{A_2(\widehat\beta)}}\)<br>\(\widehat\gamma=\bar{x}-\widehat\eta G_1(\widehat\beta)\)',65,815,550,145,color=GREEN,fill='#EAF4ED',size=28)
    d.edge('sample-to-equation','sample-moments','shape-equation',color=GREEN,start='bottom',end='top')
    d.edge('shape-to-recover','shape-equation','moment-recover',color=GREEN,start='bottom',end='top')

    heading(d,'cran-title','B  Cran：生存曲线积分',690,180,560,GREEN)
    d.text('cran-theory',r'\(\gamma\geq0\)<br>\(\bar\mu_k=\int_0^\infty[1-F(x)]^k\,dx\)<br>\(=\gamma+\eta\Gamma\!\left(1+\frac{1}{\beta}\right)k^{-1/\beta}\)',695,255,550,150,size=26)
    d.text('cran-sample',r'\(x_{(0)}=0,\quad k=1,2,4\)<br>\(\bar m_k=\sum_{r=0}^{n-1}\left(1-\frac{r}{n}\right)^k[x_{(r+1)}-x_{(r)}]\)<br>\(\bar m_1=\bar x\)',695,440,550,150,size=24)
    d.box('cran-differences',r'\(d_{12}=\bar m_1-\bar m_2\)<br>\(d_{24}=\bar m_2-\bar m_4\)<br>\(\frac{d_{12}}{d_{24}}=2^{1/\beta}\)',695,625,550,140,color=GREEN,size=26)
    d.text('cran-recover',r'\(\widehat\beta=\frac{\ln2}{\ln d_{12}-\ln d_{24}}\)<br>\(\widehat\gamma=\frac{\bar m_1\bar m_4-\bar m_2^2}{\bar m_1+\bar m_4-2\bar m_2}\)<br>\(\widehat\eta=\frac{\bar m_1-\widehat\gamma}{\Gamma(1+1/\widehat\beta)}\)',695,800,550,200,size=26)

    heading(d,'lm-title','C  PWM → L矩 → TL矩',1320,180,560,GREEN)
    d.text('pwm',r'\(b_r=\mathbb{E}[XF(X)^r]\)<br>\(\widehat b_r=\frac{1}{n}\sum_{i=1}^n\frac{\binom{i-1}{r}}{\binom{n-1}{r}}x_{(i)}\)<br>\(\bar\mu_k=k\mathbb{E}\{X[1-F(X)]^{k-1}\}\)',1325,255,550,165,size=24)
    d.box('lm-conversion',r'\(\lambda_1=b_0\)<br>\(\lambda_2=2b_1-b_0\)<br>\(\lambda_3=6b_2-6b_1+b_0\)',1325,455,550,145,color=GREEN,size=26)
    d.text('lm-recover',r'\(\lambda_1=\gamma+\eta a_1(\beta)\)<br>\(\lambda_r=\eta a_r(\beta),\quad r\geq2\)<br>\(\lambda_3/\lambda_2\rightarrow\beta\)<br>\(\lambda_2\rightarrow\eta,\quad\lambda_1\rightarrow\gamma\)',1325,635,550,160,size=25)
    d.box('tl-moments',r'TL矩<br>\(\lambda_1^{(1,1)}=\mathbb{E}[X_{(2:3)}]\)<br>\(\lambda_2^{(1,1)}=\frac12\mathbb{E}[X_{(3:4)}-X_{(2:4)}]\)',1325,850,550,150,color=GREEN,fill='#EAF4ED',size=24)

    heading(d,'w-title','D  LSPF：消去位置与尺度',1950,180,560,GREEN)
    d.text('w-cancel',r'\(W_i=\frac{X_{(i)}-X_{(1)}}{X_{(n)}-X_{(1)}}\)<br>\(=\frac{Y_{(i)}-Y_{(1)}}{Y_{(n)}-Y_{(1)}}\)<br>\(W_1=0,\quad W_n=1\)',1955,255,550,160,size=27)
    d.box('w-density',r'\(\widehat\beta_W=\operatorname*{arg\,max}_{\beta}\)<br>\(f_W(w_2,\ldots,w_{n-1};\beta)\)',1955,465,550,125,color='#AB4D3D',fill='#FFF7F3',size=27)
    d.text('w-recover',r'\(b=\widehat\beta_W\)<br>\(\eta_{\mathrm{init}}=\left[\frac{1}{n}\sum_i(x_i-x_{(1)})^b\right]^{1/b}\)<br>\(\widehat\gamma_W=x_{(1)}-\eta_{\mathrm{init}}\Gamma(1+1/b)n^{-1/b}\)<br>\(\widehat\eta_W=\left[\frac{1}{n}\sum_i(x_i-\widehat\gamma_W)^b\right]^{1/b}\)',1955,655,550,245,size=24)
    d.text('w-mean',r'均值关系分支：\(\mathbb{E}_\beta[\bar W]\rightarrow\beta\)',1955,955,550,50,size=24)
    d.edge('w-statistic-density','w-cancel','w-density',color=GREEN,start='bottom',end='top')
    d.edge('w-density-recovery','w-density','w-recover',color=GREEN,start='bottom',end='top')

    heading(d,'v-title','E  LPF：消去位置',2580,180,560,GREEN)
    d.text('v-cancel',r'\(V_i=X_{(i)}-X_{(1)}\)<br>\(=\eta(Y_{(i)}-Y_{(1)})\)<br>\(V_1=0\)',2585,255,550,160,size=27)
    d.box('v-density',r'\((\widehat\eta_{V0},\widehat\beta_V)=\operatorname*{arg\,max}_{\eta,\beta}\)<br>\(f_V(v_2,\ldots,v_n;\eta,\beta)\)',2585,465,550,125,color='#AB4D3D',fill='#FFF7F3',size=26)
    d.text('v-recover',r'固定 \(b=\widehat\beta_V,\quad y_i=x_i-\gamma\)<br>\(\frac{\sum_i y_i^b\ln y_i}{\sum_i y_i^b}-\frac{1}{n}\sum_i\ln y_i=\frac{1}{b}\)<br>\(\Downarrow\ \widehat\gamma_V\)<br>\(\widehat\eta_V=\left[\frac{1}{n}\sum_i(x_i-\widehat\gamma_V)^b\right]^{1/b}\)',2585,655,550,245,size=25)
    d.edge('v-statistic-density','v-cancel','v-density',color=GREEN,start='bottom',end='top')
    d.edge('v-density-recovery','v-density','v-recover',color=GREEN,start='bottom',end='top')

    d.panel('mvlue-bg',40,1080,3120,275,fill='#F2F8F4')
    heading(d,'mvlue-title',r'F  条件位置 MVLUE｜给定 \(\beta,\eta\)',65,1095,1090,GREEN)
    d.text('mvlue-statistics',r'\(T_i=X_{(i)}-\eta\mathbb{E}_\beta[Y_{(i)}],\quad\mathbb{E}[T_i]=\gamma\)<br>\(T_1=X_{(1)}-\eta\Gamma(1+1/\beta)n^{-1/\beta}\)',65,1170,1090,120,size=27)
    d.box('mvlue-covariance',r'\(S=\operatorname{Cov}(T),\quad\mathbf1^{\mathsf T}c=1\)<br>\(\min_c c^{\mathsf T}Sc\)',1240,1160,730,140,color=GREEN,size=28)
    d.box('mvlue-weights',r'\(c=\frac{S^{-1}\mathbf1}{\mathbf1^{\mathsf T}S^{-1}\mathbf1}\)<br>\(\widehat\gamma=\sum_i c_iT_i\)',2060,1160,690,140,color=GREEN,fill='#FFFFFF',size=29)
    d.edge('mvlue-minimize','mvlue-covariance','mvlue-weights',color=GREEN)
    d.text('mvlue-plugin',r'代入 \(\widetilde\beta,\widetilde\eta\)<br>↓ 更新 \(\gamma\)<br>↓ 平移后重估',2820,1160,300,140,size=25,align='center')
    d.save(ROOT/'03-统计关系反演路线-机制图.drawio')

def validate():
    for name in ['02-分布匹配路线-机制图.drawio','03-统计关系反演路线-机制图.drawio']:
        root=ET.parse(ROOT/name).getroot()
        cells=root.findall('.//mxCell'); ids=[c.get('id') for c in cells]
        assert len(ids)==len(set(ids)),name
        model=root.find('.//mxGraphModel')
        assert (model.get('pageWidth'),model.get('pageHeight'))==('3200','1400')
        for c in cells:
            if c.get('edge')=='1':
                assert c.get('source') in ids and c.get('target') in ids,c.attrib
            if c.get('vertex')=='1':
                g=c.find('mxGeometry');x,y,w,h=[float(g.get(k)) for k in ('x','y','width','height')]
                assert 0<=x<=x+w<=3200 and 0<=y<=y+h<=1400,(name,c.get('id'))
        print(f'{name}: {len(cells)} cells; IDs, endpoints and 16:7 bounds OK')

if __name__=='__main__':
    distribution()
    statistics()
    validate()
