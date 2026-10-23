"""Decompose archived common-sample MSE and its growth; no estimator calls."""
from itertools import combinations
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
from 验证MDM偏移量与廓线群体 import STUDY,OUT,HERE,NS,sha,dump
from studies.common.metrics import summarize_standard_errors
from 绘制偏移量与代表廓线 import ASSETS,MC,LABEL,PARS

BETAS=[1.5,2.,2.5,3.,3.5,4.,4.5,5.]
METHODS=list(MC);DISPLAY=METHODS[:-1]
PAIRS=list(combinations(range(6),2))


def statistics():
    rows=[];sources={}
    for beta in BETAS:
        for n in NS:
            p=STUDY/f'结果/W{beta:g},1000,500/估计结果/n{n}.csv'
            sources[p.relative_to(STUDY).as_posix()]=sha(p)
            d=pd.read_csv(p,float_precision='round_trip')
            assert len(d)==1200
            common=d[[m+'_状态' for m in METHODS]].eq('success').all(axis=1)
            for m in METHODS:
                for par,chinese,truth,scale in [('beta','形状',beta,beta),('eta','尺度',1000.,1000.),('gamma','位置',500.,1000.)]:
                    values=d.loc[common,m+'_'+chinese+'估计'].to_numpy(float)
                    st=summarize_standard_errors(values-truth);R=len(values)
                    bias2=st['bias']**2/scale**2
                    variance=(R-1)/R*st['sd']**2/scale**2
                    mse=st['rmse']**2/scale**2
                    np.testing.assert_allclose(bias2+variance,mse,rtol=1e-11,atol=1e-12)
                    rows.append(dict(beta=beta,n=n,method=m,parameter=par,valid=R,
                        bias=st['bias'],sd=st['sd'],rmse=st['rmse'],scale=scale,
                        bias_squared_normalized=bias2,variance_normalized=variance,mse_normalized=mse))
    return pd.DataFrame(rows),sources


def draw(data,beta,include_mm=False):
    methods=METHODS if include_mm else DISPLAY
    d=data[data.beta.eq(beta)]
    fig,axs=plt.subplots(2,3,figsize=(16,9.2))
    fig.subplots_adjust(left=.075,right=.985,bottom=.085,top=.87,hspace=.80,wspace=.28)
    width=.80/len(methods)
    pc=['#0072B2','#D55E00','#009E73','#CC79A7','#A97500']
    for j,par in enumerate(PARS):
        ax=axs[0,j];v=d[d.parameter.eq(par)]
        for k,m in enumerate(methods):
            q=v[v.method.eq(m)].set_index('n').loc[NS]
            x=np.arange(5)+(k-(len(methods)-1)/2)*width
            color=MC[m];light=tuple(.28*z+.72 for z in to_rgb(color))
            ax.bar(x,q.bias_squared_normalized,width=width*.92,color=light,
                edgecolor=color,linewidth=.7,hatch='///')
            ax.bar(x,q.variance_normalized,bottom=q.bias_squared_normalized,
                width=width*.92,color=color,edgecolor=color,linewidth=.6)
        ax.set(xticks=range(5),xticklabels=NS,xlabel=r'$n$',ylim=(0,None),
            title=[r'$\beta$',r'$\eta$',r'$\gamma$'][j],ylabel=r'$\mathrm{RMSE}^2/s_0^2$')
        ax.grid(axis='y',color='#e1e6e9',lw=.6,zorder=0);ax.set_axisbelow(True)
        for k,(a,b) in enumerate(PAIRS):
            qa=v[v.method.eq(DISPLAY[a])].set_index('n').loc[NS]
            qb=v[v.method.eq(DISPLAY[b])].set_index('n').loc[NS]
            gap=np.abs(qa.rmse.to_numpy()-qb.rmse.to_numpy())/qa.scale.to_numpy()
            axs[1,j].plot(range(5),gap,color=pc[k%5],ls=['-','--',':'][k//5],
                marker=['o','s','D'][k//5],lw=1.3,ms=3,
                label=LABEL.get(DISPLAY[a],DISPLAY[a])+' / '+LABEL.get(DISPLAY[b],DISPLAY[b]))
        axs[1,j].set(xticks=range(5),xticklabels=NS,xlabel=r'$n$',ylim=(0,None),
            ylabel=r'$|\mathrm{RMSE}_i-\mathrm{RMSE}_j|/s_0$')
        axs[1,j].grid(axis='y',color='#e1e6e9',lw=.6)
    handles=[Patch(facecolor=MC[m],label=LABEL.get(m,m)) for m in methods]
    handles.extend([Patch(facecolor='#eee',edgecolor='#555',hatch='///',label=r'$\mathrm{Bias}^2$'),
        Patch(facecolor='#666',label=r'$\mathrm{Var}$')])
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.53,.99),ncol=len(handles),frameon=False,fontsize=10.5)
    fig.legend(*axs[1,0].get_legend_handles_labels(),loc='upper center',
        bbox_to_anchor=(.53,.52),ncol=5,frameon=False,fontsize=9.5)
    path=ASSETS/f'误差组成与方法差距_β{beta:g}{"_含MM" if include_mm else ""}.png'
    fig.savefig(path,dpi=240,facecolor='white');plt.close(fig)
    return dict(beta=beta,include_mm=include_mm,path=path.relative_to(STUDY).as_posix(),sha256=sha(path))


def main():
    data,sources=statistics()
    OUT.mkdir(parents=True,exist_ok=True)
    data.to_csv(OUT/'七法全条件误差组成.csv',index=False,encoding='utf-8')
    growth=[]
    for (beta,method,parameter),d in data.groupby(['beta','method','parameter'],sort=False):
        v=d.set_index('n');dB=float(v.loc[7,'bias_squared_normalized']-v.loc[50,'bias_squared_normalized'])
        dV=float(v.loc[7,'variance_normalized']-v.loc[50,'variance_normalized'])
        dM=float(v.loc[7,'mse_normalized']-v.loc[50,'mse_normalized'])
        np.testing.assert_allclose(dM,dB+dV,rtol=1e-11,atol=1e-12)
        growth.append(dict(beta=float(beta),method=method,parameter=parameter,
            delta_bias_squared=dB,delta_variance=dV,delta_mse=dM,
            rmse50=float(v.loc[50,'rmse']),rmse7=float(v.loc[7,'rmse']),
            valid50=int(v.loc[50,'valid']),valid7=int(v.loc[7,'valid'])))
    figures=[draw(data,b) for b in BETAS]+[draw(data,5.,True)]
    record=dict(subset='Seven-method common valid set within each beta/n; sets differ across n.',
        source_sha256=sources,estimator_calls=0,new_samples=0,
        identity='MSE = Bias^2 + (R-1)/R * SD_ddof1^2; growth uses n7 minus n50.',
        stack='Each n has method-colored bars; hatched pale base Bias^2, solid top empirical variance.',
        units='beta / true_beta; eta and gamma /1000; all squared for MSE.',
        data=data.to_dict(orient='records'),growth=growth,figures=figures)
    dump(HERE/'3.1误差增长分解.json',record)
    text='# 3.1补充：误差平方及其增长的组成\n\n'
    text+='对应[报告下v2.1](../../报告下（方法对比）-v2.1.md)。数据读取正式40条件七法原结果，经共享指标函数汇总。每个条件采用七法共同有效样本，各n集合不相同；这不是同一固定队列的纵向方差变化。未调用估计器或新抽样。\n\n'
    text+=r'每根柱高为标准化$\mathrm{RMSE}^2$；浅色斜线部分为$\mathrm{Bias}^2$，实色为经验方差$V_R=(R-1)\mathrm{SD}^2/R$，SD采用ddof=1。增长分解为$\Delta\mathrm{MSE}=\Delta\mathrm{Bias}^2+\Delta V_R$，Δ为n=7减n=50；负项抵消增长，不截成零。'+ '\n\n'
    text+='## β=5的三参数增长分解\n\n| 方法 | 参数 | ΔMSE | ΔBias² | Δ方差 |\n|---|---|---:|---:|---:|\n'
    for q in growth:
        if q['beta']!=5:continue
        text+='| '+LABEL.get(q['method'],q['method'])+' | '+dict(beta='β',eta='η',gamma='γ')[q['parameter']]+' | '+' | '.join(f'{q[k]:+.5f}' for k in ['delta_mse','delta_bias_squared','delta_variance'])+' |\n'
    text+='\n所有值均为标准化误差平方单位，贡献不是三个可相加的RMSE值。原单位Bias、SD、RMSE及八档β的完整增长数值保存在[核对记录](3.1误差增长分解.json)。\n'
    for q in figures:
        text+=f"\n## β={q['beta']:g}{'：含MM完整范围' if q['include_mm'] else ''}\n\n![误差组成与方法差距](../../{q['path']})\n"
    (HERE/'3.1误差增长分解.md').write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps(dict(status='complete',conditions=40,metrics=len(data),identities_checked=len(data),figures=figures),ensure_ascii=False))


if __name__=='__main__':main()
