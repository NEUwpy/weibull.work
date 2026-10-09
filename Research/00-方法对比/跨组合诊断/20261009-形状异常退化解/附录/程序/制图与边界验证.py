from pathlib import Path
import csv,json,math
import numpy as np
from scipy.special import logsumexp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
APP=Path(__file__).resolve().parent.parent
FIG=APP.parent/'图片'
FIG.mkdir(parents=True,exist_ok=True)
inputs=json.loads((APP/'五组输入.json').read_text(encoding='utf8'))
selected=inputs['samples']
diagnostics=json.loads((APP/'五组独立诊断.json').read_text(encoding='utf8'))
def read_csv(name):
 names={'profiles.csv':'位置剖面.csv','boundary_directions.csv':'扩展参数域边界方向.csv'}
 with (APP/names.get(name,name)).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def csv_write(path,rows):
 with path.open('w',encoding='utf8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
proof = []
embedded = []
fixed_dense = []
for item in diagnostics:
    x = np.array(selected[item['case']])
    b, e, g = item['independent']
    z = np.log((x-g)/e)
    w = np.exp(b*z)
    hb = -len(x)/b**2 - np.dot(w, z*z)
    he = -b/e**2*((b+1)*w.sum()-len(x))
    cross = (w.sum()-len(x)+b*np.dot(w,z))/e
    transformed = np.diag([b,e]) @ np.array([[hb,cross],[cross,he]]) @ np.diag([b,e])
    eigen = np.linalg.eigvalsh(transformed)
    assert eigen.max() < 0 and item['score'][2] < 0
    proof.append(dict(case=item['case'], score_beta=item['score'][0],
        score_eta=item['score'][1], score_gamma=item['score'][2],
        log_parameter_hessian_eigen_min=eigen[0],
        log_parameter_hessian_eigen_max=eigen[1],
        lower_location_kkt=True, fixed_location_strict_maximum=True))
    mu = item['gumbel']['mu']; sigma = item['gumbel']['sigma']
    v = (x-mu)/sigma
    for q in np.linspace(0, .02, 201):
        if q == 0:
            value = -len(x)*np.log(sigma) + v.sum()-np.exp(v).sum()
            shape = scale = location = None
        else:
            shape=1/q; scale=shape*sigma; location=mu-scale
            a=np.log1p(v*q)
            value=-len(x)*np.log(sigma)+(shape-1)*a.sum()-np.exp(shape*a).sum()
        embedded.append(dict(case=item['case'],inverse_shape=q,beta=shape,
            eta=scale,gamma=location,ll=float(value),
            difference_from_gumbel=float(value-item['gumbel']['ll'])))
    for shape in np.linspace(.5, 60, 500):
        logs=np.log(x); centered=logs-logs.mean()
        value=len(x)*np.log(shape)-len(x)*logs.mean()-len(x)*(logsumexp(shape*centered)-np.log(len(x)))-len(x)
        fixed_dense.append(dict(case=item['case'],beta=shape,gamma=0,ll=float(value)))
csv_write(APP / '边界极值验证.csv', proof)
csv_write(APP / '嵌入分布受控路径.csv', embedded)
csv_write(APP / '固定零位置稠密曲线.csv', fixed_dense)

plt.rcParams.update({'font.family':'sans-serif', 'font.sans-serif':['Microsoft YaHei','Arial'],
    'font.size':11, 'axes.labelsize':12, 'axes.titlesize':12,
    'axes.spines.top':False, 'axes.spines.right':False,
    'lines.linewidth':1.8, 'savefig.dpi':600, 'axes.unicode_minus':False})
blue='#0072B2'; orange='#D55E00'; green='#009E73'; grey='#666666'
profiles = read_csv('profiles.csv')
case = diagnostics[0]['case']
item = diagnostics[0]
rows = [row for row in profiles if row['case']==case]
gamma=np.array([float(row['gamma']) for row in rows])

# Figure 1: one question -- whether each stored point optimizes its own rule.
fig, axes = plt.subplots(1,3,figsize=(12,3.6),layout='constrained')
for ax, method, column, color in zip(axes,['MLE','LSE','LRE'],['ll','lse_loss','lre_loss'],[blue,orange,green]):
    values=np.array([float(row[column]) for row in rows])
    if method=='MLE':
        values-=item['independent_ll']; opt_gamma=item['stored'][2]; opt_value=0
        label=r'$\ell_p(\gamma)-\ell_p(\hat\gamma)$'
    else:
        result=item['regression'][method];opt_gamma=result['stored'][2];opt_value=result['stored_loss']
        label=r'$1-R^2(\gamma)$'
    ax.plot(gamma,values,color=color)
    ax.axvline(500,color=grey,ls='--',lw=1)
    ax.scatter([opt_gamma],[opt_value],color=color,s=38,zorder=5,clip_on=False)
    ax.set(xlim=(0,550),xticks=[0,100,200,300,400,500],xlabel=r'$\gamma$',ylabel=label,title=method)
axes[1].set_ylim(0,.22);axes[2].set_ylim(0,.22)
zoom=axes[2].inset_axes([.16,.34,.48,.42])
local=gamma<=200
zoom.plot(gamma[local],(np.array([float(row['lre_loss']) for row in rows])[local]-item['regression']['LRE']['loss'])*1e6,color=green,lw=1.4)
zoom.scatter([item['regression']['LRE']['stored'][2]],[0],s=18,c=green,zorder=5)
zoom.set(xlim=(0,200),xticks=[0,100,200],ylim=(-2,100),yticks=[0,50,100],xlabel=r'$\gamma$',ylabel=r'$10^6\Delta(1-R^2)$')
zoom.tick_params(labelsize=8)
zoom.xaxis.label.set_size(9);zoom.yaxis.label.set_size(9)
fig.savefig(FIG/'图1_各自准则的真实极值.png');plt.close(fig)

# Figure 2: one question -- large parameter changes can preserve sample fit.
fig,axes=plt.subplots(1,3,figsize=(12,3.6),layout='constrained')
x=np.array(selected[case]);t=np.linspace(450,740,600)
def cdf(t,b,e,g):
    return -np.expm1(-np.maximum((t-g)/e,0)**b)
axes[0].plot(t,cdf(t,*item['truth']),color=grey,ls='--',label='真分布')
axes[0].plot(t,cdf(t,*item['stored']),color=blue,label='MLE')
axes[0].scatter(x,(np.arange(1,len(x)+1)-.5)/len(x),s=18,c='black',label='排序样本')
axes[0].set(xlabel=r'$t$',ylabel=r'$F(t)$',xlim=(450,740),ylim=(0,1),title='同一组样本')
axes[0].legend(frameon=False,fontsize=9)
for ax,column,truth,ylabel,limits in [(axes[1],'beta',2,r'$\hat\beta(\gamma)$',(0,25)),(axes[2],'eta',100,r'$\hat\eta(\gamma)$',(0,650))]:
    values=np.array([float(row[column]) for row in rows]);idx=0 if column=='beta' else 1
    ax.plot(gamma,values,color=blue)
    ax.axvline(500,color=grey,ls='--',lw=1);ax.axhline(truth,color=grey,ls='--',lw=1)
    ax.scatter([0],[item['stored'][idx]],s=38,color=blue,clip_on=False,zorder=5)
    ax.set(xlim=(0,550),ylim=limits,xticks=[0,100,200,300,400,500],xlabel=r'$\gamma$',ylabel=ylabel,title='位置改变后的条件估计')
fig.savefig(FIG/'图2_位置左移与参数补偿.png');plt.close(fig)

# Figure 3: distinguish finite maximum, unbounded endpoint and finite embedding.
case=diagnostics[0]['case'];item=diagnostics[0]
fig,axes=plt.subplots(1,3,figsize=(12,3.6),layout='constrained')
rows=[row for row in fixed_dense if row['case']==case]
axes[0].plot([row['beta'] for row in rows],[row['ll']-item['stored_ll'] for row in rows],color=blue)
axes[0].scatter([item['stored'][0]],[0],s=38,c=blue,zorder=5)
axes[0].set(xlabel=r'$\beta$',ylabel=r'$\ell-\ell(\hat\theta)$',title=r'$\gamma=0$',xlim=(0,60))
rows=[row for row in read_csv('boundary_directions.csv') if row['case']==case and row['branch']=='fixed_beta_0.5']
relative=[-math.log10((item['sample_min']-float(row['gamma']))/item['sample_min']) for row in rows]
axes[1].plot(relative,[float(row['ll']) for row in rows],color=orange,marker='o',ms=4)
axes[1].set(xlabel=r'$-\log_{10}[(x_{(1)}-\gamma)/x_{(1)}]$',ylabel=r'$\ell$',title=r'$\beta=0.5,\ \eta=100$',xlim=(0,13))
rows=[row for row in embedded if row['case']==case]
axes[2].plot([row['inverse_shape'] for row in rows],[row['difference_from_gumbel'] for row in rows],color=green)
axes[2].scatter([0],[0],s=36,c=green,clip_on=False,zorder=5)
axes[2].set(xlabel=r'$1/\beta$',ylabel=r'$\ell_W-\ell_G$',title=r'$\mu,\sigma$ 固定',xlim=(0,.02))
fig.savefig(FIG/'图3_三种边界方向.png');plt.close(fig)

