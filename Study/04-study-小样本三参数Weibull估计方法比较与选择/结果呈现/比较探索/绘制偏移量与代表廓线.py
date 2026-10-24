"""Figures for population delta comparison and preselected nested examples."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from 验证MDM偏移量与廓线群体 import STUDY,OUT,HERE,NS,sha,dump,table
from 绘制嵌套样本拟合 import nested_samples
from 第三章机制候选图 import gradient
from methods.conditional_profiles import mle_profile

ASSETS=STUDY/'reviewbyhtml/方法对比-v1.0/assets'
plt.rcParams.update({'font.family':['Times New Roman','Microsoft YaHei'],'font.size':12,
    'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,
    'mathtext.fontset':'custom','mathtext.rm':'Times New Roman','mathtext.it':'Times New Roman:italic',
    'mathtext.bf':'Times New Roman:bold','mathtext.fallback':'stix'})
NC={50:'#0072B2',20:'#009E73',15:'#A67C00',10:'#CC79A7',7:'#D55E00'}
MC={'MDM-0.1':'#0072B2','LSE':'#009E73','LRE(Park)':'#A67C00','WMLE':'#D55E00',
    'MLE':'#8064A2','MMLE(KR)':'#CC79A7','MM':'#333333'}
LABEL={'MDM-0.1':'MDM(0.1)','LRE(Park)':'LRE','MMLE(KR)':'MMLE'}
SYMBOLS=[r'$\hat\beta$',r'$\hat\eta$',r'$\hat\gamma$']
PARS=['beta','eta','gamma'];TRUTH=[5.,1000.,500.]
OUTPUTS=[]


def save(fig,name):
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    for legend in fig.legends:
        box=legend.get_window_extent(renderer)
        assert box.x0>=0 and box.y0>=0 and box.x1<=fig.bbox.width and box.y1<=fig.bbox.height
    p=ASSETS/name;fig.savefig(p,dpi=220,facecolor='white');plt.close(fig)
    OUTPUTS.append(dict(path=p.relative_to(STUDY).as_posix(),sha256=sha(p)))


def bias_sd(include_mm=False):
    d=pd.read_csv(OUT/'七法指标.csv');d=d[d.subset.eq('common')]
    methods=list(MC) if include_mm else list(MC)[:-1]
    fig,axs=plt.subplots(2,3,figsize=(16,7),sharex=True)
    fig.subplots_adjust(left=.075,right=.985,bottom=.12,top=.87,hspace=.20,wspace=.27)
    for j,p in enumerate(PARS):
        for method in methods:
            v=d[d.method.eq(method)].set_index('n').loc[NS]
            for i,metric in enumerate(['bias','sd']):
                ax=axs[i,j];ax.plot(range(5),v[p+'_'+metric]/(5 if p=='beta' else 1000),
                    color=MC[method],marker='o',ms=3.7,lw=1.7,label=LABEL.get(method,method))
        axs[0,j].axhline(0,color='#888',lw=.8)
        axs[0,j].set_title([r'$\beta$',r'$\eta$',r'$\gamma$'][j])
        axs[1,j].set(xticks=range(5),xticklabels=NS,xlabel=r'$n$')
        axs[0,j].set_ylabel(r'$\mathrm{Bias}/s_0$')
        axs[1,j].set_ylabel(r'$\mathrm{SD}/s_0$');axs[1,j].set_ylim(bottom=0)
    fig.legend(*axs[0,0].get_legend_handles_labels(),loc='upper center',ncol=len(methods),frameon=False)
    save(fig,'31M_七法偏差与标准差.png' if include_mm else '31M_六法偏差与标准差.png')


def delta_distributions():
    d=pd.read_csv(OUT/'正式样本/results.csv',float_precision='round_trip')
    fig,axs=plt.subplots(2,3,figsize=(16,7),sharex='col',sharey='col')
    fig.subplots_adjust(left=.065,right=.985,bottom=.13,top=.86,hspace=.22,wspace=.25)
    for j,p in enumerate(PARS):
        maximum=float(d[p+'_hat'].max())
        upper=15.1 if p=='beta' else np.ceil(maximum/100)*100+30
        edges=np.linspace(0,upper,41)
        ymax=0.
        for i,n in enumerate([50,7]):
            ax=axs[i,j]
            for variant,color in [('MDM-0','#6B7780'),('MDM-0.1','#0072B2')]:
                v=d[d.n.eq(n)&d.method_variant.eq(variant)];assert v.status.eq('success').all()
                values=v[p+'_hat'].to_numpy(float)
                counts,_=np.histogram(values,bins=edges);assert counts.sum()==1200
                ymax=max(ymax,float(counts.max()/1200))
                ax.stairs(counts/1200,edges,color=color,lw=1.9,fill=True,alpha=.15)
                ax.stairs(counts/1200,edges,color=color,lw=1.5,label=variant)
            ax.axvline(TRUTH[j],color='#222',ls='--',lw=1.2)
            ax.text(.96,.88,rf'$n={n}$',transform=ax.transAxes,ha='right')
            ax.set(xlim=(0,upper),ylabel='比例')
            if i==1:ax.set_xlabel(SYMBOLS[j])
        for ax in axs[:,j]:ax.set_ylim(0,ymax*1.08)
    handles=[Line2D([],[],color='#6B7780',lw=2,label=r'$\mathrm{MDM}\ (\delta=0)$'),
             Line2D([],[],color='#0072B2',lw=2,label=r'$\mathrm{MDM}\ (\delta=0.1)$'),
             Line2D([],[],color='#222',ls='--',label='真实参数')]
    fig.legend(handles=handles,loc='upper center',ncol=3,frameon=False)
    save(fig,'31N_MDM两偏移量估计分布.png')


def delta_mse():
    d=pd.read_csv(OUT/'偏移量指标.csv');d=d[d.subset.eq('common')]
    fig,axs=plt.subplots(1,3,figsize=(16,7))
    fig.subplots_adjust(left=.07,right=.985,bottom=.15,top=.83,wspace=.25)
    for j,p in enumerate(PARS):
        ax=axs[j];scale=(5 if p=='beta' else 1000)**2
        for v,shift,color,light in [('MDM-0',-.18,'#6B7780','#d8dee3'),('MDM-0.1',.18,'#0072B2','#c8e1f0')]:
            rows=d[d.method.eq(v)].set_index('n').loc[NS]
            bias2=rows[p+'_bias']**2/scale;variance=(rows.valid-1)/rows.valid*rows[p+'_sd']**2/scale
            np.testing.assert_allclose(bias2+variance,rows[p+'_rmse']**2/scale)
            ax.bar(np.arange(5)+shift,bias2,width=.32,color=light,edgecolor=color,lw=1)
            ax.bar(np.arange(5)+shift,variance,bottom=bias2,width=.32,color=color,edgecolor=color,lw=1)
        ax.set(xticks=range(5),xticklabels=NS,xlabel=r'$n$',ylabel=r'$\mathrm{MSE}/s_0^2$',
               title=[r'$\beta$',r'$\eta$',r'$\gamma$'][j],ylim=(0,None))
    handles=[Line2D([],[],color='#d8dee3',marker='s',ls='',ms=10,label=r'$\delta=0:\ \mathrm{Bias}^2$'),
             Line2D([],[],color='#6B7780',marker='s',ls='',ms=10,label=r'$\delta=0:\ \mathrm{Var}$'),
             Line2D([],[],color='#c8e1f0',marker='s',ls='',ms=10,label=r'$\delta=0.1:\ \mathrm{Bias}^2$'),
             Line2D([],[],color='#0072B2',marker='s',ls='',ms=10,label=r'$\delta=0.1:\ \mathrm{Var}$')]
    fig.legend(handles=handles,loc='upper center',ncol=4,frameon=False)
    save(fig,'31O_MDM两偏移量误差分解.png')


def population_geometry(summary):
    g=pd.read_csv(OUT/'廓线几何.csv');nested=pd.read_csv(OUT/'嵌套四法/results.csv')
    fig,axs=plt.subplots(1,2,figsize=(16,7))
    fig.subplots_adjust(left=.075,right=.985,bottom=.17,top=.90,wspace=.27)
    groups=[('MLE','kappa','MLE（总）'),('MLE','kappa_per_observation','MLE（每观测）'),
            ('MDM-0','kappa','MDM(0)'),('MDM-0.1','kappa','MDM(0.1)')]
    for i,(m,k,label) in enumerate(groups):
        d=g[g.method.eq(m)&g.category.eq('reliable')].pivot(index='source_id',columns='n',values=k)
        d=d[[50,7]].dropna();ratio=np.sort((d[7]/d[50]).to_numpy())
        offset=np.random.default_rng(20261024+i).permutation(np.linspace(-.16,.16,len(ratio)))
        axs[0].scatter(i+offset,ratio,s=18,color=['#8064A2','#8064A2','#6B7780','#0072B2'][i],alpha=.45)
        item=next(r for r in summary['ratios'] if r['method']==m and r['quantity']==k)
        lo,hi=item['ratio_median_ci95'];med=item['ratio_median']
        axs[0].errorbar(i,med,yerr=[[med-lo],[hi-med]],fmt='o',color='#222',lw=2,capsize=5,ms=6)
    axs[0].axhline(1,color='#666',ls='--',lw=1.2)
    axs[0].set(yscale='log',xticks=range(4),xticklabels=[q[2] for q in groups],
               ylabel=r'$\kappa_7/\kappa_{50}$',title='(a)')
    for v,c in [('MLE','#8064A2'),('MDM-0','#6B7780'),('MDM-0.1','#0072B2')]:
        vals=[]
        for n in NS:
            d=nested[nested.n.eq(n)&nested.method_variant.eq(v)]
            vals.append(float((d.gamma_hat.eq(0)&d.status.eq('success')).sum()/120))
        axs[1].plot(range(5),vals,marker='o',color=c,lw=2,label=v)
    failed=[float(nested[nested.n.eq(n)&nested.method_variant.eq('MLE')].status.ne('success').mean()) for n in NS]
    axs[1].plot(range(5),failed,color='#8064A2',ls='--',marker='x',label='MLE失败')
    axs[1].set(xticks=range(5),xticklabels=NS,xlabel=r'$n$',ylabel='比例',ylim=(0,.65),title='(b)')
    axs[1].legend(frameon=False,fontsize=11)
    save(fig,'31P_群体曲率与边界比例.png')


def criterion_example(sid,suffix):
    paths=nested_samples(table(50).reset_index(),[sid]);d=pd.read_csv(OUT/'嵌套四法/results.csv',float_precision='round_trip')
    d=d[d.repeat_id.eq(sid//10)]
    fig,axs=plt.subplots(1,4,figsize=(16,7))
    fig.subplots_adjust(left=.055,right=.985,bottom=.17,top=.83,wspace=.43)
    gx=max(paths[sid,n][0] for n in NS)
    for row_index,n in enumerate(NS):
        x=paths[sid,n];v=d[d.n.eq(n)].set_index('method_variant');c=NC[n]
        xmax=float(x[0]);grid=np.unique(np.r_[np.linspace(0,xmax*.97,130),
            xmax-np.geomspace(xmax*.03,xmax*.001,35),
            v.loc[['MLE','MDM-0','MDM-0.1'],'gamma_hat'].dropna().to_numpy()])
        grid=grid[(grid>=0)&(grid<xmax)]
        profile=np.array([mle_profile(x,g)['ll'] for g in grid])
        r=v.loc['MLE']
        reference=mle_profile(x,float(r.gamma_hat))['ll'] if r.status=='success' else float(np.max(profile))
        axs[0].plot(grid,(reference-profile)/n,color=c,lw=1.7)
        if r.status=='success':axs[0].scatter(r.gamma_hat,0,s=27,color=c,zorder=5)
        axs[1].scatter(x[1:],np.full(n-1,row_index),marker='|',s=90,color='#b7c0c7',lw=1.1)
        axs[1].scatter(x[0],row_index,s=55,color=c,zorder=5)
        assert float(v.loc['MMLE','gamma_hat'])==float(x[0])
        grads=np.array([gradient(x,g) for g in grid])
        for ax,variant,marker in [(axs[2],'MDM-0','o'),(axs[3],'MDM-0.1','s')]:
            ax.plot(grid,grads,color=c,lw=1.7)
            r=v.loc[variant]
            ax.scatter(r.gamma_hat,gradient(x,float(r.gamma_hat)),marker=marker,s=33,
                       facecolors='white' if marker=='o' else c,edgecolors=c,zorder=5,clip_on=False)
    for ax in [axs[0],axs[2],axs[3]]:ax.set_xlim(0,gx);ax.set_xlabel(r'$\gamma$')
    axs[0].set_ylabel(r'$[\ell_p(\hat\gamma)-\ell_p(\gamma)]/n$');axs[0].set_title('(a) MLE')
    axs[1].set(xlabel=r'$x$',ylabel=r'$n$',title='(b) MMLE',yticks=range(5),yticklabels=NS,
                ylim=(4.6,-.6),xlim=(min(paths[sid,50])*.9,max(paths[sid,50])*1.03))
    axs[2].set(ylabel=r'$g_n(\gamma)$',title='(c) MDM(0)',ylim=(-.12,.25))
    axs[3].set(ylabel=r'$g_n(\gamma)$',title='(d) MDM(0.1)',ylim=(-.12,.25))
    axs[2].axhline(0,color='#666',ls='--',lw=1)
    axs[3].axhline(.1,color='#666',ls='--',lw=1)
    handles=[Line2D([],[],color=NC[n],lw=2,label=rf'$n={n}$') for n in NS]
    handles += [Line2D([],[],color='#555',marker='o',mfc='white',ls='',label=r'$\delta=0$'),
                Line2D([],[],color='#555',marker='s',ls='',label=r'$\delta=0.1$')]
    fig.legend(handles=handles,ncol=7,loc='upper center',frameon=False,fontsize=11)
    save(fig,f'31Q_四方法判据_{suffix}_样本{sid}.png')


def parameter_response(sid):
    d=pd.read_csv(OUT/'嵌套四法/results.csv');d=d[d.repeat_id.eq(sid//10)]
    fig,axs=plt.subplots(1,3,figsize=(16,7));fig.subplots_adjust(left=.07,right=.985,bottom=.16,top=.86,wspace=.25)
    for method,c in [('MLE','#8064A2'),('MMLE','#CC79A7'),('MDM-0','#6B7780'),('MDM-0.1','#0072B2')]:
        v=d[d.method_variant.eq(method)].set_index('n').loc[NS]
        for j,p in enumerate(PARS):
            values=(v[p+'_hat']-TRUTH[j])/(5 if p=='beta' else 1000)
            values=values.where(v.status.eq('success'))
            axs[j].plot(range(5),values,marker='o',color=c,lw=2,label=method)
    for j,ax in enumerate(axs):ax.axhline(0,color='#777',ls='--',lw=1);ax.set(xticks=range(5),xticklabels=NS,xlabel=r'$n$',ylabel='标准化误差',title=SYMBOLS[j])
    fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',ncol=4,frameon=False)
    save(fig,f'31R_四方法参数响应_样本{sid}.png')


def main():
    summary=json.loads((OUT/'群体结论.json').read_text(encoding='utf-8'))
    bias_sd();bias_sd(True);delta_distributions();delta_mse();population_geometry(summary)
    examples=summary['examples'];main_id=examples['main_source_id']
    criterion_example(main_id,'共同中心');parameter_response(main_id)
    for key,label in [('curvature_typical_source_id','曲率中心'),('curvature_opposite_source_id','反向变化')]:
        sid=examples.get(key)
        if sid is not None and sid!=main_id:criterion_example(sid,label)
    dump(OUT/'图像核对.json',dict(figures=OUTPUTS,main_source_id=main_id,
        sources=summary['sources'],selection=summary['examples']))
    print(json.dumps(dict(figures=OUTPUTS),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
