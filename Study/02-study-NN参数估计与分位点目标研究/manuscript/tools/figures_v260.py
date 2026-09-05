"""Four manuscript figures from fixed predictions; no training or model selection.

Exact contribution identity: appendix C.1. Distribution ranges are not CIs.
Paired contrast CIs are read from the existing crossed-bootstrap analysis.
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / 'manuscript/figures/main'
OUT = ROOT / 'artifacts/manuscript_figures_v260'
COL = {'P': '#777777', 'Q': '#0072B2', 'QCP': '#009E73'}
MARK = {'P': 'o', 'Q': '^', 'QCP': 's'}
SHA = {}


def source(p):
    SHA[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p


def save(fig, name):
    for ext in ('png', 'pdf', 'svg'):
        fig.savefig(FIG / f'{name}.{ext}', dpi=350, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def design():
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.set(xlim=(0, 10), ylim=(0, 6))
    ax.axis('off')

    def box(x, y, w, h, label, color='#555555'):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.05,rounding_size=0.10',
                                   facecolor='white', edgecolor=color, linewidth=1.4))
        ax.text(x+w/2, y+h/2, label, ha='center', va='center', fontsize=10, color=color)

    def arrow(start, end, color='#555555'):
        ax.annotate('', end, start, arrowprops={'arrowstyle': '->', 'color': color, 'lw': 1.3})

    box(.2, 4.8, 2.4, .8, '同一寿命样本\n排序与训练折标准化')
    box(3.5, 4.8, 2.4, .8, '同一网络结构\n按样本量分别训练')
    box(6.8, 4.8, 2.9, .8, r'输出 $\hat\beta,\hat\eta,\hat\gamma$'+'\n计算所需寿命点')
    arrow((2.7, 5.2), (3.4, 5.2))
    arrow((6, 5.2), (6.7, 5.2))
    ax.text(5, 4.25, '共享数据划分、初始化与最大训练预算；改变训练与验证选点目标', ha='center', fontsize=9)
    box(.2, 2.6, 2.4, 1.1, 'P：参数恢复参照\n'+r'$\min L_P$', COL['P'])
    box(3.5, 2.6, 2.4, 1.1, 'Q：目标寿命点对齐\n'+r'$\min L_Q$', COL['Q'])
    box(6.8, 2.6, 2.9, 1.1, 'QCP：保留任务目标\n'+r'$\min L_Q\quad\mathrm{s.t.}\ L_P\leq\tau$', COL['QCP'])
    arrow((2.7, 3.15), (3.4, 3.15))
    ax.text(3.05, 3.55, '目标对齐', ha='center', fontsize=8)
    arrow((4.7, 2.5), (4.7, 1.8), COL['Q'])
    box(3.3, .7, 3.0, 1.0, '目标点总体误差略降\n参数补偿与跨寿命点退化', COL['Q'])
    arrow((6.4, 1.2), (8.3, 2.5), COL['QCP'])
    ax.text(7.8, 1.25, '限制参数偏离', ha='center', fontsize=9, color=COL['QCP'])
    ax.text(1.4, 1.4, '比较 P 与 Q\n检验收益与代价', ha='center', va='center', fontsize=10)
    ax.text(8.3, .35, '检验约束后的精度与修复效果', ha='center', fontsize=9)
    save(fig, 'fig1_research_design')


def contribution_data():
    models = pd.read_csv(source(ROOT/'artifacts/qcp_main_analysis/analysis/model_cells.csv'))
    assert len(models) == 200 and not models.duplicated(['n', 'fold', 'seed']).any()
    old = ROOT/'归档/旧实验/四路线同预算敏感性/artifacts/equal_budget_sensitivity'
    if (ROOT/'artifacts/equal_budget_sensitivity').exists():
        old = ROOT/'artifacts/equal_budget_sensitivity'
    blocks = {r: [] for r in COL}
    rows = []
    max_residual = 0.
    for m in models.itertuples():
        paired = None
        for route in COL:
            root = ROOT/'artifacts/qcp_constrained_confirm' if route == 'QCP' else old
            path = source(root/'evidence'/f'n{m.n}_f{m.fold}_s{m.seed}_r{route}.npz')
            with np.load(path) as z:
                keys = np.column_stack([z[k] for k in ('keys_beta', 'keys_gamma_over_eta', 'keys_n', 'keys_repeat_id')])
                assert len(keys) == 2400 and len(np.unique(keys, axis=0)) == 2400
                if paired is None:
                    paired = keys
                else:
                    np.testing.assert_array_equal(keys, paired)
                b, g = z['keys_beta'].astype(float), 1000*z['keys_gamma_over_eta'].astype(float)
                bh, eh, gh = [z[k].astype(float) for k in ('beta_hat', 'eta_hat', 'gamma_hat')]
            t0, t1 = (-np.log(.95))**(1/b), (-np.log(.95))**(1/bh)
            truth = g+1000*t0
            cb = .5*(1000+eh)*(t1-t0)/truth
            ce = .5*(eh-1000)*(t0+t1)/truth
            cg = (gh-g)/truth
            err = (gh+eh*t1-truth)/truth
            values = np.column_stack((cb, ce, cg, err))
            assert np.isfinite(values).all()
            np.testing.assert_allclose(cb+ce+cg, err, rtol=1e-11, atol=1e-13)
            max_residual = max(max_residual, float(np.max(np.abs(cb+ce+cg-err))))
            magnitude = np.abs(values[:, :3]).sum(axis=1)
            cancel = np.divide(magnitude-np.abs(err), magnitude, out=np.zeros_like(err), where=magnitude>0)
            blocks[route].append(values)
            rows.append(dict(route=route, n=m.n, fold=m.fold, seed=m.seed,
                             mean_magnitude=float(magnitude.mean()), mean_absolute_error=float(np.abs(err).mean()),
                             compensation=float(cancel.mean()), rmsre=float(np.sqrt(np.mean(err**2)))))
    models_out = pd.DataFrame(rows)
    models_out.to_csv(OUT/'compensation_model_cells.csv', index=False)
    quantiles = []
    for route in COL:
        blocks[route] = np.concatenate(blocks[route])
        assert blocks[route].shape == (480000, 4)
        for i, term in enumerate(('c_beta', 'c_eta', 'c_gamma', 'sum')):
            v = np.quantile(blocks[route][:, i], [.05, .25, .5, .75, .95])
            quantiles.append(dict(route=route, term=term, **dict(zip(('p05','p25','p50','p75','p95'), v))))
    pd.DataFrame(quantiles).to_csv(OUT/'contribution_quantiles.csv', index=False)
    return blocks, models_out, max_residual


def mechanism(blocks, models):
    fig, axs = plt.subplots(2, 2, figsize=(9, 7.2), constrained_layout=True)
    ub = np.linspace(-.60, 1.2, 250)
    ue = np.linspace(-.75, .8, 250)
    x, y = np.meshgrid(ub, ue)
    t = -np.log(.95)
    target = 100+1000*t**(1/1.5)
    error = (100+1000*(1+y)*t**(1/(1.5*(1+x)))-target)/target
    equivalent = (target-100)/(1000*t**(1/(1.5*(1+ub))))-1
    for i, ax in enumerate(axs[0]):
        contours = ax.contour(x, y, abs(error)*100, levels=[1, 5, 10, 20, 40], colors='#BBBBBB', linewidths=.8)
        ax.clabel(contours, levels=[5, 20, 40], fmt=lambda v: f'{v:g}%', fontsize=7)
        ax.plot(ub, equivalent, '--', color=COL['Q'], lw=1.8, label='等寿命点轨迹')
        ax.scatter([0], [0], color=COL['P'], marker='o', s=30, zorder=4, label='真值')
        ax.axhline(0, lw=.6, color='#DDDDDD'); ax.axvline(0, lw=.6, color='#DDDDDD')
        ax.set(xlim=(-.6,1.2), ylim=(-.75,.8), xlabel=r'形状相对误差 $u_\beta$', ylabel=r'尺度相对误差 $u_\eta$')
        if i:
            ax.add_patch(Circle((0,0), .52, facecolor=COL['QCP'], alpha=.15, edgecolor=COL['QCP']))
            ax.text(.02, .45, r'$L_P\leq\tau$', color=COL['QCP'], ha='center')
            ax.set_title('B  参数约束缩小可选范围', loc='left')
        else:
            ax.set_title('A  同一寿命点对应多组参数', loc='left')
        ax.legend(frameon=False, loc='upper right', fontsize=8)
    labels = [r'$c_\beta$', r'$c_\eta$', r'$c_\gamma$', r'$e=\sum c$']
    ax = axs[1,0]
    for j, route in enumerate(COL):
        v = np.quantile(blocks[route], [.05,.25,.5,.75,.95], axis=0)*100
        pos = np.arange(4)+(j-1)*.22
        ax.vlines(pos, v[0], v[4], color=COL[route], lw=1, alpha=.8)
        ax.vlines(pos, v[1], v[3], color=COL[route], lw=4)
        ax.scatter(pos, v[2], marker=MARK[route], color=COL[route], s=22, label=route, zorder=3)
    ax.axhline(0, color='#555555', ls='--', lw=.8)
    ax.set_xticks(range(4), labels)
    ax.set(ylabel='有符号相对贡献（%）', title='C  实测参数贡献与相加后的误差')
    ax.legend(frameon=False, ncol=3, fontsize=8)
    ax = axs[1,1]
    limit = models.mean_magnitude.max()*105
    ax.plot([0,limit],[0,limit],'--',color='#AAAAAA',lw=.8,label='无抵消：两者相等')
    for route in COL:
        d=models[models.route==route]
        ax.scatter(d.mean_magnitude*100,d.mean_absolute_error*100,marker=MARK[route],s=14,color=COL[route],alpha=.5,label=route)
    ax.set(xlabel=r'分量绝对值之和的均值（%）',ylabel='相加后绝对误差的均值（%）',
           title='D  同一预测内的抵消', xlim=(0,limit), ylim=(0, max(25,models.mean_absolute_error.max()*110)))
    ax.legend(frameon=False, fontsize=7, loc='upper right')
    save(fig, 'fig2_parameter_compensation')


def performance(summary):
    fig, axs=plt.subplots(1,2,figsize=(9,3.6),constrained_layout=True)
    levels=(.90,.95,.99)
    for i,route in enumerate(COL):
        vals=[summary['pooled_metrics'][f'{r:.2f}'][route]['rmsre']*100 for r in levels]
        axs[0].scatter(np.arange(3)+(i-1)*.12,vals,marker=MARK[route],s=45,color=COL[route],label=route)
    axs[0].set_xticks(range(3),['$x_{0.90}$','$x_{0.95}$\n训练目标','$x_{0.99}$'])
    axs[0].set(ylabel='总体 RMSRE（%）',title='A  三个预设寿命点的误差',ylim=(0,40))
    axs[0].legend(frameon=False,ncol=3)
    for i,(key,color,marker) in enumerate([('Q_vs_P',COL['Q'],'^'),('QCP_vs_Q',COL['QCP'],'s'),('QCP_vs_P','#D55E00','o')]):
        rows=[summary['pairwise_comparisons'][f'x_{r:.2f}'][key] for r in levels]
        effects=np.array([r['relative_rmsre_improvement'] for r in rows])*100
        ci=np.array([r['relative_rmsre_improvement_95ci'] for r in rows])*100
        axs[1].errorbar(np.arange(3)+(i-1)*.15,effects,yerr=[effects-ci[:,0],ci[:,1]-effects],fmt=marker,markersize=4,color=color,capsize=4,elinewidth=1.2,label=key.replace('_vs_',' 相对 '))
    axs[1].axhline(0,color='#888888',ls='--',lw=.8)
    axs[1].set_xticks(range(3),['$x_{0.90}$','$x_{0.95}$','$x_{0.99}$'])
    axs[1].set(ylabel='RMSRE 相对改善（%）',title='B  配对比较及 95% 区间')
    axs[1].legend(frameon=False,fontsize=8,loc='lower center')
    for ax in axs: ax.grid(axis='y',alpha=.15)
    save(fig,'fig3_cross_life_performance')


def heterogeneity(cells):
    fig,axs=plt.subplots(1,2,figsize=(9,3.9),constrained_layout=True)
    ax=axs[0]
    rng=np.random.default_rng(260)
    counts=[]
    for j,route in enumerate(('Q','QCP')):
        for i,r in enumerate((.90,.95,.99)):
            d=cells[np.isclose(cells.reliability,r)]
            assert len(d)==160
            values=100*(1-d[route.lower()+'_rmsre']/d.p_rmsre).to_numpy()
            p=i+(j-.5)*.30
            ax.scatter(p+rng.uniform(-.065,.065,len(values)),values,s=8,color=COL[route],alpha=.28,rasterized=True)
            q=np.quantile(values,[.25,.5,.75])
            ax.vlines(p,q[0],q[2],color=COL[route],lw=5)
            ax.scatter([p],[q[1]],color='white',edgecolor=COL[route],marker='D',s=26,zorder=4)
            counts.append(dict(reliability=r,route=route,favorable=int((values>0).sum()),median_effect=float(q[1])))
    ax.axhline(0,color='#555555',ls='--',lw=.8)
    for route in ('Q','QCP'): ax.scatter([],[],color=COL[route],label=route+' 相对 P',s=20)
    ax.set_xticks(range(3),['$x_{0.90}$','$x_{0.95}$','$x_{0.99}$'])
    ax.set(ylabel='单元 RMSRE 相对改善（%）',title='A  160 个真值单元的效应分布')
    ax.legend(frameon=False,fontsize=8,loc='lower left')
    c=cells[np.isclose(cells.reliability,.95)].copy()
    c['delta']=c.p_rmsre**2-c.qcp_rmsre**2
    ordered=c.sort_values(['delta','n','beta','gamma_over_eta'],ascending=[False,True,True,True])
    cumulative=np.r_[0,ordered.delta.cumsum()/ordered.delta.sum()]*100
    axs[1].plot(np.arange(161),cumulative,color=COL['QCP'],lw=1.8)
    axs[1].axhline(100,color='#888888',ls='--',lw=.8)
    axs[1].scatter([5],[cumulative[5]],color='black',s=18)
    axs[1].annotate(f'前5个单元：净收益的{cumulative[5]:.1f}%',(5,cumulative[5]),xytext=(25,65),arrowprops={'arrowstyle':'->','color':'gray'},fontsize=8)
    axs[1].set(xlabel='按 ΔMSE 从大到小累计的单元数',ylabel='累计改善 / 全部净改善（%）',title='B  目标点净收益的集中与抵消',xlim=(0,160))
    for ax in axs: ax.grid(axis='y',alpha=.15)
    pd.DataFrame(counts).to_csv(OUT/'cell_effect_checks.csv',index=False)
    save(fig,'fig4_cell_heterogeneity')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    FIG.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
                         'font.size':9,'axes.unicode_minus':False,'svg.fonttype':'none','pdf.fonttype':42,
                         'axes.spines.top':False,'axes.spines.right':False})
    cross=ROOT/'artifacts/qcp_cross_quantile_recovery/analysis'
    summary=json.loads(source(cross/'summary.json').read_text(encoding='utf-8'))
    cells=pd.read_csv(source(cross/'truth_cell_effects.csv'))
    blocks,models,residual=contribution_data()
    for route in COL:
        np.testing.assert_allclose(np.sqrt(np.mean(blocks[route][:,3]**2)),summary['pooled_metrics']['0.95'][route]['rmsre'],rtol=1e-12)
    design(); mechanism(blocks,models); performance(summary); heterogeneity(cells)
    names=('fig1_research_design','fig2_parameter_compensation','fig3_cross_life_performance','fig4_cell_heterogeneity')
    figure_paths=[FIG/f'{name}.{ext}' for name in names for ext in ('png','pdf','svg')]
    outputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in figure_paths+list(OUT.glob('*.csv'))}
    record={'new_training_fits':0,'evidence_level':'existing predictions; post-test descriptive decomposition',
            'prediction_rows_per_route':480000,'paired_model_cells':200,'max_identity_residual':residual,
            'mean_compensation':models.groupby('route').compensation.mean().to_dict(),
            'source_sha256':SHA,'output_sha256':outputs,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k not in ('source_sha256','output_sha256')},ensure_ascii=False))


if __name__=='__main__':
    main()
