"""原存档样本的拟合展示及非边界峰核对；不运行估计器。"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from scipy.stats import gaussian_kde

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent.parent
ASSETS = STUDY/'reviewbyhtml/方法对比-v1.0/assets'
METHODS = ['MDM-0.1', 'WMLE', 'LSE', 'MMLE(KR)']
COLORS = ['#0072B2', '#D55E00', '#009E73', '#CC79A7']


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def cdf(x, beta, eta, gamma):
    return -np.expm1(-np.maximum((x-gamma)/eta, 0)**beta)


def main():
    sources, modes, cases = {}, [], []
    frames = {}
    for n in [50, 7]:
        p = STUDY/f'结果/W5,1000,500/估计结果/n{n}.csv'
        sources[p.relative_to(STUDY).as_posix()] = sha(p)
        frames[n] = pd.read_csv(p, float_precision='round_trip')
        for method in ['LSE', 'LRE(Park)']:
            d = frames[n]
            d = d[d[method+'_状态'].eq('success') & d[method+'_位置估计'].gt(1e-8)]
            vals = d[method+'_尺度估计'].to_numpy()
            grid = np.linspace(0, 2000, 1001)
            for factor in [.7, 1., 1.3]:
                density = gaussian_kde(vals, bw_method=lambda k:k.scotts_factor()*factor)(grid)
                peaks, _ = find_peaks(density, prominence=.04*density.max())
                modes.append(dict(n=n, method=method, count=len(vals), bandwidth=factor,
                                  modes=grid[peaks].tolist()))
    d = frames[7]
    obs = np.sort(d.filter(regex='^观测值').to_numpy(float), axis=1)
    ok = np.logical_and.reduce([d[m+'_状态'].eq('success').to_numpy() for m in METHODS])
    # 只按样本最小值的下/上四分位选例，不按哪种方法更准选择。
    indices = np.flatnonzero(ok)
    minimum = obs[indices, 0]
    chosen = [int(indices[np.argmin(abs(minimum-np.quantile(minimum,q)))]) for q in [.25,.75]]
    plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':12,
                         'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False})
    for label, idx in zip(['较近起点','较远起点'], chosen):
        row = d.iloc[idx]
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={'width_ratios':[1.5,1]})
        fig.subplots_adjust(left=.075,right=.985,bottom=.16,top=.83,wspace=.27)
        x = np.linspace(300,2200,700)
        axes[0].plot(x,cdf(x,5,1000,500),'--',color='#333333',lw=2,label='真实分布')
        axes[0].scatter(obs[idx],(np.arange(1,8)-.5)/7,s=28,c='#333333',label='样本点',zorder=5)
        axes[0].plot(obs[idx],np.full(7,-.025),'|',color='#333333',ms=9)
        estimates = []
        for j,(m,c) in enumerate(zip(METHODS,COLORS)):
            p = row[[m+'_'+k+'估计' for k in ['形状','尺度','位置']]].to_numpy(float)
            axes[0].plot(x,cdf(x,*p),color=c,lw=1.6,label=m.replace('MMLE(KR)','K–R'))
            axes[1].scatter(p/np.array([5,1000,500]),np.arange(3)+(j-1.5)*.12,c=c,s=34)
            estimates.append(dict(method=m,parameters=p.tolist()))
        axes[0].set(xlim=(300,2200),ylim=(-.06,1.02),xlabel='寿命 t',ylabel='累计概率')
        axes[1].axvline(1,color='#555555',ls='--',lw=1)
        axes[1].set(xlabel='估计值 / 真值',yticks=[0,1,2],yticklabels=['形状 β','尺度 η','位置 γ'],ylim=(2.45,-.45),xlim=(0,3.2))
        handles,labels=axes[0].get_legend_handles_labels()
        fig.legend(handles,labels,ncol=6,loc='upper center',frameon=False,fontsize=10)
        out=ASSETS/f'同样本拟合_n7_{label}.png'
        fig.savefig(out,dpi=200,facecolor='white');plt.close(fig)
        cases.append(dict(label=label,sample_id=int(row['样本编号']),observations=obs[idx].tolist(),estimates=estimates,image=out.name))
    for p,h in sources.items(): assert sha(STUDY/p)==h
    output=HERE.parent/'分析数据/同样本拟合与内部峰核对.json'
    output.write_text(json.dumps(dict(sources=sources,modes=modes,cases=cases,
        scope='β=5、n=50/7，LSE与Park LRE非零位置结果；三带宽KDE为描述性检查，不是多峰显著性检验。',
        case_selection='n=7四方法共同有效集合，按样本最小值25%与75%分位附近选例；不按方法误差选择。'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(cases=[(x['label'],x['sample_id']) for x in cases],modes=modes),ensure_ascii=False))


if __name__=='__main__':
    main()
