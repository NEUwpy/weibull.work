"""后验与学习机制的横向构造、分支及输出。"""
from pathlib import Path
import xml.etree.ElementTree as ET
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
PURPLE, ORANGE, GREEN = '#785499', '#AE6C25', '#2C7B61'

def posterior():
    d = Diagram('posterior-detail-wide', '后验推断：构造、决策与计算', 3200, 1400)
    d.text('title','后验推断｜样本与先验 → 联合后验 → 决策与计算 → 参数',45,20,3110,60,size=38,bold=True)
    d.text('support',r'\(\theta=(\beta,\eta,\gamma),\quad\Omega=\{\beta>0,\eta>0,\gamma<x_{(1)}\}\cap\operatorname{supp}(\pi)\)',50,88,3090,45,size=27)
    d.panel('inputs-panel',40,175,680,1155,fill='#F8F5FC')
    d.panel('posterior-panel',760,175,730,1155,fill='#F7F2FA')
    d.panel('decision-panel',1530,175,950,510,fill='#F8F5FC')
    d.panel('compute-panel',1530,735,950,595,fill='#F3F8FA')
    d.panel('output-panel',2520,175,640,1155,fill='#F8F5FC')
    d.text('input-title','① 样本、先验与支持域',65,200,630,55,size=30,bold=True,color=PURPLE)
    d.box('prior',r'先验<br>\(\pi(\beta,\eta,\gamma)\)',80,340,600,145,color=PURPLE,fill='#FFFFFF',size=31)
    d.box('like',r'样本 \(D\) 的联合似然<br>\(L(\theta\mid D)=\prod_i f(x_i\mid\theta)\)',80,620,600,145,color='#A75043',fill='#FFF5F0',size=29)
    d.box('domain',r'参数域 \(\Omega\)<br>模型支持 ∩ 先验支持',80,935,600,120,color='#64748B',fill='#F3F6FA',size=29)

    d.text('joint-title','② 构造联合后验',785,200,680,55,size=30,bold=True,color=PURPLE)
    d.box('joint',r'\(p(\theta\mid D)=\frac{L(\theta\mid D)\pi(\theta)}{Z}\)',795,535,660,145,color=PURPLE,fill='#F1E9F8',size=34,bold=True)
    d.box('normalization',r'\(Z=\int_\Omega L(\theta\mid D)\pi(\theta)\,d\theta\)',795,835,660,120,color=PURPLE,size=29)
    d.edge('prior-joint','prior','joint','先验权重',color=PURPLE,start='right',end='top',via=[(735,412),(1125,412)],at=(950,412))
    d.edge('like-joint','like','joint','样本贡献',color='#A75043',start='right',end='left',via=[(740,692),(740,607)],at=(740,620))
    d.edge('domain-normalization','domain','normalization',color='#64748B',start='right',end='left',via=[(740,995),(740,895)])
    d.edge('normalization-joint','normalization','joint',color=PURPLE,start='top',end='bottom')

    d.text('decision-title','③ 选择后验量',1555,195,900,55,size=30,bold=True,color=PURPLE)
    d.box('mean',r'后验均值<br>\(\mathbb{E}(\theta\mid D)\)<br>平方损失',1570,315,270,190,color=PURPLE,size=28)
    d.box('median',r'逐参数中位数<br>\(\operatorname{median}(\theta_k\mid D)\)<br>绝对损失',1870,315,270,190,color=PURPLE,size=26)
    d.box('map',r'MAP<br>\(\operatorname*{arg\,max}_{\theta}p(\theta\mid D)\)<br>联合密度峰',2170,315,270,190,color=PURPLE,size=26)
    d.box('map-objective',r'MAP：\(\log L(\theta\mid D)+\log\pi(\theta)\)',1570,565,870,85,color=PURPLE,fill='#F1E9F8',size=28)
    d.edge('joint-decision','joint','decision-title',color=PURPLE,start='right',end='left',via=[(1510,607),(1510,222)])

    d.text('compute-title','④ 计算后验量',1555,755,900,55,size=30,bold=True,color=GREEN)
    d.box('beta',r'更新 \(\beta\)<br>\(p(\beta\mid\eta,\gamma,D)\)',1570,865,260,140,color=GREEN,size=26)
    d.box('eta',r'更新 \(\eta\)<br>\(p(\eta\mid\beta,\gamma,D)\)',1870,865,260,140,color=GREEN,size=26)
    d.box('gamma',r'更新 \(\gamma\)<br>\(p(\gamma\mid\beta,\eta,D)\)',2170,865,270,140,color=GREEN,size=26)
    d.edge('joint-compute','joint','compute-title',color=GREEN,start='right',end='left',via=[(1510,607),(1510,782)])
    d.edge('beta-eta','beta','eta',color=GREEN)
    d.edge('eta-gamma','eta','gamma',color=GREEN)
    d.edge('repeat','gamma','beta','条件抽样循环',color=GREEN,kind='feedback',start='bottom',end='bottom',via=[(2305,1040),(1700,1040)],at=(2000,1040))
    d.box('samples',r'后验样本 → 均值、中位数、区间<br>Green：Gibbs＋条件拒绝抽样；\(\gamma\) 可用 MH 核',1570,1100,870,95,color=GREEN,size=26)
    d.edge('chain-samples','eta','samples',color=GREEN,start='bottom',end='top')
    d.box('laplace',r'Laplace：后验峰二次近似 → 积分近似',1570,1245,870,60,color='#367B98',fill='#EEF7FB',size=26)
    d.edge('joint-laplace','joint','laplace',color='#367B98',kind='borrow',start='right',end='left',via=[(1510,607),(1510,1275)])

    d.text('output-title','⑤ 参数估计',2545,200,590,55,size=30,bold=True,color=PURPLE)
    d.box('estimate',r'\(\widehat\theta\)<br>\((\widehat\beta,\widehat\eta,\widehat\gamma)\)',2560,610,560,195,color=PURPLE,fill='#F1E9F8',size=36,bold=True)
    d.edge('rule-output','decision-title','estimate','决策规则',color=PURPLE,start='right',end='top',via=[(2500,222),(2500,290),(2840,290)],at=(2670,290))
    d.edge('sample-output','samples','estimate','后验量',color=GREEN,start='right',end='bottom',via=[(2500,1147),(2840,1147)],at=(2660,1147))
    d.edge('laplace-output','laplace','estimate',color='#367B98',start='right',end='right',via=[(3140,1275),(3140,707)])
    d.save(ROOT/'04-后验推断路线-机制图.drawio')

def learning():
    d = Diagram('learning-detail-wide', '学习映射：训练闭环与新样本使用',3200,1400)
    d.text('title','学习映射｜多组样本训练估计函数 → 新样本执行固定映射',45,20,3110,60,size=38,bold=True)
    d.text('notation',r'\(D_j\leftrightarrow\theta_j=(\beta_j,\eta_j,\gamma_j),\quad T:\text{特征提取},\quad h_\varphi:\text{参数映射}\)',50,88,3090,45,size=27)
    d.panel('training-panel',40,175,2310,690,fill='#FCF6EE')
    d.panel('intervention-panel',2390,175,770,1155,fill='#F5F7FA')
    d.text('training-title','① 训练：样本、标签与损失闭环',65,195,2260,55,size=30,bold=True,color=ORANGE)
    specs=[('truth',r'参数标签 \(\theta_j\)<br>样本量 \(n_j\)',75,350),
           ('train-data',r'训练样本 \(D_j\)<br>模拟／标注',505,350),
           ('features',r'特征 \(T(D_j)\)<br>排序值／分位数／统计量',935,400),
           ('network',r'参数映射<br>\(h_\varphi\)',1415,350),
           ('prediction',r'预测 \(\widehat\theta_j\)<br>\(h_\varphi[T(D_j)]\)',1845,450)]
    for key,label,x,w in specs:
        d.box(key,label,x,355,w,150,color=ORANGE,size=29)
    for key,a,b in [('label-sample','truth','train-data'),('extract','train-data','features'),('predict','features','network'),('network-pred','network','prediction')]:
        d.edge(key,a,b,color=ORANGE)
    d.box('loss',r'\(\mathcal L(\varphi)=\frac1m\sum_{j=1}^{m}\ell(\widehat\theta_j,\theta_j)\)',1415,650,880,105,color=ORANGE,fill='#FFF0DA',size=31,bold=True)
    d.edge('true-loss','truth','loss','真值',color=ORANGE,start='bottom',end='left',via=[(250,702)],at=(780,702))
    d.edge('prediction-loss','prediction','loss','误差',color=ORANGE,start='bottom',end='top',via=[(2070,575),(1855,575)],at=(1990,575))
    d.edge('backprop','loss','network',r'更新 \(\varphi\)',color='#C24F3E',kind='feedback',start='left',end='bottom',via=[(1370,702),(1370,565),(1590,565)],at=(1500,565))
    d.box('trained',r'训练结束：固定 \(h_{\varphi^*}\)',700,775,610,65,color=ORANGE,size=29,bold=True)
    d.edge('finish-training','loss','trained',color=ORANGE,start='bottom',end='right',via=[(1855,807)])

    d.panel('use-panel',40,940,2310,390,fill='#F0F8F3')
    d.text('use-title','② 使用：一组新样本 → 同一特征 → 固定映射 → 参数',65,960,2260,55,size=30,bold=True,color=GREEN)
    d.box('new-data',r'新样本 \(D\)',75,1110,400,145,color=GREEN,size=32)
    d.box('new-features',r'\(T(D)\)',625,1110,400,145,color=GREEN,size=32)
    d.box('fixed',r'\(h_{\varphi^*}[T(D)]\)',1175,1110,540,145,color=GREEN,size=32,bold=True)
    d.box('estimate',r'\((\widehat\beta,\widehat\eta,\widehat\gamma)\)',1865,1110,430,145,color=GREEN,fill='#E7F3EB',size=33,bold=True)
    for key,a,b in [('new-extract','new-data','new-features'),('new-map','new-features','fixed'),('new-output','fixed','estimate')]:
        d.edge(key,a,b,color=GREEN,width=3.2)
    d.edge('deploy','trained','fixed',r'\(\varphi^*\)',color=ORANGE,start='bottom',end='top',via=[(1005,900),(1445,900)],at=(1210,900))

    d.text('intervention-title','学习与搜索的作用位置',2415,195,720,55,size=30,bold=True)
    d.box('direct',r'直接参数映射<br>\(T(D)\rightarrow h_\varphi\rightarrow\widehat\theta\)',2430,355,690,180,color=ORANGE,fill='#FCF6EE',size=30)
    d.box('hybrid',r'过程量学习<br>\(T(D)\rightarrow\) 权重／修正量<br>→ 统计估计器 → \(\widehat\theta\)',2430,685,690,195,color=PURPLE,fill='#F7F2FA',size=29)
    d.box('optimizer',r'数值搜索<br>\(Q(\theta;D)\rightarrow\mathrm{PSO/SA}\)<br>→ \(\widehat\theta\)',2430,1045,690,195,color='#64748B',fill='#FFFFFF',size=29)
    d.save(ROOT/'05-学习映射路线-机制图.drawio')

def validate():
    for name in ['04-后验推断路线-机制图.drawio','05-学习映射路线-机制图.drawio']:
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
    posterior()
    learning()
    validate()
