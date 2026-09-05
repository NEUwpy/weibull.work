"""Targeted Python revision; preserves all existing figure assets.

Contract: quantitative grids at 183 mm, editable SVG/PDF, 600 dpi PNG/TIFF.
Figure 2: overall risk and its conditional bias/variance components explain selection.
Figure 7: the SAME three E11 samples connect gradient crossings to candidate losses;
          pooled conditional curves and within-cell correlations support the example.
No smoothing or invented samples. Lines connect evaluated nodes only. 8 pt minimum text.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

F = Path(__file__).resolve().parents[1]
S = F.parents[1]
DATA = S / 'artifacts/exploratory/offset_mechanism_scan_20260905'
E11 = S / 'artifacts/formal/E11_profile_mechanism'
plt.rcParams.update({'font.family':'sans-serif', 'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
    'font.size':8, 'axes.titlesize':9, 'axes.labelsize':8.5, 'legend.fontsize':8,
    'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,
    'xtick.major.width':.65,'ytick.major.width':.65, 'legend.frameon':False,
    'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False})
BLUE, ORANGE, GRAY = '#2B6F92', '#C76A3A', '#777777'
COLORS = [BLUE,GRAY,ORANGE]
GROUPS = ['low','middle','high']
QA = []

def axis(ax, label, title):
    ax.set_title(title,pad=9,loc='left')
    ax.text(-.16,1.08,label,transform=ax.transAxes,fontweight='bold',fontsize=10)
    ax.tick_params(labelsize=8)
    ax.grid(axis='y',color='#E5E5E5',lw=.5)
    ax.set_axisbelow(True)

def save(fig, name, folder='main'):
    target = F / folder / name
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    outside=[]
    hidden_ticks=set()
    for ax in fig.axes:
        for axis_obj, limits in [(ax.xaxis,ax.get_xlim()),(ax.yaxis,ax.get_ylim())]:
            for tick in axis_obj.get_major_ticks():
                if not min(limits)-1e-9 <= tick.get_loc() <= max(limits)+1e-9:
                    hidden_ticks.update([tick.label1,tick.label2])
    for txt in fig.findobj(matplotlib.text.Text):
        if txt not in hidden_ticks and txt.get_visible() and txt.get_text():
            bb=txt.get_window_extent(renderer)
            if bb.x0 < -1 or bb.y0 < -1 or bb.x1 > fig.bbox.x1+1 or bb.y1 > fig.bbox.y1+1:
                outside.append(txt.get_text())
    assert not outside, (name,outside)
    for ext in ['png','svg','pdf','tiff']:
        kw={'pil_kwargs':{'compression':'tiff_lzw'}} if ext=='tiff' else {}
        fig.savefig(target.with_suffix('.'+ext),dpi=600,facecolor='white',**kw)
    QA.append({'figure':name,'width_mm':round(fig.get_figwidth()*25.4,2),
               'height_mm':round(fig.get_figheight()*25.4,2),'out_of_canvas_text':outside,
               'min_font_pt':8,'dpi':600,'formats':['png','svg','pdf','tiff']})
    plt.close(fig)

def fig2():
    d=pd.read_csv(DATA/'pooled_bias_variance.csv')
    fig,axs=plt.subplots(1,2,figsize=(183/25.4,83/25.4))
    fig.subplots_adjust(left=.085,right=.985,bottom=.21,top=.83,wspace=.36)
    ax=axs[0]
    ax.plot(d.delta,d.J1,'o-',c='#333333',lw=1,ms=2.4,mfc='white')
    for v,marker,c,label in [(.06,'o',BLUE,'网格最低点（0.06）'),(.1,'s',ORANGE,'固定值（0.10）')]:
        row=d[np.isclose(d.delta,v)].iloc[0]
        ax.scatter(v,row.J1,s=28,marker=marker,c=c,zorder=5,label=label)
    ax.legend(loc='upper right',handlelength=1)
    ax.set(xlabel=r'偏移量 $\delta$',ylabel=r'联合误差 $J_1$',xlim=(-.01,.51),ylim=(.59,.98))
    axis(ax,'a','固定偏移量的联合误差')
    ax=axs[1]
    for key,c,ls,label in [('risk','#333333','-',r'总误差 $B^2+V$'),
                          ('var_sum',BLUE,'--',r'方差项 $V$'),
                          ('bias_sq_sum',ORANGE,'-.',r'偏差平方项 $B^2$')]:
        ax.plot(d.delta,d[key],ls,c=c,lw=1.1,marker='o',ms=2,mfc='white',label=label)
    ax.set(xlabel=r'偏移量 $\delta$',ylabel=r'联合均方误差及分量',xlim=(-.01,.51),ylim=(0,1.04))
    ax.legend(loc='upper right',handlelength=2)
    axis(ax,'b','条件偏差与抽样方差')
    save(fig,'fig2_offset_risk_decomposition_v112')

def representatives():
    r=pd.read_csv(E11/'representative_gradient_curves.csv')
    chunk=S/'artifacts/formal/E5_normalized_raw/shared_data/chunks'
    matches=[]
    for p in chunk.glob('*_meta.json'):
        unit=json.loads(p.read_text())['unit']
        if unit['beta']==3 and unit['gamma_over_eta']==.5 and unit['n']==10:
            matches.append(p.with_name(p.name.replace('_meta.json','_mdm.csv')))
    assert len(matches)==1
    scan=pd.read_csv(matches[0])
    scan=scan[scan.repeat_id.isin(r.repeat_id.unique())].copy()
    scan['loss']=((scan.beta_hat-scan.beta)/scan.beta)**2+((scan.eta_hat-scan.eta)/scan.eta)**2+((scan.gamma_hat-scan.gamma)/scan.eta)**2
    assert len(scan)==78 and scan.status.eq('success').all()
    for group in GROUPS:
        row=r[r.profile_group.eq(group)].iloc[0]
        z=scan[scan.repeat_id.eq(row.repeat_id)].sort_values('delta')
        assert np.isclose(z.loc[z.loss.idxmin(),'delta'],row.l6_delta)
        assert np.isclose(z[z.delta.eq(.1)].iloc[0].gamma_hat/1000,row.gamma_hat_default_over_eta)
    scan.to_csv(DATA/'representative_candidate_losses_v112.csv',index=False)
    return r,scan

def fig7():
    r,scan=representatives()
    cond=pd.read_csv(E11/'conditional_loss_curves.csv')
    cond=cond[cond.stratifier.eq('default_gamma_hat')].copy()
    assert len(cond)==78 and not cond.duplicated(['tertile','delta']).any()
    minima=cond.loc[cond.groupby('tertile').mean_excess_over_l6.idxmin()].set_index('tertile').delta
    assert all(np.isclose(minima[g],v) for g,v in zip(GROUPS,[.10,.04,.02]))
    cells=pd.read_csv(E11/'cell_associations.csv')
    fig,axs=plt.subplots(2,2,figsize=(183/25.4,155/25.4))
    fig.subplots_adjust(left=.085,right=.985,bottom=.09,top=.90,hspace=.60,wspace=.36)
    handles=[Line2D([0],[0],c=c,lw=1.2,label='样本 '+letter) for c,letter in zip(COLORS,'ABC')]
    handles += [Line2D([0],[0],c='#333333',marker='s',mfc='white',ls='',label=r'固定 $\delta=0.1$'),
                Line2D([0],[0],c='#333333',marker='o',ls='',label='逐样本 L6')]
    fig.legend(handles=handles,loc='upper center',ncol=5,bbox_to_anchor=(.53,.993),columnspacing=1,handlelength=1.3)
    a,b,c,d=axs.ravel()
    for group,color in zip(GROUPS,COLORS):
        q=r[r.profile_group.eq(group)].sort_values('gamma_over_eta'); row=q.iloc[0]
        a.plot(q.gamma_over_eta,q.gradient,c=color,lw=1,marker='.',ms=2)
        a.scatter(row.gamma_hat_default_over_eta,.1,marker='s',s=28,facecolor='white',edgecolor=color,zorder=5)
        a.scatter(row.l6_gamma_hat_over_eta,row.l6_delta,marker='o',s=23,color=color,zorder=6)
        z=scan[scan.repeat_id.eq(row.repeat_id)].sort_values('delta')
        b.plot(z.delta,z.loss,c=color,lw=1,marker='.',ms=2)
        default=z[z.delta.eq(.1)].iloc[0]; best=z.loc[z.loss.idxmin()]
        b.scatter(.1,default.loss,marker='s',s=28,facecolor='white',edgecolor=color,zorder=5)
        b.scatter(best.delta,best.loss,marker='o',s=23,color=color,zorder=6)
        z=cond[cond.tertile.eq(group)].sort_values('delta'); best=z.loc[z.mean_excess_over_l6.idxmin()]
        c.plot(z.delta,z.mean_excess_over_l6,c=color,lw=1,marker='.',ms=2,
               label={'low':'低组','middle':'中组','high':'高组'}[group])
        c.scatter(best.delta,best.mean_excess_over_l6,c=color,s=23,zorder=5)
    a.axhline(.1,c='#555555',ls='--',lw=.6,zorder=0)
    a.axvline(.5,c='#AAAAAA',ls=':',lw=.7,zorder=0)
    a.set(xlabel=r'候选位置 $\gamma/\eta$',ylabel=r'廓线梯度 $\nabla_X(\gamma)$',xlim=(0,1),ylim=(-.065,.265))
    axis(a,'a','同参数样本的搜索交点')
    b.set(xlabel=r'偏移量 $\delta$',ylabel=r'三参数联合损失 $\ell$',xlim=(-.01,.51))
    axis(b,'b','对应样本的候选损失')
    c.set(xlabel=r'偏移量 $\delta$',ylabel='平均超额损失',xlim=(-.01,.51))
    c.legend(loc='upper right',handlelength=1.5)
    axis(c,'c','按固定位置估计分组')
    for i,n in enumerate([7,10,15,20]):
        vals=cells.loc[cells.n.eq(n),'rho_default_gamma_l6_delta'].to_numpy()
        d.scatter(i+np.linspace(-.13,.13,len(vals)),vals,c=BLUE,s=17,alpha=.8)
        d.hlines(np.median(vals),i-.24,i+.24,color='#333333',lw=1.3)
    d.axhline(0,c='#777777',ls='--',lw=.7)
    d.set(xticks=range(4),xticklabels=['7','10','15','20'],xlabel=r'样本量 $n$',
          ylabel=r'组合内 Spearman $\rho$',ylim=(-.93,.035))
    axis(d,'d','固定位置估计与 L6 偏移量')
    save(fig,'fig7_sample_path_loss_v112')

def supp():
    df=pd.read_csv(DATA/'cell_bias_variance.csv')
    fig,ax=plt.subplots(figsize=(120/25.4,82/25.4))
    fig.subplots_adjust(left=.16,right=.98,top=.92,bottom=.18)
    for j,delta in enumerate([0,.1]):
        arrays=[np.sqrt(df[df.delta.eq(delta)][p+'_var']*300/299) for p in ['beta','eta','gamma']]
        positions=np.arange(3)+(j-.5)*.32
        parts=ax.violinplot(arrays,positions=positions,widths=.29,showextrema=False)
        for body in parts['bodies']:
            body.set_facecolor([ORANGE,BLUE][j]);body.set_edgecolor([ORANGE,BLUE][j]);body.set_alpha(.2)
        ax.boxplot(arrays,positions=positions,widths=.09,showfliers=False,patch_artist=True,
                   boxprops={'facecolor':'white','edgecolor':[ORANGE,BLUE][j]},
                   medianprops={'color':[ORANGE,BLUE][j]},whiskerprops={'color':[ORANGE,BLUE][j]},
                   capprops={'color':[ORANGE,BLUE][j]})
    ax.set(xticks=range(3),xticklabels=[r'$\beta$',r'$\eta$',r'$\gamma$'],ylabel='组合内标准化估计 SD')
    ax.legend(handles=[Line2D([0],[0],c=ORANGE,label=r'$\delta=0$'),Line2D([0],[0],c=BLUE,label=r'$\delta=0.1$')])
    ax.grid(axis='y',c='#E5E5E5',lw=.5);ax.set_axisbelow(True)
    save(fig,'supp_fig_offset_sd_v110','supplementary')

if __name__=='__main__':
    fig2();fig7();supp()
    (DATA/'figure_qa_v112.json').write_text(json.dumps(QA,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(QA,ensure_ascii=False))
