"""Task028 g2: plot saved Excel values only; violin plus method-by-n rate heatmap."""
import hashlib, json, platform
from pathlib import Path
import numpy as np
import scipy
from scipy.stats import gaussian_kde
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import NullLocator, PercentFormatter

HERE=Path(__file__).resolve().parent
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','Arial','DejaVu Sans'],
                    'font.size':8,'axes.linewidth':.7,'axes.spines.top':False,
                    'axes.spines.right':False,'axes.unicode_minus':False})

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(name,obj): (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def heatmap(ax, matrix, methods, ns, fontsize=9):
    im=ax.imshow(matrix,cmap='Blues',vmin=0,vmax=1,aspect='auto',interpolation='nearest')
    ax.set_xticks(range(len(ns)),ns); ax.set_yticks(range(len(methods)),methods)
    ax.set_xlabel('n'); ax.tick_params(length=0)
    ax.set_xticks(np.arange(-.5,len(ns),1),minor=True)
    ax.set_yticks(np.arange(-.5,len(methods),1),minor=True)
    ax.grid(which='minor',color='white',linewidth=1.1); ax.tick_params(which='minor',length=0)
    for spine in ax.spines.values(): spine.set_visible(False)
    texts=[]
    for row in range(len(methods)):
        for col in range(len(ns)):
            value=float(matrix[row,col]); assert 0<=value<=1
            texts.append((row,col,ax.text(col,row,f'{value:.0%}',ha='center',va='center',
                                          fontsize=fontsize,color='white' if value>=.60 else '#17212B')))
    return im,texts

def verify_cell_text(fig,ax,texts):
    fig.canvas.draw(); renderer=fig.canvas.get_renderer()
    for row,col,text in texts:
        a=ax.transData.transform((col-.5,row-.5)); b=ax.transData.transform((col+.5,row+.5))
        bbox=text.get_window_extent(renderer); lo=np.minimum(a,b); hi=np.maximum(a,b)
        assert bbox.x0>=lo[0] and bbox.x1<=hi[0] and bbox.y0>=lo[1] and bbox.y1<=hi[1]

def main():
    cfg=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
    batch=HERE.parent; out=HERE.parent/'结果' if HERE.name=='程序' else HERE.parent.parent/'结果'/HERE.name
    payload=json.loads((HERE/'Excel提取.json').read_text(encoding='utf-8')); source=payload['source']
    assert source['comparison_passed'] and not source['errors']
    assert sha(out/cfg['workbook'])==source['workbook_sha256']
    assert sha(HERE/'中间数据/matrix.json')==source['matrix_sha256']
    records=payload['records']; assert len(records)==1200
    methods=cfg['methods']; ns=cfg['sample_sizes']; truth=cfg['truth']
    groups={}; rates=[]
    for n in ns:
        for method in methods:
            group=[r for r in records if r['n']==n and r['method']==method['label']]
            assert len(group)==50 and len({r['id'] for r in group})==50
            valid=[r for r in group if r['success']]
            values=np.array([r['values'] for r in valid],dtype=float).reshape(-1,3)
            assert np.isfinite(values).all(); groups[(n,method['label'])]=(valid,values)
            rates.append(dict(combination=cfg['combination'],method=method['label'],n=n,
                              total=50,success=len(valid),success_rate=len(valid)/50,
                              note=cfg['boundary_note'] if n==7 and method['label']=='MDM δ=0.20' else ''))
    dump('有解率.json',rates)
    omissions=[]
    fig,axes=plt.subplots(3,3,figsize=(11.4,9.6),sharey=True)
    for row,(param,label,true_value) in enumerate(zip(('beta','eta','gamma'),('β','η','γ'),truth)):
        limits=cfg['display_limits'][param]; ticks=cfg['display_ticks'][param]
        for col,n in enumerate(ns):
            ax=axes[row,col]; ax.set_xscale('linear'); ax.set_xlim(limits); ax.set_ylim(7.5,-.5); ax.set_xticks(ticks)
            ax.xaxis.set_minor_locator(NullLocator()); ax.axvline(true_value,color='black',ls='--',lw=.7,zorder=1)
            for pos,method in enumerate(methods):
                valid,allvalues=groups[(n,method['label'])]; values=allvalues[:,row]
                mask=(values>=limits[0])&(values<=limits[1]); shown=values[mask]
                density=shown[shown>0] if param=='gamma' else shown
                if len(density)>1 and np.ptp(density)>1e-12:
                    grid=np.linspace(density.min(),density.max(),256)
                    kde=gaussian_kde(density,bw_method='scott')(grid); width=.30*kde/kde.max()
                    ax.fill_between(grid,pos-width,pos+width,color=method['color'],alpha=.22,lw=.6)
                ax.scatter(shown,np.full(len(shown),pos),s=3,color=method['color'],alpha=.62,linewidths=0,zorder=4)
                q=np.quantile(values,[.25,.5,.75]) if len(values) else np.array([np.nan]*3)
                mean=float(values.mean()) if len(values) else np.nan
                ax.plot([q[0],q[2]],[pos,pos],color='#48515A',lw=.5,zorder=3)
                ax.scatter(q[1],pos,s=22,marker='o',facecolor='#E78AB5',edgecolor='white',lw=.35,zorder=6)
                ax.scatter(mean,pos,s=12,marker='o',facecolor='#D62728',edgecolor='white',lw=.35,zorder=7)
                omissions.append(dict(parameter=param,n=n,method=method['label'],success=len(values),
                    displayed_count=len(shown),omitted_count=int((~mask).sum()),
                    omitted=[dict(id=r['id'],value=float(v)) for r,v,keep in zip(valid,values,mask) if not keep],
                    quartiles=q.tolist(),mean=mean,x_limits=limits,x_ticks=ticks,
                    density='Scott; displayed successful values; no tail extension; gamma=0 points only',
                    density_min=float(density.min()) if len(density) else None,
                    density_max=float(density.max()) if len(density) else None,
                    median_shown=bool(limits[0]<=q[1]<=limits[1]),mean_shown=bool(limits[0]<=mean<=limits[1]),
                    jitter=False,iqr_linewidth=.5))
            ax.set_yticks(range(8),[m['label'] for m in methods]); ax.tick_params(axis='y',length=0,labelleft=col==0)
            ax.tick_params(axis='x',direction='in'); ax.set_xlabel(label)
            if row==0: ax.set_title(f'n = {n}',fontsize=9,pad=9)
        assert all(np.array_equal(ax.get_xticks(),ticks) and np.array_equal(ax.get_xlim(),limits) for ax in axes[row])
    handles=[Line2D([],[],color='#E78AB5',marker='o',ls='',ms=5,label='中位数'),
             Line2D([],[],color='#D62728',marker='o',ls='',ms=4,label='均值')]
    fig.legend(handles=handles,loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.55,.956))
    prefix=f'真值 β={truth[0]:g}、η={truth[1]:g}、γ={truth[2]:g}'
    fig.suptitle(prefix+' ｜ 估计值分布',fontsize=10,y=.988)
    fig.subplots_adjust(left=.145,right=.984,bottom=.055,top=.902,wspace=.21,hspace=.34)
    fig.savefig(out/'01_估计分布小提琴.png',dpi=cfg['png_dpi'],facecolor='white'); plt.close(fig)

    rate_index={(r['method'],r['n']):r['success_rate'] for r in rates}
    matrix=np.array([[rate_index[(m['label'],n)] for n in ns] for m in methods])
    fig,ax=plt.subplots(figsize=(6.5,4.2))
    im,texts=heatmap(ax,matrix,[m['label'] for m in methods],ns,fontsize=10)
    fig.subplots_adjust(left=.215,right=.815,bottom=.14,top=.88)
    cax=fig.add_axes([.85,.14,.025,.74]); cb=fig.colorbar(im,cax=cax)
    cb.set_ticks([0,.25,.5,.75,1]); cb.ax.yaxis.set_major_formatter(PercentFormatter(1))
    cb.set_label('有解率'); cb.outline.set_visible(False); cb.ax.tick_params(length=0)
    fig.suptitle(prefix+' ｜ 有解率',fontsize=9,y=.965)
    verify_cell_text(fig,ax,texts)
    fig.savefig(out/'02_有解率.png',dpi=cfg['png_dpi'],facecolor='white'); plt.close(fig)
    assert len(omissions)==72 and len(rates)==24
    dump('绘图核验.json',dict(violin_panels=9,violin_groups=72,heatmap_cells=24,
        records=omissions,rate_cells=rates,linear_axes=True,PNG_only=True,notes_in_figure=False,
        density_within_observed_range=True,statistics_use_all_successful_estimates=True,
        heatmap_axes='rows: methods; columns: n',heatmap_limits=[0,1],cell_text_inside_cell=True))
    outputs=[out/name for name in ('01_估计分布小提琴.png','02_有解率.png')]
    dump('manifest.json',dict(task_id=cfg['task_id'],goal_version=cfg['goal_version'],artifact_version=cfg['artifact_version'],
        workbook_sha256=source['workbook_sha256'],matrix_sha256=source['matrix_sha256'],
        scripts={p.name:sha(p) for p in HERE.glob('*.py')},config_sha256=sha(HERE/'config.json'),
        entry_sha256=sha(HERE/'运行本组.ps1'),
        outputs=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in outputs],
        runtime=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__)))
    print(cfg['combination'],'READY: 2 PNG; 24 rate cells; 72 violin groups',flush=True)

if __name__=='__main__': main()
