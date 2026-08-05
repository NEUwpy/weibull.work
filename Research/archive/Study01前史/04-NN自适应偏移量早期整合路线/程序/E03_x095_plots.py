"""
E03 工程视角图表：双视角δ对比 + mismatch + 阶梯
"""
import matplotlib as mpl, matplotlib.pyplot as plt, numpy as np, pandas as pd
import matplotlib.colors as mcolors
from pathlib import Path

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"
IMG_DIR = BASE / "图像"

mpl.rcParams.update({
    "font.family":"sans-serif","font.sans-serif":["Arial","DejaVu Sans"],
    "svg.fonttype":"none","pdf.fonttype":42,"font.size":8,
    "axes.spines.right":False,"axes.spines.top":False,
    "axes.linewidth":0.8,"legend.frameon":False,
})
def save(fig, name):
    for e,d in [('.png',300),('.pdf',None),('.svg',None)]:
        fig.savefig(IMG_DIR/f"{name}{e}",bbox_inches='tight',dpi=d)
    plt.close(fig)

BETAS=[1.5,2.0,2.5,4.0,5.0]; NS=[7,10,20]; GERS=[0.1,0.5,1.0]

# Load both perspectives
j_l4={}; x_l4={}
for gr in GERS:
    jm=pd.read_csv(DATA_DIR/f'E03_L4_heatmap_gamma{gr}_v2.csv',index_col=0)
    xm=pd.read_csv(DATA_DIR/f'E03_L4_heatmap_gamma{gr}_x095.csv',index_col=0)
    for ns in jm.index:
        for bs in jm.columns:
            j_l4[(float(bs),int(ns),gr)]=float(jm.loc[ns,bs])
            x_l4[(float(bs),int(ns),gr)]=float(xm.loc[ns,bs])

# ══ Fig 1: Dual-perspective δ* comparison (three panels: δ*_J, δ*_x95, Δ) ══
fig,axes=plt.subplots(3,3,figsize=(9,7))
for gi,gr in enumerate(GERS):
    mat_j=np.full((3,5),np.nan); mat_x=np.full((3,5),np.nan); mat_d=np.full((3,5),np.nan)
    for ri,n in enumerate(NS):
        for ci,b in enumerate(BETAS):
            mat_j[ri,ci]=j_l4[(b,n,gr)]
            mat_x[ri,ci]=x_l4[(b,n,gr)]
            mat_d[ri,ci]=mat_x[ri,ci]-mat_j[ri,ci]
    for row_idx, (mat, title) in enumerate([(mat_j,'δ*_J'),(mat_x,'δ*_x95'),(mat_d,'Δ = x95-J')]):
        ax=axes[row_idx,gi]; vmax=0.5 if row_idx<2 else 0.25
        cm='RdYlBu_r' if row_idx<2 else 'RdBu_r'
        if row_idx==2:
            vmin,vmax=-0.5,0.5
            norm=mcolors.TwoSlopeNorm(vmin=vmin,vcenter=0,vmax=vmax)
            im=ax.imshow(mat,aspect='auto',cmap=cm,norm=norm)
        else:
            im=ax.imshow(mat,aspect='auto',cmap=cm,vmin=0,vmax=vmax)
        ax.set_xticks(range(5));ax.set_xticklabels(BETAS)
        ax.set_yticks(range(3));ax.set_yticklabels(NS)
        if gi==0:
            ax.set_ylabel('n')
        if row_idx==2:
            ax.set_xlabel('β')
        ax.set_title(f'{title}  γ/η={gr}',fontsize=7)
        for ri in range(3):
            for ci in range(5):
                if np.isfinite(mat[ri,ci]):
                    ax.text(ci,ri,f'{mat[ri,ci]:.2f}',ha='center',va='center',fontsize=6,color='black')
fig.suptitle('Dual-Perspective δ* Comparison (L4)',fontsize=9,y=1.01)
save(fig,'E03_dual_delta_heatmap')

# ══ Fig 2: Mismatch penalty by β ══
mm=pd.read_csv(DATA_DIR/'E03_mismatch.csv')
pen=mm.pivot_table(index=['beta','n','gamma_eta'],columns='delta_type',values='RMSE_x95').reset_index()
pen['penalty']=(pen['J_opt']-pen['x95_opt'])/pen['x95_opt']*100
fig,ax=plt.subplots(figsize=(5,3))
bp=pen.groupby('beta')['penalty'].agg(['mean','min','max'])
ax.bar(range(5),bp['mean'],yerr=[bp['mean']-bp['min'],bp['max']-bp['mean']],capsize=3,color='#E8A87C')
ax.set_xticks(range(5));ax.set_xticklabels(BETAS)
ax.set_xlabel('β');ax.set_ylabel('Mismatch Penalty (%)')
ax.set_title('Mismatch: x95 penalty when using J-optimal δ')
for i,(_,r) in enumerate(bp.iterrows()):
    ax.text(i,r['mean']+0.3,f'{r["mean"]:.1f}%',ha='center',fontsize=7)
save(fig,'E03_mismatch_penalty')

# ══ Fig 3: RMSE_x95 ladder ══
ld=pd.read_csv(DATA_DIR/'E03_ladder_x095.csv')
fig,ax=plt.subplots(figsize=(5,2.8))
order=['Default','L0','L1','L2','L3','L4','L5']
vals=[ld[ld['Level']==o]['RMSE_x95'].values[0] for o in order]
def_j=vals[0]
colors=['#888888']+['#95B8D1']*5+['#2ca02c']
bars=ax.barh(range(len(order)),[v/def_j-1 for v in vals],color=colors,height=0.6)
ax.axvline(0,color='#333',linewidth=0.8)
ax.set_yticks(range(len(order)));ax.set_yticklabels(order)
ax.set_xlabel('RMSE_x95 / Default - 1')
for bar,v in zip(bars,vals):
    ax.text(bar.get_width()+(0.002 if bar.get_width()>=0 else -0.03),bar.get_y()+0.3,
            f'{v:.4f}',va='center',fontsize=7)
ax.set_title('RMSE_x95 Ladder (absolute, eta=1)')
save(fig,'E03_x095_ladder')

print("Phase 2 plots done.")
