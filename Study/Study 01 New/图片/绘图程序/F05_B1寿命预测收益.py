"""Python figure: B1 predictive-score gain on the fatigue case, frozen models.

Quantitative plot, 110 x 76 mm. All four sample sizes and full pointwise
conditional intervals retained. Source is E11; no estimation or tuning here.
"""
from pathlib import Path
import hashlib
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
FIG=ROOT/'图片'
SOURCE=ROOT/'数据/E11_真实寿命重复小样本预实验/指标与跨案例探索'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    src=SOURCE/'real_comparison.csv'
    raw=pd.read_csv(src)
    d=raw[(raw.case=='fatigue101')&(raw.comparator=='MDM-0.1')&(raw.metric=='pinball_0.01')].sort_values('n')
    assert d.n.tolist()==[7,10,15,20] and (d['count']==2000).all()
    assert ((d.conditional_lo95<d.gain_percent)&(d.gain_percent<d.conditional_hi95)).all()
    assert (abs(d.gain_percent-100*(1-d.amdm/d.baseline))<1e-10).all()
    d.to_csv(FIG/'数据/F05_B1寿命预测收益.csv',index=False)
    common=pd.read_csv(SOURCE/'six_method_common_comparison.csv')
    common=common[(common.case=='fatigue101')&(common.metric=='pinball_0.01')]
    common.to_csv(FIG/'数据/T06_B1寿命预测比较.csv',index=False)
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
        'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,
        'svg.fonttype':'none','pdf.fonttype':42})
    fig,ax=plt.subplots(figsize=(110/25.4,76/25.4))
    fig.subplots_adjust(left=.18,right=.96,bottom=.2,top=.93)
    x=d.n.to_numpy();y=d.gain_percent.to_numpy()
    ax.plot(x,y,color='#436F91',lw=1.4,zorder=3)
    ax.errorbar(x,y,yerr=[y-d.conditional_lo95,d.conditional_hi95-y],fmt='o',
        color='#436F91',markersize=4,capsize=3,lw=1.1,zorder=4)
    for xi,yi,hi in zip(x,y,d.conditional_hi95):
        ax.text(xi,hi+.22,f'{yi:.2f}%',ha='center',va='bottom',fontsize=8)
    ax.axhline(0,color='#8C949B',lw=.8,ls='--')
    ax.set(xlim=(5.5,21.5),ylim=(-.25,9.3),xticks=x,yticks=[0,2,4,6,8],
        xlabel='样本量 n',ylabel='B1留出分位点损失降幅（%）')
    ax.grid(axis='y',color='#D6DBDF',alpha=.6,lw=.6);ax.set_axisbelow(True)
    for ext in ['png','svg','pdf']:
        fig.savefig(FIG/f'F05_B1寿命预测收益.{ext}',dpi=400,facecolor='white')
    plt.close(fig)
    manifest={'claim':'AMDM reduces heldout B1 pinball loss relative to fixed MDM on this fatigue case',
        'backend':'Python','size_mm':[110,76],'original_observations':101,'subsets_per_n':2000,
        'interval':'pointwise 95% paired bootstrap conditional on the observed pool and frozen models',
        'bootstrap_replicates':2000,'metric_selection':'exploratory; B1 selected after metric exploration',
        'full_intervals_retained':True,'population_calibration_claim':False,
        'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [src,SOURCE/'six_method_common_comparison.csv']},
        'script_sha256':sha(Path(__file__))}
    (FIG/'数据/F05_B1寿命预测收益.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(d[['n','gain_percent','conditional_lo95','conditional_hi95']].to_string(index=False))

if __name__=='__main__':main()
