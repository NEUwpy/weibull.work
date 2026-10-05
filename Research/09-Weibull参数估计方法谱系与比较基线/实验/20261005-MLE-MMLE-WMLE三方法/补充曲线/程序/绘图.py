"""Plot only saved three-method summary; no sampling or solver imports."""
import hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator,PercentFormatter

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parents[1]/'汇总表.csv'
SAVED=HERE/'输入汇总表.csv'
OUTPUT=HERE.parent/'结果'
MOTHER=HERE/'绘图母体.py'
spec=importlib.util.spec_from_file_location('research00_saved_style',MOTHER)
mother=importlib.util.module_from_spec(spec);spec.loader.exec_module(mother)
METHODS=['MLE','MMLE-I','WMLE'];N=np.array([7,10,15,20,50])
STYLES={
 'MLE':dict(color=mother.COLORS[4],marker='s',ls='--',markersize=4.5,markerfacecolor='white'),
 'MMLE-I':dict(color=mother.COLORS[0],marker='o',ls='-',markersize=5.4,markerfacecolor='white'),
 'WMLE':dict(color=mother.COLORS[3],marker='D',ls=':',markersize=3.8)}
plt.rcParams.update({'font.size':9,'legend.fontsize':9})

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def read_points():
    source_hash=digest(SOURCE);assert source_hash==digest(SAVED),'Original summary changed; review before reuse'
    table=pd.read_csv(SAVED).set_index('method');assert set(table.index)==set(METHODS)
    raw_path=HERE.parents[1]/'per_sample.csv.gz'
    raw=pd.read_csv(raw_path);raw['method_variant']=raw.method_variant.replace({'MMLE':'MMLE-I'})
    points=[]
    for method in METHODS:
        for n in N:
            part=raw[raw.method_variant.eq(method)&raw.n.eq(n)];good=part[part.status.eq('success')]
            total=int(table.loc[method,f'n{n}_total']);success=int(table.loc[method,f'n{n}_success'])
            assert total==len(part)==1200 and success==len(good)
            rate=float(table.loc[method,f'n{n}_success_rate']);assert np.isclose(rate,success/total)
            values={p:float(table.loc[method,f'n{n}_{p}_rmse']) for p in ['beta','eta','gamma']}
            for p,value in values.items():assert np.isclose(value,np.sqrt(np.mean(good[p+'_error']**2)),rtol=1e-12)
            joint=float(table.loc[method,f'n{n}_joint_rmse'])
            assert np.isclose(joint,np.sqrt(sum(v*v for v in values.values())),rtol=1e-12)
            points.append(dict(method=method,n=int(n),total=total,success=success,success_rate_percent=100*rate,
                **{p+'_rmse':v for p,v in values.items()},joint_rmse=joint))
    return pd.DataFrame(points),{str(SOURCE):source_hash,str(SAVED):digest(SAVED),str(raw_path):digest(raw_path)}

def draw_lines(ax,data,key):
    for method in METHODS:
        part=data[data.method.eq(method)].sort_values('n');y=part[key].to_numpy()
        line,=ax.plot(part.n,y,label=method,lw=1.15,markeredgewidth=.8,clip_on=False,**STYLES[method])
        assert np.array_equal(line.get_xdata(),N) and np.array_equal(line.get_ydata(),y)
    ax.set_xscale('linear');ax.set_yscale('linear');ax.set_xlim(5,52);ax.set_xticks(N);ax.set_xlabel('n')
    ax.xaxis.set_minor_locator(NullLocator());ax.yaxis.set_minor_locator(NullLocator());ax.tick_params(direction='out')
    assert not ax.texts and ax.get_title()==''


def save(fig,name):
    assert not fig.texts
    path=OUTPUT/name;fig.savefig(path,dpi=450,facecolor='white');plt.close(fig);return path


def main():
    data,source_hashes=read_points();OUTPUT.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(6.2,4.0))
    draw_lines(ax,data,'success_rate_percent');ax.set_ylim(0,100);ax.set_yticks([0,20,40,60,80,100])
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100,decimals=0));ax.set_ylabel('成功率')
    fig.legend(*ax.get_legend_handles_labels(),loc='upper center',ncol=3,frameon=False,bbox_to_anchor=(.53,.995))
    fig.subplots_adjust(left=.14,right=.975,bottom=.16,top=.88)
    success=save(fig,'成功率随n变化.png')
    fig,axes=plt.subplots(2,2,figsize=(8.8,6.4))
    specs=[('beta_rmse','β RMSE',[0,4],[0,1,2,3,4]),
           ('eta_rmse','η RMSE',[0,800],[0,200,400,600,800]),
           ('gamma_rmse','γ RMSE',[0,800],[0,200,400,600,800]),
           ('joint_rmse','联合 RMSE',[0,1000],[0,250,500,750,1000])]
    panels=[]
    for ax,(key,label,limits,ticks) in zip(axes.flat,specs):
        draw_lines(ax,data,key);ax.set_ylim(limits);ax.set_yticks(ticks);ax.set_ylabel(label)
        assert np.all((data[key]>=limits[0])&(data[key]<=limits[1]))
        panels.append(dict(metric=key,ylim=limits,yticks=ticks))
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='upper center',ncol=3,frameon=False,bbox_to_anchor=(.53,.995))
    fig.subplots_adjust(left=.115,right=.975,bottom=.10,top=.90,hspace=.33,wspace=.30)
    rmse=save(fig,'RMSE随n变化.png')
    record=dict(task_id='research09-three-methods-004',source_sha256=source_hashes,
        source_rows=18000,points=data.to_dict(orient='records'),new_samples=0,new_estimates=0,
        primary_precision='All own-success estimates; untrimmed and different subsets',
        joint_rmse='sqrt(MSE_beta_raw+MSE_eta_raw+MSE_gamma_raw); eta/gamma numerical units dominate',
        style_sha256=digest(MOTHER),script_sha256=digest(Path(__file__)),
        axes='Linear',x_ticks=N.tolist(),success_y_limits=[0,100],rmse_panels=panels,
        annotations='Axes,ticks,method legend only; no text boxes/notes/thresholds/titles',
        formats=['PNG'],outputs={str(p):digest(p) for p in [success,rmse]},
        python=sys.executable,numpy=np.__version__,pandas=pd.__version__,matplotlib=matplotlib.__version__,all_passed=True)
    (HERE/'绘图核验.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(outputs=[str(success),str(rmse)],point_groups=len(data),all_passed=True),ensure_ascii=False))

if __name__=='__main__':main()
