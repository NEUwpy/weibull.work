"""Put each real normal/abnormal pair and its PNG inside its own case item.

Retain method principles and the established abnormal-mechanism paragraphs.
Split MMLE's two high-estimate sources into two items. Save relocation checks.
"""
from pathlib import Path
import hashlib
import json
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
REPORT=ROOT/"报告2：小样本情况下的明显异常估计.md"
LABELS=["LSE_zero","LSE_left","LSE_right","LRE_zero","LRE_left","LRE_right",
        "MLE_high","MLE_low","MLE_stop","MDM_low","MDM_edge","WMLE_low","WMLE_high",
        "MMLE_low","MMLE_high_deletion","MMLE_high_concentrated"]
BY_METHOD=[LABELS[:3],LABELS[3:6],LABELS[6:9],LABELS[9:11],LABELS[11:13],LABELS[13:]]
METHODS=["LSE","LRE","MLE","MDM","WMLE","MMLE"]
NORMAL={
    "LSE_zero":"第35组在内部位置γ=518.20取得最低点，形状为1.42，处于正常范围。第36组的最低点则落在零边界。",
    "LSE_left":"第2组的最低点位于γ=3483.60，拟合斜率为1.178，形状为0.85，处于正常范围。第1组的最低点在真位置左侧，拟合斜率明显更小。",
    "LSE_right":"第18组也选择右侧位置，但所选位置下的对数跨度为3.66，形状为0.91，处于正常范围。第19组右移后对数跨度扩大到5.83，形状进一步降低。",
    "LRE_zero":"第4组左移至γ=2296.80后，对数跨度为1.06，斜率与形状为3.01，处于正常范围。第5组移至零边界后，对数跨度进一步缩小。",
    "LRE_left":"第35组在内部位置γ=518.85取得最佳拟合，斜率与形状为1.39，处于正常范围。第36组的最佳拟合位于真位置左侧，拟合线明显更陡。",
    "LRE_right":"第18组右移后的对数跨度为3.51，形状为0.86，处于正常范围。第19组的对数跨度扩大到5.59，拟合线进一步变平。",
    "MLE_high":"第35组联合估计返回内部位置γ=521.17、形状1.49，处于正常范围。第36组选择零位置，对应明显更大的形状。",
    "MLE_low":"第3组选择γ=0，形状为10.14，处于正常范围。第4组选择较大的位置，条件似然提高，但形状降至异常范围。",
    "MLE_stop":"第38组返回内部位置γ=3283.98，形状为1.52，处于正常范围。第37组停在零位置附近，仍有提高似然的方向。",
    "MDM_low":"第10组在γ=517.71达到梯度阈值，距最小观测26.16，得到形状2.45，处于正常范围。第11组的阈值交点更接近最小观测。",
    "MDM_edge":"第4组通过梯度阈值交点返回γ=2760.08、形状2.15，处于正常范围。第5组的梯度非单调，右端探测触发了回退。",
    "WMLE_low":"第10组的两条方程在γ=516.81、形状2.78处相交，距最小观测27.06，处于正常范围。第11组的交点更接近最小观测，对应更小的形状。",
    "WMLE_high":"第10组的交点为γ=494.70、形状1.18，处于正常范围；所选位置下的对数跨度为3.02。第9组的点列更集中，交点对应明显更大的形状。",
    "MMLE_low":"第10组同样删去最小观测并平移，保留对数跨度为1.21，形状为3.19，处于正常范围。第11组平移后的跨度为1.75，形状更小。",
    "MMLE_high_deletion":"第4组删点和平移后的保留对数跨度为1.71，形状为2.48，处于正常范围。第5组的保留对数跨度仅0.42，支持更大的形状。",
    "MMLE_high_concentrated":"第8组平移后的保留对数跨度为6.43，形状为0.56，处于正常范围。第9组的跨度仅0.68，形状达到6.86。",
}
CAPTIONS={
    "LSE_zero":"第35组的内部最低点对应形状1.42；第36组的零边界最低点对应形状21.70。",
    "LSE_left":"第2组的拟合斜率对应正常形状0.85；第1组左移后拟合线变平，内部最低点对应形状8.42。",
    "LSE_right":"两组均选择右侧位置；第19组的对数间距拉开得更多，形状为0.58，第18组为0.91。",
    "LRE_zero":"第4组左移后形状为3.01；第5组移至零边界后拟合线明显变陡，形状达到13.78。",
    "LRE_left":"第35组的内部拟合对应形状1.39；第36组左移后斜率增大，形状达到18.80。",
    "LRE_right":"第19组右移后点列的横向跨度更大，拟合线更平，形状为0.56；第18组为0.86。",
    "MLE_high":"第35组返回内部位置与形状1.49；第36组的零位置候选提高似然，并对应形状23.54。",
    "MLE_low":"第3组的左侧候选对应形状10.14；第4组的右侧候选提高似然，形状降至1.44。",
    "MLE_stop":"第38组返回内部候选与形状1.52；第37组的近零停点对应形状13.10，仍有提高似然的方向。",
    "MDM_low":"第10组的阈值交点对应形状2.45；第11组的交点更接近最小观测，标准差最低点对应形状1.35。",
    "MDM_edge":"第4组在阈值交点得到形状2.15；第5组的右端探测错过内部交点，回退后的条件拟合得到形状6.43。",
    "WMLE_low":"第11组的联合交点更接近最小观测，形状降至1.10；第10组的交点对应形状2.78。",
    "WMLE_high":"第9组的距离更集中，左侧联合交点对应形状5.31；第10组的联合交点对应形状1.18。",
    "MMLE_low":"第11组的平移放大保留距离的相对离散，形状降至1.54；第10组平移后形状为3.19。",
    "MMLE_high_deletion":"第5组删点使形状得分的根大幅右移，平移后仍为7.69；第4组最终形状为2.48。",
    "MMLE_high_concentrated":"第9组完整样本已支持高估，删点后更集中，最终形状为6.86；第8组平移后的保留距离较分散。",
}

def cleanup_case(text):
    text=re.sub(r'^!\[[^\n]+\n*','',text,flags=re.M)
    text=re.sub(r'^\*\*图\d+｜[^\n]+\n*','',text,flags=re.M)
    text=re.sub(r'(?:^\|[^\n]*\n)+','',text,flags=re.M)
    for phrase in ['两组内部最低点的典型样本如下：','后两类的典型样本如下：','图6的两类典型样本如下：']:
        text=text.replace(phrase,'')
    text=re.sub(r'尺度100下第9组的样本为[^。]+。','',text)
    text=re.sub(r'W\(2,1000,3000\)、n=7的第5组样本为[^。]*?，最小观测','第5组的最小观测',text)
    text=re.sub(r'（图\d+[^）]*）','',text)
    return re.sub(r'\n{3,}','\n\n',text).strip()

def table(pair):
    lines=['| 样本 | γ̂ | β̂ | 观测值（升序） |','|---|---:|---:|---|']
    for role in ['normal','abnormal']:
        r=pair[role];gamma=f"{r['gamma_hat']:.4f}" if 0<r['gamma_hat']<.005 else f"{r['gamma_hat']:.2f}"
        values='，'.join(f'{v:.2f}' for v in r['values'])
        lines.append(f"| {r['role']}·第{r['group']}组 | {gamma} | {r['beta_hat']:.2f} | {values} |")
    return '\n'.join(lines)

def main():
    current_path=HERE/'20261010-配对图参照线精简核验.json'
    data_path=current_path if current_path.is_file() else HERE/'20261010-各情形正常异常配对核验.json'
    data=json.loads(data_path.read_text(encoding='utf-8'));pairs=data['pairs']
    before=REPORT.read_text(encoding='utf-8')
    first,before_body=before.split('\n## 2',1)
    assert hashlib.sha256(first.encode()).hexdigest()=='97b9989c15030908053b7ef70859a191df224b05220ecdbdcf325e4d04ec76e5'
    already=all(f'配对情形_{label}.png' in before for label in LABELS)
    if not already:
        leading,area=before.split('#### 2.1.1　LSE',1)
        area='#### 2.1.1　LSE'+area
        area,tail=area.split('### 2.2　样本条件与方法差异',1)
        sections=re.split(r'(?=^#### 2\.1\.\d+　)',area,flags=re.M)[1:]
        assert len(sections)==6
        new_sections=[]
        figure_number=2
        for method,labels,section in zip(METHODS,BY_METHOD,sections):
            chunks=re.split(r'(\*\*（[123]）[^*]+\*\*)',section)
            principle=chunks[0]
            headings=chunks[1::2];bodies=chunks[2::2]
            if method=='LSE':
                principle=principle.split('W(2,100,500)、n=15的第35、36组样本如下')[0]
                principle=principle.replace('图2据此绘制1−R²随γ的变化，曲线最低点对应LSE选择的位置估计。','以γ为横坐标绘制1−R²，曲线最低点对应LSE选择的位置估计。')
            if method=='MLE':principle=principle.replace('图5的ℓₚ(γ)','以γ为自变量的ℓₚ(γ)')
            if method=='MDM':principle=principle.replace('图6依次展示梯度定位、所选位置下的标准差准则和逐点伪尺度。','梯度确定位置后，形状由该位置下伪尺度标准差的最低点确定。')
            if method=='WMLE':principle=principle.replace('图7中两条零残差曲线的交点同时满足两式。','两条零残差曲线的交点同时满足两式。')
            if method=='MMLE':
                principle=principle.replace('MMLE的84个异常分为两种情形：','MMLE的84个异常分为三种情形：')
                principle=principle.replace('| 保留样本较集中，形状高估 | 4 |','| 删点后集中，形状高估 | 1 |\n| 完整样本已集中，形状高估 | 3 |')
                principle=principle.replace('图8比较完整样本、删点后的样本，以及删点后再作最小值平移的样本，分别显示样本集中、删点和平移的作用。','比较完整样本、删点后的样本和删点后再作最小值平移的样本，可分别显示样本集中、删点和平移的作用。')
                high=cleanup_case(bodies[1]);one,two=high.split('其余3条的完整样本',1)
                bodies=[bodies[0],one.replace('这4条中，1条','这1条'),'这3条的完整样本'+two]
                headings=[headings[0],'**（2）删点后集中的高估。**','**（3）完整样本集中的高估。**']
            assert len(labels)==len(headings)==len(bodies)
            result=[principle.strip()]
            for label,heading,body in zip(labels,headings,bodies):
                pair=pairs[label];r=pair['normal']
                path='跨组合诊断/20261009-形状异常退化解/图片/配对情形_'+label+'.png'
                assert (ROOT/path).is_file()
                text=cleanup_case(body)
                result.append(heading+'\n\n'+f"{r['combination']}、n={r['n']}的正常与异常样本如下："+'\n\n'+table(pair)+'\n\n'+NORMAL[label]+'\n\n'+text+'\n\n'+
                    f"![{method}正常与异常样本对照]({path})\n\n**图{figure_number}｜{CAPTIONS[label]}**")
                figure_number+=1
            new_sections.append('\n\n'.join(result))
        tail=tail.replace('图9','图18')
        after=leading+'\n\n'.join(new_sections)+'\n\n### 2.2　样本条件与方法差异'+tail
        REPORT.write_text(after,encoding='utf-8')
    text=REPORT.read_text(encoding='utf-8');first_after=text.split('\n## 2',1)[0]
    checks={}
    for index,(method,labels) in enumerate(zip(METHODS,BY_METHOD),1):
        section=text.split(f'#### 2.1.{index}　{method}',1)[1]
        section=section.split('#### 2.1.',1)[0].split('### 2.2',1)[0]
        items=re.split(r'^\*\*（[123]）',section,flags=re.M)[1:]
        assert len(items)==len(labels)
        for label,item in zip(labels,items):
            pair=pairs[label]
            checks[label]=dict(one_corresponding_figure=item.count('配对情形_')==1 and f'配对情形_{label}.png' in item,
                normal_and_abnormal_sample_in_item=all('，'.join(f'{v:.2f}' for v in pair[role]['values']) in item for role in ['normal','abnormal']),
                original_group_ids=all(f"第{pair[role]['group']}组" in item for role in ['normal','abnormal']))
            assert all(checks[label].values()),label
    links=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',text)
    assert len(links)==18 and re.findall(r'\*\*图(\d+)｜',text)==list(map(str,range(1,19)))
    assert all((ROOT/path).is_file() for path in links)
    assert first==first_after and text.count('$$')%2==0
    digest=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    sources_unchanged=all(digest(path)==value for path,value in data['source_sha256'].items())
    protected_png_unchanged=all(digest(path)==value for path,value in data['protected_png_sha256'].items())
    pair_figures_match=all(digest(figure['path'])==figure['sha256'] for figure in data['figures'].values())
    assert sources_unchanged and protected_png_unchanged and pair_figures_match
    check_path=HERE/'20261010-分项样本图归位核验.json'
    previous=json.loads(check_path.read_text(encoding='utf-8')) if check_path.is_file() else {}
    reviewed={label:record for label,record in previous.get('manual_visual_review',{}).items()
              if label in data['figures'] and record.get('sha256')==data['figures'][label]['sha256']}
    result=dict(before_report_sha256=hashlib.sha256(before.encode()).hexdigest(),report_sha256=hashlib.sha256(text.encode()).hexdigest(),
        chapter1_unchanged=True,figure_order_1_to_18=True,normal_and_abnormal_pairs_inside_every_item=checks,
        case_items=16,original_estimates_unchanged=sources_unchanged,protected_png_unchanged=protected_png_unchanged,
        pair_figures_match=pair_figures_match,source_pairing_file=str(data_path),source_pairing_sha256=digest(data_path),
        script_sha256=digest(__file__),manual_visual_review=reviewed)
    check_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS: each of 16 case items contains its own two full samples and six-panel plot; chapter1 unchanged; figure order1-18')

if __name__=='__main__':main()
