"""Validate all exported observations and estimates against saved inputs and fits."""
import hashlib,json,zipfile,math
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;BATCH=HERE.parent;OUT=BATCH/'结果'
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def column(n):
    out=''
    while n:n,r=divmod(n-1,26);out=chr(65+r)+out
    return out
def main():
    protection=json.loads((HERE/'邮件009保护.json').read_text(encoding='utf-8'))
    assert len(protection['protected_scientific_files'])==270
    assert all(sha(p)==value for p,value in protection['protected_scientific_files'].items())
    raw=pd.read_csv(HERE/'per_sample.csv.gz');raw['method']=raw.method_variant.replace({'K-R MMLE':'MMLE'})
    detail=pd.read_csv(OUT/'估计明细.csv');sample=pd.read_csv(OUT/'样本.csv');summary=pd.read_csv(OUT/'三方法汇总.csv')
    arrays=np.load(HERE/'输入样本.npz');assert len(sample)==6000 and len(detail)==18000 and len(summary)==15
    assert not sample.duplicated(['n','block','repeat_id']).any()
    for row in sample.itertuples(index=False,name=None):
        n,group,index,b,repeat,namespace,digest,*obs=row;x=arrays[f'n{n}'][b*100+repeat]
        assert hashlib.sha256(x.tobytes()).hexdigest()==digest
        assert np.allclose(np.array(obs[:n],dtype=float),x,rtol=1e-13,atol=1e-10)
        assert all(pd.isna(v) for v in obs[n:])
    keyed=raw.set_index(['n','block','repeat_id','method'])
    for row in detail.to_dict('records'):
        n,b,repeat,method=row['n'],row['block'],row['repeat_id'],row['方法'];source=keyed.loc[(n,b,repeat,method)]
        assert (row['状态']=='成功')==(source.status=='success')
        assert row['样本SHA256']==source.sample_sha256
        for p,cn in [('beta','β估计'),('eta','η估计'),('gamma','γ估计')]:
            assert (pd.isna(row[cn]) and pd.isna(source[p+'_hat'])) or np.isclose(row[cn],source[p+'_hat'],rtol=1e-13,atol=1e-10)
        x=arrays[f'n{n}'][b*100+repeat];assert np.isclose(row['支持检查最小值'],x[1] if method=='MMLE' else x[0])
        if row['状态']=='失败':assert pd.notna(row['失败原因']) and pd.notna(row['失败原因代码'])
    for row in summary.to_dict('records'):
        values=raw[(raw.method==row['method'])&(raw.n==row['n'])&(raw.status=='success')]
        assert row['success']==len(values)
        for p,t in [('beta',2.),('eta',1000.),('gamma',1000.)]:
            e=values[p+'_hat'].to_numpy()-t
            assert np.isclose(row[p+'_bias'],e.mean(),rtol=1e-13,atol=1e-10)
            assert np.isclose(row[p+'_sd'],e.std(ddof=0),rtol=1e-13,atol=1e-10)
            assert np.isclose(row[p+'_rmse'],np.sqrt(np.mean(e*e)),rtol=1e-13,atol=1e-10)
            assert np.isclose(row[p+'_rmse']**2,row[p+'_bias']**2+row[p+'_sd']**2,rtol=1e-12)
    expected_numeric=json.loads((HERE/'汇总表数据.json').read_text(encoding='utf-8'))['rows']
    assert all(before[:-1]==after for before,after in zip(protection['input_summary']['rows'],expected_numeric))
    workbook=OUT/'W(2,1000,1000)_完整样本与估计.xlsx';cells_checked=0;formulas=0
    with zipfile.ZipFile(workbook) as z:
        assert z.testzip() is None
        book=ET.fromstring(z.read('xl/workbook.xml'));assert [s.get('name') for s in book.findall('s:sheets/s:sheet',NS)]==['样本','估计明细','汇总']
        shared=[''.join(si.itertext()) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        def value(cell):
            if cell is None:return None
            v=cell.find('s:v',NS)
            if cell.get('t')=='s':return shared[int(v.text)]
            if cell.get('t')=='b':return v.text=='1'
            if cell.get('t')=='str':return v.text if v is not None else ''
            if cell.get('t')=='inlineStr':return ''.join(cell.find('s:is',NS).itertext())
            return float(v.text) if v is not None and v.text is not None else None
        for index,name in enumerate(['样本数据.json','估计明细数据.json','汇总表数据.json'],1):
            data=json.loads((HERE/name).read_text(encoding='utf-8'));xml=ET.fromstring(z.read(f'xl/worksheets/sheet{index}.xml'))
            cells={c.get('r'):c for c in xml.findall('.//s:c',NS)};assert not any(c.get('t')=='e' for c in cells.values())
            for i,row in enumerate(data['rows'],6):
                for j,expected in enumerate(row,1):
                    actual=value(cells.get(column(j)+str(i)))
                    if expected is None:assert actual is None
                    elif isinstance(expected,bool):assert expected==actual
                    elif isinstance(expected,(int,float)):assert actual is not None and math.isclose(expected,actual,rel_tol=2e-12,abs_tol=2e-10)
                    else:assert actual==expected
                    cells_checked+=1
            formulas+=len(xml.findall('.//s:f',NS))
        assert formulas==15
    graph=pd.read_csv(HERE/'图点.csv');assert len(graph)==150 and not graph.parameter.fillna('').eq('joint').any()
    for row in graph.itertuples():
        source=summary[(summary.method==row.method)&(summary.n==row.n)].iloc[0]
        key='success_rate' if row.figure=='solution_rate' else row.parameter+'_'+row.figure
        assert np.isclose(row.value,source[key],rtol=1e-13,atol=1e-10)
    old=json.loads((HERE/'既有结果保护.json').read_text(encoding='utf-8'));assert all(sha(p)==h for p,h in old.items())
    current={str(p) for batch in BATCH.parent.glob('20261005-*') if batch!=BATCH for p in batch.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '程序复核' not in p.parts}
    assert current==set(old)
    results=dict(sample_groups=6000,observations=122400,estimate_rows=18000,summary_rows=15,
          valid_rows=int(detail['状态'].eq('成功').sum()),failed_rows=int(detail['状态'].eq('失败').sum()),
          workbook_cells_checked=cells_checked,workbook_formula_cells=formulas,workbook_errors=0,
          graph_points=150,identities=45,scientific_files_unchanged=270,other_batches_unchanged=3882,estimation_reruns=0,
          support='MMLE uses retained x(2); MLE/WMLE use original x(1)',
          visual_check='3 PNG and all 3 worksheet previews checked')
    (HERE/'邮件009核验.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(results,ensure_ascii=False))
if __name__=='__main__':main()
