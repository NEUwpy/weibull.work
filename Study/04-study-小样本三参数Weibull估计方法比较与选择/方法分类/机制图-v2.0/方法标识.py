"""Use one verified identity catalog for map nodes and method-panel headings."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
CATALOG=json.loads((ROOT/'方法标识对照.json').read_text(encoding='utf-8-sig'))

def label(key,layout='map'):
    item=CATALOG[key]
    ident=f"{item['abbreviation']}（{item['year']}）"
    return ident if layout=='short' else ident+('<br>' if layout=='map' else '｜')+item['chinese_name']

DETAILS={
 '01':{'kr-title':('kr','inline'),'dmmle-title':('dmmle','inline'),'wmle-title':('wmle','inline'),'cw-title':('cw','inline'),'cmle-title':('cmle','inline'),'penalty-title':('hall-wang','inline')},
 '02':{'park-title':('park','inline'),'mps-title':('mps','inline'),'mdm-title':('mdm','inline')},
 '03':{'moment-title':('mm','inline'),'cran-title':('cran','inline'),'w-title':('lspf','inline'),'v-title':('lpf','inline'),'mvlue-title':('mvlue','inline')},
}

def unify_file(path):
    path=Path(path); number=path.name[:2]
    if number not in {'01','02','03','04','05','06'}:return
    doc=ET.parse(path);changed=False
    for cell in doc.findall('.//mxCell'):
        key=cell.get('id');value=None
        if number=='06' and cell.get('renderRole')=='method' and key in CATALOG:
            value=label(key)
            cell.set('methodId',key);cell.set('methodYear',CATALOG[key]['year'])
            if key=='ann':value=label('ann','inline')+'<br>'+label('bpnn','inline')
            if key=='mvlue':value=label('mvlue','short')+r'<br>给定\(\beta,\eta\)：位置线性无偏估计'
        if key in DETAILS.get(number,{}):
            method,layout=DETAILS[number][key];value=label(method,layout)
            if number=='01' and key=='cw-title':value=value.replace('MMLE（','MMLE-II（',1)
            if number=='03' and key=='mvlue-title':value+=r'（给定\(\beta,\eta\)）'
            cell.set('methodId',method);cell.set('methodYear',CATALOG[method]['year'])
        if number=='02' and key=='white-title':value=label('white','short')+' → '+label('soman','short')+'<br>概率图分数与位置评分回归'
        if number=='03' and key=='lm-title':value=label('pwm','short')+' → '+label('lmom','short')+'<br>→ '+label('tlmom','short')+'｜秩加权矩'
        if number=='05' and key=='direct-title':value=label('ann','short')+'／'+label('bpnn','short')+'｜直接参数映射'
        if value is not None:
            changed=changed or cell.get('value')!=value
            cell.set('value',value)
            # Method panels reserve the heading strip; two lines need a real height.
            if number in {'02','03'} and key in {'white-title','lm-title'}:
                geo=cell.find('mxGeometry');geo.set('height','85')
                cell.set('style',cell.get('style','').replace('fontSize=29;','fontSize=27;').replace('fontSize=30;','fontSize=27;'))
    ET.indent(doc,space='  ')
    doc.write(path,encoding='utf-8',xml_declaration=True)

if __name__=='__main__':
    for path in ROOT.glob('*.drawio'):unify_file(path)
    print('Unified map identities and method headings from catalog')
