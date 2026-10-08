"""Stored real profile-gradient grids; change the threshold without re-estimating δ=.20."""
import hashlib,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
HERE=Path(__file__).resolve().parent
def main():
    cfg=json.loads((HERE/'config.json').read_text(encoding='utf-8'));contract=cfg['figure_contract']
    curves=json.loads((HERE/'中间数据/MDM曲线.json').read_text(encoding='utf-8'))
    plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],
      'font.size':8,'axes.linewidth':.8,'axes.unicode_minus':True})
    meta=[]
    for n in [7,15,30]:
        rows=sorted([r for r in curves if r['n']==n],key=lambda r:r['id']);assert [r['id'] for r in rows]==list(range(1,51))
        for delta in [.10,.15,.20]:
            fig,ax=plt.subplots(figsize=(130/25.4,92/25.4));point_count=0
            for row in rows:
                points=sorted([p for p in row['points'] if p.get('source')=='trace_grid' and not p.get('virtual',False)],key=lambda p:p['gamma'])
                assert len(points)==240 and all(np.isfinite(p['gradient']) for p in points)
                point_count+=len(points)
                ax.plot([p['gamma'] for p in points],[p['gradient'] for p in points],color='black',lw=.48,alpha=.82,solid_capstyle='round')
            ax.axhline(delta,color='#b2182b',lw=.85,ls='-.',zorder=5)
            ax.set_xlim(contract['mdm_x_range']);ax.set_ylim(contract['mdm_y_range'])
            ax.spines['bottom'].set_position(('data',0));ax.spines['left'].set_position(('data',0))
            ax.spines['top'].set_visible(False);ax.spines['right'].set_visible(False)
            xmax=contract['mdm_x_range'][1];ax.set_xticks(np.arange(0,xmax+.1,500 if xmax==1500 else 100))
            ax.set_yticks(np.arange(-.8,1.6001,.4));ax.xaxis.set_minor_locator(MultipleLocator(100 if xmax==1500 else 20));ax.yaxis.set_minor_locator(MultipleLocator(.1))
            ax.tick_params(which='major',direction='in',length=4.2,pad=3);ax.tick_params(which='minor',direction='in',length=2.4)
            ax.set_ylabel('Std gradient',labelpad=8);fig.text(.56,.055,'Location parameter value adopted',ha='center',va='center')
            fig.subplots_adjust(left=.14,right=.96,bottom=.18,top=.975)
            out=HERE.parent/'结果' if HERE.name=='程序' else HERE.parent.parent/'结果'/HERE.name
            output=out/f'样本量{n}_偏移量{delta:.2f}.png';fig.savefig(output,dpi=600,facecolor='white');plt.close(fig)
            meta.append(dict(file=str(output),n=n,delta=delta,curves=50,points=point_count,x_limits=contract['mdm_x_range'],y_limits=contract['mdm_y_range'],
              source='stored task20261004 trace_grid; same gamma profile grid across thresholds; no virtual root/probe points',
              sha256=hashlib.sha256(output.read_bytes()).hexdigest(),bytes=output.stat().st_size))
    (HERE/'MDM绘图核验.json').write_text(json.dumps(dict(figures=meta,PNG_only=True,notes_in_figure=False,reestimation_calls=0),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('MDM_PNG_DONE',cfg['combination'],'9 PNG / 50 real curves per figure')
if __name__=='__main__':main()
