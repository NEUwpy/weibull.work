"""将样本处理对象、构造公式和参数选择准则展开为可编辑流程。"""
from pathlib import Path
from 细图绘制 import Diagram
ROOT=Path(__file__).resolve().parent
RED,BLUE,GREEN,PURPLE,ORANGE='#A94F40','#2D6D91','#347B68','#785499','#AE6C25'

def canvas(key,title,subtitle,height):
 d=Diagram(key,title,2000,height)
 d.text('title',title,45,20,1910,65,size=35,bold=True)
 d.text('subtitle',subtitle,45,100,1910,65,size=25)
 return d

def chain(d,key,y,heading,parts,color,h=210):
 d.text(key+'-heading',heading,50,y,1900,50,size=28,bold=True)
 for i,(title,body) in enumerate(parts):
  d.box(f'{key}-{i}',title+'<br>'+body,50+i*680,y+70,540,h,color=color,fill='#F7F9FC' if i<2 else '#EDF5EF',size=25,bold=False)
  if i:d.edge(f'{key}-edge-{i}',f'{key}-{i-1}',f'{key}-{i}',color=color,width=3)

def likelihood():
 d=canvas('likelihood-information-flow','似然估计｜从观测处的密度构造联合似然，再以整体贡献定参数','固定已经观测到的寿命；不同候选参数改变各观测处的密度，所有观测的贡献共同进入准则。',1060)
 chain(d,'construction',190,'怎样构造似然函数？',[
  ('① 将观测代入Weibull密度','yᵢ=xᵢ−γ>0<br>fθ(xᵢ)=(β/η)(yᵢ/η)^(β−1)<br>×exp[−(yᵢ/η)^β]<br>每个观测对应一个密度贡献'),
  ('② 利用独立性组合观测贡献','L(θ)=fθ(x₁)×…×fθ(xₙ)<br>=∏ᵢ fθ(xᵢ)<br>把整组样本在候选θ下的<br>联合密度作为参数函数'),
  ('③ 取对数，把乘积变成求和','ℓ(θ)=Σᵢ ln fθ(xᵢ)<br>=n lnβ−nβ lnη+(β−1)Σᵢ ln yᵢ<br>−Σᵢ(yᵢ/η)^β<br>取对数保持最大点不变'),
 ],RED,h=235)
 d.box('maximum','④ 原始MLE：选择联合贡献最大的候选<br>θ̂=argmaxθ ℓ(θ)<br>哪组参数使整组已观测寿命的联合密度最大，就选哪组',150,690,790,170,color=RED,fill='#FFF3ED',size=28,bold=True)
 d.box('equations','由同一ℓ导出方程式构造<br>内点候选满足 ∂ℓ/∂β=∂ℓ/∂η=∂ℓ/∂γ=0<br>方程修正方法在这些关系中加权或替换部分方程，再联立求解',1060,690,790,170,color=RED,fill='#FFF8F4',size=26)
 d.edge('to-max','construction-2','maximum',color=RED,start='bottom',end='top',via=[(1680,585),(545,585)])
 d.edge('to-score','construction-2','equations',color=RED,start='bottom',end='top',via=[(1680,625),(1455,625)])
 d.edge('candidate-loop','maximum','construction-0','数值搜索更新候选θ，重新计算密度贡献',color=RED,kind='feedback',start='bottom',end='left',via=[(545,940),(30,940),(30,377.5)],at=(380,940))
 d.text('scope','最大化或求解均在所选模型支持域内进行；具体的数据修改、方程替换与最小值项处理见下方机制细图。',50,980,1900,50,size=24)
 d.save(ROOT/'07-似然估计路线-信息处理流程.drawio')

def distribution():
 d=canvas('distribution-information-flow','分布匹配｜先构造可比较的分布量，再建立评分并选择参数','各行展开一种实际构造：比较对象、评分的来源和参数判定原则连续相接。',1370)
 chain(d,'plot',190,'概率图：把Weibull分布关系变成直线',[
  ('构造变换后的坐标','uᵢ(γ)=ln(x₍ᵢ₎−γ)<br>Park：pᵢ→zᵢ=ln[−ln(1−pᵢ)]<br>White：取标准对数Weibull<br>次序统计量的期望'),
  ('由分布关系形成回归残差','z≈βu−β lnη<br>选u对z或z对u回归<br>Q=Σ(观测坐标−拟合坐标)²'),
  ('依据拟合程度与位置评分确定','回归使Q最小<br>Soman按F评分、Park按相关性定γ<br>再由斜率和截距反解β、η'),
 ],BLUE)
 chain(d,'cdf',560,'CDF差异／MPS：把观测位置换成累积概率，再比较整组评分',[
  ('在候选θ下计算观测的CDF值','Fᵢ=Fθ(x₍ᵢ₎)<br>MPS另加F₀=0、Fₙ₊₁=1<br>候选θ改变各概率区间的长度'),
  ('把概率偏离或间距合成目标','CDF差异：D(θ)=Σᵢwᵢ(Fᵢ−pᵢ)²<br>MPS间距：Dᵢ=Fᵢ−Fᵢ₋₁<br>间距评分：Q(θ)=Σᵢ₌₁ⁿ⁺¹ln Dᵢ'),
  ('按所选目标比较候选参数','差异准则：θ̂=argminθ D(θ)<br>间距准则：θ̂=argmaxθ Q(θ)<br>比较的是整组概率关系的总评分'),
 ],BLUE)
 chain(d,'mdm',930,'MDM：同一分布模型应让各观测反推的尺度尽量一致',[
  ('每个观测反推一个尺度','qᵢ=−ln(1−pᵢ)<br>ηᵢ(β,γ)=(x₍ᵢ₎−γ)/qᵢ^(1/β)<br>同一候选β、γ产生一组伪尺度'),
  ('先形成条件最小离散曲线','s(β,γ)=stdᵢ[ηᵢ(β,γ)]<br>固定γ：β*(γ)=argminβ s(β,γ)<br>s*(γ)=s[β*(γ),γ]'),
  ('再由梯度阈值和均值确定','g(γ)=ds*(γ)/dγ，按g(γ)=δ定位<br>约束γ≥0时：g(0)≥δ则γ̂=0<br>β̂=β*(γ̂)，η̂=meanᵢηᵢ(β̂,γ̂)'),
 ],BLUE)
 d.save(ROOT/'08-分布匹配路线-信息处理流程.drawio')

def statistics():
 d=canvas('statistics-information-flow','统计关系反演｜写出统计量如何依赖参数，再用消元或条件关系定参数','各行给出具体的统计量、模型关系与确定原则，展示不同的反演路径。',1700)
 chain(d,'moment',190,'常规矩：先用偏度消去位置与尺度',[
  ('由观测计算样本矩','x̄=mean(xᵢ)<br>m₂=mean[(xᵢ−x̄)²]<br>m₃=mean[(xᵢ−x̄)³]<br>样本偏度ĝ=m₃/m₂^(3/2)'),
  ('用模型消去γ、η','理论偏度g(β)只依赖β<br>理论方差=η²A₂(β)<br>A₂(β)=Γ(1+2/β)−Γ²(1+1/β)'),
  ('令样本与理论关系相等','解g(β)=ĝ确定β<br>η̂=√[m₂/A₂(β̂)]<br>γ̂=x̄−η̂Γ(1+1/β̂)'),
 ],GREEN)
 chain(d,'cran',550,'Cran：改用生存曲线积分矩，以矩差比显式消元',[
  ('对经验生存曲线求积分','μ̂ₖ=∫₀∞[1−Fₙ(x)]ᵏdx<br>取k=1、2、4<br>形成三个样本积分矩'),
  ('理论矩差消去位置和尺度','γ≥0时：μₖ=γ+c·k^(−1/β)<br>c=ηΓ(1+1/β)<br>R=(μ₁−μ₂)/(μ₂−μ₄)=2^(1/β)'),
  ('以样本矩差比反解参数','R̂=(μ̂₁−μ̂₂)/(μ̂₂−μ̂₄)<br>β̂=ln2/ln R̂<br>再由任意两条μₖ关系解γ、η'),
 ],GREEN)
 chain(d,'invariance',910,'W／V：先移除干扰参数，再评价剩余信息的联合密度',[
  ('由次序观测构造差与比','Wᵢ=(X₍ᵢ₎−X₍₁₎)/(X₍ₙ₎−X₍₁₎)<br>Vᵢ=X₍ᵢ₎−X₍₁₎<br>差消γ；标准化比值再消η'),
  ('写出变换统计量的联合密度','W内部非退化分量：fW(w;β)<br>V非退化分量：fV(v;η,β)<br>保留各分量之间的相关结构'),
  ('以联合密度最大点确定','W：最大化fW估β，再恢复η、γ<br>V：先联合最大化fV估η、β<br>下一阶段保留β，再恢复η、γ'),
 ],GREEN)
 chain(d,'linear',1270,'条件位置估计：构造共同期望为γ的量，再以最小方差选权',[
  ('给定真实β、η时消去理论偏移','Tᵢ=X₍ᵢ₎−ηEβ[Y₍ᵢ₎]<br>E(Tᵢ)=γ，S=Cov(T)<br>形成一组无偏位置量'),
  ('把线性组合的方差写成目标','γ̂=cᵀT<br>在1ᵀc=1下最小化cᵀSc<br>约束保持无偏，目标压低方差'),
  ('由协方差决定组合系数','c=S⁻¹1/(1ᵀS⁻¹1)<br>再计算γ̂=cᵀT<br>参数未知时另以临时估计代入<br>并可接入参数恢复迭代'),
 ],GREEN)
 d.save(ROOT/'09-统计关系反演路线-信息处理流程.drawio')

def posterior():
 d=canvas('posterior-information-flow','后验推断｜用先验重加权似然，再以损失或密度峰决定估计','先构造完整的参数后验；所选后验规则随后决定需要计算的目标。',1110)
 chain(d,'posterior-build',190,'后验怎样由观测和已有信息形成？',[
  ('计算候选参数的样本支持','L(θ|D)=∏ᵢfθ(xᵢ)<br>π(θ)描述已有参数信息<br>同时限定模型与先验的允许域'),
  ('将样本贡献与先验权重相乘','q(θ)=L(θ|D)π(θ)<br>观测和先验共同改变<br>不同候选参数的相对权重'),
  ('积分归一化为参数后验','Z=∫q(θ)dθ<br>p(θ|D)=q(θ)/Z<br>积分在允许参数域内进行'),
 ],PURPLE)
 d.box('risk','后验损失最小化<br>R(a|D)=∫损失(a,θ)p(θ|D)dθ<br>选择a使后验平均损失最小<br>平方损失→后验均值；逐参数绝对损失→边缘中位数',95,700,1010,225,color=PURPLE,fill='#F6F0FB',size=27)
 d.box('map','后验密度最大化（MAP）<br>θ̂MAP=argmaxθ p(θ|D)<br>=argmaxθ[lnL(θ|D)+lnπ(θ)]<br>选联合后验密度最高的候选',1215,700,690,225,color=PURPLE,fill='#F6F0FB',size=27)
 d.edge('to-risk','posterior-build-2','risk',color=PURPLE,start='bottom',end='top',via=[(1680,580),(600,580)])
 d.edge('to-map','posterior-build-2','map',color=PURPLE,start='bottom',end='top',via=[(1680,625),(1560,625)])
 d.text('calculation','积分、Gibbs／MH抽样、Laplace近似或优化，是计算相应后验量的路径；参数选择依据来自上述规则。',50,1000,1900,60,size=25)
 d.save(ROOT/'10-后验推断路线-信息处理流程.drawio')

def learning():
 d=canvas('learning-information-flow','学习映射｜把多组参数预测误差写成训练目标，再选择估计函数','参数标签提供训练判据；要确定的是共享映射的权重φ，训练结束后再用于当前新样本。',1000)
 chain(d,'learn',190,'训练目标怎样由样本及其真值形成？',[
  ('把每组样本变成统一特征','tⱼ=T(Dⱼ)<br>如排序值、分位数或统计量<br>用当前映射预测θ̂ⱼ=hφ(tⱼ)'),
  ('逐组对照参数真值，形成损失','将θ̂ⱼ与对应标签θⱼ比较<br>ℒ(φ)=(1/m)Σⱼℓ(θ̂ⱼ,θⱼ)<br>例：ℓ=Σₖ(θ̂ⱼₖ−θⱼₖ)²<br>多组预测误差合成一个训练目标'),
  ('按预测误差选择映射权重','φ*=argminφ ℒ(φ)<br>按梯度等方法更新φ并重新预测<br>使训练样本上的规定损失更小'),
 ],ORANGE,h=245)
 d.edge('training-loop','learn-2','learn-0','更新φ→重算各组预测与损失→继续减小训练目标',color=ORANGE,kind='feedback',start='bottom',end='bottom',via=[(1680,580),(320,580)],at=(1000,580))
 d.box('fixed','训练完成后固定φ*<br>新样本仍按同一T提取特征，再计算hφ*(T(D))<br>参数估计来自已经确定的映射',390,715,1220,170,color=GREEN,fill='#F0F8F3',size=28,bold=True)
 d.edge('freeze','learn-2','fixed',color=ORANGE,start='right',end='right',via=[(1970,382.5),(1970,800)])
 d.save(ROOT/'11-学习映射路线-信息处理流程.drawio')

if __name__=='__main__':
 likelihood();distribution();statistics();posterior();learning()
 print('generated five construction-and-criterion flowcharts')
