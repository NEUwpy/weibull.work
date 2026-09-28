"""A bounded, source-traceable adoption chart for the report's recent candidates."""
from pathlib import Path
import json,sys,hashlib
deps=Path('D:/weibull/tmp/r09-plot-deps')
if deps.exists():sys.path.insert(0,str(deps))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np
B=Path(__file__).resolve().parents[1]
evidence=json.loads((B/'evidence/complete_sample_metric_audit.json').read_text(encoding='utf-8-sig'))
lookup={r['id']:r for r in evidence['records']}
# Positive uses only. Not a census; each listed subexperiment has its own scope.
rows=[
 ('182-088','WMLE · 2009',['MLE'],'迭代MLE、两步MLE；自身权重变体不计'),
 ('182-113','LSPF · 2013',['WMLE','BL'],'w-ML采用Ng等W3代入；真实例的MM不并入模拟'),
 ('182-030','MDM · 2022/23',['MLE','LS/相关系数'],'ML、概率图相关LS'),
 ('185-005','SAM · 2023',['MLE','LS/相关系数','PWM'],'MLE、CCWP、PWM；真实例历史结果另列'),
 ('182-117','PM · 2024',['MLE','LS/相关系数','PWM'],'只统计§5.1的n=5模拟，LSE/MLE/PWM；大n求解器比较不计入此子实验'),
 ('184-009','BPNN · 2025',['LS/相关系数','MDM'],'CCM、MDM'),
 ('182-111','DMMLE · 2025',['MMLE','CMLE'],'MMLE与corrected MLE（CMLE）；不与普通MLE合并'),
 ('182-050','低形状估计 · 2025',['BL','LSPF','w-MLE*'],'原文所称w-MLE与Cousineau方程修正不同，单列；身份疑点不影响原文列为对手这一事实'),
 ('187-001','ADGBO · 2026',['MLE','LS/相关系数'],'只统计无噪完整样本模拟；Newton/PSO均求MLE，合计一次；CCLSE另计'),
]
cols=['MLE','LS/相关系数','PWM','BL','WMLE','MDM','MMLE','CMLE','LSPF','w-MLE*']
out={'scope':'报告近期候选及相关求解工作中的9篇已核模拟来源，2009—2026，普通三参数完整样本；不限n。定向示例集，非近年全部文献。',
 'counting':'每篇×每列最多1次；排除新方法自身及自身分支；仅统计注明的模拟子实验。空白表示所选子实验未记录该列，不表示该论文其他部分未使用。',
 'aggregation':'LS/相关系数为展示层合并，版本不等价；普通MLE的数值求解版本归并；MMLE/CMLE分列。WMLE列允许已声明的W3代入版本，w-MLE*不归并。',
 'columns':cols,'records':[]}
for id,label,methods,note in rows:
 r=lookup[id];p=Path(r['source_path'])
 out['records'].append(dict(id=id,label=label,comparators=methods,scope_note=note,source_path=str(p),locator=r['locator'],source_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
out['counts']={m:sum(m in r[2] for r in rows) for m in cols}
(B/'evidence/comparison_adoption_matrix.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False,'svg.fonttype':'none'})
fig,ax=plt.subplots(figsize=(14,7.8),dpi=180)
fig.subplots_adjust(left=.27,right=.98,top=.91,bottom=.1)
ax.set_xlim(-.6,len(cols)-.4);ax.set_ylim(len(rows)-.5,-2.7)
for j,c in enumerate(cols):
 count=out['counts'][c]
 ax.scatter(j,-1.65,s=145*count,color='#D66A18',zorder=3)
 ax.text(j,-1.65,str(count),ha='center',va='center',color='white',fontsize=12,fontweight='bold')
 ax.text(j,-.73,c.replace('/','/\n'),ha='center',va='center',fontsize=11,color='#223B58')
for i,(id,label,methods,note) in enumerate(rows):
 ax.axhline(i,color='#E0E5EA',lw=.7,zorder=0)
 ax.text(-.73,i,f'{label}  [{id}]',ha='right',va='center',fontsize=12,color='#223B58')
 for j,c in enumerate(cols):
  if c in methods:ax.scatter(j,i,s=68,color='#34649A',zorder=3)
ax.text(-.73,-1.65,'采用论文数',ha='right',va='center',fontsize=13,color='#C85A10',fontweight='bold')
ax.set_xticks([]);ax.set_yticks([])
for s in ax.spines.values():s.set_visible(False)
fig.text(.04,.965,'近期方法论文实际采用了哪些对手？',fontsize=18,fontweight='bold',color='#223B58')
fig.text(.04,.027,'蓝点：该子实验采用此类对手。橙色气泡面积 ∝ 采用篇数（数字为篇数）。仅限本图9篇，频次不代表性能。',fontsize=11,color='#52616F')
for ext in ['png','svg','pdf']:fig.savefig(B/f'图片/近期论文对照采用矩阵.{ext}',dpi=220,facecolor='white')
print(json.dumps(out['counts'],ensure_ascii=False))
