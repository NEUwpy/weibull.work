"""Audit the historical MDM export order and independently verify scale meaning."""
import sys
import csv
import json
from pathlib import Path
import numpy as np
import scipy
sys.path.append(r'C:\Users\36089\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\site-packages')
from openpyxl import load_workbook
ROOT=Path('D:/weibull')
sys.path.insert(0,str(ROOT/'python'))
from methods.mdm import MDM

src=ROOT/'docs/临时任务/工作输出/20260906-W5-parameters/W5-1000-500'
book=ROOT/'docs/临时任务/临时任务-W2-1000-3000-MDM偏移量估计-20260825/260906-W5参数估计案例/W(5,1000,500)/5,1000,500.xlsx'
wb=load_workbook(book,read_only=True,data_only=True)
sample_rows={n:list(wb[f'生成样本_n{n}'].values) for n in [7,15]}
result_rows={n:list(wb[f'估计结果_n{n}'].values) for n in [7,15]}
with (src/'mdm_estimates.csv').open(encoding='utf-8-sig',newline='') as f:
    archived=list(csv.DictReader(f))
error=[]
for r in archived:
    n=int(r['sample_size']); sid=int(r['sample_id']); offset=float(r['offset'])
    row={.1:4,.15:62,.2:120}[offset]+sid-1
    recorded=np.array([float(r[k]) for k in ['beta_hat','eta_hat','gamma_hat']])
    cells=np.array(result_rows[n][row][1:4],float)
    error.extend(abs(recorded-cells))
assert len(error)==900 and max(error)==0
print('ALL_300_ROWS_900_CELLS_MATCH_CSV_ORDER_SHAPE_SCALE_LOCATION',max(error))
print('HEADERS_AND_NOTE',repr(result_rows[7][3][1:4]),repr(result_rows[7][55][0]))

for n,sid in [(7,1),(7,31),(15,1),(15,39)]:
    x=np.array(sample_rows[n][sid][1:n+1],float)
    z=-np.log1p(-(np.arange(1,n+1)-.3)/(n+.4))
    for delta,row0 in [(.1,4),(.2,120)]:
        expected=np.array(result_rows[n][row0+sid-1][1:4],float)
        fit=np.array(MDM(x).run(offset=delta,gamma_steps=240)[:3])
        direct_scale=float(np.mean((x-fit[2])/z**(1/fit[0])))
        assert np.max(abs(fit-expected))<1e-5
        assert abs(direct_scale-fit[1])<1e-9
        print('FIT',json.dumps({'n':n,'sample_id':sid,'delta':delta,'xlsx_shape_scale_location':expected.tolist(),
             'rerun_shape_scale_location':fit.tolist(),'max_error':float(np.max(abs(fit-expected))),
             'scale_from_formula':direct_scale}))

x=np.array(sample_rows[7][31][1:8],float)
original=np.array(MDM(x).run(offset=.1,gamma_steps=240)[:3])
translated=np.array(MDM(x+2500).run(offset=.1,gamma_steps=240)[:3])
print('TRANSLATION_TEST',json.dumps({'before':original.tolist(),'after':translated.tolist(),'difference':(translated-original).tolist()}))
assert np.max(abs((translated-original)-np.array([0,0,2500])))<1e-3
wb.close()
