"""Draw saved two-domain statistics with the frozen Research00 style."""
import hashlib,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator,PercentFormatter
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r00_domain_style',HERE/'绘图母体.py');mother=importlib.util.module_from_spec(spec);spec.loader.exec_module(mother)
STYLES={'cw_engineering':dict(label='工程域 MMLE-I',color=mother.COLORS[0],marker='o',ls='-',markerfacecolor='white'),
        'cw_paper':dict(label='原文域 MMLE-I',color=mother.COLORS[3],marker='D',ls='--',markerfacecolor='white')}
N=np.array([7,10,15,20,50]);plt.rcParams.update({'font.size':9,'legend.fontsize':9})
def main():
    d=pd.read_csv(HERE/'两口径分n统计.csv');raw=pd.read_csv(HERE/'per_sample.csv.gz')
    fig,axes=plt.subplots(2,2,figsize=(8.8,6.4));panels=[]
    specs=[('acceptance_rate','域内有效估计率',[0,1],np.linspace(0,1,6)),
           ('beta_rmse','β RMSE',[0,3],[0,1,2,3]),
           ('eta_rmse','η RMSE',[0,1500],[0,500,1000,1500]),
           ('gamma_rmse','γ RMSE',[0,1500],[0,500,1000,1500])]
    points=[]
    for ax,(key,label,limits,ticks) in zip(axes.flat,specs):
        for policy,style in STYLES.items():
            part=d[d.policy==policy].sort_values('n');y=part[key].to_numpy()
            assert np.array_equal(part.n,N)
            for r in part.itertuples():
                rows=raw[(raw.method_variant==policy)&(raw.n==r.n)];good=rows[rows.status=='success']
                actual=len(good)/len(rows) if key=='acceptance_rate' else np.sqrt(np.mean(good[key.replace('_rmse','_error')]**2))
                assert np.isclose(actual,getattr(r,key),rtol=1e-12)
            line,=ax.plot(part.n,y,lw=1.15,markersize=4.7,markeredgewidth=.8,clip_on=False,**style)
            assert np.array_equal(line.get_xdata(),N) and np.array_equal(line.get_ydata(),y)
            assert np.all((y>=limits[0])&(y<=limits[1]))
            points.extend(dict(policy=policy,n=int(n),metric=key,value=float(value)) for n,value in zip(N,y))
        ax.set_xscale('linear');ax.set_yscale('linear');ax.set_xlim(5,52);ax.set_xticks(N);ax.set_xlabel('n')
        ax.set_ylim(limits);ax.set_yticks(ticks);ax.set_ylabel(label)
        ax.xaxis.set_minor_locator(NullLocator());ax.yaxis.set_minor_locator(NullLocator());ax.tick_params(direction='out')
        if key=='acceptance_rate':ax.yaxis.set_major_formatter(PercentFormatter(xmax=1,decimals=0))
        assert not ax.texts and not ax.get_title()
        panels.append(dict(metric=key,ylim=limits,yticks=list(ticks)))
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.53,.995))
    fig.subplots_adjust(left=.13,right=.975,bottom=.10,top=.90,hspace=.33,wspace=.35)
    output=HERE/'两口径有效率与RMSE.png';assert not fig.texts
    fig.savefig(output,dpi=450,facecolor='white');plt.close(fig)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    (HERE/'绘图核验.json').write_text(json.dumps(dict(points=points,panels=panels,axes='linear',xlim=[5,52],xticks=N.tolist(),
       annotations='Only axes,ticks,domain legend; no extra text/titles',formats=['PNG'],
       precision='Own accepted estimates, no trimming',input_sha256=digest(HERE/'两口径分n统计.csv'),
       mother_sha256=digest(HERE/'绘图母体.py'),script_sha256=digest(Path(__file__)),output_sha256=digest(output),all_passed=True),ensure_ascii=False,indent=2),encoding='utf-8')
    print(output)
if __name__=='__main__':main()
