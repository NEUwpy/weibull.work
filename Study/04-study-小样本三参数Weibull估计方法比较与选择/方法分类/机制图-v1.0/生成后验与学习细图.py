"""后验的模型/决策/计算，及学习映射的训练/使用原理展开。"""
from pathlib import Path
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
PURPLE, ORANGE, GREEN = '#785499', '#AE6C25', '#2C7B61'


def posterior():
    d = Diagram('posterior-detail-v10', '后验推断：联合后验、决策与计算', 1800, 1650)
    d.text('title','后验推断｜联合后验怎样变成三个参数的估计',45,20,1710,60,size=35,bold=True)
    d.text('subtitle','先把样本贡献、参数先验与支持域组合，再选择所需后验量和计算路径。',45,90,1710,45,size=24)
    d.box('prior','参数先验 π(β,η,γ)<br>表达参数范围与已有信息',60,170,480,145,color=PURPLE,fill='#F7F1FB',size=26)
    d.box('like','样本 D 的联合似然<br>L(β,η,γ|D)=∏ᵢ f(xᵢ|β,η,γ)',660,170,480,145,color='#A75043',fill='#FFF5F0',size=26)
    d.box('domain','模型与先验的支持域相交<br>β>0，η>0，γ<x₍₁₎<br>再结合位置参数的先验域',1260,170,480,145,color='#64748B',fill='#F3F6FA',size=25)
    d.box('joint','三参数联合后验<br>p(β,η,γ|D) = L(β,η,γ|D) π(β,η,γ) / Z<br>Z 为允许参数域内 Lπ 的积分',430,425,940,155,color=PURPLE,fill='#F4EDF9',size=28,bold=True)
    d.edge('prior-joint','prior','joint','先验权重',color=PURPLE,start='bottom',end='left',via=[(300,502)],at=(307,410))
    d.edge('like-joint','like','joint','样本贡献',color='#A75043',start='bottom',end='top',at=(990,370))
    d.edge('domain-joint','domain','joint','限定积分与抽样范围',color='#64748B',start='bottom',end='right',via=[(1500,502)],at=(1510,410))

    d.panel('decision-panel',45,680,825,680,fill='#F8F5FC')
    d.panel('compute-panel',930,680,825,680,fill='#F3F8FA')
    d.box('decision-title','① 选取哪一个后验量作为估计',70,700,775,60,size=28,bold=True,color=PURPLE,fill='#F8F5FC')
    d.box('compute-title','② 怎样计算需要的后验量',955,700,775,60,size=28,bold=True,color=GREEN,fill='#F3F8FA')
    d.box('mean','后验均值<br>θ̂ = E(θ|D)<br>对应平方损失',75,825,230,180,color=PURPLE,fill='#FFFFFF',size=25)
    d.box('median','逐参数后验中位数<br>median(θₖ|D)<br>对应绝对损失',340,825,230,180,color=PURPLE,fill='#FFFFFF',size=25)
    d.box('map','MAP<br>argmaxθ p(θ|D)<br>取联合后验密度峰',605,825,230,180,color=PURPLE,fill='#FFFFFF',size=24)
    d.edge('joint-decision','joint','decision-title',color=PURPLE,start='bottom',end='top',via=[(900,630),(457.5,630)])
    d.edge('rule-mean','decision-title','mean',color=PURPLE,start='bottom',end='top',via=[(457.5,790),(190,790)])
    d.edge('rule-median','decision-title','median',color=PURPLE,start='bottom',end='top')
    d.edge('rule-map','decision-title','map',color=PURPLE,start='bottom',end='top',via=[(457.5,790),(720,790)])
    d.box('decision-meaning','先验与似然决定同一个联合后验<br>输出规则决定取其期望、中位数还是密度峰',75,1080,760,110,color=PURPLE,fill='#FFFFFF',size=25)
    d.box('map-example','MAP 的目标为 log L + log π<br>先验改变不同候选参数的相对权重',75,1240,760,85,color=PURPLE,fill='#F1E9F8',size=24)

    d.box('beta','β 条件更新<br>从 p(β|η,γ,D)<br>抽取新的 β',960,825,230,170,color=GREEN,fill='#FFFFFF',size=25)
    d.box('eta','η 条件更新<br>给定新 β、当前 γ<br>抽取新的 η',1227,825,230,170,color=GREEN,fill='#FFFFFF',size=24)
    d.box('gamma','γ 条件更新<br>给定新 β、η<br>在允许域内抽取 γ',1494,825,230,170,color=GREEN,fill='#FFFFFF',size=25)
    d.edge('joint-compute','joint','compute-title',color=GREEN,start='bottom',end='top',via=[(900,650),(1342.5,650)])
    d.edge('compute-chain','compute-title','beta',color=GREEN,start='bottom',end='top',via=[(1342.5,790),(1075,790)])
    d.edge('beta-eta','beta','eta',color=GREEN)
    d.edge('eta-gamma','eta','gamma',color=GREEN)
    d.edge('repeat','gamma','beta','循环更新，形成联合后验样本',color=GREEN,kind='feedback',start='bottom',end='bottom',via=[(1609,1040),(1075,1040)],at=(1340,1040))
    d.box('samples','由后验样本近似期望、中位数与区间<br>Green 方案：Gibbs＋条件拒绝抽样；γ 更新也可构造 MH 核',960,1110,764,100,color=GREEN,fill='#FFFFFF',size=24)
    d.edge('chain-samples','eta','samples',color=GREEN,start='bottom',end='top')
    d.box('laplace','另一条计算路径：Laplace<br>在后验峰附近作二次近似，再近似积分',960,1260,764,80,color='#367B98',fill='#EEF7FB',size=24)
    d.edge('joint-laplace','joint','laplace',color='#367B98',kind='borrow',start='right',end='right',via=[(1770,502),(1770,1300)])
    d.box('estimate','输出 θ̂=(β̂,η̂,γ̂)<br>由所选后验规则与相应计算共同确定',540,1460,720,105,color=PURPLE,fill='#F1E9F8',size=29,bold=True)
    d.edge('rule-output','decision-meaning','estimate','所选规则',color=PURPLE,start='left',end='left',via=[(58,1135),(58,1400),(500,1400),(500,1512)],at=(410,1400))
    d.edge('sample-output','samples','estimate','计算后验量',color=GREEN,start='right',end='right',via=[(1740,1160),(1740,1512)],at=(1550,1512))
    d.edge('laplace-output','laplace','estimate',color='#367B98',start='bottom',end='top',via=[(1342,1420),(900,1420)])
    d.text('basis','构造依据：方法工作稿 §5.3；Green 的条件抽样、后验均值决策与 Laplace 积分近似。',55,1590,1690,36,size=21)
    d.save(ROOT/'04-后验推断路线-机制图.drawio')


def learning():
    d = Diagram('learning-detail-v10', '学习映射：训练闭环与新样本使用',1800,1650)
    d.text('title','学习映射｜多组样本训练估计函数，新样本执行固定映射',45,20,1710,60,size=35,bold=True)
    d.text('subtitle','训练阶段学习网络权重 φ；使用阶段把新样本的相同特征直接映射为分布参数。',45,90,1710,45,size=24)
    d.panel('training-panel',40,165,1720,625,fill='#FCF6EE')
    d.text('training-title','训练阶段：同时看到样本与对应参数',65,185,1630,60,size=29,bold=True)
    specs=[('truth','参数标签 θⱼ<br>βⱼ、ηⱼ、γⱼ<br>与样本量 nⱼ',65,255),
           ('train-data','训练样本 Dⱼ<br>来自模拟或标注<br>每组对应一组参数',395,255),
           ('features','统一的特征 T(Dⱼ)<br>如排序值、分位数<br>或汇总统计量',725,255),
           ('network','参数映射 hφ<br>网络把特征组合<br>转换为参数预测',1055,255),
           ('prediction','训练样本的预测<br>θ̂ⱼ = hφ(T(Dⱼ))',1385,285)]
    for key,text,x,w in specs:d.box(key,text,x,300,w,145,color=ORANGE,fill='#FFFFFF',size=24)
    for key,a,b in [('label-sample','truth','train-data'),('extract','train-data','features'),('predict','features','network'),('network-pred','network','prediction')]:d.edge(key,a,b,color=ORANGE)
    d.box('loss','逐样本对照预测与真值<br>ℒ(φ) = 平均ⱼ ℓ(θ̂ⱼ, θⱼ)',1055,590,615,100,color=ORANGE,fill='#FFF0DA',size=27,bold=True)
    d.edge('true-loss','truth','loss','对应的真参数标签',color=ORANGE,start='bottom',end='left',via=[(192.5,640)],at=(640,640))
    d.edge('prediction-loss','prediction','loss','预测误差',color=ORANGE,start='bottom',end='top',via=[(1527.5,530),(1362.5,530)],at=(1530,530))
    d.edge('backprop','loss','network','按损失更新 φ',color='#C24F3E',kind='feedback',start='left',end='bottom',via=[(1015,640),(1015,505),(1182.5,505)],at=(1135,505))
    d.box('trained','训练结束，固定映射 hφ*',385,705,635,60,color=ORANGE,fill='#FFFFFF',size=27,bold=True)
    d.edge('finish-training','loss','trained',color=ORANGE,start='bottom',end='right',via=[(1362.5,735)])

    d.panel('use-panel',40,875,1720,395,fill='#F0F8F3')
    d.text('use-title','使用阶段：一组新样本走一次映射',65,895,1630,60,size=29,bold=True)
    d.box('new-data','新寿命样本 D<br>当前观测值',70,1020,330,135,color=GREEN,fill='#FFFFFF',size=27)
    d.box('new-features','沿用相同特征定义<br>T(D)',500,1020,330,135,color=GREEN,fill='#FFFFFF',size=27)
    d.box('fixed','固定的估计函数<br>hφ*(T(D))',930,1020,360,135,color=GREEN,fill='#FFFFFF',size=27,bold=True)
    d.box('estimate','输出三个参数<br>β̂、η̂、γ̂',1390,1020,310,135,color=GREEN,fill='#E7F3EB',size=28,bold=True)
    for key,a,b in [('new-extract','new-data','new-features'),('new-map','new-features','fixed'),('new-output','fixed','estimate')]:d.edge(key,a,b,color=GREEN,width=3.2)
    d.edge('deploy','trained','fixed','携带训练得到的固定权重',color=ORANGE,start='bottom',end='top',via=[(702.5,830),(1110,830)],at=(1110,830))
    d.text('use-note','训练域给出所学映射的参数范围；特征与损失决定映射怎样利用信息、重视哪种误差。',75,1195,1610,48,size=24)

    d.text('intervention-title','映射、辅助学习与数值搜索在估计中的作用位置',55,1345,1690,55,size=29,bold=True)
    d.box('direct','直接参数映射<br>T(D) → hφ → θ̂',65,1440,490,120,color=ORANGE,fill='#FCF6EE',size=27)
    d.box('hybrid','学习中间量<br>T(D) → 权重／修正量 → 统计估计器 → θ̂',655,1440,490,120,color='#785499',fill='#F7F2FA',size=25)
    d.box('optimizer','当前样本的数值求解<br>固定 Q(θ;D) → PSO／SA 搜索 → θ̂',1245,1440,490,120,color='#64748B',fill='#F4F7FA',size=25)
    d.text('basis','构造依据：方法工作稿 §5.4 的直接ANN/BPNN、过程量学习与既定目标搜索的作用位置。',55,1590,1690,36,size=21)
    d.save(ROOT/'05-学习映射路线-机制图.drawio')


if __name__=='__main__':
    posterior()
    learning()
    print('generated posterior and learning mechanism details')
