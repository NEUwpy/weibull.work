"""Submission figure revision from existing evidence; no training.

Contract: four main figures retain design, compensation, paired performance,
and heterogeneous gains. Replace per-prediction constraint art with actual
validation-average feasibility. Add regional localization in the appendix.
Python; 180-230 mm working figures; editable PDF/SVG and 350 dpi PNG.
"""
from pathlib import Path
import json,hashlib,sys,os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import figures_v260 as base
import figure_english_v270 as en

ROOT=base.ROOT;OUT=ROOT/'artifacts/manuscript_figures_v270'
MAIN=ROOT/'manuscript/figures/main';APP=ROOT/'manuscript/figures/appendix'
COL=base.COL;MARK=base.MARK

def save(fig,name,appendix=False):
    dest=APP if appendix else MAIN
    for ext in ('png','pdf','svg'):
        p=dest/f'{name}.{ext}';fig.savefig(p,dpi=350,bbox_inches='tight',facecolor='white')
        if ext=='svg':p.write_text('\n'.join(x.rstrip() for x in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    en.english(fig)
    translated=ROOT/'manuscript/submission/figures'/('appendix' if appendix else 'main')
    translated.mkdir(parents=True,exist_ok=True)
    for ext in ('png','pdf','svg'):
        p=translated/f'{name}.{ext}';fig.savefig(p,dpi=350,bbox_inches='tight',facecolor='white')
        if ext=='svg':p.write_text('\n'.join(x.rstrip() for x in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    plt.close(fig)

def read(rel):
    p=base.source(ROOT/rel)
    return json.loads(p.read_text(encoding='utf-8'))

def design():
    # Reuse the design geometry, then edit its semantic links before exporting.
    original=base.save
    def finish(fig,name):
        ax=fig.axes[0]
        ax.text(.2,3.92,'研究递进（箭头不表示模型传递）',fontsize=8,color='#555555')
        ax.annotate('早期 P 的验证损失决定阈值',xy=(7.8,3.72),xytext=(6.7,4.03),
                    fontsize=8,ha='center',arrowprops={'arrowstyle':'->','lw':.7,'color':'#888888'})
        for text in ax.texts:
            if text.get_text()=='检验约束后的精度与修复效果':text.set_text('各路线分别训练并配对评价')
        save(fig,name)
    base.save=finish;base.design();base.save=original

def mechanism(blocks,models):
    original=base.save
    def finish(fig,name):
        axes=fig.axes;ax=axes[1];ax.clear()
        rows=[]
        for m in models[models.route=='QCP'].itertuples():
            v=read(f'artifacts/qcp_constrained_confirm/fit_metadata/n{m.n}_f{m.fold}_s{m.seed}_rQCP.json')
            rows.append(dict(n=m.n,fold=m.fold,seed=m.seed,ratio=v['best_val_p_loss']/v['p_constraint_limit'],q=np.sqrt(v['best_val_loss'])*100))
        d=pd.DataFrame(rows);d.to_csv(OUT/'validation_feasibility.csv',index=False)
        assert d.ratio.max()<=1+1e-10
        for n,marker in zip((7,10,15,20),('o','s','^','D')):
            z=d[d.n==n];ax.scatter(z.ratio,z.q,color=COL['QCP'],marker=marker,s=18,alpha=.55,label=f'n={n}')
        ax.axvline(1,color='#555555',ls='--',lw=1)
        ax.set(xlabel=r'验证集平均 $L_P/\tau_j$',ylabel='验证目标点 RMSRE（%）',
            title='B  实际 QCP 检查点的平均约束',xlim=(0,1.08))
        ax.text(.04,.95,'200/200 检查点可行',transform=ax.transAxes,va='top',fontsize=8)
        ax.legend(frameon=False,fontsize=7,loc='lower left',ncol=2)
        axes[2].set_title('C  仿真测试预测的参数贡献')
        axes[3].set_title('D  同一预测内的抵消')
        # Equal axes in a small inset clarify the P/QCP cloud; main axes retain Q.
        inset=axes[3].inset_axes([.12,.66,.36,.28])
        inset.plot([0,30],[0,30],'--',color='#AAAAAA',lw=.7)
        for route in ('P','QCP'):
            z=models[models.route==route];inset.scatter(z.mean_magnitude*100,z.mean_absolute_error*100,s=8,color=COL[route],marker=MARK[route],alpha=.6)
        inset.set(xlim=(5,30),ylim=(5,30),title='P / QCP 局部（等比例）');inset.set_aspect('equal');inset.tick_params(labelsize=6);inset.title.set_fontsize(7)
        for n in (7,10,15,20):
            z=models[(models.route=='Q')&(models.n==n)]
            axes[3].annotate(f'n={n}',(z.mean_magnitude.mean()*100,z.mean_absolute_error.mean()*100),xytext=(5,-10 if n==20 else 5),textcoords='offset points',fontsize=7)
        save(fig,name)
    base.save=finish;base.mechanism(blocks,models);base.save=original

def performance(summary):
    original=base.save
    def finish(fig,name):
        ax=fig.axes[1];inset=ax.inset_axes([.38,.72,.31,.22])
        for i,(key,col,mk) in enumerate([('Q_vs_P',COL['Q'],'^'),('QCP_vs_Q',COL['QCP'],'s'),('QCP_vs_P','#D55E00','o')]):
            row=summary['pairwise_comparisons']['x_0.95'][key];v=100*row['relative_rmsre_improvement'];ci=np.array(row['relative_rmsre_improvement_95ci'])*100
            inset.errorbar([i],[v],yerr=[[v-ci[0]],[ci[1]-v]],fmt=mk,color=col,capsize=3,markersize=4)
        inset.set(ylim=(0,5),title='$x_{0.95}$ 局部放大');inset.title.set_fontsize(8)
        inset.set_xticks(range(3),['Q/P','QCP/Q','QCP/P'],fontsize=6);inset.tick_params(axis='y',labelsize=6)
        save(fig,name)
    base.save=finish;base.performance(summary);base.save=original

def heterogeneity(cells):
    original=base.save
    def finish(fig,name):
        ax=fig.axes[1]
        save(fig,name)
    base.save=finish;base.heterogeneity(cells);base.save=original
    c=cells[np.isclose(cells.reliability,.95)].copy();c['delta']=c.p_rmsre**2-c.qcp_rmsre**2
    top=c.sort_values(['delta','n','beta','gamma_over_eta'],ascending=[False,True,True,True]).head(5)
    top.to_csv(OUT/'top5_cells.csv',index=False)
    fig,axs=plt.subplots(2,2,figsize=(7.2,5.0),constrained_layout=True)
    c['gain']=100*(1-c.qcp_rmsre/c.p_rmsre);lim=float(np.ceil(c.gain.abs().max()/5)*5)
    for n,ax in zip((7,10,15,20),axs.flat):
        z=c[c.n==n].pivot(index='gamma_over_eta',columns='beta',values='gain').sort_index()
        im=ax.imshow(z,origin='lower',aspect='auto',cmap='RdBu',norm=TwoSlopeNorm(vmin=-lim,vcenter=0,vmax=lim))
        ax.set_xticks(range(len(z.columns)),[f'{v:g}' for v in z.columns]);ax.set_yticks(range(len(z.index)),[f'{v:g}' for v in z.index])
        ax.set(xlabel=r'形状参数 $\beta$',ylabel=r'位置比 $\gamma/\eta$',title=f'n = {n}')
        for j,row in enumerate(top.itertuples(),1):
            if row.n==n:
                x=list(z.columns).index(row.beta);y=list(z.index).index(row.gamma_over_eta)
                ax.text(x,y,str(j),ha='center',va='center',color='black',fontsize=8,bbox=dict(facecolor='white',edgecolor='black',boxstyle='circle,pad=.15'))
    fig.colorbar(im,ax=axs,label='QCP 相对 P 的单元 RMSRE 改善（%）',shrink=.8)
    save(fig,'figB4_regional_gains',True)

def appendix(summary):
    common=read('artifacts/qcp_main_analysis/analysis/summary.json')
    resource=pd.read_csv(base.source(ROOT/'artifacts/qcp_main_analysis/analysis/resource_cells.csv'))
    # Main comparison repeats are removed; retain compensation and optimization depth.
    fig,axs=plt.subplots(1,2,figsize=(7.2,2.9),constrained_layout=True)
    for i,m in enumerate(COL):
        value=common['diagnostics'][m]['mean_exact_cancellation_index']
        axs[0].scatter(i,value,color=COL[m],marker=MARK[m],s=42);axs[0].text(i,value+.04,f'{value:.3f}',ha='center',fontsize=8)
    axs[0].set(xticks=range(3),xticklabels=list(COL),xlim=(-.4,2.4),ylim=(0,1.05),ylabel='平均补偿指数',title='A  参数贡献抵消')
    # Inspect the saved schema explicitly; resource table is long by route.
    for i,m in enumerate(COL):
        vals=resource.loc[resource.route==m,'best_epoch'].to_numpy()
        axs[1].boxplot(vals,positions=[i],widths=.45,patch_artist=True,boxprops={'facecolor':COL[m],'alpha':.4},medianprops={'color':'black'},showfliers=False)
    axs[1].axhline(600,ls='--',color='#888888',lw=.8);axs[1].text(.0,610,'当前上限：600轮',fontsize=7)
    axs[1].set(xticks=range(3),xticklabels=list(COL),ylim=(0,650),ylabel='最佳检查点轮次',title='B  选定轮次分布')
    save(fig,'figB1_common_budget_results',True)
    size=read('artifacts/qcp_sample_size_analysis/analysis/summary.json');d=pd.DataFrame(size['by_n'])
    fig,axs=plt.subplots(1,2,figsize=(7.2,3),constrained_layout=True)
    for m in COL:
        key=m.lower()+'_rrmse';v=d[key].to_numpy()*100;lo=d[key+'_ci_low'].to_numpy()*100;hi=d[key+'_ci_high'].to_numpy()*100
        axs[0].errorbar(d.n,v,yerr=[v-lo,hi-v],color=COL[m],marker=MARK[m],capsize=3,label=m)
    for m in ('Q','QCP'):
        key=m.lower()+'_equivalent_added_n';v=d[key].to_numpy()
        axs[1].errorbar(d.n,v,yerr=[v-d[key+'_ci_low'],d[key+'_ci_high']-v],color=COL[m],marker=MARK[m],capsize=3,label=m)
    axs[0].set(xlabel='单次估计的寿命观测数 n',ylabel='目标点 RMSRE（%）',title='A  样本量与误差')
    axs[1].set(xlabel='单次估计的寿命观测数 n',ylabel='相对 P 的等效新增观测数',title='B  经验曲线换算')
    for ax in axs:ax.legend(frameon=False,fontsize=8);ax.set_xticks((7,10,15,20))
    save(fig,'figB2_sample_size_equivalence',True)
    curve=pd.read_csv(base.source(ROOT/'artifacts/qcp_cross_quantile_recovery/analysis/reliability_curve.csv'))
    fig,axs=plt.subplots(1,2,figsize=(7.2,3),constrained_layout=True)
    for m in COL:
        z=curve[curve.route==m];axs[0].plot(z.reliability,z.rmsre*100,color=COL[m],ls={'P':'--','Q':'-.','QCP':'-'}[m],label=m)
        vals=[100*summary['parameter_normalized_rmse'][m][k] for k in ('beta','eta','gamma')]
        axs[1].scatter(np.arange(3)+(list(COL).index(m)-1)*.15,vals,color=COL[m],marker=MARK[m],label=m)
    for r in (.90,.95,.99):axs[0].axvline(r,color='#BBBBBB',ls=':',lw=.8)
    axs[0].annotate('训练点 0.95',xy=(.95,16),xytext=(.68,25),arrowprops={'arrowstyle':'->','color':'#777777'},fontsize=7)
    axs[0].set(xlabel='可靠度 R',ylabel='寿命点 RMSRE（%）',title='A  较宽可靠度范围')
    axs[1].set(yscale='log',xticks=range(3),xticklabels=[r'$u_\beta$',r'$u_\eta$',r'$u_\gamma$'],ylabel='归一化参数 RMSE（%，对数轴）',title='B  参数恢复')
    for ax in axs:ax.legend(frameon=False,fontsize=7,ncol=3)
    save(fig,'figB3_extended_reliability',True)

def historical():
    # Redraw historic figures from their existing calculations; no image editing.
    import importlib.util
    path=ROOT/'code/study02pq/paper_figures.py';base.source(path)
    spec=importlib.util.spec_from_file_location('historic_paper_figures',path);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    from matplotlib.text import Text
    def save_history(fig,name,out):
        is_c=name=='fig2_mechanism'
        translations={'Fig 2 · Why direct target loss is not a fixed parameter weighting':'附录图 C1：静态代理检验（早期300/20预算）',
            'Fig 3 · Exploratory audit: target-aligned training redistributes $x_{0.95}$ error':'附录图 D1：早期300/20预算的误差分布'}
        translations.update({
            '(a) What changes during backpropagation':'A  输出误差空间的梯度',
            'fixed normalized parameter-error rule':'固定的归一化参数损失',
            'current B5 sensitivity is recalculated at each prediction':'目标敏感度随预测参数改变',
            '(b) A truth-point static matrix\ndoes not replace Q':'B  静态代理未复现 Q 的精度',
            'B5 rRMSE (24-cell equal weight)':'目标点 RMSRE（24模型单元等权）',
            'P\nparameter loss':'P\n参数损失', 'M95\nfixed local matrix':'M95\n静态局部矩阵',
            'Q\ndirect B5 loss':'Q\n目标寿命点损失',
            '(c) The local rule improves, but what it misses\nis larger':'C  遗漏项反转局部近似的改善',
            'local rule\n(better)':'局部项\n（降低）','missed error\n(worse)':'遗漏项\n（增加）','actual B5\n(worse)':'实际目标误差\n（增加）',
            r'M95 $-$ P mean squared B5 error':'M95 − P 的目标点相对均方误差',
            '(a) Q shifts the error distribution toward\nunderestimation (exploratory)':'A  有符号误差分布',
            '(b) Q is slightly worse at moderate errors\nbut better in the far tail (exploratory)':'B  绝对误差的超越比例',
            '(c) Under a guaranteed-life interpretation, Q\nreduces overestimation but increases underestimation':'C  高估与低估的再分配',
            '(d) Decomposing the 5.91% MSE difference\nshows opposite directional changes':'D  高估与低估的平方误差贡献',
            r'signed relative error $(\hat x_{0.95}-x_{0.95})/x_{0.95}$, %':'有符号相对误差（%）',
            'empirical cumulative probability, %':'经验累计比例（%）',
            'absolute relative-error threshold, %':'绝对相对误差阈值（%）',
            'predictions exceeding threshold, %':'超过阈值的预测比例（%）',
            'one-sided relative-error threshold, %':'单侧相对误差阈值（%）',
            'predictions beyond threshold, %':'超过阈值的预测比例（%）',
            'P: overestimate':'P：高估','P: underestimate':'P：低估','Q: overestimate':'Q：高估','Q: underestimate':'Q：低估',
            'overestimation\ncontribution':'高估侧贡献','underestimation\ncontribution':'低估侧贡献',
        })
        for item in fig.findobj(Text):
            s=item.get_text();s=translations.get(s,s).replace('$P_{equal}$','P').replace('$Q_{param}$','Q').replace('rRMSE','RMSRE').replace('B5',r'$x_{0.95}$')
            if s.startswith('Fig 3'):s='附录图 D1：早期300/20预算的误差分布'
            s=s.replace('mean bias:','平均偏差：').replace('overestimate MSE:','高估侧MSE：').replace('underestimate MSE:','低估侧MSE：').replace('cells','模型单元')
            s=s.replace('paired change Q−P in MSE contribution,','Q−P 的配对MSE贡献差，')
            item.set_text(s)
        if is_c:
            fig.axes[1].patches[0].set_facecolor(COL['P']);fig.axes[1].patches[2].set_facecolor(COL['Q'])
            fig.axes[1].set_xticks([0,1,2],['P\n参数损失','M95\n静态局部矩阵','Q\n目标寿命点损失'])
            fig.axes[2].set_xticks([0,1,2],['局部项\n（降低）','遗漏项\n（增加）','实际目标误差\n（增加）'])
        else:
            fig.axes[3].set_xticks([0,1],['高估侧贡献','低估侧贡献'])
        save(fig,'figC1_target_sensitivity_mechanism' if is_c else 'figD1_error_distribution',True)
    old._save=save_history
    old.C_BLUE=COL['P'];old.C_GREEN=COL['Q'];old.C_ORANGE=COL['Q']
    for rel in ('pq_mechanism_closure/summary.json','pq_mechanism_closure/pmq_24_cells.csv','pq_engineering_audit/cell_metrics.csv','pq_engineering_audit/summary.json'):
        p=ROOT/'artifacts'/rel
        if p.exists():base.source(p)
    for sub in ('pq_iid_main/evidence','pq_s5b_revision/grid_extra/evidence'):
        for p in (ROOT/'artifacts'/sub).glob('*.npz'):base.source(p)
    old.fig2_mechanism(str(ROOT/'artifacts'),str(APP))
    old.fig3_error_distribution(str(ROOT/'artifacts'),str(APP))

def main():
    OUT.mkdir(parents=True,exist_ok=True);base.OUT=OUT
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],'font.size':9,'axes.unicode_minus':False,'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
    cross='artifacts/qcp_cross_quantile_recovery/analysis/'
    summary=read(cross+'summary.json');cells=pd.read_csv(base.source(ROOT/(cross+'truth_cell_effects.csv')))
    blocks,models,residual=base.contribution_data()
    design();mechanism(blocks,models);performance(summary);heterogeneity(cells);appendix(summary);historical()
    base.source(Path(en.__file__))
    outputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in (MAIN,APP,OUT,ROOT/'manuscript/submission/figures/main',ROOT/'manuscript/submission/figures/appendix') for p in folder.glob('*') if p.suffix in ('.png','.pdf','.svg','.csv')}
    (OUT/'manifest.json').write_text(json.dumps({'new_training_fits':0,'max_identity_residual':residual,'source_sha256':base.SHA,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'base_script_sha256':hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest(),'output_sha256':outputs},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS main=4 appendix=6 exact_contribution_residual=',residual)
if __name__=='__main__':main()
