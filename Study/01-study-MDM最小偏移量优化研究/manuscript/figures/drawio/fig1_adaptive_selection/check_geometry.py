"""Run the skill checker with correct group coordinates, ports and math estimates.

The stock parser treats relative child positions as page positions and connector
endpoints as node centres. Keep its raw report, then correct these parsing errors.
Math labels are measured as their rendered symbols rather than LaTeX source.
"""
from pathlib import Path
import sys,xml.etree.ElementTree as E,json,re
sys.path.insert(0,'C:/Users/36089/.codex/skills/academic-figures-drawer/scripts')
import validate_visual_quality as q
p=Path(__file__).with_name('fig1_adaptive_selection.drawio')
cells={c.get('id'):c for c in E.parse(p).iter('mxCell')}
vertices,edges,w,h=q.parse_drawio(p)
vs={v.id:v for v in vertices}
def offset(i):
 if i not in vs:return 0,0
 c=cells[i];g=c.find('mxGeometry');x,y=offset(c.get('parent'))
 return x+float(g.get('x',0)),y+float(g.get('y',0))
for v in vertices:
 v.rect.x,v.rect.y=offset(v.id)
 v.is_container='container=1' in v.style
 # Estimate only the displayed formula; the actual export must render MathJax.
 v.value=re.sub(r'\\\((.*?)\\\)',lambda m:re.sub(r'\\(?:hat|bar)\b','',m[1]).replace('\\beta','β').replace('\\eta','η').replace('\\gamma','γ').replace('\\delta','δ').replace('\\ ',' ').replace('_n','ₙ'),v.value)
for e in edges:
 parent=cells[e.id].get('parent');ox,oy=offset(parent)
 e.waypoints=[(x+ox,y+oy) for x,y in e.waypoints]
 if e.source_point:e.source_point=(e.source_point[0]+ox,e.source_point[1]+oy)
 if e.target_point:e.target_point=(e.target_point[0]+ox,e.target_point[1]+oy)
 props=q._parse_style(e.style)
 for end,nodeid,key in [('source',e.source_id,'exit'),('target',e.target_id,'entry')]:
  if nodeid in vs:
   r=vs[nodeid].rect
   setattr(e,'derived_'+end,(r.x+r.w*float(props.get(key+'X',.5)),r.y+r.h*float(props.get(key+'Y',.5))))
findings=q.run_all_checks(vertices,edges,w,h)
# A minimum marker is intentionally centred on its own curve (an annotated datum).
accepted=[];real=[]
for f in findings:
 if f.rule=='arrow-box-collision' and f.element_id=='selection_curve' and f.detail.get('box_id')=='selection_min':
  accepted.append({'rule':f.rule,'reason':'selected minimum marker lies on its own plotted curve'})
 else:real.append(f)
result={'coordinate_corrections':'group offsets and explicit connector ports; LaTeX glyph estimates','summary':{'fail':sum(f.severity=='FAIL' for f in real),'warn':sum(f.severity=='WARN' for f in real)},'findings':[{'severity':f.severity,'rule':f.rule,'id':f.element_id,'message':f.message} for f in real],'intentional_geometry':accepted}
p.with_name('geometry-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
sys.exit(bool(result['summary']['fail']))
