"""Research00 linear plots of saved estimates and untrimmed summary statistics."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter,NullLocator
from scipy.stats import gaussian_kde
HERE=Path(__file__).resolve().parent;SOURCE=HERE.parent/'结果';OUT=SOURCE;AUDIT=HERE
METHODS=['MLE','MMLE','WMLE'];NS=[7,10,15,20,50];COLORS=['#5F6570','#345D7E','#B27448']
PARAMS=['beta','eta','gamma'];LABELS=['β','η','γ'];TRUTH=json.loads((HERE/'config.json').read_text(encoding='utf-8'))['truth']
def setting_title(suffix=''):
    try:
        _c=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
        _t=_c.get('truth',TRUTH);_b=_c.get('blocks');_r=_c.get('repeats')
        _extra='，每 n %d×%d=%d 组'%(_b,_r,_b*_r) if _b and _r else ''
    except Exception:
        _t=TRUTH;_extra=''
    _f=lambda v:('%g'%v)
    _h='三参数 Weibull 抽样估计 ｜ 真值 β=%s、η=%s、γ=%s%s'%(_f(_t[0]),_f(_t[1]),_f(_t[2]),_extra)
    return _h+(' ｜ '+suffix if suffix else '')
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','Arial','DejaVu Sans'],
 'font.size':8,'axes.linewidth':.7,'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False})
def save(fig,name):
    fig.savefig(OUT/name,dpi=450,facecolor='white');plt.close(fig)
def common(ax):
    ax.set_xscale('linear');ax.set_yscale('linear');ax.set_xlim(5,52);ax.set_xticks(NS)
    ax.set_xlabel('n');ax.tick_params(direction='in');ax.xaxis.set_minor_locator(NullLocator())
def main():
    global OUT,AUDIT
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    OUT=(args.output or SOURCE).resolve();OUT.mkdir(parents=True,exist_ok=True);AUDIT=OUT/'.运行记录';AUDIT.mkdir(exist_ok=True)
    raw=SOURCE/'估计明细.csv';data=pd.read_csv(raw,float_precision='round_trip').rename(columns={'方法':'method_variant','β估计':'beta_hat','η估计':'eta_hat','γ估计':'gamma_hat'});data['status']=data['状态'].map({'成功':'success','失败':'failure'})
    stats=pd.read_csv(SOURCE/'三方法汇总.csv',float_precision='round_trip');records=[];points=[]
    fig,axes=plt.subplots(3,5,figsize=(12.4,7.0),sharey=True)
    for row,(p,label,t) in enumerate(zip(PARAMS,LABELS,TRUTH)):
        limits=[0,10] if p=='beta' else [0,2000];ticks=[0,2,4,6,8,10] if p=='beta' else [0,500,1000,1500,2000]
        for col,n in enumerate(NS):
            ax=axes[row,col];ax.set_xlim(limits);ax.set_ylim(2.5,-.5);ax.set_xticks(ticks);ax.set_xscale('linear')
            ax.xaxis.set_minor_locator(NullLocator());ax.axvline(t,color='black',ls='--',lw=.7,zorder=1)
            for pos,m in enumerate(METHODS):
                g=data[(data.method_variant==m)&(data.n==n)&(data.status=='success')].sort_values(['block','repeat_id'])
                values=g[p+'_hat'].to_numpy();mask=(values>=limits[0])&(values<=limits[1]);shown=values[mask]
                density=shown[shown>0] if p=='gamma' else shown
                if len(density)>1 and np.ptp(density)>1e-12:
                    grid=np.linspace(density.min(),density.max(),256);kde=gaussian_kde(density,bw_method='scott')(grid)
                    width=.30*kde/kde.max();ax.fill_between(grid,pos-width,pos+width,color=COLORS[pos],alpha=.22,lw=.6)
                ax.scatter(shown,np.full(len(shown),pos),s=3,color=COLORS[pos],alpha=.62,linewidths=0,zorder=4)
                q=np.quantile(values,[.25,.5,.75]);mean=float(values.mean())
                ax.plot([q[0],q[2]],[pos,pos],color='#48515A',lw=.5,zorder=3)
                ax.scatter(q[1],pos,s=22,marker='o',facecolor='#E78AB5',edgecolor='white',lw=.35,zorder=6)
                ax.scatter(mean,pos,s=12,marker='o',facecolor='#D62728',edgecolor='white',lw=.35,zorder=7)
                records.append(dict(parameter=p,n=n,method=m,success=len(values),displayed_count=len(shown),
                    omitted_count=int((~mask).sum()),omitted_values=values[~mask].tolist(),
                    omitted_ids=g.loc[~mask,['block','repeat_id']].values.tolist(),quartiles=q.tolist(),mean=mean,
                    median_marker='pink circle',mean_marker='red circle',summary_source='all successful estimates',
                    x_limits=limits,x_ticks=ticks,density='Scott, displayed successful values, no tail extension',
                    density_min=float(density.min()),density_max=float(density.max()),jitter=False,iqr_linewidth=.5))
            ax.set_yticks(range(3),METHODS);ax.tick_params(axis='y',length=0,labelleft=col==0);ax.tick_params(axis='x',direction='in')
            ax.set_xlabel(label)
            if row==0:ax.set_title(f'n = {n}',fontsize=9,pad=9)
        assert all(np.array_equal(axes[row,0].get_xticks(),axes[row,c].get_xticks()) for c in range(1,5))
    violin_legend=[Line2D([],[],color='#E78AB5',marker='o',ls='',ms=5,label='中位数'),
                   Line2D([],[],color='#D62728',marker='o',ls='',ms=4,label='均值')]
    fig.legend(handles=violin_legend,loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.53,.952))
    fig.suptitle(setting_title('估计值分布'),fontsize=10,y=.988)
    fig.subplots_adjust(left=.085,right=.982,bottom=.08,top=.872,wspace=.23,hspace=.43)
    save(fig,'01_估计分布小提琴.png')
    fig,ax=plt.subplots(figsize=(5.9,3.6))
    for i,m in enumerate(METHODS):
        g=stats[stats.method==m].sort_values('n');y=g.success_rate.to_numpy()
        ax.plot(NS,y,color=COLORS[i],lw=1.25 if i!=2 else 1.8,ls='--' if i==2 else '-',
                marker='s' if i==2 else 'o',ms=5 if i==2 else 3.4,mfc='none' if i==2 else COLORS[i],label=m)
        points.extend(dict(figure='solution_rate',method=m,n=n,value=float(v)) for n,v in zip(NS,y))
    common(ax);ax.set_ylim(0,1.03);ax.set_yticks([0,.2,.4,.6,.8,1]);ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel('有效解比例');ax.legend(frameon=False,loc='lower right')
    fig.suptitle(setting_title('有效解比例'),fontsize=9,y=.985);fig.subplots_adjust(left=.14,right=.98,bottom=.17,top=.855)
    save(fig,'02_有解率.png')
    metric_limits={'rmse':[(0,3),(0,900),(0,900)],'bias':[(-.5,1.5),(-400,400),(-400,400)],'sd':[(0,2.5),(0,900),(0,900)]}
    metric_ticks={'rmse':[[0,.5,1,1.5,2,2.5,3],[0,200,400,600,800],[0,200,400,600,800]],
                  'bias':[[-.5,0,.5,1,1.5],[-400,-200,0,200,400],[-400,-200,0,200,400]],
                  'sd':[[0,.5,1,1.5,2,2.5],[0,200,400,600,800],[0,200,400,600,800]]}
    fig,axes=plt.subplots(3,3,figsize=(10.8,8.4))
    for row,metric in enumerate(['rmse','bias','sd']):
        for ax,p,label,limits,ticks in zip(axes[row],PARAMS,LABELS,metric_limits[metric],metric_ticks[metric]):
            for i,m in enumerate(METHODS):
                g=stats[stats.method==m].sort_values('n');y=g[p+'_'+metric].to_numpy()
                assert np.all((y>=limits[0])&(y<=limits[1]))
                ax.plot(NS,y,color=COLORS[i],lw=1.25,marker=['o','D','s'][i],ms=3.3,label=m)
                points.extend(dict(figure=metric,parameter=p,metric=metric,method=m,n=n,value=float(v)) for n,v in zip(NS,y))
            common(ax)
            if metric=='bias':ax.axhline(0,color='.75',lw=.55,zorder=0)
            ax.set_ylim(limits);ax.set_yticks(ticks);ax.set_ylabel(label+' '+{'rmse':'RMSE','bias':'Bias','sd':'SD'}[metric])
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='upper center',ncol=3,frameon=False,bbox_to_anchor=(.51,.955))
    fig.suptitle(setting_title('RMSE / Bias / SD'),fontsize=10.5,y=.988)
    fig.subplots_adjust(left=.08,right=.984,bottom=.065,top=.912,wspace=.28,hspace=.39);save(fig,'03_RMSE_Bias_SD九格.png')
    pd.DataFrame(points).to_csv(AUDIT/'图点.csv',index=False)
    assert len(points)==150
    (AUDIT/'绘图核验.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
      panels=15,records=records,curve_points=150,linear_axes=True,PNG_only=True,
      nine_panel_layout='rows RMSE/Bias/SD; columns beta/eta/gamma; no joint RMSE',
      RMSE_limits={'beta':[0,3],'eta':[0,900],'gamma':[0,900]},
      Bias_limits=dict(zip(PARAMS,metric_limits['bias'])),SD_limits=dict(zip(PARAMS,metric_limits['sd'])),
      solution_rate_limits=[0,1.03],statistics_untrimmed=True,notes_in_figure=False),ensure_ascii=False),encoding='utf-8')
    print('3 PNG written; median/mean circles, 45 violin groups and 150 curve points verified; no joint RMSE')
if __name__=='__main__':main()
