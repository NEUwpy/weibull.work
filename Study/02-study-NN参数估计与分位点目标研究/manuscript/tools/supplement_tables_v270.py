"""Render only verified full-matrix supplementary results into reviewable tables."""
from pathlib import Path
import json

S=Path(__file__).resolve().parents[2]
LABEL={'P':'P','Q':'Q','P_QSELECT':'P_QSELECT','QP':'QP','QCP':'QCP','QMULTI':'QMULTI'}

def main():
 d=json.loads((S/'artifacts/submission_controls_v1/analysis/summary.json').read_text())
 assert d['training_trajectories']==600 and d['q_reproduction_all_200']
 zh='''### F.1 对照设计与完整性

补充对照沿用原40参数组合、4样本量、5折、10种子和600/60最大预算，独立新增600条训练轨迹。P_QSELECT仍按参数损失训练，但检查点选择与早停均按验证LQ；与Q的比较因此固定了验证准则，实际停止轮次允许不同。Q重跑时旁路记录同一原生早停轨迹内满足原QCP阈值的最佳验证Q检查点，记为Q_FEAS；旁路记录不影响训练或早停，无可行检查点时不回退、不剔除后重新汇总。QMULTI采用三个寿命点的等权相对平方损失，训练、验证选点与早停均使用该平均损失：

$$
L_{\\mathrm{multi}}=\\frac13\\sum_{R\\in\\{0.90,0.95,0.99\\}}\\operatorname{mean}\\left[\\left(\\frac{\\hat x_R-x_R}{x_R}\\right)^2\\right].
$$

三个新轨迹各包含200个模型单元。所有新旧比较均核对训练/验证/测试行、初始化、标准化器、首轮批顺序和网络标识；重跑Q的200个目标指标及最佳轮次均重现原结果。保存逐轮验证历史和选定模型状态。P、QP和QCP复用既有同预算预测，新Q使用重跑结果；新预测保留双精度，旧预测参数的存储精度不回写改变。

该协议在旧测试结果已知后确定，数据仍为原48,000组仿真样本，不是独立新数据确认。每条路线480,000条预测中的训练种子重复仍保留。以下区间使用原按n分层fold×全局seed的配对经验bootstrap规则，200,000次重采样，未作多重比较校正。

### F.2 完整结果

**表F1　共同验证与多点监督的总体RMSRE及参数损失**

| 路线 | x0.90 RMSRE | x0.95 RMSRE | x0.99 RMSRE | 平均参数损失 |
|---|---:|---:|---:|---:|
'''
 en='''### F.1 Controls and completeness

The supplementary experiment retained the original 40 parameter combinations, four sample sizes, five folds, ten seeds, and 600/60 maximum budget, adding 600 training trajectories in a separate output directory. P_QSELECT trained on parameter loss but used validation LQ for both checkpoint selection and early stopping. Its contrast with Q therefore held the validation criterion fixed while allowing stopping epochs to vary. Repeated Q fits recorded the best validation-Q checkpoint satisfying the original QCP threshold within the same native early-stopping trajectory (Q_FEAS), without changing updates or stopping. Unavailable feasible checkpoints were neither replaced by unconstrained Q nor silently discarded. QMULTI trained, selected, and stopped using the equally weighted mean of three relative squared life-point losses:

$$
L_{\\mathrm{multi}}=\\frac13\\sum_{R\\in\\{0.90,0.95,0.99\\}}\\operatorname{mean}\\left[\\left(\\frac{\\hat x_R-x_R}{x_R}\\right)^2\\right].
$$

Each new trajectory type comprised 200 model units. Train/validation/test rows, initialization, standardizer, first-epoch batch order, and network identifiers were checked against the original pairing. All 200 repeated Q target metrics and selected epochs reproduced the original records. Validation histories and selected states were saved. Existing common-budget P, QP, and QCP predictions were reused; Q predictions came from the repeated fits. New predictions retained double precision; the stored precision of historical predictions was not changed.

These controls were specified after earlier test results were known and reused the original 48,000 simulation samples. They are not independent fresh-data confirmation. Each route's 480,000 prediction rows retain the repeated-seed structure. Intervals used the existing sample-size-stratified fold-by-global-seed paired empirical bootstrap, with 200,000 replicates and no multiplicity adjustment.

### F.2 Full results

**Table F1. Pooled RMSRE and parameter loss for supplementary controls.**

| Procedure | x0.90 RMSRE | x0.95 RMSRE | x0.99 RMSRE | Mean parameter loss |
|---|---:|---:|---:|---:|
'''
 for m in LABEL:
  row=f"| {m} | "+' | '.join(f"{d['pooled'][r][m]*100:.4f}%" for r in ['0.9','0.95','0.99'])+f" | {d['parameter_loss'][m]:.6f} |\n"
  zh+=row;en+=row
 zh+='\n**表F2　补充对照的配对RMSRE相对改善**\n\n| 寿命点R | 对比（前者相对后者） | 改善 | 95%经验区间 | 有利模型单元 | 有利种子 |\n|---|---|---:|---:|---:|---:|\n'
 en+='\n**Table F2. Paired relative RMSRE improvements.**\n\n| Reliability R | Contrast (first vs second) | Improvement | 95% empirical interval | Favorable model units | Favorable seeds |\n|---|---|---:|---:|---:|---:|\n'
 for key,v in d['contrasts'].items():
  r,c=key.split(':');lo,hi=v['relative_rrmse_improvement_95ci'];a=f'{100*v["relative_improvement"]:.3f}%';c=c.replace('_vs_',' vs ')
  for lang in ['zh','en']:
   interval=f'{lo*100:.3f}% '+('至' if lang=='zh' else 'to')+f' {hi*100:.3f}%'
   row=f'| {r} | {c} | {a} | {interval} | {v["favorable_model_units"]}/200 | {v["favorable_seeds"]}/10 |\n'
   if lang=='zh':zh+=row
   else:en+=row
 f=d['q_feas'];a=f['available'];minimum=f['minimum_observed_val_p_over_limit']
 zh+=f'\nQ_FEAS在{a}/200条原生Q轨迹内可用；全部记录轮次的最小验证参数损失/阈值比为{minimum:.3f}。'
 en+=f'\nQ_FEAS was available in {a}/200 native Q trajectories; the smallest recorded validation parameter-loss/threshold ratio was {minimum:.3f}. '
 if a==0:
  zh+='因此没有可汇总的Q_FEAS测试精度。该结果排除了在本批Q原生早停轨迹中仅靠可行选点实现同一修复的可能性，不能推断延长训练或改变优化策略后仍无可行点。\n'
  en+='There was therefore no Q_FEAS test-accuracy result to aggregate. Feasible selection alone could not supply the repair within these native Q trajectories; this does not establish infeasibility under longer training or a different optimizer.\n'
 else:
  zh+='可用范围与完整矩阵不同，不将其子集误差与200单元总体误差直接比较。\n'
  en+='Its available subset differs from the full matrix and is not directly compared with 200-unit pooled errors.\n'
 zh+='\nQMULTI对表中的三个寿命点均作直接监督，故其表现不是未监督寿命点的泛化证据。参数损失与寿命点风险需分别比较；当前固定等权设置也不代表多点权重最优。新运行加入逐轮记录且执行环境负载不同，其计时仅随元数据保存，不跨批次宣称速度优势。来源为 `artifacts/submission_controls_v1/analysis/` 的summary、model_mse、parameter_loss、resources与manifest。\n'
 en+='\nQMULTI directly supervised all three life points in the table; its performance is not evidence of generalization to unsupervised life points. Parameter loss and life-point risk require separate comparisons, and fixed equal weighting is not claimed optimal. New runs recorded epoch histories under a different concurrent load; timings are retained in metadata without cross-run speed claims. Sources are the summary, model_mse, parameter_loss, resources, and manifest files in `artifacts/submission_controls_v1/analysis/`.\n'
 a=S/'manuscript/Study02论文附录-v2.7.0.md';text=a.read_text(encoding='utf-8').split('## 附录 F')[0].rstrip()+'\n\n## 附录 F 共同验证、可行选点与多寿命点监督\n\n'+zh;a.write_text(text.replace('附录按 A–E 编排','附录按 A–F 编排'),encoding='utf-8')
 a=S/'manuscript/submission/Study02-supplement-v2.7.0-en.md';text=a.read_text(encoding='utf-8').split('## Appendix F')[0].rstrip()+'\n\n## Appendix F Supplementary controls\n\n'+en;a.write_text(text,encoding='utf-8')
 a=S/'docs/independent/submission-controls-v1-结果报告.md';a.write_text('# 投稿补充对照：完整结果\n\n依据用户要求落实投稿审查修改，执行协议25。结果按原设定完整报告，无新参数搜索。以下表格来自验证通过的完整矩阵；与旧三路线主表分开。\n\n'+zh,encoding='utf-8')
 print('PASS supplementary tables generated from full 600-trajectory matrix')

if __name__=='__main__':main()
