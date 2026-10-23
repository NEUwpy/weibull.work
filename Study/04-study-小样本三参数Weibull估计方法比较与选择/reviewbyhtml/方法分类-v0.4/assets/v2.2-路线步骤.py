"""五条路线的共同主步骤；两张图共用名称、编号和视觉层级。"""

STEPS = {
    'L': [('L1', '构造联合似然'), ('L2', '联合最大化')],
    'D': [('D1', '构造分布表示'), ('D2', '定义匹配准则'), ('D3', '确定参数')],
    'S': [('S1', '提取样本特征'), ('S2', '建立理论关系'), ('S3', '识别与恢复参数')],
    'B': [('B1', '构造后验'), ('B2', '后验决策')],
    'N': [('N1', '训练映射'), ('N2', '固定映射用于新样本')],
}
LABELS = {code: code + ' ' + name for steps in STEPS.values() for code, name in steps}


def label(code):
    return LABELS[code]


def main_group(d, code, x, y, w, h, *, color, fill, heading_y=None, size=32):
    """一个带主标题的整块区域；区域内部算例子过程不再独立编号。"""
    key = 'main-' + code
    d.panel(key, x, y, w, h, color=color, fill=fill)
    cell = d.root[-1]
    cell.set('routeStep', code)
    cell.set('stepLabel', label(code))
    d.text(key + '-title', label(code), x+20, y+15 if heading_y is None else heading_y,
           w-40, 60, size=size, bold=True, color=color)
    return key


def hide_panel(d, key):
    cell = next(c for c in d.root.findall('mxCell') if c.get('id') == key)
    cell.set('style', cell.get('style') + 'strokeColor=none;fillColor=none;')


def set_label(d, key, value, *, y=None, size=None, bold=None):
    cell = next(c for c in d.root.findall('mxCell') if c.get('id') == key)
    from 数学排版 import normalize_markup
    cell.set('value', normalize_markup(value))
    if y is not None:
        cell.find('mxGeometry').set('y', str(y))
    if size is not None:
        cell.set('style', cell.get('style') + f'fontSize={size};')
    if bold is not None:
        cell.set('style', cell.get('style') + f'fontStyle={1 if bold else 0};')


def validate_pairs(root):
    import json
    import xml.etree.ElementTree as ET
    from pathlib import Path
    root = Path(root)
    report = {'pairs': []}
    for route, pair in zip('LDSBN', [(7,1),(8,2),(9,3),(10,4),(11,5)]):
        expected = [(code, label(code)) for code, _ in STEPS[route]]
        files = []
        for number in pair:
            path = next(root.glob(f'{number:02d}-*.drawio'))
            cells = ET.parse(path).findall('.//mxCell')
            actual = [(c.get('routeStep'), c.get('stepLabel')) for c in cells if c.get('routeStep')]
            assert actual == expected, (path.name, actual, expected)
            for code, title in expected:
                headings = [c for c in cells if c.get('id') == 'main-'+code+'-title' or c.get('id') == code]
                assert len(headings) == 1 and headings[0].get('value').split('<br>')[0] == title, (path.name, code)
            files.append(path.name)
        report['pairs'].append({'route': route, 'files': files, 'main_steps': expected, 'matching': True})
    (root/'预览'/'步骤对应核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('five figure pairs: identical main step labels, counts, order and IDs (2/3/3/2/2)')


if __name__ == '__main__':
    from pathlib import Path
    validate_pairs(Path(__file__).resolve().parent)
