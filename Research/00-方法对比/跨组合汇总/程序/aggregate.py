"""Pool saved Excel-display success counts and plot eight combination panels."""
import csv,json,hashlib,platform
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from draw import heatmap,verify_cell_text

HERE=Path(__file__).resolve().parent; OUT=HERE.parent; R00=OUT.parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(name,obj):(HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write_csv(name,rows,fields):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:
            row=dict(row);row['success_rate']=format(row['success_rate'],'.17g');writer.writerow(row)

def main():
    entries=json.loads((HERE/'combinations.json').read_text(encoding='utf-8'))
    rows=[];boundaries=[];sources=[]
    for entry in entries:
        program=R00/entry['path']/'程序/分布与统计'
        cfg=json.loads((program/'config.json').read_text(encoding='utf-8'))
        payload=json.loads((program/'Excel提取.json').read_text(encoding='utf-8'))
        source=payload['source']; assert source['comparison_passed'] and not source['errors']
        assert sha(R00/entry['path']/cfg['workbook'])==source['workbook_sha256']
        rates=json.loads((program/'有解率.json').read_text(encoding='utf-8'))
        assert len(rates)==24 and all(r['total']==50 for r in rates)
        for rate in rates:
            records=[r for r in payload['records'] if r['n']==rate['n'] and r['method']==rate['method']]
            assert len(records)==50 and rate['success']==sum(r['success'] for r in records)
            assert rate['success_rate']==rate['success']/50
        rows.extend(rates)
        boundaries.extend(dict(combination=entry['combination'],**r) for r in source['acknowledged_status_differences'])
        sources.append(dict(combination=entry['combination'],path=entry['path'],
                            workbook_sha256=source['workbook_sha256'],matrix_sha256=source['matrix_sha256']))
    assert len(rows)==192 and len({(r['combination'],r['n'],r['method']) for r in rows})==192
    assert len(boundaries)==6
    write_csv('R00_统计汇总.csv',rows,['combination','method','n','total','success','success_rate','note'])
    methods=[r['method'] for r in rows[:8]]; ns=[7,15,30]
    truth={e['combination']:e['truth'] for e in entries}
    marginal=[]
    for group_by,idx in [('beta',0),('gamma',2),('n',None)]:
        levels=ns if idx is None else sorted({v[idx] for v in truth.values()})
        for level in levels:
            selected=[r for r in rows if (r['n']==level if idx is None else truth[r['combination']][idx]==level)]
            for method in methods:
                subset=[r for r in selected if r['method']==method]
                total=sum(r['total'] for r in subset);success=sum(r['success'] for r in subset)
                notes=list(dict.fromkeys(r['note'] for r in subset if r['note']))
                marginal.append(dict(group_by=group_by,group_value=f'{level:g}',method=method,
                                     conditions=len(subset),total=total,success=success,
                                     success_rate=success/total,note=' '.join(notes)))
    assert len(marginal)==72
    write_csv('R00_跨参数统计.csv',marginal,
              ['group_by','group_value','method','conditions','total','success','success_rate','note'])

    index={(r['combination'],r['method'],r['n']):r['success_rate'] for r in rows}
    fig,axes=plt.subplots(2,4,figsize=(19.2,9.6))
    fig.subplots_adjust(left=.07,right=.925,bottom=.07,top=.91,wspace=.60,hspace=.31)
    checks=[];cell_values=[];images=[]
    for ax,entry in zip(axes.flat,entries):
        matrix=np.array([[index[(entry['combination'],method,n)] for n in ns] for method in methods])
        im,texts=heatmap(ax,matrix,methods,ns,fontsize=10)
        ax.tick_params(labelsize=8.5);ax.set_title(f"β={entry['truth'][0]:g}, γ={entry['truth'][2]:g}",fontsize=11,pad=8)
        checks.append((ax,texts));images.append(im)
        cell_values.extend(dict(combination=entry['combination'],method=method,n=n,value=float(matrix[i,j]))
                           for i,method in enumerate(methods) for j,n in enumerate(ns))
    cax=fig.add_axes([.951,.20,.012,.59]);cb=fig.colorbar(images[0],cax=cax)
    cb.set_ticks([0,.25,.5,.75,1]);cb.ax.yaxis.set_major_formatter(PercentFormatter(1))
    cb.set_label('有解率',fontsize=10);cb.outline.set_visible(False);cb.ax.tick_params(length=0)
    fig.suptitle('η=1000 ｜ 各参数组合有解率',fontsize=12,y=.972)
    for ax,texts in checks:verify_cell_text(fig,ax,texts)
    fig.savefig(OUT/'跨参数对比_有解率热图.png',dpi=450,facecolor='white');plt.close(fig)
    assert len(cell_values)==192
    dump('汇总核验.json',dict(artifact_version='rates-v1',rows=192,marginal_rows=72,
         rate_denominator_per_condition=50,heatmap_panels=8,heatmap_cells=192,
         heatmap_axes='rows: methods; columns: n',heatmap_cmap='Blues',heatmap_limits=[0,1],
         cell_text_inside_cell=True,rate_cells=cell_values,acknowledged_status_differences=boundaries,
         success_rule='excel_converged_display',counts_from_saved_Excel=True,
         total_method_records=sum(r['total'] for r in rows),successful_method_records=sum(r['success'] for r in rows)))
    files=[OUT/name for name in ('R00_统计汇总.csv','R00_跨参数统计.csv','跨参数对比_有解率热图.png')]
    dump('manifest.json',dict(task_id='research00-figs-stats-028',goal_version='g2',artifact_version='rates-v1',
         sources=sources,scripts={p.name:sha(p) for p in HERE.glob('*.py')},
         outputs=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in files],
         runtime=dict(python=platform.python_version(),numpy=np.__version__)))
    print('AGGREGATE_READY: 192 within-parameter rates; 72 marginal rates; 192 heatmap cells;',
          sum(r['success'] for r in rows),'/',sum(r['total'] for r in rows),'displayed successes',flush=True)

if __name__=='__main__':main()
