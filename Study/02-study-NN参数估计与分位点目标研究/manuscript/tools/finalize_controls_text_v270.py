"""Integrate the completed, checked supplementary results into both manuscripts."""
from pathlib import Path
import json,re
S=Path(__file__).resolve().parents[2];M=S/'manuscript'
d=json.loads((S/'artifacts/submission_controls_v1/analysis/summary.json').read_text(encoding='utf-8'))
assert d['training_trajectories']==600 and d['q_reproduction_all_200'] and d['q_feas']['available']==0
assert round(100*d['contrasts']['0.95:Q_vs_P_QSELECT']['relative_improvement'],3)==1.322
assert '<!-- SUPPLEMENTAL_RESULTS -->' in (M/'submission/Study02-manuscript-v2.7.0-en.md').read_text(encoding='utf-8'), 'One-time integration already applied; edit the reviewed manuscript directly.'

en_abstract='''Minimizing parameter error need not minimize error in a derived engineering quantity. We examine the benefits and costs of aligning three-parameter Weibull neural estimation with one reliability life point. Parameter-oriented (P) and target-oriented (Q) procedures share data, network structure, and maximum training budgets, but use their respective training and validation losses. Fixed-scale simulations cover 40 parameter combinations, four sample sizes, and 200 paired model units. Q reduces pooled root mean squared relative error (RMSRE) at $x_{0.95}$ from 16.43% to 16.09%, a relative improvement of 2.07% (95% empirical interval: 1.28%–2.81%), but increases error at $x_{0.90}$ and $x_{0.99}$ by 36.41% and 63.11%. With a common validation criterion, Q retains a 1.32% target improvement (0.63%–1.96%). Loss geometry and prediction-level decompositions show that single-point supervision permits large, compensating parameter errors. Parameter-constrained learning (QCP) reduces target RMSRE to 15.84% and repairs deterioration at the other two points; fixed-weight parameter regularization achieves similar accuracy. Direct supervision of all three points also reduces the cross-point errors, but recovers parameters less accurately than the parameter-regularized procedures. Pooled gains concentrate in a few high-error cells, while P retains an advantage in typical absolute error. These post-test controls reuse the original samples. The evidence supports matching supervision to both the intended life points and parameter interpretation, without demonstrating an accuracy advantage of QCP over simple weighting.'''
zh_abstract='''当最终使用量是可靠度寿命点时，参数误差最小并不等于该寿命点误差最小。本文以三参数Weibull神经估计为例，研究任务对齐的收益、参数代价及修复方式。参数导向流程P与目标寿命点导向流程Q共用数据、网络和最大训练预算，分别按对应损失训练和验证选点。固定尺度仿真覆盖40个参数组合、4种样本量和200个配对模型单元。Q将目标 $x_{0.95}$ 的总体均方根相对误差（RMSRE）由16.43%降至16.09%，相对改善2.07%（95%经验区间：1.28%至2.81%），但 $x_{0.90}$、$x_{0.99}$ 的误差分别增加36.41%和63.11%。统一验证准则后，Q仍保留1.32%的目标改善（0.63%至1.96%）。损失几何与逐预测分解显示，单点监督允许较大的参数误差在目标点相互抵消。参数约束流程QCP将目标RMSRE降至15.84%，并修复另外两点的退化；固定加权参数损失获得接近的精度。三点直接监督也能缓解跨点误差，但参数恢复弱于参数正则化流程。总体收益集中于少数高误差单元，P仍保留典型绝对误差优势。这些事后补充对照复用原样本；当前证据支持根据寿命点任务与参数解释需求共同设计监督，不支持QCP精度优于简单加权。'''
zh_results='''### 3.5 共同验证与替代修复对照

为区分训练目标与验证准则，并检验更简单的修复方式，补充实验新增600条训练轨迹，每类200个模型单元（附录F）。P_QSELECT仍按参数损失训练，但与Q一样按验证目标损失选择检查点和早停。它的目标RMSRE为16.3077%，相对原P改善0.757%（95%经验区间：0.477%至1.029%）；Q相对P_QSELECT仍改善1.322%（0.631%至1.957%）。共同验证准则缩小了原P/Q差距，未消除Q的目标优势。该比较允许实际停止轮次不同，不能把两项相对改善相加当作独立因果贡献。

重跑Q的200个目标指标及最佳轮次全部复现原结果。在其原生早停轨迹内，没有模型出现满足原QCP参数阈值的检查点（0/200），所有记录轮次中的最小验证参数损失/阈值比为10.268。因此，本批Q轨迹不能仅靠可行选点获得同一修复；该结果不涉及延长训练或改变优化后的可行性，也没有可汇总的Q_FEAS测试精度。

QMULTI直接监督三个预设寿命点，三点RMSRE依次为14.0130%、16.0977%和20.8491%。相对Q，两个非目标点分别改善24.781%和41.795%，目标点差异的经验区间跨零。QMULTI在三个点的误差仍均高于QP和QCP（各配对区间均不跨零；表F2）；其平均参数损失为0.301916，QP和QCP分别为0.055208和0.055218。多点监督因而能够缓解跨点代价，但本次等权设置未达到参数正则化流程的参数恢复或寿命点精度。三个点均被直接监督，该结果不是未监督寿命点的泛化证据。

补充协议在旧测试结果已知后确定，并复用原仿真样本。以上对照限定了可支持的解释，未提供独立新数据确认。

'''
en_results='''### 3.5 Common validation and alternative repairs

Supplementary controls added 600 training trajectories, with 200 model units per trajectory type (Appendix F). P_QSELECT retained parameter-loss training but used the same validation target loss as Q for checkpoint selection and early stopping. Its target RMSRE was 16.3077%, a 0.757% improvement over P (95% empirical interval: 0.477%–1.029%). Q retained a 1.322% improvement over P_QSELECT (0.631%–1.957%). Common validation reduced the original P/Q gap without eliminating Q's target advantage. Stopping epochs could still differ, and the two relative improvements cannot be added as independent causal contributions.

All 200 repeated Q target metrics and selected epochs reproduced the original records. No checkpoint within any native Q early-stopping trajectory satisfied the original QCP parameter threshold (0/200); the smallest recorded validation parameter-loss/threshold ratio was 10.268. Feasible selection alone therefore supplied no repair within these trajectories and no Q_FEAS test-accuracy result to aggregate. This finding does not establish infeasibility under longer training or altered optimization.

QMULTI directly supervised the three prespecified life points, with RMSRE of 14.0130%, 16.0977%, and 20.8491%. Compared with Q, it reduced error at the two non-target points by 24.781% and 41.795%, while the empirical interval for the target-point difference crossed zero. Its errors remained higher than QP and QCP at all three points, with each paired interval excluding zero (Table F2). Mean parameter loss was 0.301916 for QMULTI, versus 0.055208 for QP and 0.055218 for QCP. Thus multi-point supervision mitigated the cross-point cost, but this equal-weight setting did not match the parameter recovery or life-point accuracy of the parameter-regularized procedures. All three points were directly supervised, so these results do not establish generalization to unsupervised life points.

The supplementary protocol was specified after earlier test outcomes were known and reused the original simulation samples. These controls narrow the supported interpretations without providing independent fresh-data confirmation.

'''
for p,zh in [(M/'Study02论文初稿-v2.7.0.md',True),(M/'submission/Study02-manuscript-v2.7.0-en.md',False)]:
 t=p.read_text(encoding='utf-8')
 t=re.sub(r'(## Abstract\n\n).*?(\n\n\*\*(?:Keywords|关键词))',lambda m:m[1]+en_abstract+m[2],t,flags=re.S) if not zh else re.sub(r'(## Abstract\n\n).*?(\n\n## 1)',lambda m:m[1]+en_abstract+m[2],t,flags=re.S)
 if zh:
  t=re.sub(r'(## 摘要\n\n).*?(\n\n\*\*关键词)',lambda m:m[1]+zh_abstract+m[2],t,flags=re.S)
  t=t.replace('## 4 讨论',zh_results+'## 4 讨论')
  t=t.replace('具体证据范围见补充对照说明。','共同验证后Q的优势仍在，而原生Q轨迹没有可行检查点（第3.5节）。多点监督提供了另一种有效缓解方式，因此修复跨点误差并不必然要求参数约束；当参数本身也需解释时，参数恢复指标仍需单独检查。')
  t=t.replace('固定加权QP也取得接近的精度。','固定加权QP也取得接近的精度。统一验证后Q仍保留目标优势；三点直接监督能缓解跨点误差，但当前等权设置的参数恢复弱于QP/QCP。')
  t=t.replace('附录 A–E：实验与推断细节、完整结果、敏感度推导、历史预算分析及复算索引','附录 A–F：实验与推断细节、完整结果、敏感度推导、历史预算分析、复算索引及补充对照')
  t=t.replace('早期训练预算的结果单列于附录 D。','早期训练预算的结果单列于附录 D，完整补充对照见附录 F。')
 else:
  t=t.replace('<!-- SUPPLEMENTAL_RESULTS -->\n\n',en_results)
  t=t.replace('Appendix F examines common selection, feasible selection within Q trajectories, and direct supervision of multiple life points as distinct controls.','The common-validation control retained Q\'s target advantage, whereas native Q trajectories supplied no feasible checkpoint (Section 3.5). Multi-point supervision also mitigated cross-point errors, showing that such repair need not require a parameter constraint. When the parameters themselves need interpretation, parameter-recovery metrics still require separate assessment.')
  t=t.replace('fixed weighting achieved similar accuracy.','fixed weighting achieved similar accuracy. Q retained its target advantage under common validation. Direct three-point supervision also mitigated cross-point errors, but its current equal-weight setting recovered parameters less accurately than QP/QCP.')
 p.write_text(t,encoding='utf-8')
print('Integrated verified supplementary results into both main manuscripts')
