"""Real MDM traces and complete successful-estimate violin distributions."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

# Reuse the already available plotting runtime without changing dependencies.
try:
    import matplotlib
except ModuleNotFoundError:
    sys.path.append(str(Path.home() / 'AppData/Local/hermes/hermes-agent/venv/Lib/site-packages'))
    import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import LogFormatterMathtext, LogLocator, NullFormatter
from scipy.stats import gaussian_kde

METHODS=['mdm','lse','lre','wmle','mle']
NAMES=['MDM','LSE','LRE','WMLE','MLE']
COLORS=['#345D7E','#589CA3','#8A7398','#B27448','#5F6570']
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','Arial','DejaVu Sans'],
                     'font.size':8,'axes.linewidth':.7,'axes.spines.top':False,'axes.spines.right':False,
                     'axes.unicode_minus':False})


def save(fig, output, name):
    fig.savefig(output/f'{name}.png',dpi=450,facecolor='white')
    plt.close(fig)


def draw(program):
    program=Path(program)
    output=program.parents[1]/'结果'/program.name
    source=output/'中间数据/results.json'
    data=json.loads(source.read_text(encoding='utf-8'))
    beta,eta,gamma=data['truth']
    gradient_metadata=[]
    xmax=1500 if eta==1000 else 700
    xticks=[0,500,1000,1500] if eta==1000 else [0,100,200,300,400,500,600,700]
    for n in data['n']:
        fig,ax=plt.subplots(figsize=(5.12,3.62))
        rows=[r for r in data['gradient_curves'] if r['n']==n]
        for row in rows:
            points=sorted(row['points'],key=lambda p:p['gamma'])
            ax.plot([p['gamma'] for p in points],[p['gradient'] for p in points],color='black',lw=.48,alpha=.75)
        ax.axhline(data['offset'],color='#B55E3E',lw=.9,ls='-.')
        ax.axvline(gamma,color='.55',lw=.7,ls=':')
        ax.set_xlim(0,xmax); ax.set_ylim(-.8,1.6)
        ax.set_xticks(xticks); ax.set_yticks([-.8,-.4,0,.4,.8,1.2,1.6])
        ax.set_xlabel('γ'); ax.set_ylabel(r'$d\sigma(\gamma)/d\gamma$')
        ax.tick_params(direction='in'); fig.subplots_adjust(left=.145,right=.975,bottom=.18,top=.97)
        name=f'样本量{n}_偏移量{data["offset"]:.2f}'
        save(fig,output,name)
        gradient_metadata.append(dict(file=name,n=n,curves=len(rows),points=sum(len(r['points']) for r in rows),
                                      x_limits=[0,xmax],y_limits=[-.8,1.6],threshold=data['offset']))
    fig,axes=plt.subplots(3,3,figsize=(8.2,6.9),sharex='col',sharey=True)
    panel_records=[]
    for col,(key,truth,logarithmic,label) in enumerate([
            ('beta_hat',beta,True,'β'),('eta_hat',eta,True,'η'),('gamma_hat',gamma,False,'γ')]):
        pooled=np.array([r[key] for r in data['results'] if r['converged'] and r[key] is not None])
        limits=[min(pooled.min(),truth)*.78,max(pooled.max(),truth)*1.2] if logarithmic else [-.06*max(pooled.max(),truth),max(pooled.max(),truth)*1.06]
        for row,n in enumerate(data['n']):
            ax=axes[row,col]
            if logarithmic: ax.set_xscale('log')
            ax.set_xlim(limits); ax.set_ylim(4.6,-.6)
            ax.axvline(truth,color='black',ls='--',lw=.75,zorder=1)
            for pos,method in enumerate(METHODS):
                rr=sorted([r for r in data['results'] if r['n']==n and r['method_id']==method and r['converged']],key=lambda r:r['id'])
                values=np.array([r[key] for r in rr]); density_values=values[values>0] if key=='gamma_hat' else values
                coords=np.log10(density_values) if logarithmic else density_values
                if len(coords)>1 and np.ptp(coords)>1e-12:
                    grid=np.linspace(coords.min(),coords.max(),256); kde=gaussian_kde(coords,bw_method='scott')(grid)
                    width=.32*kde/kde.max(); shown=10**grid if logarithmic else grid
                    ax.fill_between(shown,pos-width,pos+width,color=COLORS[pos],alpha=.22,lw=.6)
                ax.scatter(values,np.full(len(values),pos),s=3,color=COLORS[pos],alpha=.65,linewidths=0,zorder=4)
                quartiles=np.quantile(values,[.25,.5,.75]) if len(values) else [None]*3
                if len(values):
                    ax.plot([quartiles[0],quartiles[2]],[pos,pos],color='#48515A',lw=.5,zorder=3)
                    ax.scatter(quartiles[1],pos,s=10,marker='D',facecolor='white',edgecolor='#48515A',lw=.5,zorder=5)
                panel_records.append(dict(n=n,method=method,parameter=key,truth=truth,sample_ids=[r['id'] for r in rr],
                                          values=values.tolist(),quartiles=list(quartiles),zeros=int(np.count_nonzero(values==0)),
                                          success=len(values),failure=50-len(values),x_limits=limits,points_on_centerline=True))
            ax.set_yticks(range(5),NAMES)
            ax.tick_params(axis='y',length=0,labelleft=col==0)
            ax.tick_params(axis='x',labelbottom=True)
            ax.set_xlabel(label)
            ax.text(-.07,1.08,chr(97+row*3+col),transform=ax.transAxes,fontsize=9,weight='bold')
            if col==0: ax.text(.02,1.08,f'n={n}',transform=ax.transAxes,fontsize=8)
    for col in (0,1):
        for ax in axes[:,col]:
            ax.xaxis.set_major_locator(LogLocator(base=10,numticks=5))
            ax.xaxis.set_major_formatter(LogFormatterMathtext(base=10,labelOnlyBase=True))
            ax.xaxis.set_minor_locator(LogLocator(base=10,subs=range(2,10)))
            ax.xaxis.set_minor_formatter(NullFormatter())
    fig.subplots_adjust(left=.09,right=.98,top=.94,bottom=.08,wspace=.23,hspace=.63)
    save(fig,output,'估计分布_小提琴图')
    record=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),gradient_figures=gradient_metadata,
                violin=dict(panels=9,records=panel_records,bandwidth='Scott',beta_eta_coordinate='log10',gamma_coordinate='linear',
                            zero_gamma_excluded_from_density=True,all_successful_points_preserved=True,iqr_linewidth=.5),
                formats=['png 450dpi'],notes_on_figures=False)
    (output/'中间数据/绘图核验.json').write_text(json.dumps(record,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print('PLOTTED',data['distribution'],'3 MDM plots and 1 violin grid.',flush=True)
