"""Research00 mother style, transposed to parameter rows and n columns."""
import hashlib,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator

HERE=Path(__file__).resolve().parent
MOTHER=HERE/'style_snapshot/绘图母体.py'
spec=importlib.util.spec_from_file_location('saved_research00_mother',MOTHER)
mother=importlib.util.module_from_spec(spec);spec.loader.exec_module(mother)
METHODS=['MLE','MMLE-I','WMLE']
COLORS=[mother.COLORS[4],mother.COLORS[0],mother.COLORS[3]]

def main():
    data=pd.read_csv(HERE/'per_sample.csv.gz');data['method_variant']=data.method_variant.replace({'MMLE':'MMLE-I'})
    specs=[('beta_hat',2.0,'β',[0.,10.],[0.,2.,4.,6.,8.,10.]),
           ('eta_hat',1000.0,'η',[0.,2000.],[0.,500.,1000.,1500.,2000.]),
           ('gamma_hat',1000.0,'γ',[0.,2000.],[0.,500.,1000.,1500.,2000.])]
    n_values=[7,10,15,20,50]
    fig,axes=plt.subplots(3,5,figsize=(12.0,7.0),sharex='row',sharey=True)
    records=[]
    for row,(parameter,truth,label,limits,ticks) in enumerate(specs):
        for col,n in enumerate(n_values):
            ax=axes[row,col];ax.set_xscale('linear');ax.set_xlim(limits);ax.set_ylim(2.6,-.6)
            ax.set_xticks(ticks);ax.xaxis.set_minor_locator(NullLocator())
            ax.axvline(truth,color='black',ls='--',lw=.75,zorder=1)
            for pos,method in enumerate(METHODS):
                part=data[(data.n==n)&data.method_variant.eq(method)].sort_values(['block','repeat_id'])
                good=part[part.status.eq('success')];values=good[parameter].to_numpy()
                case_ids=(good.block.astype(str)+':'+good.repeat_id.astype(str)).to_numpy()
                displayed=(values>=limits[0])&(values<=limits[1]);shown=values[displayed]
                density_values=shown[shown>0] if parameter=='gamma_hat' else shown
                grid=np.array([]);density=np.array([])
                if len(density_values)>1 and np.ptp(density_values)>1e-12:
                    grid=np.linspace(density_values.min(),density_values.max(),256)
                    density=gaussian_kde(density_values,bw_method='scott')(grid)
                    width=.32*density/density.max()
                    ax.fill_between(grid,pos-width,pos+width,color=COLORS[pos],alpha=.22,lw=.6,zorder=2)
                coordinates=np.full(len(shown),pos,dtype=float)
                ax.scatter(shown,coordinates,s=3,color=COLORS[pos],alpha=.65,linewidths=0,zorder=4)
                q=np.quantile(values,[.25,.5,.75])
                ax.plot([q[0],q[2]],[pos,pos],color='#48515A',lw=.5,zorder=3)
                ax.scatter(q[1],pos,s=10,marker='D',facecolor='white',edgecolor='#48515A',lw=.5,zorder=5)
                assert np.all(coordinates==pos) and np.all((shown>=limits[0])&(shown<=limits[1]))
                assert not len(density_values) or (grid.size and grid[0]==density_values.min() and grid[-1]==density_values.max())
                records.append(dict(n=n,method=method,parameter=parameter,truth=truth,success=len(values),failure=1200-len(values),
                    x_limits=limits,x_ticks=ticks,axis_scale='linear',point_layout='centerline_without_jitter',
                    bandwidth='Scott',quartiles_all_success=q.tolist(),iqr_linewidth=.5,
                    white_diamond_median=True,zero_count=int((values==0).sum()),density_count=len(density_values),
                    density_limits=[float(density_values.min()),float(density_values.max())] if len(density_values) else None,
                    displayed_values=shown.tolist(),displayed_case_ids=case_ids[displayed].tolist(),
                    omitted_count=int((~displayed).sum()),omitted_values=values[~displayed].tolist(),
                    omitted_case_ids=case_ids[~displayed].tolist()))
            ax.set_yticks(range(3),METHODS);ax.tick_params(axis='y',length=0,labelleft=col==0,pad=4)
            ax.tick_params(axis='x',labelbottom=True);ax.set_xlabel(label)
            if row==0:ax.set_title(f'n={n}',fontsize=9)
            assert not ax.texts  # no text boxes, notes or panel letters
        assert all(np.array_equal(axes[row,0].get_xticks(),axes[row,c].get_xticks()) for c in range(5))
    assert not fig.texts
    fig.subplots_adjust(left=.075,right=.975,top=.945,bottom=.075,wspace=.23,hspace=.40)
    target=HERE/'估计分布小提琴.png';fig.savefig(target,dpi=450,facecolor='white');plt.close(fig)
    record=dict(layout='3 parameter rows x5 n columns;3 methods each',formats=['PNG'],
        png_dimensions=[5400,3150],mother_path=str(MOTHER),mother_sha256=hashlib.sha256(MOTHER.read_bytes()).hexdigest(),
        reference_style_sha256=hashlib.sha256((HERE/'style_snapshot/绘制图1小提琴.py').read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256((HERE/'per_sample.csv.gz').read_bytes()).hexdigest(),
        summary_source='all successful estimates',density_source='displayed successful estimates',
        gamma_zero_scatter_retained=True,gamma_zero_excluded_from_density=True,
        annotations='only coordinates,ticks,method labels and n column labels',panels=records,all_passed=True)
    (HERE/'绘图记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(dict(file=str(target),panels=15,method_distributions=len(records),plot_checks_passed=True))

if __name__=='__main__':main()
