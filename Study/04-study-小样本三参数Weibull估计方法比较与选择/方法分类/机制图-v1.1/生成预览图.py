from pathlib import Path
import xml.etree.ElementTree as ET
import html
import re
import unicodedata
import json
import os
import shutil
import subprocess
import tempfile
from 数学排版 import normalize_markup, unmarked_expressions

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

    def rich_label(key,value,x,y,w,h,size,color,bold=False,align='center',pad=8,role='method',edge=False):
        value=normalize_markup(value)
        py=0 if role=='label' else pad
        edge_class=' edge-label' if edge else ''
        attrs=f' data-edge="true" data-cx="{x+w/2}" data-cy="{y+h/2}"' if edge else ''
        parts.append(f'<foreignObject x="{x}" y="{y}" width="{w}" height="{h}"{attrs}><div xmlns="http://www.w3.org/1999/xhtml" class="label-box{edge_class}" data-pad-x="{pad}" data-pad-y="{py}" style="font-size:{size}px;color:{color};font-weight:{700 if bold else 400};padding:{py}px {pad}px;text-align:{align}"><div class="label-content" data-cell-id="{escape(key)}" data-font-size="{size}" data-source="{escape(value)}"></div></div></foreignObject>')

    def vertex(item):
        cell, x, y, w, h, st = item
        fill = st.get('fillColor', '#ffffff'); stroke = st.get('strokeColor', '#83968a'); stroke_width = st.get('strokeWidth', '1.2')
        radius = '10' if st.get('rounded') == '1' else '0'; dash = ' stroke-dasharray="7 5"' if st.get('dashed') == '1' else ''
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius}" fill="{escape(fill)}" stroke="{escape(stroke)}" stroke-width="{stroke_width}"{dash}/>')
        text = cell.get('value','')
        if not text:
            return
        size = float(st.get('fontSize', '18')); color = st.get('fontColor', '#263238')
        spacing = float(st.get('spacing', '8'))
        rich_label(cell.get('id'),text,x,y,w,h,size,color,st.get('fontStyle')=='1',st.get('align','center'),spacing,cell.get('renderRole','method'))

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
        label=cell.get('value','')
        if label:labels.append((cell,st,label,(start[0]+end[0])/2,(start[1]+end[1])/2))
    for item in vertices:
        if not background(item):vertex(item)
    for cell,st,label,mx,my in labels:
        mx=float(cell.get('labelX',mx));my=float(cell.get('labelY',my));size=float(st.get('fontSize','17'))
        rich_label(cell.get('id'),label,mx-700,my-100,1400,200,size,st.get('strokeColor','#475569'),pad=0,role='label',edge=True)
    parts.append('</svg>')
    dst.write_text(''.join(parts), encoding='utf-8')

def main():
    import fitz
    sources=sorted(ROOT.glob('*.drawio'))
    unmarked=[]
    for source in sources:
        for cell in ET.parse(source).findall('.//mxCell'):
            value=cell.get('value','')
            if value and unmarked_expressions(value):unmarked.append((source.name,cell.get('id'),value))
    if unmarked:
        raise ValueError('请将这些数学表达写成显式LaTeX：\n'+'\n'.join(f'{name}/{key}: {value}' for name,key,value in unmarked[:30]))
    with tempfile.TemporaryDirectory(prefix='study04-typography-') as scratch:
        temp=Path(scratch).resolve()
        assert temp.is_relative_to(Path(tempfile.gettempdir()).resolve())
        jobs=[]
        for source in sources:
            layout=temp/(source.stem+'.svg');render(source,layout)
            model=ET.parse(source).find('.//mxGraphModel')
            jobs.append(dict(name=source.name,input=str(layout),pdf=str(layout.with_suffix('.pdf')),width=int(model.get('pageWidth')),height=int(model.get('pageHeight'))))
        jobfile=temp/'jobs.json';jobfile.write_text(json.dumps(jobs,ensure_ascii=False),encoding='utf-8')
        resultfile=temp/'report.json'
        env=os.environ.copy()
        bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node'
        env['NODE_PATH']=str(bundled/'node_modules')+os.pathsep+env.get('NODE_PATH','')
        node=shutil.which('node') or str(bundled/'bin/node.exe')
        subprocess.run([node,str(ROOT/'渲染数学标签.cjs'),str(jobfile),str(resultfile)],env=env,check=True)
        report=json.loads(resultfile.read_text(encoding='utf-8'))
        for job,item in zip(jobs,report['figures']):
            pdf=fitz.open(job['pdf']);assert len(pdf)==1,job['name']
            page=pdf[0]
            item['fonts']=sorted({f[3].split('+')[-1] for f in page.get_fonts()})
            item['small_labels']=[v for v in item.pop('labels') if v['size']<18 or v['size']<v['original']*.8]
            svg=ET.fromstring(page.get_svg_image(text_as_path=True))
            svg.set('width',str(job['width']));svg.set('height',str(job['height']))
            svg.set('role','img');svg.set('aria-label',Path(job['name']).stem)
            meta=ET.Element('{http://www.w3.org/2000/svg}metadata')
            meta.text=json.dumps(dict(source=job['name'],math='LaTeX / KaTeX MathML',latin_font='Times New Roman',pdf_fonts=item['fonts']),ensure_ascii=False)
            svg.insert(0,meta)
            ET.register_namespace('','http://www.w3.org/2000/svg')
            ET.ElementTree(svg).write(OUT/(Path(job['name']).stem+'.svg'),encoding='utf-8',xml_declaration=True)
            pdf.close()
        (OUT/'排版核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f'rendered {len(sources)} vector SVGs with standard math and Times New Roman')


if __name__=='__main__':main()
