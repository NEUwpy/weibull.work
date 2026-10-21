"""五张原理细图共用的 draw.io 图元；总览图保持独立。"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET


class Diagram:
    def __init__(self, ident, title, width=1800, height=1300):
        self.width, self.height, self.boxes = width, height, {}
        self.doc = ET.Element('mxfile', host='app.diagrams.net', version='26.0.9')
        diagram = ET.SubElement(self.doc, 'diagram', id=ident, name=title)
        self.model = ET.SubElement(diagram, 'mxGraphModel', page='1', pageWidth=str(width), pageHeight=str(height), background='#ffffff')
        self.root = ET.SubElement(self.model, 'root')
        ET.SubElement(self.root, 'mxCell', id='0')
        ET.SubElement(self.root, 'mxCell', id='1', parent='0')

    def box(self, key, text, x, y, w, h, *, fill='#FFFFFF', color='#64748B', size=23, bold=False, role='method', align='center', extra=''):
        if key in self.boxes:
            raise ValueError(f'duplicate id: {key}')
        style = f'html=1;whiteSpace=wrap;rounded=1;arcSize=10;strokeColor={color};fillColor={fill};fontColor=#243449;fontFamily=Microsoft YaHei;fontSize={size};spacing=12;align={align};verticalAlign=middle;strokeWidth=1.8;'
        if role == 'label':style += 'strokeColor=none;fillColor=none;'
        if bold:style += 'fontStyle=1;'
        cell=ET.SubElement(self.root,'mxCell',id=key,value=text,vertex='1',parent='1',style=style+extra,renderRole=role)
        ET.SubElement(cell,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),**{'as':'geometry'})
        self.boxes[key]=(x,y,w,h)
        return key

    def text(self, key, text, x, y, w, h, *, size=23, bold=False, color='#243449', align='left'):
        return self.box(key,text,x,y,w,h,size=size,bold=bold,color=color,role='label',align=align)

    def panel(self,key,x,y,w,h,*,fill='#F7F9FC',color='#DFE6EB'):
        return self.box(key,'',x,y,w,h,fill=fill,color=color,role='background')

    def _port(self, key, side):
        x,y,w,h=self.boxes[key]
        return {'left':(x,y+h/2),'right':(x+w,y+h/2),'top':(x+w/2,y),'bottom':(x+w/2,y+h)}[side]

    def edge(self,key,src,dst,label='',*,color='#475569',kind='flow',start='right',end='left',via=(),at=None,width=2.5,arrow='block',evidence=''):
        positions={'left':(0,.5),'right':(1,.5),'top':(.5,0),'bottom':(.5,1)}
        sx,sy=positions[start];tx,ty=positions[end]
        style=f'html=1;rounded=0;strokeWidth={width};strokeColor={color};fontColor={color};fontFamily=Microsoft YaHei;fontSize=20;labelBackgroundColor=#ffffff;endArrow={arrow};endFill=1;exitX={sx};exitY={sy};entryX={tx};entryY={ty};exitPerimeter=0;entryPerimeter=0;'
        if kind in {'math','borrow','feedback'}:style+='dashed=1;dashPattern='+('10 4 2 4;' if kind=='borrow' else '7 5;')
        cell=ET.SubElement(self.root,'mxCell',id=key,value=label,edge='1',parent='1',source=src,target=dst,style=style,relationKind=kind,evidence=evidence)
        geo=ET.SubElement(cell,'mxGeometry',relative='1',**{'as':'geometry'})
        if via:
            points=ET.SubElement(geo,'Array',**{'as':'points'})
            for x,y in via:ET.SubElement(points,'mxPoint',x=str(x),y=str(y))
        if at:
            lx,ly=at;cell.set('labelX',str(lx));cell.set('labelY',str(ly))
            path=[self._port(src,start),*via,self._port(dst,end)]
            lengths=[math.dist(a,b) for a,b in zip(path,path[1:])];total=sum(lengths);walk=0;best=None
            for a,b,length in zip(path,path[1:],lengths):
                if not length:continue
                t=max(0,min(1,((lx-a[0])*(b[0]-a[0])+(ly-a[1])*(b[1]-a[1]))/length**2))
                px,py=a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]);candidate=(math.dist((lx,ly),(px,py)),walk+t*length,px,py)
                if best is None or candidate[0]<best[0]:best=candidate
                walk+=length
            if best and total:
                geo.set('x',str(2*best[1]/total-1))
                ET.SubElement(geo,'mxPoint',x=str(lx-best[2]),y=str(ly-best[3]),**{'as':'offset'})
        return key

    def line(self,key,points,*,color='#64748B',width=2,arrow='none',dashed=False):
        a,b=points[0],points[-1]
        for suffix,(x,y) in [('a',a),('b',b)]:
            self.box(key+'-'+suffix,'',x,y,0,0,fill='none',color='none',size=1,role='anchor')
        return self.edge(key,key+'-a',key+'-b',color=color,width=width,arrow=arrow,via=points[1:-1],kind='math' if dashed else 'flow')

    def save(self,path):
        ET.indent(self.doc,space='  ')
        ET.ElementTree(self.doc).write(Path(path),encoding='utf-8',xml_declaration=True)
