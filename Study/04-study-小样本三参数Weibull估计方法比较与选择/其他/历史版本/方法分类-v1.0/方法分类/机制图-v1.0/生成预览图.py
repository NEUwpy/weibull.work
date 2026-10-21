from pathlib import Path
import xml.etree.ElementTree as ET
import html
import re
import unicodedata

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '预览'
OUT.mkdir(exist_ok=True)

def style_map(value):
    out = {}
    for item in (value or '').split(';'):
        if '=' in item:
            key, val = item.split('=', 1)
            out[key] = val
    return out

def clean(value):
    value = html.unescape(html.unescape(value or ''))
    value = re.sub(r'<br\s*/?>', '\n', value, flags=re.I)
    return re.sub(r'<[^>]+>', '', value).replace('&nbsp;', ' ')

def escape(value):
    return html.escape(value, quote=True)

def wrap(line, width, size):
    lines, current, used = [], '', 0
    for char in line:
        advance = size * (1 if unicodedata.east_asian_width(char) in 'WF' else .58)
        if current and used + advance > width:
            lines.append(current); current, used = '', 0
        current += char; used += advance
    return lines + [current]

def render(src, dst):
    model = ET.parse(src).find('.//mxGraphModel')
    width = int(float(model.get('pageWidth', '2400')))
    height = int(float(model.get('pageHeight', '1600')))
    cells = model.findall('./root/mxCell')
    vertices, edges, boxes = [], [], {}
    for cell in cells:
        geo = cell.find('./mxGeometry')
        if geo is None:
            continue
        if cell.get('edge') == '1':
            edges.append((cell, style_map(cell.get('style'))))
        elif cell.get('vertex') == '1':
            x = float(geo.get('x', 0)); y = float(geo.get('y', 0))
            w = float(geo.get('width', 0)); h = float(geo.get('height', 0))
            boxes[cell.get('id')] = (x, y, w, h)
            vertices.append((cell, x, y, w, h, style_map(cell.get('style'))))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(src.stem)}">', '<rect width="100%" height="100%" fill="#ffffff"/>']
    colors = sorted({st.get('strokeColor', '#83968a') for _,st in edges})
    parts.append('<defs>')
    for color in colors:
        key=color.lstrip('#')
        for arrow in ('block','open'):
            fill=color if arrow=='block' else 'none'
            shape='M1 1 L14 7 L1 13 Z' if arrow=='block' else 'M1 1 L14 7 L1 13'
            parts.append(f'<marker id="arrow-{arrow}-{key}" markerWidth="15" markerHeight="14" refX="14" refY="7" markerUnits="userSpaceOnUse" orient="auto"><path d="{shape}" fill="{fill}" stroke="{color}" stroke-width="1.3"/></marker>')
    parts.append('</defs>')

    def vertex(item):
        cell, x, y, w, h, st = item
        fill = st.get('fillColor', '#ffffff'); stroke = st.get('strokeColor', '#83968a'); stroke_width = st.get('strokeWidth', '1.2')
        radius = '10' if st.get('rounded') == '1' else '0'; dash = ' stroke-dasharray="7 5"' if st.get('dashed') == '1' else ''
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius}" fill="{escape(fill)}" stroke="{escape(stroke)}" stroke-width="{stroke_width}"{dash}/>')
        text = clean(cell.get('value'))
        if not text:
            return
        size = float(st.get('fontSize', '18')); color = st.get('fontColor', '#263238')
        bold = ' font-weight="700"' if st.get('fontStyle') == '1' else ''
        spacing = float(st.get('spacing', '8'))
        lines = [piece for line in text.split('\n') for piece in wrap(line, w - spacing * 2, size)]
        line_height = size * 1.25
        valign = st.get('verticalAlign', 'middle')
        if valign == 'top':
            start = y + spacing + size
        elif valign == 'bottom':
            start = y + h - spacing - (len(lines) - 1) * line_height
        else:
            start = y + (h - (len(lines) - 1) * line_height) / 2 + size * .35
        align = st.get('align', 'center')
        if align == 'left':
            tx, anchor = x + spacing, 'start'
        elif align == 'right':
            tx, anchor = x + w - spacing, 'end'
        else:
            tx, anchor = x + w / 2, 'middle'
        for index, line in enumerate(lines):
            parts.append(f'<text x="{tx:.1f}" y="{start + index * line_height:.1f}" font-family="Microsoft YaHei,Segoe UI,sans-serif" font-size="{size:.1f}" fill="{escape(color)}" text-anchor="{anchor}"{bold}>{escape(line)}</text>')

    def background(item):
        cell, _, _, _, _, st = item
        return cell.get('renderRole')=='background' or st.get('dashed')=='1' or cell.get('id','').endswith('-panel')

    # 分组背景先画，关系线随后画，方法节点和关系文字最后画。
    for item in sorted((v for v in vertices if background(v)),key=lambda v:-v[3]*v[4]):vertex(item)
    labels=[]
    for cell,st in edges:
        source,target=cell.get('source'),cell.get('target')
        if source not in boxes or target not in boxes:
            raise ValueError(f'{src.name}: edge {cell.get("id")} has no endpoint')
        x1,y1,w1,h1=boxes[source];x2,y2,w2,h2=boxes[target]
        c1=(x1+w1/2,y1+h1/2);c2=(x2+w2/2,y2+h2/2)
        def clip(x,y,w,h,center,toward):
            dx,dy=toward[0]-center[0],toward[1]-center[1]
            if dx==dy==0:return center
            scale=min(w/2/abs(dx) if dx else float('inf'),h/2/abs(dy) if dy else float('inf'))
            return center[0]+dx*scale,center[1]+dy*scale
        points=[(float(p.get('x')),float(p.get('y'))) for p in cell.findall('./mxGeometry/Array/mxPoint')]
        start=(x1+w1*float(st['exitX']),y1+h1*float(st['exitY'])) if 'exitX' in st else clip(x1,y1,w1,h1,c1,points[0] if points else c2)
        end=(x2+w2*float(st['entryX']),y2+h2*float(st['entryY'])) if 'entryX' in st else clip(x2,y2,w2,h2,c2,points[-1] if points else c1)
        path=[start,*points,end];color=st.get('strokeColor','#83968a');arrow=st.get('endArrow','').lower()
        marker=f' marker-end="url(#arrow-{arrow}-{color.lstrip(chr(35))})"' if arrow in ('open','block') else ''
        dash=f' stroke-dasharray="{st.get("dashPattern","7 5")}"' if st.get('dashed')=='1' else ''
        coords=' '.join(f'{x:.1f},{y:.1f}' for x,y in path)
        parts.append(f'<polyline points="{coords}" fill="none" stroke="{escape(color)}" stroke-width="{st.get("strokeWidth","1.5")}" stroke-linejoin="round"{dash}{marker}/>')
        label=clean(cell.get('value'))
        if label:labels.append((cell,st,label,(start[0]+end[0])/2,(start[1]+end[1])/2))
    for item in vertices:
        if not background(item):vertex(item)
    for cell,st,label,mx,my in labels:
        mx=float(cell.get('labelX',mx));my=float(cell.get('labelY',my));size=float(st.get('fontSize','17'))
        lines=label.split('\n');start=my-(len(lines)-1)*size*.65+size*.3
        for i,line in enumerate(lines):
            parts.append(f'<text x="{mx:.1f}" y="{start+i*size*1.3:.1f}" font-family="Microsoft YaHei,Segoe UI,sans-serif" font-size="{size}" fill="{st.get("strokeColor","#475569")}" text-anchor="middle" paint-order="stroke" stroke="#fff" stroke-width="7" stroke-linejoin="round">{escape(line)}</text>')
    parts.append('</svg>')
    dst.write_text(''.join(parts), encoding='utf-8')

for drawio in sorted(ROOT.glob('*.drawio')):
    render(drawio, OUT / (drawio.stem + '.svg'))
print(f'rendered {len(list(ROOT.glob("*.drawio")))} drawio files')
