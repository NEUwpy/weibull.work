"""分布匹配与统计关系反演的机制细图，独立于总览地图。"""
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
    """同一组人为示意点；分别画水平和竖直的最小二乘残差。"""
    us = [.12, .28, .43, .61, .78, .91]
    zs = [.15, .12, .53, .48, .91, .78]
    um, zm = sum(us)/6, sum(zs)/6
    su = sum((u-um)**2 for u in us)
    sz = sum((z-zm)**2 for z in zs)
    suz = sum((u-um)*(z-zm) for u,z in zip(us,zs))
    w,h = 310,230
    axis(d,key,x,y,w,h,'u','z')
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
    d.text('subtitle','形状 β · 尺度 η · 位置 γ；排序寿命 x₍₁₎＜…＜x₍ₙ₎，候选位置 γ＜x₍₁₎',45,80,1920,45,size=24)
    d.panel('identity-bg',45,145,1910,180,fill='#F1F7FB')
    d.text('cdf','F(x;θ) = 1 − exp{−[(x−γ)/η]ᵝ}',70,162,690,65,size=29,bold=True)
    d.text('coordinates','pᵢ → qᵢ = −ln(1−pᵢ) → zᵢ = ln qᵢ<br>x₍ᵢ₎ → uᵢ(γ) = ln(x₍ᵢ₎−γ)',795,160,1110,85,size=27)
    d.text('identity','概率图关系：zᵢ ≈ βuᵢ(γ) − β lnη　　⇄　　逐点反推尺度：ηᵢ = (x₍ᵢ₎−γ) / qᵢ^(1/β)',70,250,1840,55,size=27,bold=True)

    d.panel('regression-bg',45,360,1910,720,fill='#F8FAFC')
    heading(d,'regression-title','A　概率图：分数、位置与回归方向，分别改变哪一步？',70,376,1850)
    d.line('regression-divider',[(1000,446),(1000,990)],color='#D7E2EB',width=2)
    heading(d,'white-title','White → Soman：对数寿命 u 对分数 z 回归',75,440,900)
    d.text('white-score','White：zᵢ = E[Z₍ᵢ:ₙ₎]，Z 的密度 h(z)=exp(z−eᶻ)<br>两参数时 γ=0；Soman 主分支将其接到候选 γ 上',80,500,875,82,size=24)
    regression_demo(d,'white-plot',110,640,'horizontal',BLUE)
    d.text('white-fit','uᵢ = a + bzᵢ + eᵢ<br>min Σ[uᵢ−a−bzᵢ]²<br><br>β̂ = 1/b<br>η̂ = exp(a)',455,622,470,235,size=27)
    d.text('white-distance','水平残差：在同一 z 上比较 u<br>示意点用于解释距离方向',85,905,875,70,size=23)
    d.text('soman-gamma','Soman 选位置：最大化 F(γ)=[SSTᵤ/(n−1)]/[SSEᵤ/(n−2)]<br>每换一个 γ，重新计算 u、回归与评分',80,990,880,75,size=24)

    heading(d,'park-title','Park Proposed+Plot：分数 z 对对数寿命 u 回归',1020,440,900)
    d.text('park-score','n≤10：pᵢ=(i−3/8)/(n+1/4)；n≥11：pᵢ=(i−1/2)/n<br>再取 zᵢ=ln[−ln(1−pᵢ)]',1020,500,900,82,size=24)
    regression_demo(d,'park-plot',1060,640,'vertical',GREEN)
    d.text('park-fit','zᵢ = a + buᵢ + eᵢ<br>min Σ[zᵢ−a−buᵢ]²<br><br>β̂ = b<br>η̂ = exp(−a/b)',1400,622,470,235,size=27)
    d.text('park-distance','竖直残差：在同一 u 上比较 z<br>同一组示意点，换了被最小化的距离',1020,905,900,70,size=23)
    d.text('park-gamma','Park 选位置：γ̂ = arg max corr[u(γ),z]，0≤γ＜x₍₁₎<br>定位后可接上述回归，也可接平移样本的二参数 MLE',1020,990,900,75,size=24)
    d.text('direction-identity','固定同一组 z、同一 γ 时：β̂(z 对 u) = r² β̂(u 对 z)。实际 White 与 Park 还使用不同分数。',70,1090,1870,50,size=24,bold=True)

    d.panel('mps-bg',45,1180,680,630,fill='#F1F7FB')
    heading(d,'mps-title','B　MPS：把观测映到 CDF 纵轴',65,1195,640)
    axis(d,'cdf-axis',110,1330,400,210,'x','F')
    curve=[(.02,.02),(.15,.05),(.28,.15),(.40,.35),(.55,.58),(.70,.78),(.85,.91),(.97,.96)]
    d.line('cdf-curve',[(110+400*x,1330+210*(1-f)) for x,f in curve],color=BLUE,width=3)
    for i,(x,f) in enumerate(curve[1:-1]):
        point(d,'cdf-p'+str(i),110+400*x,1330+210*(1-f),BLUE)
        d.line('cdf-proj'+str(i),[(110+400*x,1330+210*(1-f)),(545,1330+210*(1-f))],dashed=True,color='#A8BAC7')
    d.line('spacing',[(560,1330+210*(1-.35)),(560,1330+210*(1-.58))],color=ORANGE,width=5)
    d.text('spacing-label','Dᵢ',565,1410,90,45,size=27,bold=True,color=ORANGE)
    d.text('cdf-demo','CDF 曲线与观测位置为原理示意',85,1580,610,45,size=23)
    d.text('mps-equations','Fᵢ=F(x₍ᵢ₎;θ)，F₀=0，Fₙ₊₁=1<br>Dᵢ=Fᵢ−Fᵢ₋₁，θ̂=arg max Σᵢ lnDᵢ<br>候选 θ 改变每个概率区间的长度',70,1632,620,142,size=25)

    d.panel('mdm-bg',765,1180,1190,630,fill='#F2F8F4')
    heading(d,'mdm-title','C　MDM：每个点都能反推 η，让这些尺度尽量一致',785,1195,1145,GREEN)
    d.text('mdm-input','pᵢ=(i−0.3)/(n+0.4)；ηᵢ(β,γ)=(x₍ᵢ₎−γ)/[−ln(1−pᵢ)]^(1/β)',790,1258,1130,60,size=25)
    d.text('mdm-conditional-title','① 固定 γ，只沿 β 压缩尺度离散',785,1330,540,45,size=25,bold=True,color=GREEN)
    d.text('mdm-conditional','sη = std(η₁,…,ηₙ)<br>β*(γ)=arg minβ sη(β,γ)<br>当前求解域 β∈[0.1,15]<br>s*(γ)=sη[β*(γ),γ]',790,1380,530,165,size=26)
    d.text('mdm-gradient-title','② 随 γ 得到廓线，再按梯度定位',1365,1330,545,45,size=25,bold=True,color=GREEN)
    axis(d,'gradient-axis',1415,1420,400,125,'γ','g(γ)')
    d.line('gradient-curve',[(1415,1540),(1480,1535),(1540,1520),(1600,1493),(1660,1458),(1720,1398)],color=GREEN,width=3)
    d.line('gradient-threshold',[(1415,1475),(1815,1475)],dashed=True,color=ORANGE,width=2.5)
    point(d,'gradient-cross',1630,1475,ORANGE,6)
    d.text('gradient-delta','δ',1820,1450,60,45,size=27,color=ORANGE)
    d.text('gradient-caption','g(γ)=ds*/dγ；曲线为原理示意',1365,1580,545,45,size=23)
    d.text('mdm-location','位置规则：g(γ̂)=δ（MDM-0.1 取 δ=0.1）；g(0)≥δ 时，γ̂=0',790,1640,1130,55,size=25,bold=True)
    d.text('mdm-recover','③ β̂=β*(γ̂)，η̂=meanᵢ ηᵢ(β̂,γ̂)<br>形状来自条件最小差异；位置来自梯度规则；尺度来自伪尺度均值。',790,1700,1130,90,size=25)
    d.text('distribution-footer','其他拟合对象：CDF-WLSE 比较 Σwᵢ[Fᵢ−pᵢ]²；密度拟合比较经验密度与参数密度。它们改变的是被比较的量。',55,1820,1890,55,size=23)
    d.save(ROOT/'02-分布匹配路线-机制图.drawio')


def statistics():
    d=Diagram('statistics-mechanism-detail','统计关系反演：提取统计量、消元与参数恢复',2000,2500)
    heading(d,'title','统计关系反演：先提取可计算的量，再由理论关系拆开三个参数',45,25,1920,GREEN)
    d.text('identity','模型依赖：X = γ + ηY，Y 的分布只由 β 决定。差值消去 γ，标准化比值进一步消去 η。',45,88,1910,55,size=27)

    d.panel('moment-bg',45,175,1910,470,fill='#F2F8F4')
    heading(d,'moment-title','A　常规矩法原型：偏度只留形状，再由方差、均值恢复尺度和位置',65,190,1870,GREEN)
    d.box('sample-moments','从样本提取<br>x̄ = mean(xᵢ)<br>m₂ = mean[(xᵢ−x̄)²]<br>m₃ = mean[(xᵢ−x̄)³]<br>样本偏度 g₁=m₃/m₂^(3/2)',80,285,460,220,fill='#FFFFFF',color=GREEN,size=26)
    d.box('shape-equation','总体关系消去 γ、η<br>Gₖ(β)=Γ(1+k/β)<br>A₂=G₂−G₁²<br>A₃=G₃−3G₁G₂+2G₁³<br>解 g₁=A₃/A₂^(3/2) 得 β̂',620,285,640,220,fill='#FFFFFF',color=GREEN,size=26)
    d.box('moment-recover','参数恢复<br>η̂ = √[m₂/A₂(β̂)]<br>γ̂ = x̄−η̂G₁(β̂)<br><br>先 β，再 η，再 γ',1340,285,540,220,fill='#FFFFFF',color=GREEN,size=27)
    d.edge('sample-to-equation','sample-moments','shape-equation',color=GREEN)
    d.edge('shape-to-recover','shape-equation','moment-recover',color=GREEN)
    d.text('moment-explanation','中心化去掉位置；三阶中心矩与方差的 3/2 次方相除，尺度 η³ 抵消；最后用未标准化的量恢复 η、γ。',75,552,1830,65,size=25)

    d.panel('cran-bg',45,685,935,650,fill='#F8FAFC')
    heading(d,'cran-title','B1　Cran：把幂矩改成生存曲线的积分',65,700,895,GREEN)
    d.text('cran-theory','非负位置 γ≥0 时<br>μ̄ₖ=∫₀∞[1−F(x)]ᵏdx<br>　 = γ+ηΓ(1+1/β)k^(−1/β)',75,770,870,135,size=27)
    d.text('cran-sample','样本阶梯积分（x₍₀₎=0）<br>m̄ₖ=Σᵣ₌₀ⁿ⁻¹(1−r/n)ᵏ[x₍ᵣ₊₁₎−x₍ᵣ₎]<br>提取 k=1、2、4；m̄₁=x̄',75,925,870,130,size=26)
    d.box('cran-differences','d₁₂=m̄₁−m̄₂，d₂₄=m̄₂−m̄₄<br>总体 d₁₂/d₂₄=2^(1/β)<br>差值消 γ，再作比值消 η',80,1080,835,112,fill='#F2F8F4',color=GREEN,size=25)
    d.text('cran-recover','β̂ = ln2 / ln(d₁₂/d₂₄)<br>γ̂ = (m̄₁m̄₄−m̄₂²)/(m̄₁+m̄₄−2m̄₂)<br>η̂ = (m̄₁−γ̂)/Γ(1+1/β̂)',75,1210,875,105,size=25)

    d.panel('l-moments-bg',1020,685,935,650,fill='#F8FAFC')
    heading(d,'lm-title','B2　PWM → L矩 → TL矩：改造样本权重',1040,700,895,GREEN)
    d.text('pwm','PWM：bᵣ=E[X F(X)ʳ]<br>b̂ᵣ=(1/n)Σᵢ[C(i−1,r)/C(n−1,r)]x₍ᵢ₎<br>秩权重将样本排序信息压缩成若干个量<br>μ̄ₖ=k E{X[1−F(X)]ᵏ⁻¹}：与 Cran 有泛函联系',1040,770,880,130,size=24)
    d.box('lm-conversion','L矩由同组 PWM 线性转换<br>λ₁=b₀<br>λ₂=2b₁−b₀<br>λ₃=6b₂−6b₁+b₀',1055,915,850,170,fill='#F2F8F4',color=GREEN,size=26)
    d.text('lm-recover','λ₁=γ+ηa₁(β)，λᵣ=ηaᵣ(β)（r≥2）<br>λ₃/λ₂ 定 β → λ₂ 定 η → λ₁ 定 γ',1040,1100,880,85,size=25)
    d.text('tl-moments','TL矩：改用概念样本内部次序量<br>例如 λ₁⁽¹,¹⁾=E[X₍₂:₃₎]<br>λ₂⁽¹,¹⁾=½E[X₍₃:₄₎−X₍₂:₄₎]<br>端部处理改变权重与理论关系，再作样本—总体匹配。',1040,1190,880,130,size=24)

    d.panel('invariant-bg',45,1375,1910,680,fill='#F2F8F4')
    heading(d,'invariant-title','C　W 与 V：先消去哪些未知量，再对保留下来的信息建立联合密度',65,1390,1870,GREEN)
    d.line('invariant-divider',[(1000,1465),(1000,2010)],color='#D5E4DB',width=2)
    heading(d,'w-title','LSPF：W 同时消去位置与尺度',75,1465,885,GREEN)
    d.text('w-cancel','Wᵢ=(X₍ᵢ₎−X₍₁₎)/(X₍ₙ₎−X₍₁₎)<br>　 =(Y₍ᵢ₎−Y₍₁₎)/(Y₍ₙ₎−Y₍₁₎)<br>W₁=0、Wₙ=1；内部 n−2 个量只依赖 β',80,1530,880,125,size=26)
    d.box('w-density','β̂W = arg maxβ fW(w₂,…,wₙ₋₁;β)<br>这里使用统计量联合密度',80,1678,850,85,fill='#FFFFFF',color=GREEN,size=26)
    d.text('w-recover','代入 β̂W，记 b=β̂W<br>ηinit={mean[(xᵢ−x₍₁₎)ᵇ]}^(1/b)<br>γ̂W=x₍₁₎−ηinitΓ(1+1/b)n^(−1/b)<br>η̂W={mean[(xᵢ−γ̂W)ᵇ]}^(1/b)',80,1800,880,160,size=25)
    d.edge('w-statistic-density','w-cancel','w-density',start='bottom',end='top',color=GREEN,width=2)
    d.edge('w-density-recovery','w-density','w-recover',start='bottom',end='top',color=GREEN,width=2)
    d.text('w-mean','同一 W 也可匹配 Eβ(W 的均值) 来估 β；<br>换成联合密度，改变的是确定参数的原则。',80,1975,880,65,size=23)

    heading(d,'v-title','LPF：V 只消去位置，尺度仍在',1020,1465,895,GREEN)
    d.text('v-cancel','Vᵢ=X₍ᵢ₎−X₍₁₎=η(Y₍ᵢ₎−Y₍₁₎)<br>V₁=0；其余 n−1 个量仍依赖 η、β<br>少一个恒定分量，并保留绝对间距大小',1025,1530,880,125,size=26)
    d.box('v-density','(η̂V0,β̂V)=arg maxη,β fV(v₂,…,vₙ;η,β)<br>下一阶段保留 β̂V，重新恢复 η、γ',1025,1678,870,85,fill='#FFFFFF',color=GREEN,size=26)
    d.text('v-recover','固定 b=β̂V，令 yᵢ=xᵢ−γ；解原文恢复方程<br>Σyᵢᵇ ln yᵢ / Σyᵢᵇ − mean(ln yᵢ)=1/b<br>得到 γ̂V 后：η̂V={mean[(xᵢ−γ̂V)ᵇ]}^(1/b)',1025,1795,880,145,size=25)
    d.edge('v-statistic-density','v-cancel','v-density',start='bottom',end='top',color=GREEN,width=2)
    d.edge('v-density-recovery','v-density','v-recover',start='bottom',end='top',color=GREEN,width=2)
    d.text('v-meaning','数据间距的联合密度保留相关结构；<br>图中的消元与恢复，是两次有不同对象的估计。',1025,1965,880,75,size=23)

    d.panel('mvlue-bg',45,2095,1910,310,fill='#F8FAFC')
    heading(d,'mvlue-title','D　条件位置 MVLUE：已知 β、η 时，把无偏位置估计按协方差组合',65,2110,1860,GREEN)
    d.text('mvlue-statistics','Tᵢ=X₍ᵢ₎−ηEβ(Y₍ᵢ₎)，E(Tᵢ)=γ<br>尤其 T₁=X₍₁₎−ηΓ(1+1/β)n^(−1/β)<br>取 S=Cov(T)，在 1ᵀc=1 下最小化 cᵀSc',75,2180,1030,140,size=26)
    d.box('mvlue-weights','c = S⁻¹1 / (1ᵀS⁻¹1)<br>γ̂ = ΣcᵢTᵢ',1200,2185,680,115,fill='#F2F8F4',color=GREEN,size=29)
    d.text('mvlue-plugin','与二参数估计组合时：临时 β̃、η̃ → 代入 Tᵢ 与 S 的理论系数 → 更新 γ → 平移样本并重估 β、η。',75,2330,1810,55,size=25)
    d.text('footer','公式依据：Newby 矩构造；Cran（1988）；Hosking（1990）、Elamir–Seheult（2003）；LPF 原文 §2.1–2.2；位置 MVLUE 原文式(7)–(18)。',55,2425,1890,55,size=23)
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
