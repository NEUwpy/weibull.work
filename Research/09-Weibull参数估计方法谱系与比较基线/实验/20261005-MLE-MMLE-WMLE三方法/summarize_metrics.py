"""Updated request: parameter Bias/SD(ddof0)/RMSE, raw joint RMSE."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from three_methods import HERE
from studies.common.metrics import summarize_standard_errors

METHODS=['MLE','MMLE-I','WMLE'];KEY=['n','block','repeat_id']

def aggregate(data):
    rows=[]
    for (method,n),part in data.groupby(['method_variant','n']):
        good=part[part.status.eq('success')];k=len(good)
        item=dict(method=method,n=int(n),total=len(part),success=k,success_rate=k/len(part))
        for p in ['beta','eta','gamma']:
            metrics=summarize_standard_errors(good[p+'_error'].to_numpy())
            sd=float(metrics['sd'])*np.sqrt((k-1)/k) if k>1 else 0.0
            item.update({p+'_bias':metrics['bias'],p+'_sd':sd,p+'_rmse':metrics['rmse']})
            assert np.isclose(item[p+'_rmse']**2,item[p+'_bias']**2+sd**2,rtol=1e-12,atol=1e-8)
        item['joint_rmse']=float(np.sqrt(sum(item[p+'_rmse']**2 for p in ['beta','eta','gamma'])))
        rows.append(item)
    return pd.DataFrame(rows)

def main():
    data=pd.read_csv(HERE/'per_sample.csv.gz');data['method_variant']=data.method_variant.replace({'MMLE':'MMLE-I'})
    assert set(data.method_variant)==set(METHODS) and len(data)==18000
    own=aggregate(data);own.to_csv(HERE/'by_n_own_valid.csv',index=False)
    keys=data[data.status.eq('success')].groupby(KEY).method_variant.nunique()
    keys=keys[keys.eq(3)].reset_index()[KEY]
    common=data.merge(keys,on=KEY,validate='many_to_one');aggregate(common).to_csv(HERE/'by_n_common.csv',index=False)
    wide=[];lines=['| 方法 | n=7 | n=10 | n=15 | n=20 | n=50 |','|---|---|---|---|---|']
    for method in METHODS:
        item={'method':method};cells=[]
        for n in [7,10,15,20,50]:
            row=own[(own.method==method)&(own.n==n)].iloc[0]
            for col in ['total','success','success_rate','joint_rmse']+[
                p+'_'+metric for p in ['beta','eta','gamma'] for metric in ['bias','sd','rmse']]:item[f'n{n}_{col}']=row[col]
            cell=f'{row.success_rate*100:.1f}%; 联合RMSE {row.joint_rmse:.1f}'
            for p,label,dec in [('beta','β',3),('eta','η',1),('gamma','γ',1)]:
                vals=[row[p+'_'+q] for q in ['bias','sd','rmse']]
                cell+='<br>'+label+': '+' / '.join(f'{v:.{dec}f}' for v in vals)
            cells.append(cell)
        wide.append(item);lines.append('| '+method+' | '+' | '.join(cells)+' |')
    table=pd.DataFrame(wide);table.to_csv(HERE/'汇总表.csv',index=False,encoding='utf-8-sig')
    (HERE/'汇总表.md').write_text('# 成功率、Bias、SD、RMSE\n\n'
        '每格依次给成功率、联合RMSE，以及各参数 **Bias / SD / RMSE**；SD用ddof=0。'
        '指标用全部成功估计，未因图像显示范围裁剪。联合RMSE按原始参数MSE之和开平方。\n\n'
        +'\n'.join(lines)+'\n',encoding='utf-8')
    failed=data[data.status.ne('success')]
    failed.groupby(['method_variant','n','failure_reason']).size().rename('count').reset_index().to_csv(
        HERE/'failure_reasons.csv',index=False)
    # Paired raw-unit joint RMSE diagnostics, without forcing a tiny intersection.
    data['raw_joint_squared']=sum(data[p+'_error']**2 for p in ['beta','eta','gamma'])
    reference=data[data.method_variant.eq('WMLE')&data.status.eq('success')][KEY+['raw_joint_squared']]
    rng=np.random.default_rng(20260923);pairs=[]
    for method in ['MLE','MMLE-I']:
        part=data[data.method_variant.eq(method)&data.status.eq('success')][KEY+['raw_joint_squared']].merge(
            reference,on=KEY,suffixes=('_method','_wmle'),validate='one_to_one')
        for n,matched in part.groupby('n'):
            draws=np.zeros((2000,2))
            for _,block in matched.groupby('block'):
                a=block[['raw_joint_squared_method','raw_joint_squared_wmle']].to_numpy()
                idx=rng.integers(0,len(a),size=(2000,len(a)));draws+=a[idx].sum(axis=1)
            point=np.sqrt(matched[['raw_joint_squared_method','raw_joint_squared_wmle']].mean().to_numpy())
            draws=np.sqrt(draws/len(matched));delta=draws[:,0]-draws[:,1]
            pairs.append(dict(method=method,n=n,common_samples=len(matched),joint_rmse_method=point[0],joint_rmse_wmle=point[1],
                delta_joint_rmse=point[0]-point[1],ci95_low=float(np.quantile(delta,.025)),ci95_high=float(np.quantile(delta,.975))))
    pd.DataFrame(pairs).to_csv(HERE/'paired_vs_wmle.csv',index=False)
    record=dict(parameter_statistics='Bias/SD(ddof0)/RMSE on all own-success estimates',
        identity='RMSE^2=Bias^2+SD(ddof0)^2',joint_rmse='sqrt(MSE_beta_raw+MSE_eta_raw+MSE_gamma_raw)',
        joint_note='Fixed original numerical units; eta and gamma dominate. Not unit-invariant; parameter-specific metrics are primary.',
        sample_count=6000,new_samples=0,rows=18000,methods=METHODS,
        raw_data_sha256=hashlib.sha256((HERE/'per_sample.csv.gz').read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),identities_verified=45,all_passed=True)
    (HERE/'metrics_verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(own.to_string(index=False));print(pd.DataFrame(pairs).to_string(index=False))

if __name__=='__main__':main()
