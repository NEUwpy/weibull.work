"""Task028 pilot: R09-style PNGs and statistics from saved Excel values only."""
import csv, hashlib, json, math, platform
from pathlib import Path
import numpy as np
import pandas as pd
import scipy
from scipy.stats import gaussian_kde
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter, NullLocator, MaxNLocator

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent.parent
CONFIG = json.loads((HERE/'config.json').read_text(encoding='utf-8'))
OUT = BATCH/'结果'
CSV = (BATCH/CONFIG['statistics_csv']).resolve()
METHODS = CONFIG['methods']; NS = CONFIG['sample_sizes']
PARAMS = ['beta', 'eta', 'gamma']; LABELS = ['β', 'η', 'γ']; TRUTH = CONFIG['truth']
plt.rcParams.update({'font.family':'sans-serif', 'font.sans-serif':['Microsoft YaHei','Arial','DejaVu Sans'],
                    'font.size':8, 'axes.linewidth':.7, 'axes.spines.top':False,
                    'axes.spines.right':False, 'axes.unicode_minus':False})

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name, obj): (HERE/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def title(suffix): return f'真值 β={TRUTH[0]:g}、η={TRUTH[1]:g}、γ={TRUTH[2]:g} ｜ {suffix}'
def save(fig, name):
    fig.savefig(OUT/name, dpi=CONFIG['png_dpi'], facecolor='white'); plt.close(fig)
def common(ax):
    ax.set_xscale('linear'); ax.set_yscale('linear')
    ax.set_xlim(min(NS)-1, max(NS)+1); ax.set_xticks(NS); ax.set_xlabel('n')
    ax.tick_params(direction='in'); ax.xaxis.set_minor_locator(NullLocator())
def series(ax, method, y):
    ax.plot(NS, y, color=method['color'], lw=1.25 if method['label']!='WMLE' else 1.8,
            ls=method['linestyle'], marker=method['marker'],
            ms=5 if method['label']=='WMLE' else 3.4,
            mfc='none' if method['label']=='WMLE' else method['color'], label=method['label'])

def main():
    payload = json.loads((HERE/'Excel提取.json').read_text(encoding='utf-8'))
    source = payload['source']
    assert source['comparison_passed'] and not source['errors']
    assert sha(BATCH/CONFIG['workbook']) == source['workbook_sha256']
    assert sha(BATCH/CONFIG['crosscheck_matrix']) == source['matrix_sha256']
    records = payload['records']; assert len(records)==1200
    groups = {}; rows = []; independent_checks = []
    for n in NS:
        for method in METHODS:
            group = [r for r in records if r['n']==n and r['method']==method['label']]
            assert len(group)==50 and len({r['id'] for r in group})==50
            valid = [r for r in group if r['success']]
            values = np.array([r['values'] for r in valid], dtype=float).reshape(-1,3)
            assert np.isfinite(values).all()
            groups[(n,method['label'])] = (valid, values)
            row = dict(combination=CONFIG['combination'], method=method['label'], n=n,
                       total=50, success=len(valid), success_rate=len(valid)/50)
            for column, (param, truth) in enumerate(zip(PARAMS, TRUTH)):
                vals = values[:,column]
                if len(vals):
                    error=vals-truth; bias=float(error.mean()); sd=float(vals.std(ddof=0))
                    rmse=float(np.sqrt(np.mean(error*error)))
                    scalar = [float(v) for v in vals]
                    mean=math.fsum(scalar)/len(scalar)
                    check_bias=math.fsum(v-truth for v in scalar)/len(scalar)
                    check_sd=math.sqrt(math.fsum((v-mean)**2 for v in scalar)/len(scalar))
                    check_rmse=math.sqrt(math.fsum((v-truth)**2 for v in scalar)/len(scalar))
                    assert all(math.isclose(a,b,rel_tol=2e-13,abs_tol=1e-12)
                               for a,b in zip((bias,sd,rmse),(check_bias,check_sd,check_rmse)))
                    assert math.isclose(rmse*rmse,bias*bias+sd*sd,rel_tol=2e-13,abs_tol=1e-10)
                else: bias=sd=rmse=float('nan')
                row.update({param+'_bias':bias,param+'_sd':sd,param+'_rmse':rmse})
                independent_checks.append(dict(n=n,method=method['label'],parameter=param,
                                               count=len(vals),bias=bias,sd=sd,rmse=rmse))
            row['note'] = CONFIG['boundary_note'] if n==7 and method['label']=='MDM δ=0.20' else ''
            rows.append(row)
    stats=pd.DataFrame(rows)
    assert len(stats)==24 and stats.total.eq(50).all()
    CSV.parent.mkdir(parents=True,exist_ok=True)
    if CSV.exists():
        previous=pd.read_csv(CSV,float_precision='round_trip')
        assert len(previous)==24 and previous.combination.eq(CONFIG['combination']).all(), 'do not replace another statistics batch'
    stats.to_csv(CSV,index=False,encoding='utf-8-sig',float_format='%.17g')
    roundtrip=pd.read_csv(CSV,float_precision='round_trip')
    for col in stats.select_dtypes(include='number').columns:
        assert np.array_equal(stats[col].to_numpy(),roundtrip[col].to_numpy(),equal_nan=True),col
    dump('统计核验.json',dict(rows=24,total_per_method_n=50,own_successful_sets=True,
         sd_ddof=0,normalized_gamma=False,statistics_untrimmed=True,
         numpy_vs_independent_fsum=True,rmse_squared_equals_bias_squared_plus_sd_squared=True,
         csv_roundtrip_exact=True,success_rule=CONFIG['success_rule'],
         acknowledged_status_differences=source['acknowledged_status_differences'],checks=independent_checks))

    omissions=[]; points=[]
    fig, axes=plt.subplots(3,3,figsize=(11.4,9.6),sharey=True)
    for row,(param,label,truth) in enumerate(zip(PARAMS,LABELS,TRUTH)):
        limits=CONFIG['display_limits'][param]; ticks=CONFIG['display_ticks'][param]
        for col,n in enumerate(NS):
            ax=axes[row,col]; ax.set_xscale('linear'); ax.set_xlim(limits); ax.set_ylim(7.5,-.5); ax.set_xticks(ticks)
            ax.xaxis.set_minor_locator(NullLocator())
            ax.axvline(truth,color='black',ls='--',lw=.7,zorder=1)
            for pos,method in enumerate(METHODS):
                valid,allvalues=groups[(n,method['label'])]; values=allvalues[:,row]
                mask=(values>=limits[0])&(values<=limits[1]); shown=values[mask]
                density=shown[shown>0] if param=='gamma' else shown
                if len(density)>1 and np.ptp(density)>1e-12:
                    grid=np.linspace(density.min(),density.max(),256)
                    kde=gaussian_kde(density,bw_method='scott')(grid); width=.30*kde/kde.max()
                    ax.fill_between(grid,pos-width,pos+width,color=method['color'],alpha=.22,lw=.6)
                ax.scatter(shown,np.full(len(shown),pos),s=3,color=method['color'],alpha=.62,linewidths=0,zorder=4)
                q=np.quantile(values,[.25,.5,.75]) if len(values) else [np.nan]*3
                mean=float(values.mean()) if len(values) else np.nan
                ax.plot([q[0],q[2]],[pos,pos],color='#48515A',lw=.5,zorder=3)
                ax.scatter(q[1],pos,s=22,marker='o',facecolor='#E78AB5',edgecolor='white',lw=.35,zorder=6)
                ax.scatter(mean,pos,s=12,marker='o',facecolor='#D62728',edgecolor='white',lw=.35,zorder=7)
                omissions.append(dict(parameter=param,n=n,method=method['label'],success=len(values),
                    displayed_count=len(shown),omitted_count=int((~mask).sum()),
                    omitted=[dict(id=r['id'],value=float(v)) for r,v,keep in zip(valid,values,mask) if not keep],
                    quartiles=np.asarray(q).tolist(),mean=mean,x_limits=limits,x_ticks=ticks,
                    density='Scott, displayed successful values, no tail extension; gamma=0 points only',
                    density_min=float(density.min()) if len(density) else None,
                    density_max=float(density.max()) if len(density) else None,
                    median_shown=bool(limits[0]<=q[1]<=limits[1]),mean_shown=bool(limits[0]<=mean<=limits[1]),
                    jitter=False,iqr_linewidth=.5))
            ax.set_yticks(range(8),[m['label'] for m in METHODS]); ax.tick_params(axis='y',length=0,labelleft=col==0)
            ax.tick_params(axis='x',direction='in'); ax.set_xlabel(label)
            if row==0: ax.set_title(f'n = {n}',fontsize=9,pad=9)
        assert all(np.array_equal(axes[row,0].get_xticks(),axes[row,c].get_xticks()) for c in (1,2))
        assert all(np.array_equal(axes[row,0].get_xlim(),axes[row,c].get_xlim()) for c in (1,2))
        assert all(np.array_equal(ax.get_xticks(),ticks) and np.array_equal(ax.get_xlim(),limits) for ax in axes[row])
    handles=[Line2D([],[],color='#E78AB5',marker='o',ls='',ms=5,label='中位数'),
             Line2D([],[],color='#D62728',marker='o',ls='',ms=4,label='均值')]
    fig.legend(handles=handles,loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.55,.956))
    fig.suptitle(title('估计值分布'),fontsize=10,y=.988)
    fig.subplots_adjust(left=.145,right=.984,bottom=.055,top=.902,wspace=.21,hspace=.34)
    save(fig,'01_估计分布小提琴.png')

    fig,ax=plt.subplots(figsize=(6.5,4.2))
    for method in METHODS:
        g=stats[stats.method==method['label']].sort_values('n'); y=g.success_rate.to_numpy()
        series(ax,method,y)
        points.extend(dict(figure='solution_rate',method=method['label'],n=n,value=float(v)) for n,v in zip(NS,y))
    common(ax); ax.set_ylim(0,1.03); ax.set_yticks([0,.2,.4,.6,.8,1]); ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel('有效解比例'); ax.legend(frameon=False,loc='lower right',ncol=2,fontsize=7.5,columnspacing=1.2)
    fig.suptitle(title('有效解比例'),fontsize=9,y=.985)
    fig.subplots_adjust(left=.13,right=.98,bottom=.16,top=.87); save(fig,'02_有解率.png')

    limits_by_metric={}; ticks_by_metric={}
    for metric in ('rmse','bias','sd'):
        limits_by_metric[metric]={}; ticks_by_metric[metric]={}
        for param in PARAMS:
            values=stats[param+'_'+metric].to_numpy(dtype=float); values=values[np.isfinite(values)]
            if metric=='bias':
                span=max(np.abs(values).max(initial=0),1e-9)*1.08
                ticks=MaxNLocator(nbins=5).tick_values(-span,span)
            else:
                ticks=MaxNLocator(nbins=5).tick_values(0.,max(values.max(initial=0),1e-9)*1.08)
            assert np.all((values>=ticks[0])&(values<=ticks[-1]))
            limits_by_metric[metric][param]=[float(ticks[0]),float(ticks[-1])]
            ticks_by_metric[metric][param]=ticks.tolist()
    fig,axes=plt.subplots(3,3,figsize=(10.8,8.4))
    for row,metric in enumerate(('rmse','bias','sd')):
        for col,(param,label) in enumerate(zip(PARAMS,LABELS)):
            ax=axes[row,col]; limits=limits_by_metric[metric][param]; ticks=ticks_by_metric[metric][param]
            for method in METHODS:
                g=stats[stats.method==method['label']].sort_values('n'); y=g[param+'_'+metric].to_numpy()
                series(ax,method,y)
                points.extend(dict(figure=metric,parameter=param,metric=metric,method=method['label'],
                                   n=n,value=float(v)) for n,v in zip(NS,y))
            common(ax)
            if metric=='bias': ax.axhline(0,color='.75',lw=.55,zorder=0)
            ax.set_ylim(limits); ax.set_yticks(ticks); ax.set_ylabel(label+' '+{'rmse':'RMSE','bias':'Bias','sd':'SD'}[metric])
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='upper center',ncol=4,frameon=False,
               bbox_to_anchor=(.53,.965),fontsize=7.6,columnspacing=1.6)
    fig.suptitle(title('RMSE / Bias / SD'),fontsize=10,y=.992)
    fig.subplots_adjust(left=.085,right=.984,bottom=.065,top=.87,wspace=.29,hspace=.39)
    save(fig,'03_RMSE_Bias_SD九格.png')
    pd.DataFrame(points).to_csv(HERE/'图点.csv',index=False,float_format='%.17g')
    assert len(omissions)==72 and len(points)==240
    dump('绘图核验.json',dict(workbook_sha256=source['workbook_sha256'],
         csv_sha256=sha(CSV),violin_panels=9,violin_groups=72,curve_points=240,
         records=omissions,linear_axes=True,PNG_only=True,notes_in_figure=False,
         nine_panel_layout='rows RMSE/Bias/SD; columns beta/eta/gamma',
         metric_limits=limits_by_metric,metric_ticks=ticks_by_metric,
         statistics_untrimmed=True,solution_rate_limits=[0,1.03]))
    outputs=[OUT/name for name in ('01_估计分布小提琴.png','02_有解率.png','03_RMSE_Bias_SD九格.png')]+[CSV]
    dump('manifest.json',dict(task_id=CONFIG['task_id'],artifact_version=CONFIG['artifact_version'],
         workbook_sha256=source['workbook_sha256'],crosscheck_matrix_sha256=source['matrix_sha256'],
         scripts={p.name:sha(p) for p in HERE.glob('*.py')},config_sha256=sha(HERE/'config.json'),
         outputs=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in outputs],
         runtime=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,
                      matplotlib=matplotlib.__version__,pandas=pd.__version__)))
    print('PILOT_READY: 3 PNG; 24 CSV rows; 72 violin groups; 240 plotted curve points')
    print(stats[['method','n','success','success_rate','gamma_bias']].to_string(index=False))

if __name__=='__main__': main()
