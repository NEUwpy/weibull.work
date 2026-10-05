"""Export all saved sample observations and estimates, without simulation or fitting."""
import csv,hashlib,json,shutil
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;OUT=HERE.parent/'结果'
NS=[7,10,15,20,50];METHODS=['MLE','MMLE','WMLE']
def native(value):return None if pd.isna(value) else value.item() if isinstance(value,np.generic) else value
def save(name,columns,rows):
    with (OUT/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(columns);writer.writerows(rows)
    (HERE/(name+'数据.json')).write_text(json.dumps(dict(columns=columns,rows=rows),ensure_ascii=False),encoding='utf-8')
def main():
    raw=pd.read_csv(HERE/'per_sample.csv.gz');samples=np.load(HERE/'输入样本.npz');groups=[];mapping={}
    for n in NS:
        for i,x in enumerate(samples[f'n{n}']):
            block,repeat=divmod(i,100);group=f'n{n:02d}-{i+1:04d}'
            namespace='study01_selector_confirmation_20260922_v1'+(f':research09-versions:block{block:02d}' if block else '')
            digest=hashlib.sha256(x.tobytes()).hexdigest();mapping[(n,block,repeat)]=(group,x,digest)
            groups.append([n,group,i+1,block,repeat,namespace,digest,*x.tolist(),*[None]*(50-n)])
    sample_columns=['n','样本组ID','组号','block','repeat_id','种子命名空间','样本SHA256']+[f'x({i})' for i in range(1,51)]
    save('样本',sample_columns,groups)
    raw['display_method']=raw.method_variant.replace({'K-R MMLE':'MMLE'});raw['order']=raw.display_method.map({m:i for i,m in enumerate(METHODS)})
    raw=raw.sort_values(['n','block','repeat_id','order']);estimates=[]
    reason_names={'no_stationary_root_in_paper_location_domain':'原文位置域内未找到驻点根',
                  'no_likelihood_maximum_root':'驻点候选中没有似然局部极大根',
                  'all_stationary_roots_outside_shape_domain':'驻点根形状超原文域',
                  'fixed_point_not_converged':'固定点未收敛'}
    for row in raw.itertuples():
        group,x,digest=mapping[(row.n,int(row.block),int(row.repeat_id))];assert digest==row.sample_sha256
        info=json.loads(row.extra).get('solution_info',{});ok=row.status=='success'
        code='' if ok else info.get('status','unknown_failure');reason='' if ok else reason_names.get(code,code)
        minimum=float(x[1] if row.display_method=='MMLE' else x[0])
        estimates.append([row.n,group,int(row.block)*100+int(row.repeat_id)+1,int(row.block),int(row.repeat_id),row.display_method,
            2.,1000.,1000.,native(row.beta_hat),native(row.eta_hat),native(row.gamma_hat),bool(row.converged),
            '成功' if ok else '失败',reason,code,float(x[0]),minimum,1 if row.display_method=='MMLE' else 0,
            native(row.time),digest])
    columns=['n','样本组ID','组号','block','repeat_id','方法','β真值','η真值','γ真值','β估计','η估计','γ估计',
             '收敛','状态','失败原因','失败原因代码','原始最小值','支持检查最小值','删除观测数','耗时(秒)','样本SHA256']
    save('估计明细',columns,estimates)
    # Remove only the optional joint column, preserving all numeric CSV text in the nine requested metrics.
    with (OUT/'三方法汇总.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.reader(f))
    joint_index=rows[0].index('joint_rmse') if 'joint_rmse' in rows[0] else None
    if joint_index is not None:
        with (OUT/'三方法汇总.csv').open('w',encoding='utf-8-sig',newline='') as f:
            csv.writer(f).writerows([[v for j,v in enumerate(r) if j!=joint_index] for r in rows])
    summary_frame=pd.read_csv(OUT/'三方法汇总.csv',float_precision='round_trip')
    summary=dict(columns=summary_frame.columns.tolist(),rows=summary_frame.values.tolist())
    (HERE/'汇总表数据.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=HERE/'邮件008图表';archive.mkdir(exist_ok=True)
    for name in ['03_RMSE.png','04_偏差.png','05_标准差.png','三方法汇总.xlsx']:
        path=OUT/name
        if path.exists():
            target=archive/name;assert not target.exists();shutil.move(str(path),str(target))
    print(json.dumps(dict(sample_rows=len(groups),estimate_rows=len(estimates),summary_rows=15,recomputed_estimates=0),ensure_ascii=False))
if __name__=='__main__':main()
