"""Preview the saved estimates with three linear axes; keep existing end cuts."""
import hashlib
import json
from pathlib import Path

from 绘图母体 import COLORS, METHODS, NAMES, gaussian_kde, np, plt, save
from matplotlib.ticker import MaxNLocator, NullLocator

PROGRAM=Path(__file__).resolve().parent
OUTPUT=PROGRAM.parents[1]/'结果'/PROGRAM.name
SOURCE=OUTPUT/'中间数据/results.json'
NAME='估计分布_线性坐标试画'


def draw():
    data=json.loads(SOURCE.read_text(encoding='utf-8'))
    fig,axes=plt.subplots(3,3,figsize=(8.2,6.9),sharex='col',sharey=True)
    records=[]
    for col,(key,truth,label) in enumerate(zip(
            ['beta_hat','eta_hat','gamma_hat'],data['truth'],['β','η','γ'])):
        pooled=np.array([r[key] for r in data['results'] if r['converged'] and r[key] is not None])
        maximum=max(float(pooled.max()),truth)
        limits=[-.06*maximum,1.06*maximum] if key=='gamma_hat' else [0,1.06*maximum]
        for row,n in enumerate(data['n']):
            ax=axes[row,col]
            ax.set_xscale('linear'); ax.set_xlim(limits); ax.set_ylim(4.6,-.6)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=4,steps=[1,2,2.5,5,10],min_n_ticks=3))
            ax.xaxis.set_minor_locator(NullLocator())
            ax.axvline(truth,color='black',ls='--',lw=.75,zorder=1)
            for pos,method in enumerate(METHODS):
                rows=sorted([r for r in data['results'] if r['n']==n and r['method_id']==method and r['converged']],key=lambda r:r['id'])
                values=np.array([r[key] for r in rows])
                density=values[values>0] if key=='gamma_hat' else values
                if len(density)>1 and np.ptp(density)>1e-12:
                    grid=np.linspace(density.min(),density.max(),256)
                    kde=gaussian_kde(density,bw_method='scott')(grid)
                    width=.32*kde/kde.max()
                    ax.fill_between(grid,pos-width,pos+width,color=COLORS[pos],alpha=.22,lw=.6)
                ax.scatter(values,np.full(len(values),pos),s=3,color=COLORS[pos],alpha=.65,linewidths=0,zorder=4)
                quartiles=np.quantile(values,[.25,.5,.75]) if len(values) else np.array([None]*3)
                if len(values):
                    ax.plot([quartiles[0],quartiles[2]],[pos,pos],color='#48515A',lw=.5,zorder=3)
                    ax.scatter(quartiles[1],pos,s=10,marker='D',facecolor='white',edgecolor='#48515A',lw=.5,zorder=5)
                assert all(limits[0]<=value<=limits[1] for value in values)
                records.append(dict(n=n,method=method,parameter=key,ids=[r['id'] for r in rows],
                                    values=values.tolist(),quartiles=quartiles.tolist(),zeros=int(np.count_nonzero(values==0)),
                                    x_limits=limits,axis_scale=ax.get_xscale(),density_coordinate='original',
                                    density_endpoints='observed minimum and maximum',points_on_centerline=True))
            ax.set_yticks(range(5),NAMES); ax.tick_params(axis='y',length=0,labelleft=col==0)
            ax.tick_params(axis='x',labelbottom=True); ax.set_xlabel(label)
            ax.text(-.07,1.08,chr(97+row*3+col),transform=ax.transAxes,fontsize=9,weight='bold')
            if col==0: ax.text(.02,1.08,f'n={n}',transform=ax.transAxes,fontsize=8)
    assert len(records)==45
    for col in range(3):
        assert all(np.array_equal(axes[0,col].get_xticks(),axes[row,col].get_xticks()) for row in (1,2))
    fig.subplots_adjust(left=.09,right=.98,top=.94,bottom=.08,wspace=.23,hspace=.63)
    save(fig,OUTPUT,NAME)
    record=dict(distribution=data['distribution'],source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                panels=9,coordinate='linear for all parameters',bandwidth='Scott',
                zero_gamma_excluded_from_density=True,all_successful_points_preserved=True,
                density_endpoint_rule_unchanged=True,format='PNG 450dpi',records=records)
    (OUTPUT/'中间数据/线性坐标试画核验.json').write_text(json.dumps(record,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print('SAVED',OUTPUT/f'{NAME}.png',flush=True)


if __name__=='__main__':
    draw()
