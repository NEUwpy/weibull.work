"""Mathematical illustrations, not an estimator benchmark. PNG/SVG + editable draw.io."""
from pathlib import Path
import sys, math, json, xml.etree.ElementTree as ET
deps=Path('D:/weibull/tmp/r09-plot-deps')
if deps.exists(): sys.path.insert(0,str(deps))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.colors import to_hex
from scipy.special import gamma
from scipy.optimize import brentq

B=Path(__file__).resolve().parents[1]; P=B/'图片'
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':12,'axes.titlesize':14,
 'axes.labelsize':12,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,
 'axes.unicode_minus':False,'lines.linewidth':2.1,'figure.facecolor':'white'})
BLUE='#286D9B'; RED='#C26340'; GREEN='#43836A'; GRAY='#75808C';PURPLE='#8065A6'
doc=ET.Element('mxfile',host='app.diagrams.net'); manifest={}
n=9;p=(np.arange(1,n+1)-.3)/(n+.4);t=2+4*np.sqrt(-np.log1p(-p))
def figure(title,cols=2):
 f,axs=plt.subplots(1,cols,figsize=(12,4.8),dpi=120,squeeze=False)
 f.subplots_adjust(left=.075,right=.975,bottom=.19,top=.76,wspace=.32)
 f.suptitle(title,fontsize=19,y=.97)
 f.text(.5,.865,'数学原理示意 · 示例条件与适用边界见图下注释',ha='center',fontsize=10.5,color=GRAY)
 return f,axs[0]
def style(ax,x,y,title):
 ax.set(xlabel=x,ylabel=y,title=title);ax.grid(alpha=.15)
def note(f,text):f._principle_note=text
def drawio(f,name):
 # Translate numerical artists to native editable polylines, circles and labels.
 # No plot bitmap is embedded in draw.io.
 f.canvas.draw();renderer=f.canvas.get_renderer();W,H=f.canvas.get_width_height()
 d=ET.SubElement(doc,'diagram',id=name[:2],name=name)
 m=ET.SubElement(d,'mxGraphModel',page='1',pageWidth=str(W),pageHeight=str(H));root=ET.SubElement(m,'root')
 ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0');k=0
 def cell(**kwargs):
  nonlocal k;k+=1;return ET.SubElement(root,'mxCell',id=f'{name[:2]}_{k}',parent='1',**kwargs)
 def path(xy,color,width=1.5,dash=False,alpha=1):
  if len(xy)<2:return
  c=cell(edge='1',style=f'endArrow=none;startArrow=none;rounded=0;strokeColor={color};strokeWidth={width:.2f};dashed={int(dash)};opacity={100*alpha};')
  g=ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
  ET.SubElement(g,'mxPoint',x=str(xy[0,0]),y=str(H-xy[0,1]),attrib={'as':'sourcePoint'})
  ET.SubElement(g,'mxPoint',x=str(xy[-1,0]),y=str(H-xy[-1,1]),attrib={'as':'targetPoint'})
  if len(xy)>2:
   ar=ET.SubElement(g,'Array',attrib={'as':'points'})
   for x,y in xy[1:-1]:ET.SubElement(ar,'mxPoint',x=f'{x:.2f}',y=f'{H-y:.2f}')
 for ax in f.axes:
  for sp in ax.spines.values():
   if sp.get_visible():path(sp.get_transform().transform(sp.get_path().vertices),'#333333',1.2)
 lines=[]; text_objects=list(f.texts)
 for ax in f.axes:
  lines.extend((line,ax) for line in ax.lines)
  text_objects.extend([ax.title,ax.xaxis.label,ax.yaxis.label]);text_objects.extend(ax.texts)
  for axis,limits in [(ax.xaxis,ax.get_xlim()),(ax.yaxis,ax.get_ylim())]:
   for tick in axis.get_major_ticks():
    if min(limits)-1e-9 <= tick.get_loc() <= max(limits)+1e-9:
     lines.append((tick.gridline,ax));text_objects.extend([tick.label1,tick.label2])
  legend=ax.get_legend()
  if legend is not None:
   lines.extend((line,None) for line in legend.get_lines());text_objects.extend(legend.get_texts())
 for line,owner in lines:
  if not line.get_visible():continue
  xy=line.get_transform().transform(line.get_xydata())
  if not len(xy):continue
  color=to_hex(line.get_color());finite=np.isfinite(xy).all(axis=1)
  if owner is not None and line.get_clip_on():
   bounds=owner.bbox;finite &= (xy[:,0]>=bounds.x0-1)&(xy[:,0]<=bounds.x1+1)&(xy[:,1]>=bounds.y0-1)&(xy[:,1]<=bounds.y1+1)
  inds=np.flatnonzero(finite)
  for group in np.split(inds,np.where(np.diff(inds)>1)[0]+1):
   if len(group) and line.get_linestyle() not in ('None','none','',' '):path(xy[group],color,line.get_linewidth()*f.dpi/72,line.get_linestyle() in ('--',':','-.'),line.get_alpha() if line.get_alpha() is not None else 1)
  if line.get_marker() in ('o','s','D'):
   size=line.get_markersize()*f.dpi/72
   for x,y in xy[finite]:
    c=cell(vertex='1',style=f'ellipse;fillColor={color};strokeColor={color};');ET.SubElement(c,'mxGeometry',x=str(x-size/2),y=str(H-y-size/2),width=str(size),height=str(size),attrib={'as':'geometry'})
 for text in text_objects:
  if not text.get_visible() or not text.get_text().strip():continue
  bb=text.get_window_extent(renderer);color=to_hex(text.get_color());fs=text.get_fontsize()*f.dpi/72;rotation=text.get_rotation()
  x,y,w,h=bb.x0,H-bb.y1,bb.width,bb.height
  if rotation==90:x,y,w,h=x+(w-h)/2,y+(h-w)/2,h,w
  c=cell(vertex='1',value=text.get_text(),style=f'text;html=0;whiteSpace=wrap;align=center;verticalAlign=middle;fontFamily=Microsoft YaHei;fontSize={fs};fontColor={color};rotation={-rotation};strokeColor=none;fillColor=none;')
  ET.SubElement(c,'mxGeometry',x=str(x-3),y=str(y-2),width=str(w+6),height=str(h+4),attrib={'as':'geometry'})
 return k
def save(f,name,description):
 f.savefig(P/f'原理-{name}.png',dpi=150);f.savefig(P/f'原理-{name}.svg')
 count=drawio(f,name);manifest[name]={'description':description,'caption':getattr(f,'_principle_note',''),'editable_cells':count};plt.close(f)
def loglik(beta,eta,loc):
 a=t-loc
 return np.sum(np.log(beta)-beta*np.log(eta)+(beta-1)*np.log(a)-(a/eta)**beta)

# 1. Actual likelihood section and actual finite-sample shape estimating equations.
f,ax=figure('似然路线：似然的峰值与估计方程的零点')
betas=np.linspace(.5,4,160);ll=np.array([loglik(b,4,2) for b in betas]);j=ll.argmax()
ax[0].plot(betas,ll,color=BLUE,label='固定 η=4、γ=2 的似然切片');ax[0].plot(betas[j],ll[j],'o',color=RED)
ax[0].axvline(betas[j],color=RED,ls='--',lw=1);ax[0].legend(fontsize=10,loc='lower right')
style(ax[0],'形状 β','对数似然 ℓ','MLE：寻找声明参数域内的最大值')
a=t-2
def eq(b,j2):return j2/b+np.log(a).mean()-np.sum(a**b*np.log(a))/np.sum(a**b)
# J2 is intentionally schematic; do not label this as calibrated Cousineau output.
for j2,col,label in [(1,BLUE,'普通形状方程：J2=1'),(.8,RED,'修正示意：J2=0.8（人为设定）')]:
 yy=[eq(b,j2) for b in betas];ax[1].plot(betas,yy,color=col,label=label);r=brentq(lambda b:eq(b,j2),.5,4);ax[1].plot(r,0,'o',color=col)
ax[1].axhline(0,color=GRAY,lw=1);ax[1].legend(fontsize=9)
style(ax[1],'形状 β','形状估计方程残差','WMLE思想：改变方程，零点随之改变')
note(f,'右图仅隔离形状方程的修正作用；实际WMLE还须联立位置方程并使用原文权重。')
save(f,'01-似然路线','Fixed eta/gamma likelihood and schematic J2 shape score; not a calibrated WMLE comparison.')

# 2. Probability-plot geometry, same observations and plotting scores.
f,ax=figure('概率图路线：位置改变散点形状，回归方向改变残差')
z=np.log(-np.log1p(-p))
for loc,col in [(0,RED),(2,BLUE)]:
 x=np.log(t-loc);ax[0].plot(x,z,'o-',color=col,label=f'候选位置 γ={loc}')
style(ax[0],'对数寿命 x = ln(t − γ)','绘图分数 z','同一组数据：位置改变直线性');ax[0].legend(fontsize=10)
x=np.log(t-(t.min()-.05));b,c=np.polyfit(x,z,1);s,q=np.polyfit(z,x,1);xx=np.linspace(x.min()-.05,x.max()+.05,100)
ax[1].plot(x,z,'o',color=GRAY,label='相同散点（γ接近样本最小值）');ax[1].plot(xx,c+b*xx,color=BLUE,label='z 对 x：竖向残差');ax[1].plot(xx,(xx-q)/s,color=RED,label='x 对 z：横向残差')
for xi,zi in zip(x,z):
 ax[1].plot([xi,xi],[zi,c+b*xi],color=BLUE,lw=1);ax[1].plot([xi,q+s*zi],[zi,zi],color=RED,lw=1)
style(ax[1],'对数寿命 x','绘图分数 z','两种OLS投影一般不等价');ax[1].legend(fontsize=9)
note(f,'散点由理想分位数构造，γ=2时恰好线性；随机样本通常不会落在一条直线上。')
save(f,'02-概率图路线','Ideal quantiles and regression residual geometry; same scores on right to isolate regression direction.')

# 3. Moment equations: first solve shape by skewness, then eta/gamma by mean/variance.
f,ax=figure('矩路线：样本统计量给出约束，交点确定参数')
def skew(b):
 g1,g2,g3=gamma(1+1/b),gamma(1+2/b),gamma(1+3/b)
 return (g3-3*g1*g2+2*g1**3)/(g2-g1*g1)**1.5
bg=np.linspace(.8,4.5,150);target=skew(2)
ax[0].plot(bg,skew(bg),color=BLUE,label='理论偏度，仅取决于β');ax[0].axhline(target,color=RED,label='示例样本偏度');ax[0].plot(2,target,'o',color=GREEN);ax[0].axvline(2,color=GREEN,ls='--',lw=1)
style(ax[0],'形状 β','偏度','第三个统计量确定形状');ax[0].legend(fontsize=10)
eg=np.linspace(1,7,120);mu=2+4*gamma(1.5);variance=16*(gamma(2)-gamma(1.5)**2)
ax[1].plot(eg,mu-eg*gamma(1.5),color=BLUE,label='均值约束：γ = 均值 − ηΓ(1+1/β)');ax[1].axvline(4,color=RED,label='方差约束确定η');ax[1].plot(4,2,'o',color=GREEN)
style(ax[1],'尺度 η','位置 γ','给定形状后，两条约束相交');ax[1].legend(fontsize=9)
note(f,'示例统计量设为理论值以展示交点；PWM和L矩替换匹配的统计量，未必得到同一交点。')
save(f,'03-矩匹配路线','Illustrative exact theoretical moments for beta=2 eta=4 gamma=2; not empirical accuracy.')

# 4. CDF geometry and probability-axis spacings; endpoints explicitly included.
f,ax=figure('MPS：观测之间的概率质量，就是要比较的间距')
grid=np.linspace(2,10,140);F=1-np.exp(-((grid-2)/4)**2)
ax[0].plot(grid,F,color=BLUE);ax[0].plot(t,p,'o',color=BLUE)
for i in [2,3]:
 ax[0].plot([t[i],t[i]],[0,p[i]],color=GRAY,ls='--',lw=1);ax[0].plot([2,t[i]],[p[i],p[i]],color=GRAY,ls='--',lw=1)
ax[0].plot([2.2,2.2],[p[2],p[3]],color=RED,lw=5);ax[0].text(2.35,(p[2]+p[3])/2,'概率差 D',color=RED,fontsize=11)
style(ax[0],'寿命 t','拟合分布 F(t)','CDF上的纵向差，不是寿命横向差')
u=np.r_[0,p,1]
for i in range(len(u)-1):
 ax[1].plot([u[i],u[i+1]],[0,0],color=BLUE if i%2 else RED,lw=5)
ax[1].plot(u,np.zeros(len(u)),'o',color=GRAY,ms=4)
for i in [0,3,9]:ax[1].text((u[i]+u[i+1])/2,.15,['首间距','内部间距','尾间距'][[0,3,9].index(i)],ha='center',fontsize=10)
ax[1].set(xlim=(-.02,1.02),ylim=(-.45,.65),yticks=[],xlabel='概率轴：0 ≤ F(t) ≤ 1',title='加入0与1，形成 n+1 个间距');ax[1].spines['left'].set_visible(False)
ax[1].text(.5,-.27,'最大化 D1 × D2 × … × D(n+1)',ha='center',fontsize=13)
note(f,'参数改变时，CDF及全部概率间距一起改变；乘积惩罚极小间距。')
save(f,'04-概率间距路线','CDF vertical gap and full n+1 spacings including endpoints.')

# 5. Different candidate beta/gamma yield different scale pseudo-estimates.
f,ax=figure('MDM：让每个观测反推的尺度尽量一致')
for axis,b,loc,col in [(ax[0],1,0,RED),(ax[1],2,2,BLUE)]:
 vals=(t-loc)/(-np.log1p(-p))**(1/b);mean=vals.mean()
 axis.plot(np.arange(1,n+1),vals,'o',color=col)
 axis.axhline(mean,color=GRAY,ls='--',label='尺度伪估计的均值')
 for i,v in enumerate(vals,1):axis.plot([i,i],[mean,v],color=col,lw=1.5)
 style(axis,'排序观测编号 i','尺度伪估计 η(i)',f'候选 β={b}，γ={loc}；离散度={vals.std(ddof=1):.2f}')
 axis.set(ylim=(0,45),xticks=[1,3,5,7,9]);axis.legend(fontsize=9)
note(f,'两图使用同一组理想分位数；右图尺度完全一致是构造结果，不代表真实样本能无误差估计。')
save(f,'05-构造差异路线','Scale pseudo-estimate dispersion for two candidates on ideal quantiles.')

# 6. Minimum distribution: mean vs median, then two location update curves.
f,ax=figure('组合估计：用最小值的分布关系定位起点')
mins=np.linspace(2,6,150);density=n*2/4*((mins-2)/4)*np.exp(-n*((mins-2)/4)**2)
emin=2+4/n**.5*gamma(1.5);med=2+4*(np.log(2)/n)**.5
ax[0].plot(mins,density,color=BLUE,label='样本最小值的密度');ax[0].axvline(emin,color=RED,label='期望');ax[0].axvline(med,color=GREEN,ls='--',label='中位数');style(ax[0],'最小值 T(1)','概率密度','最小值的期望与中位数不同');ax[0].legend(fontsize=10)
bg=np.linspace(.8,4,150);tmin=float(t[0]);gmean=tmin-4*n**(-1/bg)*gamma(1+1/bg);gmed=tmin-4*(np.log(2)/n)**(1/bg)
ax[1].plot(bg,gmean,color=RED,label='SAM：由期望关系反推γ');ax[1].plot(bg,gmed,color=GREEN,ls='--',label='PM：由中位数关系反推γ');style(ax[1],'当前形状 β（此图固定η=4）','更新后的位置 γ','同一最小观测，两种更新关系');ax[1].legend(fontsize=9)
note(f,'图展示位置更新的数学依据；SAM的回归更新与PM的条件似然更新另见正文。')
save(f,'06-组合估计路线','Minimum density and different mean/median location update functions; not iterative trajectories.')

# 7. Supervised mapping geometry: conceptual 1D projection, not ANN reproduction.
f,ax=figure('学习估计：在“样本特征—参数”空间学习映射')
rng=np.random.default_rng(20260927);train_b=rng.uniform(1,4,90);samples=rng.weibull(train_b[:,None],(90,20));features=samples.std(axis=1)/samples.mean(axis=1)
xx=np.linspace(.2,1.25,130)
def smooth(x):
 w=np.exp(-.5*((features-x)/.10)**2);return np.sum(w*train_b)/np.sum(w)
yy=np.array([smooth(x) for x in xx]);xnew=.62;pred=smooth(xnew)
ax[0].plot(features,train_b,'o',color=GRAY,ms=3.5,label='模拟训练配对（每组n=20）');ax[0].plot(xx,yy,color=BLUE,label='示意拟合映射');style(ax[0],'样本特征：变异系数','训练标签：真实形状 β','同一特征附近可对应不同真参数');ax[0].legend(fontsize=9)
ax[1].plot(xx,yy,color=BLUE,label='固定后的示意映射');ax[1].plot([xnew,xnew],[.8,pred],color=RED,ls='--');ax[1].plot([.15,xnew],[pred,pred],color=RED,ls='--');ax[1].plot(xnew,pred,'o',color=RED);ax[1].text(.73,pred+.1,'由特征读出预测值',fontsize=11,color=RED);style(ax[1],'新样本的同一种特征','输出的形状估计','使用阶段不需要新样本的真参数');ax[1].set(xlim=(.15,1.3),ylim=(.8,4.1))
note(f,'仅用一维核平滑展示监督映射几何，非ANN复现；完整三参数网络使用多维特征并输出三个参数。')
save(f,'07-学习估计路线','90 simulated pairs, kernel smoother as explicit conceptual mapping, not a BPNN implementation.')

# 8. Actual conditional likelihood and prior posterior on eta grid.
f,ax=figure('贝叶斯：似然与先验相乘，再归一化为后验')
eg=np.linspace(1,9,220);logs=np.array([loglik(2,e,2) for e in eg]);like=np.exp(logs-logs.max());prior=np.exp(-.5*((np.log(eg)-np.log(6))/.35)**2)/eg
normalize=lambda y:y/np.trapezoid(y,eg)
prior=normalize(prior);like=normalize(like);post=normalize(prior*like);postmean=np.trapezoid(eg*post,eg)
ax[0].plot(eg,like,color=BLUE,label='归一化似然（用于形状比较）');ax[0].plot(eg,prior,color=RED,ls='--',label='示例先验');style(ax[0],'尺度 η（固定β=2、γ=2）','归一化曲线高度','两种信息对同一参数的支持');ax[0].legend(fontsize=9)
ax[1].plot(eg,post,color=PURPLE,label='后验密度');ax[1].axvline(postmean,color=GREEN,ls='--',label='后验均值');style(ax[1],'尺度 η','后验密度','后验分布与点估计不同');ax[1].legend(fontsize=10)
note(f,'先验为示例对数正态分布；后验均值是平方损失下的决策，不等于后验峰值。')
save(f,'08-贝叶斯推断','Actual conditional eta posterior, lognormal prior; numerical normalization on [1,9].')

# 9. Mathematical objective landscape and different search paths, not algorithm runs.
f,ax=figure('数值求解：目标曲面不变，搜索路径可以不同')
angles=np.linspace(0,2*np.pi,140)
for axis in ax:
 for radius in [.4,.8,1.2,1.6,2]:axis.plot(radius*np.cos(angles),.65*radius*np.sin(angles),color=GRAY,lw=1)
 axis.plot(0,0,'o',color=GREEN);axis.set(xlim=(-2.2,2.2),ylim=(-1.5,1.5),aspect='equal');style(axis,'参数坐标1','参数坐标2','相同的目标函数等高线')
ax[0].plot([-1.8,-.8,-.2,0],[1.2,.55,.12,0],'o-',color=BLUE,label='搜索路径A（示意）');ax[0].legend(fontsize=9,loc='lower left')
ax[1].plot([1.8,-1,.7,.1,0],[1.2,-.4,.6,-.1,0],'o-',color=RED,label='搜索路径B（示意）');ax[1].legend(fontsize=9,loc='lower left')
note(f,'椭圆来自示例二次目标；路径为示意，未运行Newton或PSO，也不表示三参数似然总有有限最优点。')
save(f,'09-数值求解','Schematic quadratic objective and hand-defined search paths; not measured algorithm behavior.')
ET.ElementTree(doc).write(P/'各路线基本原理.drawio',encoding='utf-8',xml_declaration=True)
manifest['shared_example']={'n':n,'beta':2,'eta':4,'gamma':2,'p':p.tolist(),'t':t.tolist(),'type':'deterministic ideal quantiles, not random experiment'}
(B/'evidence/原理图示例说明.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('Exported 9 mathematical figures and native editable draw.io pages.')
