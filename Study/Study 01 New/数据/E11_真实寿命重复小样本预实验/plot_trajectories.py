"""Explore whether six estimators approach a common parameter region.

Quantitative grid, Python, 183 x 86 mm overview and method-specific detail.
Medians and IQR describe repeated real-data subsets, not truth uncertainty.
Do not impose an MLE reference or a consensus value on these figures.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from run_trajectories import OUT,METHODS,MODEL_PATHS

COLORS=dict(zip(METHODS,['#315D83','#659B89','#B88755','#777780','#AA7794','#7C91B5']))
MARKERS=dict(zip(METHODS,['o','s','^','D','v','P']))
LABELS={'AMDM':'AMDM','MDM-0.1':r'MDM ($\delta=0.1$)','WMLE':'WMLE','MLE':'MLE','LSE':'LSE','LRE':'LRE'}
PARAMS=['beta','eta','gamma']
AXLABELS=[r'形状参数 $\beta$',r'尺度参数 $\eta$（千次循环）',r'位置参数 $\gamma$（千次循环）']

def style():
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
        'mathtext.fontset':'stix','font.size':7,'axes.labelsize':8,'xtick.labelsize':7,'ytick.labelsize':7,
        'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,
        'pdf.fonttype':42,'svg.fonttype':'none','legend.frameon':False,'axes.unicode_minus':False})

def save(fig,name):
    for ext in ['png','svg','pdf']:fig.savefig(OUT/f'{name}.{ext}',dpi=400,facecolor='white')
    plt.close(fig)

def draw(ax,data,method,wide=False):
    c=COLORS[method]
    d=data[data.method==method].sort_values('n')
    band=d[d.n<101]
    fill=band[band.n<=50] if method=='AMDM' else band
    if wide:
        ax.fill_between(fill.n,fill.q025,fill.q975,color=c,alpha=.09,lw=0)
    ax.fill_between(fill.n,fill.q250,fill.q750,color=c,alpha=.22 if wide else .075,lw=0)
    line=d[d.n<=50] if method=='AMDM' else (d[d.n<=100] if method=='WMLE' else d)
    ax.plot(line.n,line['median'],color=c,lw=1.65 if method=='AMDM' else 1.0,
        marker=MARKERS[method],ms=3.7 if method=='AMDM' else 2.7,
        markeredgecolor='white',markeredgewidth=.4,zorder=5 if method=='AMDM' else 3)
    if method=='AMDM':
        endpoints=d[d.n.isin([50,100])]
        ax.plot(endpoints.n,endpoints['median'],color=c,lw=1.4,ls='--',zorder=5)
        end=d[d.n==100].iloc[0]
        ax.errorbar(100,end['median'],yerr=[[end['median']-end.q250],[end.q750-end['median']]],color=c,fmt='o',ms=3.7,lw=1.3,capsize=2,zorder=6)
        if wide:ax.vlines(100,end.q025,end.q975,color=c,alpha=.35,lw=1)
    full=d[d.n==101]
    if len(full):ax.scatter(full.n,full['median'],marker='*',s=45,color=c,edgecolor='white',lw=.4,zorder=7)
    ax.set_xlim(3,106)
    ax.set_xticks([7,20,50,80,101])
    ax.grid(axis='y',color='#E6E8EB',lw=.55,zorder=0)

def main():
    style();df=pd.read_csv(OUT/'trajectory_summary.csv')
    fig,axes=plt.subplots(1,3,figsize=(183/25.4,86/25.4))
    fig.subplots_adjust(left=.074,right=.985,bottom=.20,top=.82,wspace=.37)
    for j,(p,ax) in enumerate(zip(PARAMS,axes)):
        sub=df[df.parameter==p]
        for m in METHODS:draw(ax,sub,m)
        ax.set_xlabel('样本量 n');ax.set_ylabel(AXLABELS[j])
        ax.text(-.19,1.06,chr(97+j),transform=ax.transAxes,fontweight='bold',fontsize=10)
    handles=[Line2D([0],[0],color=COLORS[m],marker=MARKERS[m],lw=1.4,ms=4,label=LABELS[m]) for m in METHODS]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.52,.985),ncol=6,columnspacing=1.15,handlelength=1.4,fontsize=7)
    save(fig,'P11_三参数估计轨迹')

    fig,axes=plt.subplots(6,3,figsize=(183/25.4,270/25.4),sharex=True)
    fig.subplots_adjust(left=.10,right=.985,bottom=.055,top=.957,wspace=.30,hspace=.37)
    for i,m in enumerate(METHODS):
        for j,p in enumerate(PARAMS):
            ax=axes[i,j];sub=df[df.parameter==p]
            draw(ax,sub,m,wide=True)
            if i==0:ax.set_title(AXLABELS[j],fontsize=8,pad=9)
            if j==0:ax.text(-.31,.5,LABELS[m],rotation=90,ha='center',va='center',transform=ax.transAxes,color=COLORS[m],fontsize=8,fontweight='bold')
            if i==5:ax.set_xlabel('样本量 n')
    save(fig,'P11_逐方法抽样波动')
    # Common-valid summaries are a check on method-specific failure conditioning.
    own=df[['n','method','parameter','median']]
    common=pd.read_csv(OUT/'common_valid_summary.csv')
    check=own.merge(common,on=['n','method','parameter'],suffixes=('_own','_common'))
    check['median_difference']=check.median_common-check.median_own
    check.to_csv(OUT/'common_valid_sensitivity.csv',index=False)
    writeup=dict(backend='Python/matplotlib',purpose='Inspect approach to a shared region; no consensus assumed',overview_center='median among each method valid fits',overview_band='25th-75th percentiles of successful subset estimates',detail_band='inner25th-75th; outer2.5th-97.5th percentiles; individual y-scales per panel',full101='Stars: one fit of all observations. No band or confidence interval inferred from repeated identical full data.',AMDM='Frozen models at n7,10,15,20,30,50,100 only; dashed50-100 guides the eye over missing n80, no fitted model at n80 or n101. n100 errorbar is IQR.',WMLE='n101 star is disconnected because existing solver switches J2/J3 to asymptotic weights above n100; closeness to MLE is not independent convergence evidence.',sampling='500 per n<=80; n100 exhausts all101 leave-one-out subsets. Different n are not nested sample paths.',source='trajectory_summary.csv; fit_coverage.csv; per_subsample.csv.gz',formats=['PNG400dpi','SVG editable text','PDF embedded fonts'])
    (OUT/'figure_manifest.json').write_text(json.dumps(writeup,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

if __name__=='__main__':main()
