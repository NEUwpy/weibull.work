"""Tables for the manuscript, all computed from the single E09 row file."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent


def main():
    data=pd.read_csv(HERE/'per_sample.csv.gz')
    pooled=[]; params=[]; by_n=[]
    for method,g in data.groupby('method'):
        valid=g[g.valid]
        row={'method':method,'samples':len(g),'failures':int((~g.valid).sum()),
             'failure_rate':float((~g.valid).mean()),
             'J1_complete_case':float(np.sqrt(valid.squared_loss.mean())),
             'J1_failure3':float(np.sqrt(g.score.mean()))}
        pooled.append(row)
        entry={'method':method,'valid_samples':len(valid)}
        for p in ['beta','eta','gamma']:
            e=valid['err_'+p]
            entry.update({f'bias_{p}':e.mean(),f'sd_{p}':e.std(ddof=1),
                          f'rmse_{p}':np.sqrt((e**2).mean()),f'mae_{p}':e.abs().mean()})
        params.append(entry)
        for n,gn in g.groupby('n'):
            vn=gn[gn.valid]
            entry={'method':method,'n':n,'samples':len(gn),'failures':int((~gn.valid).sum()),
                   'failure_rate':float((~gn.valid).mean()),
                   'J1_complete_case':float(np.sqrt(vn.squared_loss.mean())),
                   'J1_failure3':float(np.sqrt(gn.score.mean()))}
            for p in ['beta','eta','gamma']:
                e=vn['err_'+p]
                entry.update({f'bias_{p}':e.mean(),f'sd_{p}':e.std(ddof=1),
                              f'rmse_{p}':np.sqrt((e**2).mean()),f'mae_{p}':e.abs().mean()})
            by_n.append(entry)
    pd.DataFrame(pooled).to_csv(HERE/'pooled.csv',index=False)
    pd.DataFrame(params).to_csv(HERE/'pooled_parameter_metrics.csv',index=False)
    pd.DataFrame(by_n).to_csv(HERE/'by_n.csv',index=False)
    rows=[]
    for keys,d in data.groupby(['method','cell_id','n','beta','gamma_over_eta']):
        out=dict(zip(['method','cell_id','n','beta','gamma_over_eta'],keys))
        valid=d[d.valid]
        out.update(samples=len(d),valid_samples=len(valid),failures=int((~d.valid).sum()),
                   J1_failure3=float(np.sqrt(d.score.mean())))
        for p in ['beta','eta','gamma']:
            err=valid['err_'+p]
            out.update({f'bias_{p}':err.mean(),f'sd_{p}':err.std(ddof=1),
                        f'rmse_{p}':np.sqrt((err**2).mean())})
        rows.append(out)
    cell=pd.DataFrame(rows)
    cell.to_csv(HERE/'by_cell.csv',index=False)
    # Within-cell SD measures repeated-sample spread at identical true parameters.
    out=[]
    for method,g in cell.groupby('method'):
        row={'method':method,'cells':len(g)}
        for p in ['beta','eta','gamma']:
            row[f'within_cell_rms_sd_{p}']=float(np.sqrt(np.mean(g[f'sd_{p}']**2)))
        out.append(row)
    pd.DataFrame(out).to_csv(HERE/'within_cell_stability.csv',index=False)
    for axis in ['beta','gamma_over_eta']:
        out=[]
        for (method,value),g in data.groupby(['method',axis]):
            row={'method':method,axis:value,'samples':len(g),'failures':int((~g.valid).sum()),
                 'J1_failure3':float(np.sqrt(g.score.mean()))}
            for p in ['beta','eta','gamma']:
                row[f'rmse_{p}']=float(np.sqrt(np.mean(g.loc[g.valid,f'err_{p}']**2)))
            out.append(row)
        pd.DataFrame(out).to_csv(HERE/f'by_{axis}.csv',index=False)
    a=data[data.method=='AMDM'].set_index(['cell_id','repeat_id'])
    out=[]
    for method,g in data.groupby('method'):
        b=g.set_index(['cell_id','repeat_id'])
        good=a.valid & b.valid
        aj=float(np.sqrt(a.loc[good,'squared_loss'].mean()))
        bj=float(np.sqrt(b.loc[good,'squared_loss'].mean()))
        row={'method':method,'paired_valid_samples':int(good.sum()),'AMDM_J1':aj,
             'comparator_J1':bj,'relative_gain':1-aj/bj}
        for penalty in [1,3,10]:
            row[f'J1_failure{penalty}']=float(np.sqrt(np.where(b.valid,b.squared_loss,penalty).mean()))
        out.append(row)
    pd.DataFrame(out).to_csv(HERE/'paired_valid_and_failure_sensitivity.csv',index=False)
    manifest=json.loads((HERE/'manifest.json').read_text(encoding='utf8'))
    manifest['methods']=sorted(data.method.unique())
    manifest['rows']=len(data)
    config=json.loads((HERE/'实验配置.json').read_text(encoding='utf8'))
    manifest['version']=config['version']
    manifest['manuscript_methods']=config['manuscript_methods']
    manifest['source_hashes'][str((HERE/'run_e09.py').relative_to(HERE.parents[3]))]=hashlib.sha256((HERE/'run_e09.py').read_bytes()).hexdigest()
    for name in ['per_sample.csv.gz','pooled.csv','pooled_parameter_metrics.csv','by_n.csv',
                 'additional_methods.csv.gz','extension_manifest.json']:
        if (HERE/name).exists():
            manifest['output_hashes'][name]=hashlib.sha256((HERE/name).read_bytes()).hexdigest()
    for name in ['by_cell.csv','within_cell_stability.csv','by_beta.csv','by_gamma_over_eta.csv',
                 'paired_valid_and_failure_sensitivity.csv','paired_interval.json','wmle_recovery.csv',
                 'wmle_failure_audit.csv','wmle_audit_summary.json','verification.json']:
        manifest['output_hashes'][name]=hashlib.sha256((HERE/name).read_bytes()).hexdigest()
    for name in ['summarize_e09.py','paired_uncertainty.py','audit_wmle.py','repair_wmle_rows.py','verify_e09.py',
                 'extend_conventional.py','实验配置.json']:
        relative=(HERE/name).relative_to(HERE.parents[3])
        manifest['source_hashes'][str(relative)]=hashlib.sha256((HERE/name).read_bytes()).hexdigest()
    extension=json.loads((HERE/'extension_manifest.json').read_text(encoding='utf8'))
    for relative,digest in extension['source_hashes'].items():
        if relative!='extension_driver':
            manifest['source_hashes'][str(Path(relative))]=digest
    manifest['model_hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted((HERE/'models').glob('n*_final.json'))}
    (HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(data.groupby('method').agg(samples=('valid','size'),valid=('valid','sum'),mean_score=('score','mean')))


if __name__=='__main__':main()
