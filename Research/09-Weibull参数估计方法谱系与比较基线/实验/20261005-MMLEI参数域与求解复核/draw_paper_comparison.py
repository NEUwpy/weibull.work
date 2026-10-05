"""Plot three saved original-equation methods, using the frozen Research00 style."""
import hashlib,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator,PercentFormatter
HERE=Path(__file__).resolve().parent;DEST=HERE/'三方法原文口径'
spec=importlib.util.spec_from_file_location('r00_paper_comparison',HERE/'绘图母体.py');mother=importlib.util.module_from_spec(spec);spec.loader.exec_module(mother)
METHODS=['MLE','MMLE-I','WMLE'];N=np.array([7,10,15,20,50])
STYLE={'MLE':dict(color=mother.COLORS[4],marker='s',ls='--',markerfacecolor='white'),
       'MMLE-I':dict(color=mother.COLORS[0],marker='o',ls='-',markerfacecolor='white'),
       'WMLE':dict(color=mother.COLORS[3],marker='D',ls=':',markerfacecolor='white')}
plt.rcParams.update({'font.size':9,'legend.fontsize':9})
def main():
    d=pd.read_csv(DEST/'分n统计.csv');raw=pd.read_csv(DEST/'per_sample.csv.gz');points=[]
    def lines(ax,key):
        for method in METHODS:
            part=d[d.method==method].sort_values('n');y=part[key].to_numpy();assert np.array_equal(part.n,N)
            for row in part.itertuples():
                data=raw[(raw.method_variant==method)&(raw.n==row.n)];good=data[data.status=='success']
                actual=len(good)/len(data) if key=='acceptance_rate' else np.sqrt(sum(np.mean(good[p+'_error']**2) for p in ['beta','eta','gamma'])) if key=='joint_rmse' else np.sqrt(np.mean(good[key.replace('_rmse','_error')]**2))
                assert np.isclose(actual,getattr(row,key),rtol=1e-12)
                points.append(dict(method=method,n=int(row.n),metric=key,value=float(actual)))
            line,=ax.plot(part.n,y,label=method,lw=1.15,markersize=4.5,markeredgewidth=.8,clip_on=False,**STYLE[method])
            assert np.array_equal(line.get_ydata(),y)
        ax.set_xscale('linear');ax.set_yscale('linear');ax.set_xlim(5,52);ax.set_xticks(N);ax.set_xlabel('n')
        ax.xaxis.set_minor_locator(NullLocator());ax.yaxis.set_minor_locator(NullLocator());ax.tick_params(direction='out')
        assert not ax.texts and not ax.get_title()
    fig,ax=plt.subplots(figsize=(6.2,4.));lines(ax,'acceptance_rate');ax.set_ylim(0,1);ax.set_yticks(np.linspace(0,1,6));ax.yaxis.set_major_formatter(PercentFormatter(xmax=1,decimals=0));ax.set_ylabel('原文口径有效解率')
    fig.legend(*ax.get_legend_handles_labels(),loc='upper center',ncol=3,frameon=False,bbox_to_anchor=(.53,.995));fig.subplots_adjust(left=.14,right=.975,bottom=.16,top=.88)
    success=DEST/'成功率随n变化.png';fig.savefig(success,dpi=450,facecolor='white');plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(8.8,6.4));panels=[]
    specs=[('beta_rmse','β RMSE',[0,3],[0,1,2,3]),('eta_rmse','η RMSE',[0,1500],[0,500,1000,1500]),
           ('gamma_rmse','γ RMSE',[0,1500],[0,500,1000,1500]),('joint_rmse','联合 RMSE',[0,2000],[0,500,1000,1500,2000])]
    for ax,(key,label,limits,ticks) in zip(axes.flat,specs):
        lines(ax,key);ax.set_ylim(limits);ax.set_yticks(ticks);ax.set_ylabel(label)
        assert np.all((d[key]>=limits[0])&(d[key]<=limits[1]))
        panels.append(dict(metric=key,ylim=limits,yticks=ticks))
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='upper center',ncol=3,frameon=False,bbox_to_anchor=(.53,.995));fig.subplots_adjust(left=.13,right=.975,bottom=.10,top=.90,hspace=.33,wspace=.35)
    rmse=DEST/'RMSE随n变化.png';fig.savefig(rmse,dpi=450,facecolor='white');plt.close(fig)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    (DEST/'绘图核验.json').write_text(json.dumps(dict(points=points,point_count=len(points),axes='linear',xticks=N.tolist(),panels=panels,success_ylim=[0,1],
        precision='All own accepted estimates, untrimmed',annotations='Axes,ticks,method legend only',formats=['PNG'],
        source_sha256=digest(DEST/'分n统计.csv'),mother_sha256=digest(HERE/'绘图母体.py'),
        output_sha256={str(p):digest(p) for p in [success,rmse]},all_passed=True),ensure_ascii=False,indent=2),encoding='utf-8')
    print(success);print(rmse)
if __name__=='__main__':main()
