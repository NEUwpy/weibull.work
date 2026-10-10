"""Report observed parameter cells for every method-specific anomaly case.

Read the 963 archived classifications and validate against the full flow audit.
Split MMLE high cases by the existing complete-sample condition at true gamma.
Save all 624 case/parameter/n cells (including zeros), then replace only the
six classification tables in report2. No estimation or figure generation.
"""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
REPORT=ROOT/'报告2：小样本情况下的明显异常估计.md'
METHOD_CASES={
    'LSE': [('zero_high','零边界高估',105),('interior_left_high','内部左侧高估',28),('interior_right_low','内部右侧低估',110)],
    'LRE': [('zero_high','零边界高估',104),('interior_left_high','内部左侧高估',35),('interior_right_low','内部右侧低估',116)],
    'MLE': [('left_higher_likelihood_high','左侧较高似然高估',158),('right_higher_likelihood_low','右侧较高似然低估',27),('search_stop_high','搜索停点高估',12)],
    'MDM δ=0.20': [('right_threshold_low','阈值交点低估',99),('right_edge_high','右端回退高估',1)],
    'WMLE': [('right_joint_intersection_low','右侧交点低估',82),('left_joint_intersection_high','左侧交点高估',2)],
    'MMLE': [('minimum_shift_low','最小值平移低估',80),('deletion_concentrated_high','删点后集中高估',1),('complete_concentrated_high','完整样本集中高估',3)],
}
NOTE='分类表的单元格列出出现该类异常的样本量n，列名括号内为异常数量。'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def key(row):
    return row['combination'],int(row['n']),int(row['group']),row['method']

def truth(row):
    return tuple(float(row[name]) for name in ['beta_true','eta_true','gamma_true'])

def combo_name(values):
    return 'W('+','.join(f'{value:g}' for value in values)+')'

def first_table(section):
    match=re.search(r'^\|[^\n]*\n(?:\|[^\n]*\n)+',section,flags=re.M)
    assert match is not None
    return match

def main():
    class_path=HERE/'20261010-六方法异常情形.csv'
    class_qa_path=HERE/'20261010-六方法异常情形核验.json'
    flow_path=HERE/'全量流程定位.csv'
    flow_qa_path=HERE/'全量流程定位.json'
    class_qa=json.loads(class_qa_path.read_text(encoding='utf-8'))
    flow_qa=json.loads(flow_qa_path.read_text(encoding='utf-8'))
    sources=dict(flow_qa['source_sha256'])
    sources.update({str(path):digest(path) for path in [class_path,class_qa_path,flow_path,flow_qa_path,Path(__file__)]})
    assert all(digest(path)==value for path,value in sources.items())
    pngs={str(path):digest(path) for path in HERE.parents[1].rglob('*.png')}
    old_report=REPORT.read_text(encoding='utf-8')
    chapter1=old_report.split('\n## 2',1)[0]
    classes=list(csv.DictReader(class_path.open(encoding='utf-8-sig',newline='')))
    full=list(csv.DictReader(flow_path.open(encoding='utf-8-sig',newline='')))
    full_abnormal={key(row):row for row in full if row['abnormal']=='True'}
    assert len(classes)==len(full_abnormal)==963
    assert len({key(row) for row in classes})==963
    assert {key(row) for row in classes}==set(full_abnormal)
    combos=sorted({truth(row) for row in full})
    assert len(combos)==13
    counts=Counter()
    mmle_check={}
    for row in classes:
        original=full_abnormal[key(row)]
        for name in ['beta_hat','eta_hat','gamma_hat','beta_true','eta_true','gamma_true']:
            assert float(row[name])==float(original[name]),(key(row),name)
        case=row['case']
        if row['method']=='MMLE' and case=='concentrated_retained_high':
            already_high=float(original['beta_full_sample_fixed_true'])>=3*float(original['beta_true'])
            case='complete_concentrated_high' if already_high else 'deletion_concentrated_high'
            mmle_check[key(row)[:3]]=already_high
        counts[row['method'],case,truth(row),int(row['n'])]+=1
    expected_mmle={(row['combination'],row['n'],row['group']):row['complete_already_high']
                   for row in class_qa['mmle_same_true_location_deletion_comparisons']}
    assert mmle_check==expected_mmle

    cells=[]
    case_summaries={}
    tables={}
    represented=set()
    for method,cases in METHOD_CASES.items():
        case_summaries[method]={}
        for case,label,total in cases:
            assert sum(v for (m,c,_,_),v in counts.items() if m==method and c==case)==total
            support=[]
            for values in combos:
                for n in [7,15,30]:
                    count=counts[method,case,values,n]
                    entry=dict(method=method,case=case,case_label=label,combination=combo_name(values),
                               beta_true=values[0],eta_true=values[1],gamma_true=values[2],n=n,count=count)
                    cells.append(entry)
                    if count:support.append(entry)
            case_summaries[method][case]=dict(label=label,total=total,observed_cells=support)
        header=['参数组合']+[f'{label}（{total}）' for _,label,total in cases]
        lines=['| '+' | '.join(header)+' |','|'+'|'.join(['---']+[':---:']*len(cases))+'|']
        for values in combos:
            if not any(counts[method,case,values,n] for case,_,_ in cases for n in [7,15,30]):continue
            row=[combo_name(values)]
            for case,_,_ in cases:
                ns=[n for n in [7,15,30] if counts[method,case,values,n]]
                row.append('、'.join(map(str,ns)) if ns else '—')
                represented.update((method,case,values,n) for n in ns)
            lines.append('| '+' | '.join(row)+' |')
        tables[method]='\n'.join(lines)+'\n'
    assert len(cells)==624 and sum(row['count'] for row in cells)==963
    assert represented=={k for k,v in counts.items() if v}

    report=old_report
    preserved_bodies={}
    for index,(method,_) in enumerate(METHOD_CASES.items(),1):
        heading=f'#### 2.1.{index}　{method.split(" δ=")[0]}'
        leading,section=report.split(heading,1)
        next_heading='#### 2.1.' if index<6 else '### 2.2'
        area,ending=section.split(next_heading,1)
        match=first_table(area)
        preserved_bodies[method]=hashlib.sha256(area[match.end():].encode()).hexdigest()
        area=area[:match.start()]+tables[method]+area[match.end():]
        assert hashlib.sha256(area[first_table(area).end():].encode()).hexdigest()==preserved_bodies[method]
        report=leading+heading+area+next_heading+ending
    if NOTE not in report:
        report=report.replace('### 2.1　各方法的异常形成机制\n\n','### 2.1　各方法的异常形成机制\n\n'+NOTE+'\n\n',1)
    assert report.split('\n## 2',1)[0]==chapter1
    assert old_report.split('### 2.2',1)[1]==report.split('### 2.2',1)[1]
    assert re.findall(r'\*\*图(\d+)｜',report)==list(map(str,range(1,19)))
    REPORT.write_text(report,encoding='utf-8')
    data_path=HERE/'20261010-各类异常参数空间.csv'
    with data_path.open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(cells[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(cells)
    output=dict(scope='Six methods, all 963 original R00 shape anomalies; 13 combinations and n=7,15,30.',
                presentation='Each method has an exact combination by anomaly-case matrix; cells list observed n levels.',
                case_summaries=case_summaries,total_anomalies=963,total_case_parameter_cells=624,
                observed_cells=len(represented),source_sha256=sources,protected_png_sha256=pngs,
                sources_unchanged=all(digest(path)==value for path,value in sources.items()),
                png_unchanged=all(digest(path)==value for path,value in pngs.items()),
                all_abnormal_records_covered=True,all_condition_sets_exact=True,
                chapter1_unchanged=True,mechanism_case_bodies_unchanged=preserved_bodies,
                section2_2_and_chapter3_unchanged=True,report_sha256=digest(REPORT),
                data_sha256=digest(data_path))
    assert output['sources_unchanged'] and output['png_unchanged']
    (HERE/'20261010-各类异常参数空间核验.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS: six method tables cover all 963 anomalies in 16 cases; exact parameter/n cells saved including zeros; samples, estimates, figures and mechanism bodies unchanged')

if __name__=='__main__':main()
