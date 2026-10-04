"""Audit every saved sample/value/plot; independently rerun 120 selected fits."""
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
METHODS=['mdm','lse','lre','wmle','mle']


def check_layout():
    assert {p.name for p in ROOT.iterdir()}=={'程序','结果'}
    programs={p.name for p in (ROOT/'程序').glob('W(*)') if p.is_dir()}
    outputs={p.name for p in (ROOT/'结果').glob('W(*)') if p.is_dir()}
    assert programs==outputs and len(programs)==8
    for name in programs:
        output=ROOT/'结果'/name
        expected={
            f'{name}.xlsx','估计分布_小提琴图.png','中间数据',
            *[f'样本量{n}_偏移量0.20.png' for n in (7,15,30)]}
        if (output/'估计分布_线性坐标试画.png').is_file():
            expected.add('估计分布_线性坐标试画.png')
        assert {p.name for p in output.iterdir()}==expected
    return dict(top_level_folders=['程序','结果'],parameter_pairs=8,image_format='PNG',
                preview_figures=len(list((ROOT/'结果').glob('W(*)/估计分布_线性坐标试画.png'))))


def read_workbook(path):
    with ZipFile(path) as book:
        shared=[]
        if 'xl/sharedStrings.xml' in book.namelist():
            shared=[''.join(t.itertext()) for t in ET.fromstring(book.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        workbook=ET.fromstring(book.read('xl/workbook.xml'))
        names=[s.attrib['name'] for s in workbook.findall('s:sheets/s:sheet',NS)]
        sheets=[]
        for index,name in enumerate(names,1):
            xml=ET.fromstring(book.read(f'xl/worksheets/sheet{index}.xml'))
            cells={}
            for c in xml.findall('.//s:sheetData/s:row/s:c',NS):
                v=c.find('s:v',NS)
                kind=c.get('t')
                if kind=='s': value=shared[int(v.text)]
                elif kind=='inlineStr': value=''.join(c.find('s:is',NS).itertext())
                elif v is None or v.text is None: continue
                else: value=float(v.text) if kind!='str' else v.text
                cells[c.attrib['r']]=value
            sheets.append((name,cells))
        assert not any('comments' in name.lower() for name in book.namelist())
        return sheets


def column(index):
    result=''
    while index:
        index,remainder=divmod(index-1,26); result=chr(65+remainder)+result
    return result


def same(actual,expected):
    if isinstance(expected,(int,float)):
        assert isinstance(actual,(int,float)) and math.isclose(actual,expected,rel_tol=3e-15,abs_tol=1e-12),(actual,expected)
    else: assert actual==expected,(actual,expected)


def one_case(case,rerun):
    output=ROOT/'结果'/case.name
    config=json.loads((case/'配置.json').read_text(encoding='utf-8'))
    source=output/'中间数据/results.json'
    data=json.loads(source.read_text(encoding='utf-8'))
    b,e,g=data['truth']
    assert data['truth']==config['truth'] and case.name==data['distribution']
    assert len(data['samples'])==150 and len(data['results'])==750 and len(data['gradient_curves'])==150
    snapshot=case/'依赖快照/python'
    sys.path.insert(0,str(snapshot))
    from studies.common.sample import generate_sample
    from studies.common.runner import run_method
    samples={(s['n'],s['id']):s for s in data['samples']}
    fits={(r['n'],r['id'],r['method_id']):r for r in data['results']}
    for sample in data['samples']:
        n,sid=sample['n'],sample['id']
        latent=generate_sample(1.,1.,0.,n,sid-1,seed=data['seed'])
        assert np.array_equal(latent,sample['latent_E'])
        assert np.array_equal(g+e*latent**(1/b),sample['values'])
        assert len(sample['values'])==n and min(sample['values'])>g
        seedtext=f"{data['seed']!r}|{1.!r}|{1.!r}|{0.!r}|{n}|{sid-1}"
        seed=int.from_bytes(hashlib.sha256(seedtext.encode()).digest()[:4],'big')
        independent=np.sort(-np.log(1-np.random.default_rng(seed).uniform(size=n)))
        assert np.array_equal(independent,latent)
    for name,digest in data['code_sha256'].items():
        assert hashlib.sha256((case/name).read_bytes()).hexdigest()==digest
    for r in data['results']:
        if r['converged']:
            assert r['beta_hat']>0 and r['eta_hat']>0 and 0<=r['gamma_hat']<samples[r['n'],r['id']]['values'][0]
    with (output/'中间数据/results.csv').open(encoding='utf-8',newline='') as stream:
        records=list(csv.DictReader(stream))
    assert len(records)==750
    for row in records:
        r=fits[int(row['n']),int(row['repeat_id'])+1,row['method_id']]
        for key in ('beta_hat','eta_hat','gamma_hat','r_squared'):
            if r[key] is None: assert row[key]==''
            else: same(float(row[key]),r[key])
        assert row['status']==r['status'] and (row['converged']=='True')==r['converged']
    workbook=read_workbook(output/f'{case.name}.xlsx')
    assert [name for name,_ in workbook]==[f'估计结果_n{n}' for n in data['n']]+[f'生成样本_n{n}' for n in data['n']]
    numbers=0
    for name,cells in workbook:
        n=int(name.rsplit('n',1)[1])
        if name.startswith('估计结果'):
            assert max(int(''.join(c for c in k if c.isdigit())) for k in cells)<=54
            assert all(cells[f'{column(i)}4']==['β','η','γ'][(i-2)%3] for i in range(2,17))
            for sid in range(1,51):
                same(cells[f'A{sid+4}'],sid)
                for m,method in enumerate(METHODS):
                    for k,key in enumerate(('beta_hat','eta_hat','gamma_hat')):
                        same(cells[f'{column(2+3*m+k)}{sid+4}'],fits[n,sid,method][key] if fits[n,sid,method][key] is not None else '—')
                        numbers+=1
        else:
            assert max(int(''.join(c for c in k if c.isdigit())) for k in cells)<=51
            for sid in range(1,51):
                same(cells[f'A{sid+1}'],sid)
                for i,value in enumerate(samples[n,sid]['values'],2):
                    same(cells[f'{column(i)}{sid+1}'],value)
    qa=json.loads((output/'中间数据/绘图核验.json').read_text(encoding='utf-8'))
    assert qa['source_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    for panel in qa['violin']['records']:
        rr=[fits[panel['n'],sid,panel['method']] for sid in panel['sample_ids']]
        assert panel['values']==[r[panel['parameter']] for r in rr]
        assert panel['success']+panel['failure']==50 and panel['points_on_centerline']
        assert np.allclose(panel['quartiles'],np.quantile(panel['values'],[.25,.5,.75]))
    for n in data['n']:
        assert len([c for c in data['gradient_curves'] if c['n']==n])==50
        assert {c['id'] for c in data['gradient_curves'] if c['n']==n}==set(range(1,51))
        for c in [c for c in data['gradient_curves'] if c['n']==n]:
            assert all(not p.get('virtual',False) and 0<=p['gamma']<samples[n,c['id']]['values'][0] for p in c['points'])
    assert len(list(output.glob('*.png')))==4+int((output/'估计分布_线性坐标试画.png').is_file())
    assert not list(output.glob('*.pdf'))
    assert not list(output.glob('*.svg'))
    assert qa['formats']==['png 450dpi']
    checked=0
    if rerun:
        for n in data['n']:
            x=samples[n,1]['values']
            for method in METHODS:
                result=run_method(method,x,**({'offset':.2,'gamma_steps':240} if method=='mdm' else {}))
                original=fits[n,1,method]
                assert result['converged']==original['converged']
                for key in ('beta_hat','eta_hat','gamma_hat'):
                    if original[key] is None: assert result[key] is None
                    else: assert math.isclose(result[key],original[key],rel_tol=1e-6,abs_tol=1e-5)
                checked+=1
    record=dict(distribution=case.name,samples_checked=150,observations_checked=sum(s['n'] for s in data['samples']),
                fit_records_checked=750,excel_parameter_cells_checked=numbers,excel_sheets_checked=6,
                gradient_curves_checked=150,violin_distributions_checked=45,independent_fit_reruns=checked,
                full_sample_regeneration=True,source_hashes_verified=True,excel_notes=0)
    print(json.dumps(record,ensure_ascii=False),flush=True)
    return record


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--case':
        result=one_case(Path(sys.argv[2]),True)
        (ROOT/'结果'/Path(sys.argv[2]).name/'中间数据/复核.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    else:
        layout=check_layout()
        records=[]
        for case in sorted((ROOT/'程序').glob('W(*)')):
            subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--case',str(case)],check=True)
            records.append(json.loads((ROOT/'结果'/case.name/'中间数据/复核.json').read_text(encoding='utf-8')))
        record=dict(combinations=8,samples=1200,observations=20800,method_records=6000,independent_fit_reruns=120,
                    workbooks=8,scientific_figures=32,figure_exports=32,layout=layout,records=records)
        (ROOT/'程序/核验结果.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('VERIFIED 8 workbooks, all samples and values, 120 independent method reruns.',flush=True)
