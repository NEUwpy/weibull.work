"""Figure 7: three sample columns, aligned offset axes, location over joint loss.

Python/Matplotlib revision of the existing workflow. 183 x 116 mm; 8 pt type;
same E11 samples and all 26 candidates. Each sample has its own vertical scale.
No smoothing, no resampling. Group evidence exported separately for the appendix.
"""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, ScalarFormatter
from matplotlib.lines import Line2D
from plot_offset_revision_v112 import F, DATA, E11, COLORS, GROUPS, save, QA


def main():
    scan=pd.read_csv(DATA/'representative_candidate_losses_v112.csv')
    rep=pd.read_csv(E11/'representative_gradient_curves.csv').groupby('profile_group').first()
    fig,axes=plt.subplots(2,3,figsize=(183/25.4,116/25.4),sharex='col')
    fig.subplots_adjust(left=.105,right=.98,bottom=.12,top=.81,wspace=.55,hspace=.28)
    handles=[Line2D([0],[0],color='#333333',marker='s',mfc='white',ls='',label=r'固定 $\delta=0.1$'),
             Line2D([0],[0],color='#333333',marker='o',ls='',label='L6 最低损失点'),
             Line2D([0],[0],color='#999999',ls='--',lw=.8,label='真位置')]
    fig.legend(handles=handles,ncol=3,loc='upper center',bbox_to_anchor=(.53,.99),handlelength=1.4,columnspacing=1.8)
    labels='abcdef'
    for col,(group,color,letter) in enumerate(zip(GROUPS,COLORS,'ABC')):
        r=rep.loc[group]; z=scan[scan.repeat_id.eq(r.repeat_id)].sort_values('delta')
        assert len(z)==26
        best=z.loc[z.loss.idxmin()];default=z[z.delta.eq(.1)].iloc[0]
        for row,ykey in enumerate(['gamma_hat','loss']):
            ax=axes[row,col]; div=1000 if row==0 else 1
            ax.plot(z.delta,z[ykey]/div,color=color,lw=1.25,marker='o',ms=2.1,mew=0)
            ax.scatter(.1,default[ykey]/div,marker='s',s=28,facecolor='white',edgecolor=color,lw=1.1,zorder=6)
            ax.scatter(best.delta,best[ykey]/div,marker='o',s=30,color=color,edgecolor='white',lw=.6,zorder=7)
            ax.axvline(.1,color='#CCCCCC',ls=':',lw=.65,zorder=0)
            ax.set_xlim(-.015,.515)
            ax.set_xticks([0,.1,.3,.5])
            ax.yaxis.set_major_locator(MaxNLocator(4))
            fmt=ScalarFormatter(useOffset=False);fmt.set_scientific(False);ax.yaxis.set_major_formatter(fmt)
            ax.margins(y=.17)
            ax.grid(axis='y',color='#E7E7E7',lw=.5);ax.set_axisbelow(True)
            ax.text(-.24,1.04,labels[row*3+col],transform=ax.transAxes,fontweight='bold',fontsize=9)
            if row==0:
                # Show the truth only when inside the natural data range; do not compress C's path.
                lo,hi=ax.get_ylim()
                if lo<=.5<=hi:ax.axhline(.5,color='#999999',ls='--',lw=.8)
                ax.set_title('样本 '+letter,pad=13,color=color,fontsize=10,fontweight='bold')
            else:ax.set_xlabel(r'偏移量 $\delta$',labelpad=5)
        axes[0,0].set_ylabel(r'位置估计 $\hat{\gamma}/\eta$',labelpad=6)
        axes[1,0].set_ylabel(r'联合损失 $\ell$',labelpad=6)
    save(fig,'fig7_sample_columns_v112')

    cond=pd.read_csv(E11/'conditional_loss_curves.csv')
    cond=cond[cond.stratifier.eq('default_gamma_hat')]
    assert len(cond)==78
    cells=pd.read_csv(E11/'cell_associations.csv')
    fig,(a,b)=plt.subplots(1,2,figsize=(183/25.4,83/25.4))
    fig.subplots_adjust(left=.09,right=.98,bottom=.21,top=.85,wspace=.38)
    for group,color in zip(GROUPS,COLORS):
        z=cond[cond.tertile.eq(group)].sort_values('delta');best=z.loc[z.mean_excess_over_l6.idxmin()]
        a.plot(z.delta,z.mean_excess_over_l6,c=color,lw=1.1,label={'low':'低组','middle':'中组','high':'高组'}[group])
        a.scatter(best.delta,best.mean_excess_over_l6,c=color,s=22,zorder=4)
    a.legend();a.set(xlabel=r'偏移量 $\delta$',ylabel='平均超额损失',xlim=(-.01,.51),title='按固定位置估计分组')
    for i,n in enumerate([7,10,15,20]):
        values=cells.loc[cells.n.eq(n),'rho_default_gamma_l6_delta'].to_numpy()
        b.scatter(i+np.linspace(-.14,.14,len(values)),values,c=COLORS[0],s=20,alpha=.8)
        b.hlines(np.median(values),i-.23,i+.23,color='#333333',lw=1.3)
    b.set(xticks=range(4),xticklabels=['7','10','15','20'],xlabel=r'样本量 $n$',ylabel=r'组合内 Spearman $\rho$',ylim=(-.93,.025),title='固定位置估计与 L6 偏移量')
    b.axhline(0,color='#999999',ls='--',lw=.7)
    for ax,label in zip([a,b],'ab'):
        ax.grid(axis='y',c='#E7E7E7',lw=.5);ax.set_axisbelow(True)
        ax.text(-.16,1.09,label,transform=ax.transAxes,fontweight='bold',fontsize=10)
    save(fig,'supp_fig_sample_groups_v110','supplementary')
    (DATA/'figure7_redesign_qa.json').write_text(json.dumps(QA,indent=2),encoding='utf-8')

if __name__=='__main__': main()
