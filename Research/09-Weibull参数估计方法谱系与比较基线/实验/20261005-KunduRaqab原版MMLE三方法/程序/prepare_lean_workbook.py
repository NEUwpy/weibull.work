"""Reshape saved data into Research00 wide tables, retaining no process columns."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;BATCH=HERE.parent;OUT=BATCH/'结果'
def main():
    guard=json.loads((HERE/'邮件009保护.json').read_text(encoding='utf-8'))['protected_scientific_files']
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==s for p,s in guard.items())
    sources=[HERE/'per_sample.csv.gz',HERE/'输入样本.npz',OUT/'三方法汇总.csv',OUT/'样本.csv',OUT/'估计明细.csv',*OUT.glob('*.png')]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (HERE/'邮件011保护.json').write_text(json.dumps(dict(protected_scientific_files=guard,protected_deliveries=hashes),ensure_ascii=False,indent=2),encoding='utf-8')
    data=pd.read_csv(HERE/'per_sample.csv.gz');data['method']=data.method_variant.replace({'K-R MMLE':'MMLE'})
    data=data.set_index(['n','block','repeat_id','method']);arrays=np.load(HERE/'输入样本.npz');sheets=[]
    for n in [7,10,15,20,50]:
        estimated=[];samples=[]
        for i,x in enumerate(arrays[f'n{n}']):
            block,repeat=divmod(i,100);values=[i+1]
            for method in ['MLE','MMLE','WMLE']:
                row=data.loc[(n,block,repeat,method)]
                values.extend([float(row[p+'_hat']) for p in ['beta','eta','gamma']] if row.status=='success' else [None]*3)
            estimated.append(values);samples.append([i+1,*x.tolist()])
        sheets.append(dict(name=f'估计结果_n{n}',kind='estimates',n=n,rows=estimated))
        sheets.append(dict(name=f'生成样本_n{n}',kind='samples',n=n,rows=samples))
    summary=json.loads((HERE/'汇总表数据.json').read_text(encoding='utf-8'))
    (HERE/'精简工作簿数据.json').write_text(json.dumps(dict(sheets=sheets,summary=summary),ensure_ascii=False),encoding='utf-8')
    print('6000 saved sample groups reshaped; 5 estimate sheets + 5 sample sheets + summary; no fitting')
if __name__=='__main__':main()
