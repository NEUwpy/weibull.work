"""Check the plot-only revision against the protected scientific result."""
import hashlib,json,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;BATCH=HERE.parent;OUT=BATCH/'结果'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    guard=json.loads((HERE/'返工保护.json').read_text(encoding='utf-8'))
    files=guard['protected_scientific_files'];assert len(files)==270
    assert all(Path(p).exists() and sha(p)==value for p,value in files.items())
    original=guard['original_summary'];updated=json.loads((HERE/'汇总表数据.json').read_text(encoding='utf-8'))
    assert all(before[1:]==after[1:] for before,after in zip(original['rows'],updated['rows']))
    assert set(row[0] for row in updated['rows'])=={'MLE','MMLE','WMLE'}
    summary=pd.read_csv(OUT/'三方法汇总.csv');raw=pd.read_csv(HERE/'per_sample.csv.gz')
    raw['method_variant']=raw.method_variant.replace({'K-R MMLE':'MMLE'})
    plot=json.loads((HERE/'绘图核验.json').read_text(encoding='utf-8'))
    for record in plot['records']:
        values=raw[(raw.method_variant==record['method'])&(raw.n==record['n'])&(raw.status=='success')][record['parameter']+'_hat'].to_numpy()
        assert record['median_marker']=='pink circle' and record['mean_marker']=='red circle'
        assert np.isclose(record['mean'],values.mean(),rtol=1e-13,atol=1e-12)
        assert np.isclose(record['quartiles'][1],np.median(values),rtol=1e-13,atol=1e-12)
    points=pd.read_csv(HERE/'图点.csv');assert len(points)==165
    for row in points.itertuples():
        source=summary[(summary.method==row.method)&(summary.n==row.n)].iloc[0]
        key='success_rate' if row.figure=='solution_rate' else row.parameter+'_rmse' if row.figure=='rmse' else row.parameter+'_'+row.figure
        assert np.isclose(row.value,source[key],rtol=1e-13,atol=1e-12)
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(OUT/'三方法汇总.xlsx') as z:
        assert z.testzip() is None;root=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        cells={c.get('r'):c for c in root.findall('.//s:c',ns)}
        strings=ET.fromstring(z.read('xl/sharedStrings.xml')) if 'xl/sharedStrings.xml' in z.namelist() else None
        shared=[''.join(si.itertext()) for si in strings] if strings is not None else []
        def text(cell):
            if cell.get('t')=='s':return shared[int(cell.find('s:v',ns).text)]
            if cell.get('t')=='inlineStr':return ''.join(cell.find('s:is',ns).itertext())
            return cell.find('s:v',ns).text if cell.find('s:v',ns) is not None else ''
        for i,expected in enumerate(updated['rows'],6):
            assert text(cells['A'+str(i)])==expected[0]
            for j,value in enumerate(expected[1:],1):
                assert np.isclose(float(text(cells[chr(65+j)+str(i)])),value,rtol=2e-12,atol=2e-10)
        assert len(root.findall('.//s:f',ns))==30
        assert not any('K-R MMLE' in text(c) or 'KRMMLE' in text(c) for c in cells.values())
    expected={'01_估计分布小提琴.png','02_有解率.png','03_RMSE.png','04_偏差.png','05_标准差.png','三方法汇总.csv','三方法汇总.xlsx'}
    assert {p.name for p in OUT.iterdir()}==expected
    assert 'K-R' not in (BATCH/'README.md').read_text(encoding='utf-8')
    old=json.loads((HERE/'既有结果保护.json').read_text(encoding='utf-8'));assert all(Path(p).exists() and sha(p)==h for p,h in old.items())
    current={str(p) for batch in BATCH.parent.glob('20261005-*') if batch!=BATCH for p in batch.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '程序复核' not in p.parts}
    assert current==set(old)
    checks=dict(scientific_files_unchanged=270,other_batch_files_unchanged=len(old),numeric_summary_values_unchanged=210,
       median_and_mean_groups_checked=45,curve_points_checked=165,workbook_numeric_cells_checked=210,
       workbook_formulas_preserved=30,visual_check='five PNG and the only workbook sheet inspected',
       labels=['MLE','MMLE','WMLE'],estimation_reruns=0)
    (HERE/'返工核验.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False))
if __name__=='__main__':main()
