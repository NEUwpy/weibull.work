"""Read-only post-test diagnostics; no training, selection or source-data writes.

Figure contract: fig2 shows cross-life-point cost and constraint recovery;
fig3 locates pooled gains rather than counting them as universal improvement.
All panels use observed predictions/derived summaries, not fitted mechanism art.
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/manuscript_review_v250'
FIG = ROOT / 'manuscript/figures/main'
COLORS = {'P': '#777777', 'Q': '#0072B2', 'QCP': '#009E73'}


def save(fig, name):
    for ext in ('png', 'pdf', 'svg'):
        path = FIG / f'{name}.{ext}'
        fig.savefig(path, dpi=400, bbox_inches='tight')
        if ext == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'],
                         'font.size': 8, 'axes.unicode_minus': False, 'svg.fonttype': 'none', 'pdf.fonttype': 42,
                         'axes.spines.top': False, 'axes.spines.right': False})
    source = ROOT / 'artifacts/equal_budget_sensitivity'
    if not source.exists():
        source = ROOT / '归档/旧实验/四路线同预算敏感性/artifacts/equal_budget_sensitivity'
    models = pd.read_csv(ROOT / 'artifacts/qcp_main_analysis/analysis/model_cells.csv')
    assert len(models) == 200 and not models.duplicated(['n','fold','seed']).any()
    fields = ('beta_hat','eta_hat','gamma_hat','min_x','rel_err')
    blocks = {r: {k: [] for k in fields} for r in COLORS}
    hashes = {}
    cell_mse=[]
    for row in models.itertuples():
        base = None
        for route in COLORS:
            root = ROOT / 'artifacts/qcp_constrained_confirm' if route == 'QCP' else source
            p = root / 'evidence' / f'n{row.n}_f{row.fold}_s{row.seed}_r{route}.npz'
            hashes[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
            with np.load(p) as z:
                keys = np.column_stack([z[k] for k in ('keys_beta','keys_gamma_over_eta','keys_n','keys_repeat_id')])
                if base is None:
                    base = keys
                else:
                    np.testing.assert_array_equal(base, keys)
                for k in fields:
                    assert len(z[k]) == 2400 and np.isfinite(z[k]).all()
                    if k == 'rel_err':
                        beta=z['keys_beta'].astype(np.float64)
                        truth=1000*z['keys_gamma_over_eta']+1000*(-np.log(.95))**(1/beta)
                        pred=z['gamma_hat'].astype(np.float64)+z['eta_hat'].astype(np.float64)*(-np.log(.95))**(1/z['beta_hat'].astype(np.float64))
                        err=(pred-truth)/truth
                        blocks[route][k].append(err)
                        for bv,gv in np.unique(keys[:,:2],axis=0):
                            mask=(keys[:,0]==bv)&(keys[:,1]==gv)
                            assert mask.sum()==60
                            cell_mse.append(dict(n=row.n,beta=bv,gamma_over_eta=gv,route=route,mse=float(np.mean(err[mask]**2))))
                    else:
                        blocks[route][k].append(z[k].copy())
    result = {'new_training_fits': 0, 'evidence_level': 'post-test descriptive analysis', 'source_sha256': hashes}
    costs={}
    reference=[]
    for row in models.itertuples():
        root=ROOT/'artifacts'/('pq_iid_main' if row.seed in (42,2026,3407) else 'pq_s5b_revision/grid_extra')
        p=root/'fit_metadata'/f'n{row.n}_f{row.fold}_s{row.seed}_rP.json'
        hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
        reference.append(json.loads(p.read_text(encoding='utf-8')))
    costs['P_reference']={'fits':len(reference),'hours':sum(m['runtime_s'] for m in reference)/3600}
    for phase in ('qcp_constrained_pilot','qcp_constrained_resource'):
        paths=list((ROOT/'artifacts'/phase/'fits').glob('*.json'))
        metas=[]
        for p in paths:
            hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
            m=json.loads(p.read_text(encoding='utf-8'))
            metas.append(m.get('meta',m))
        costs[phase]={'fits':len(metas),'hours':sum(m['runtime_s'] for m in metas)/3600}
    assert costs['qcp_constrained_pilot']['fits']==48 and costs['qcp_constrained_resource']['fits']==8
    result['additional_costs']=costs
    param_rows, tails = [], []
    for route, b in blocks.items():
        d = {k: np.concatenate(v) for k,v in b.items()}
        assert len(d['rel_err']) == 480000
        for k in ('beta_hat','eta_hat','gamma_hat'):
            q = np.quantile(d[k], [.01,.25,.5,.75,.99])
            param_rows.append(dict(route=route, parameter=k, **dict(zip(('p01','q25','median','q75','p99'), q))))
        gap = (d['min_x']-d['gamma_hat'])/d['min_x']
        assert np.all(gap > 0)
        tails.append(dict(route=route, rmsre=float(np.sqrt(np.mean(d['rel_err']**2))),
                          over_10=float(np.mean(d['rel_err']>.1)), over_20=float(np.mean(d['rel_err']>.2)),
                          gamma_gap_le_1e_3=float(np.mean(gap<=1e-3)),
                          gamma_gap_le_1e_2=float(np.mean(gap<=1e-2)),
                          gamma_gap_median=float(np.median(gap))))
    pd.DataFrame(param_rows).to_csv(OUT/'parameter_distributions.csv',index=False)
    pd.DataFrame(tails).to_csv(OUT/'tail_and_boundary.csv',index=False)
    result['tail_and_boundary'] = tails
    cross = ROOT/'artifacts/qcp_cross_quantile_recovery/analysis'
    cells = pd.read_csv(cross/'truth_cell_effects.csv')
    c = cells.loc[np.isclose(cells.reliability,.95)].copy()
    assert len(c)==160 and not c.duplicated(['n','beta','gamma_over_eta']).any()
    rebuilt=pd.DataFrame(cell_mse).groupby(['n','beta','gamma_over_eta','route']).mse.mean().unstack('route')
    for row in c.itertuples():
        for route in COLORS:
            np.testing.assert_allclose(np.sqrt(rebuilt.loc[(row.n,row.beta,row.gamma_over_eta),route]),getattr(row,route.lower()+'_rmsre'),rtol=1e-12)
    c['delta_mse'] = c.p_rmsre**2-c.qcp_rmsre**2
    c['relative_rmsre_gain'] = 1-c.qcp_rmsre/c.p_rmsre
    c['difficulty_quartile'] = pd.qcut(c.p_rmsre,4,labels=['Q1','Q2','Q3','Q4'])
    total=c.delta_mse.sum()
    ordered=c.sort_values(['delta_mse','n','beta','gamma_over_eta'],ascending=[False,True,True,True])
    result['concentration'] = {'mean_delta_mse':float(total/160),
        'favorable':int((c.delta_mse>0).sum()), 'median_relative_gain':float(c.relative_rmsre_gain.median()),
        'top5_net_share':float(ordered.delta_mse.iloc[:5].sum()/total),
        'top10_net_share':float(ordered.delta_mse.iloc[:10].sum()/total)}
    quart=c.groupby('difficulty_quartile',observed=True).agg(cells=('delta_mse','size'),mean_delta_mse=('delta_mse','mean'))
    quart.to_csv(OUT/'baseline_quartiles.csv')
    c.to_csv(OUT/'target_cell_contributions.csv',index=False)
    # Reconcile recomputed pooled errors with the existing source summary.
    summary=json.loads((cross/'summary.json').read_text(encoding='utf-8'))
    for name in ('summary.json','truth_cell_effects.csv','reliability_curve.csv'):
        p=cross/name
        hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    result['analysis_code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result['checks']={'paired_keys_600_files':True,'recomputed_160_cell_risks':True,'pooled_rmsre_reconciled':True}
    for t in tails:
        np.testing.assert_allclose(t['rmsre'],summary['pooled_metrics']['0.95'][t['route']]['rmsre'],rtol=1e-12)
    (OUT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    curve=pd.read_csv(cross/'reliability_curve.csv')
    # Quantitative grid: full risk curve, discrete planned contrasts, parameter errors.
    fig,axs=plt.subplots(1,3,figsize=(10.2,3.3),constrained_layout=True)
    for route in COLORS:
        x=curve[curve.route==route]
        axs[0].plot(x.reliability,x.rmsre*100,label=route,color=COLORS[route],linestyle={'P':'--','Q':'-.','QCP':'-'}[route])
    axs[0].set(xlabel='可靠度 $R$',ylabel='寿命点 RMSRE（%）',title='A  跨寿命点风险')
    axs[0].legend(frameon=False,ncol=3,fontsize=7)
    for off,(contrast,col,mark) in enumerate([('QCP_vs_Q',COLORS['QCP'],'D'),('QCP_vs_P','#D55E00','o')]):
        rows=[summary['pairwise_comparisons'][f'x_{r:.2f}'][contrast] for r in (.90,.95,.99)]
        e=np.array([r['relative_rmsre_improvement'] for r in rows])*100
        ci=np.array([r['relative_rmsre_improvement_95ci'] for r in rows])*100
        axs[1].errorbar(np.arange(3)+(off-.5)*.13,e,yerr=np.array([e-ci[:,0],ci[:,1]-e]),fmt=mark,color=col,capsize=3,label=contrast.replace('_vs_',' 相对 '))
    axs[1].axhline(0,color='gray',ls='--',lw=.8)
    axs[1].set_xticks(range(3),['$x_{0.90}$','$x_{0.95}$','$x_{0.99}$'])
    axs[1].set(ylabel='RMSRE 相对改善（%）',title='B  三个预设寿命点的修复')
    axs[1].legend(frameon=False,fontsize=7,loc='upper left')
    for i,route in enumerate(COLORS):
        vals=[100*summary['parameter_normalized_rmse'][route][k] for k in ('beta','eta','gamma')]
        axs[2].bar(np.arange(3)+(i-1)*.24,vals,width=.24,color=COLORS[route],label=route)
    axs[2].set_yscale('log')
    axs[2].set_xticks(range(3),['$u_\\beta$','$u_\\eta$','$u_\\gamma$'])
    axs[2].set(ylabel='归一化参数 RMSE（%）',title='C  参数恢复')
    axs[2].legend(frameon=False,ncol=3,loc='upper center',bbox_to_anchor=(.5,-.13),fontsize=7)
    save(fig,'fig2_cross_quantile_recovery')
    # Paired error plot avoids meaningless jitter; cumulative contribution is descriptive.
    fig,axs=plt.subplots(1,2,figsize=(8.2,3.7),constrained_layout=True)
    for n,mark in zip((7,10,15,20),('o','s','^','D')):
        v=c[c.n==n]
        axs[0].scatter(v.p_rmsre*100,v.qcp_rmsre*100,s=23,marker=mark,label=f'n={n}',alpha=.7)
    lim=max(c.p_rmsre.max(),c.qcp_rmsre.max())*105
    axs[0].plot([0,lim],[0,lim],color='gray',ls='--',lw=.8)
    axs[0].set(xlim=(0,lim),ylim=(0,lim),xlabel='P 的单元 RMSRE（%）',ylabel='QCP 的单元 RMSRE（%）',title='A  同一真值单元的配对比较')
    axs[0].legend(frameon=False,fontsize=7)
    axs[1].plot(np.arange(161),np.r_[0,ordered.delta_mse.cumsum()/total]*100,color=COLORS['QCP'])
    axs[1].axhline(100,color='gray',ls='--',lw=.8)
    axs[1].scatter([5],[result['concentration']['top5_net_share']*100],color='black',s=20,zorder=3)
    top5=result['concentration']['top5_net_share']*100
    axs[1].annotate(f'前5个单元：净收益的{top5:.1f}%',(5,top5),xytext=(27,65),arrowprops={'arrowstyle':'->','color':'gray'},fontsize=8)
    axs[1].set(xlabel='按 ΔMSE 从大到小累计的单元数',ylabel='累计改善 / 全部净改善（%）',title='B  总体收益的集中与抵消',xlim=(0,160))
    for ax in axs: ax.grid(alpha=.16)
    save(fig,'fig3_resolution_distribution')
    print(json.dumps({'concentration':result['concentration'],'tail_and_boundary':tails},ensure_ascii=False))


if __name__=='__main__':
    main()
