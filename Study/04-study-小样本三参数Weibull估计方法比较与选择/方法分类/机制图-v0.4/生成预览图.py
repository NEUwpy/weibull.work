from pathlib import Path
import xml.etree.ElementTree as ET
import html
import re

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

def wrap(line, max_chars):
    if not line:
        return ['']
    return [line[i:i + max_chars] for i in range(0, len(line), max_chars)]

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
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(src.stem)}">', '<rect width="100%" height="100%" fill="#ffffff"/>', '<defs><marker id="arrow-open" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M1 1 L9 5 L1 9" fill="none" stroke="context-stroke" stroke-width="1.3"/></marker><marker id="arrow-block" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M1 1 L9 5 L1 9 Z" fill="context-stroke" stroke="context-stroke"/></marker></defs>']
    for cell, st in edges:
        source, target = cell.get('source'), cell.get('target')
        if source not in boxes or target not in boxes:
            continue
        x1, y1, w1, h1 = boxes[source]; x2, y2, w2, h2 = boxes[target]
        cx1, cy1 = x1 + w1 / 2, y1 + h1 / 2; cx2, cy2 = x2 + w2 / 2, y2 + h2 / 2
        color = st.get('strokeColor', '#83968a'); width_px = st.get('strokeWidth', '1.5')
        dash = ' stroke-dasharray="7 5"' if st.get('dashed') == '1' else ''
        arrow = st.get('endArrow', '').lower(); marker = f' marker-end="url(#arrow-{arrow})"' if arrow in ('open', 'block') else ''
        parts.append(f'<line x1="{cx1:.1f}" y1="{cy1:.1f}" x2="{cx2:.1f}" y2="{cy2:.1f}" stroke="{escape(color)}" stroke-width="{width_px}"{dash}{marker}/>')
        label = clean(cell.get('value'))
        if label:
            mx, my = (cx1 + cx2) / 2, (cy1 + cy2) / 2
            parts.append(f'<text x="{mx:.1f}" y="{my - 4:.1f}" font-family="Microsoft YaHei,Segoe UI,sans-serif" font-size="13" fill="{escape(color)}" text-anchor="middle" paint-order="stroke" stroke="#fff" stroke-width="5" stroke-opacity=".9">{escape(label.replace(chr(10), " "))}</text>')
    vertices.sort(key=lambda item: (0 if item[5].get('dashed') == '1' or item[0].get('id', '').startswith(('lane-', 'g-', 'chain-', 'interaction-')) else 1, -item[3] * item[4]))
    for cell, x, y, w, h, st in vertices:
        fill = st.get('fillColor', '#ffffff'); stroke = st.get('strokeColor', '#83968a'); stroke_width = st.get('strokeWidth', '1.2')
        radius = '10' if st.get('rounded') == '1' else '0'; dash = ' stroke-dasharray="7 5"' if st.get('dashed') == '1' else ''
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius}" fill="{escape(fill)}" stroke="{escape(stroke)}" stroke-width="{stroke_width}"{dash}/>')
        text = clean(cell.get('value'))
        if not text:
            continue
        size = float(st.get('fontSize', '18')); color = st.get('fontColor', '#263238')
        bold = ' font-weight="700"' if st.get('fontStyle') == '1' else ''
        spacing = float(st.get('spacing', '8')); max_chars = max(8, int((w - spacing * 2) / (size * .92)))
        lines = [piece for line in text.split('\n') for piece in wrap(line, max_chars)]
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
    parts.append('</svg>')
    dst.write_text(''.join(parts), encoding='utf-8')

for drawio in sorted(ROOT.glob('*.drawio')):
    render(drawio, OUT / (drawio.stem + '.svg'))
print(f'rendered {len(list(ROOT.glob("*.drawio")))} drawio files')
