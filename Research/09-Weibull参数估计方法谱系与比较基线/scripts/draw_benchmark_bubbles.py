"""Report figure: adoption bubbles, excluding MDM on both axes.
Column citations are representative construction/comparison sources, not a
claim that all papers implemented the same historical version.
"""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

R=Path(__file__).resolve().parents[1]
d=json.loads((R/'evidence/benchmark_comparison_audit.json').read_text(encoding='utf-8'))
rows=sorted([r for r in d['records'] if r['primary_included'] and r['id']!='182-030'],key=lambda r:(r['year'],r['id']))
labels={
'182-091':('修正极大似然与修正矩估计','MMLE / MMoE · 1982 · Cohen & Whitten'),
'183-020':('人工神经网络估计','ANN · 2008 · Abbasi等'),
'182-088':('加权极大似然估计','WMLE · 2009 · Cousineau'),
'182-101':('估计方法比较研究','比较研究 · 2009 · Cousineau'),
'182-113':('位置尺度不变统计量似然估计','LSPF · 2013 · Nagatsuka等'),
'182-096':('估计方法综合比较','比较研究 · 2014 · Akram & Hayat'),
'182-047':('最小二乘迭代估计','LS迭代 · 2023 · 杨小玉等'),
'185-005':('逐次逼近估计','SAM · 2023 · Guo等'),
'182-117':('位置修正逐次逼近估计','PM · 2024 · Guo等'),
'182-111':('双重修正极大似然估计','DMMLE · 2025 · da Silva等'),
'184-009':('反向传播神经网络估计','BPNN · 2025 · Yang等'),
'187-001':('自适应梯度优化估计','ADGBO · 2026 · Wang等'),
}
cols=[
('MLE','极大似然估计','MLE · 1982 · Cohen & Whitten'),
('CC','相关回归估计','LRE · 2005 · 严晓东等 / 2017–18 · Park'),
('MM','矩估计','MM · 1982 · Cohen & Whitten / 1988 · Cran'),
('WMLE','加权极大似然估计','WMLE · 2009 · Cousineau / 2011 · Ng等'),
('MPS','最大乘积间距估计','MPS · 1983 · Cheng & Amin'),
('PWM','概率加权矩估计','PWM · 1979 · Greenwood等'),
('MMLE','修正极大似然估计','MMLE · 1982 · Cohen & Whitten / 2009 · Kundu & Raqab'),
('LS','最小二乘估计','LS · 2024 · Guo等（采用）'),
('BL','贝叶斯似然估计','BL · 2005 · Hall & Wang'),
('CMLE','校正极大似然估计','CMLE · 1987 · Cheng & Iles'),
('LM','L矩估计','LM · 1990 · Hosking'),
('MMoE','修正矩估计','MMoE · 1982 · Cohen & Whitten'),
]
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'font.family':font.get_name(),'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False})
counts=[sum(key in {b['family'] for b in r['sim_benchmarks']} for r in rows) for key,_,__ in cols]
fig,ax=plt.subplots(figsize=(24,14),dpi=160)
fig.subplots_adjust(left=.285,right=.98,top=.94,bottom=.35)
for y in range(len(rows)):
 if y%2==0:ax.axhspan(y-.5,y+.5,color='#F2F6FA',zorder=0)
for x,((key,name,detail),count) in enumerate(zip(cols,counts)):
 ys=[i for i,r in enumerate(rows) if key in {b['family'] for b in r['sim_benchmarks']}]
 # Each occupied cell encodes use; area encodes this column's adoption count.
 ax.scatter([x]*len(ys),ys,s=145*count,color='#2479AD',edgecolors='white',linewidths=1,zorder=3)
 ax.text(x,-.95,str(count),ha='center',va='center',fontsize=15,color='#2479AD',weight='bold')
ax.set_xlim(-.5,len(cols)-.5);ax.set_ylim(len(rows)-.5,-.5)
def display_label(name, detail):
 parts=detail.split(' · ',1)
 return name+'（'+parts[0]+'）\n'+parts[1]
ax.set_yticks(range(len(rows)),[display_label(*labels[r['id']]) for r in rows],fontsize=12)
ax.set_xticks(range(len(cols)),[display_label(name,detail) for _,name,detail in cols],fontsize=11,rotation=42,ha='right',rotation_mode='anchor')
ax.tick_params(axis='both',length=0,pad=12)
for x in range(len(cols)):ax.axvline(x,color='#DFE7EF',linewidth=.6,zorder=0)
for side in ax.spines.values():side.set_visible(False)
out=R/'图片/文献对照气泡图'
for ext in ['png','svg','pdf']:fig.savefig(out.with_suffix('.'+ext),dpi=200,facecolor='white',bbox_inches='tight',pad_inches=.12)
plt.close(fig)
(R/'evidence/benchmark_bubble_labels.json').write_text(json.dumps({'rows':[{'id':r['id'],'label':labels[r['id']]} for r in rows],'columns':cols,'counts':dict(zip([c[0] for c in cols],counts)),'source':'benchmark_comparison_audit.json','excluded':'MDM row and column; source audit unchanged','label_rule':'representative sources, not universal version or invention dates'},ensure_ascii=False,indent=2),encoding='utf-8')
print('Saved PNG/SVG/PDF; 12 papers; frequency bubble counts:',dict(zip([c[0] for c in cols],counts)))
