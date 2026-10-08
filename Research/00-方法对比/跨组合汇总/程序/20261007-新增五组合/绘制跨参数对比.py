"""Reproduce the 13 conditional rate panels from frozen source values; no fitting."""
import hashlib,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
HERE=Path(__file__).resolve().parent
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','Arial','DejaVu Sans'],
 'font.size':8,'axes.linewidth':.7,'axes.unicode_minus':False})
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    source=json.loads((HERE/'13组合取数.json').read_text(encoding='utf-8'))
    sources=sorted(source['sources'],key=lambda s:tuple(float(v) for v in s['combination'].removeprefix('W(').removesuffix(')').split(',')));ns=source['n'];methods=[{'label':m} for m in source['methods']]
    paths=[(s['combination'],None,s['protocol']) for s in sources]
    indexed={(c['combination'],c['method'],c['n']):c['value'] for c in source['cells']}
    grids=[np.asarray([[indexed[p[0],m['label'],n] for n in ns] for m in methods]) for p in paths]
    assert len(grids)==13 and len(indexed)==312 and source['pooled_rates'] is False
    fig,axes=plt.subplots(3,5,figsize=(15.8,10.8))
    fig.subplots_adjust(left=.075,right=.93,bottom=.07,top=.96,wspace=.28,hspace=.39)
    slots=[divmod(i,5) for i in range(13)]
    for ax in axes.flat:ax.set_visible(False)
    figure_cells=[]
    for i,((row,col),grid) in enumerate(zip(slots,grids)):
        ax=axes[row,col];ax.set_visible(True)
        im=ax.imshow(grid,cmap='Blues',vmin=0,vmax=1,aspect='auto',interpolation='nearest')
        ax.set_xticks(range(3),ns);ax.set_xlabel('n',labelpad=2)
        ax.set_yticks(range(8),[m['label'] for m in methods] if col==0 else ['']*8);ax.tick_params(length=0)
        ax.set_xticks(np.arange(-.5,3,1),minor=True);ax.set_yticks(np.arange(-.5,8,1),minor=True)
        ax.grid(which='minor',color='white',lw=1.0);ax.tick_params(which='minor',length=0)
        for spine in ax.spines.values():spine.set_visible(False)
        ax.set_title(paths[i][0].replace('(','').replace(')',''),fontsize=8.5,pad=6)
        for method in range(8):
            for n in range(3):
                value=grid[method,n];label=f'{value:.0%}'
                ax.text(n,method,label,ha='center',va='center',fontsize=8.5,color='white' if value>=.6 else '#17212B')
                figure_cells.append(dict(combination=paths[i][0],method=methods[method]['label'],n=ns[n],value=float(value),label=label))
    cax=fig.add_axes([.949,.07,.012,.84]);cb=fig.colorbar(im,cax=cax);cb.set_ticks([0,.25,.5,.75,1]);cb.ax.yaxis.set_major_formatter(PercentFormatter(1));cb.set_label('有解率',labelpad=2,fontsize=8);cb.outline.set_visible(False);cb.ax.tick_params(length=0)
    fig.canvas.draw();assert len(figure_cells)==312
    output=HERE/'跨参数对比_有解率热图.png';fig.savefig(output,dpi=450,facecolor='white');plt.close(fig)
    record=dict(task_id='research00-add-stash-5combos-032',goal_version='g1',artifact_version='five-combos-v2',
      sources=sources,rows=312,panels=13,heatmap_cells=len(figure_cells),figure_cells=figure_cells,
      frozen_source_sha256=sha(HERE/'13组合取数.json'),output=str(output),output_sha256=sha(output),
      sampling_protocols_preserved=True,pooled_rates=False,
      panel_order=[p[0] for p in paths],panel_titles=[p[0].replace('(','').replace(')','') for p in paths],
      row_labels=[m['label'] for m in methods],column_labels=ns,color_range=[0,1],colorbar_label='有解率',group_heading_count=0,
      layout_changes=['no group headings','numeric beta eta gamma ordering','W titles without parentheses','colorbar labels inside image'],
      note='Each combination/n/method cell has denominator 50; no pooled comparison.')
    (HERE/'绘图核验.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('CROSS13_PORTABLE_READY',str(output),len(figure_cells),'cells')
if __name__=='__main__':main()
