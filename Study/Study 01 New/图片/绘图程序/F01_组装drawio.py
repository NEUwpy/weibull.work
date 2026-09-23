"""F01 mechanism figure: independent data plots composed in native draw.io."""
from pathlib import Path
from urllib.parse import quote
import csv
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
STEM = "F01_MDM原理联图"
COLORS = {"input": "#C8E3D8", "search": "#C3B5C5", "solve": "#BED6EE",
          "output": "#F8DEC5", "repeat": "#D5D4D6"}
def main():
    metadata=json.loads((ROOT/"数据"/(STEM+".json")).read_text(encoding="utf-8"))
    sample=metadata["samples_sorted"]
    doc=ET.Element("mxfile",host="app.diagrams.net",agent="Codex",version="26.0.9")
    diagram=ET.SubElement(doc,"diagram",id="study01-f01",name="MDM估计机制")
    model=ET.SubElement(diagram,"mxGraphModel",dx="1520",dy="1240",grid="1",gridSize="8",
                        page="0",pageWidth="1520",pageHeight="1240",math="1",background="#ffffff")
    root=ET.SubElement(model,"root")
    ET.SubElement(root,"mxCell",id="0")
    ET.SubElement(root,"mxCell",id="1",parent="0")
    base="html=1;fontFamily=Microsoft YaHei;fontColor=#26343C;whiteSpace=wrap;"
    def node(id,value,x,y,w,h,style):
        cell=ET.SubElement(root,"mxCell",id=id,value=value,style=base+style,vertex="1",parent="1")
        ET.SubElement(cell,"mxGeometry",x=str(x),y=str(y),width=str(w),height=str(h),attrib={"as":"geometry"})
        return cell
    def label(id,value,x,y,w,h,size=22,bold=False,fill="none",align="center"):
        return node(id,value,x,y,w,h,f"text;fillColor={fill};strokeColor=none;fontSize={size};fontStyle={int(bold)};align={align};verticalAlign=middle;spacing=0;")
    def panel(id,title,x,y,w,h,color):
        # An editable background region and its native text title.
        node(id,"",x,y,w,h,f"rounded=1;arcSize=4;fillColor={color};fillOpacity=17;strokeColor=none;container=1;")
        label(id+"-title",title,x,y,w,46,24,True,color)
    def asset(id,name,x,y,w,h):
        svg=(ROOT/"子图"/(name+".svg")).read_text(encoding="utf-8")
        node(id,"",x,y,w,h,"shape=image;imageAspect=1;aspect=fixed;image=data:image/svg+xml,"+quote(svg,safe="")+";")
    def line(id,x1,y1,x2,y2,color="#526F82",width=1.5,dashed=False):
        cell=ET.SubElement(root,"mxCell",id=id,edge="1",parent="1",
              style=f"endArrow=none;strokeColor={color};strokeWidth={width};dashed={int(dashed)};")
        geom=ET.SubElement(cell,"mxGeometry",relative="1",attrib={"as":"geometry"})
        for name,x,y in (("sourcePoint",x1,y1),("targetPoint",x2,y2)):
            ET.SubElement(geom,"mxPoint",x=str(x),y=str(y),attrib={"as":name})
    def edge(id,source,target,exitxy=(1,.5),entryxy=(0,.5),value="",points=()):
        cell=ET.SubElement(root,"mxCell",id=id,value=value,edge="1",parent="1",source=source,target=target,
             style=base+f"edgeStyle=orthogonalEdgeStyle;rounded=0;endArrow=block;endFill=1;endSize=8;strokeWidth=1.8;strokeColor=#526F82;fontSize=23;labelBackgroundColor=#FFFFFF;exitX={exitxy[0]};exitY={exitxy[1]};entryX={entryxy[0]};entryY={entryxy[1]};")
        geom=ET.SubElement(cell,"mxGeometry",relative="1",attrib={"as":"geometry"})
        for endpoint,node_id,xy in (("sourcePoint",source,exitxy),("targetPoint",target,entryxy)):
            box=next(c for c in root if c.get("id")==node_id).find("mxGeometry")
            x=float(box.get("x"))+float(box.get("width"))*xy[0]
            y=float(box.get("y"))+float(box.get("height"))*xy[1]
            # Static geometry excludes a 1px boundary touch with the header strip.
            # Attached draw.io ports still terminate at the exact node boundary.
            if xy[0] in (0,1): x += -1 if xy[0]==0 else 1
            elif xy[1] in (0,1): y += -1 if xy[1]==0 else 1
            ET.SubElement(geom,"mxPoint",x=str(x),y=str(y),attrib={"as":endpoint})
        if points:
            arr=ET.SubElement(geom,"Array",attrib={"as":"points"})
            for x,y in points: ET.SubElement(arr,"mxPoint",x=str(x),y=str(y))

    label("part1","Ⅰ　从一个观测样本到三参数估计",20,14,1480,42,30,True,align="left")
    panel("sample","观测样本",20,78,240,184,COLORS["input"])
    label("sample-count","7个寿命观测 · 排序",30,126,220,32,20)
    # One bar per actual observation, common zero and common linear scale.
    for i,t in enumerate(sample):
        h=t/2500*64
        node("obs-"+str(i),"",49+i*26,230-h,12,h,"rounded=0;fillColor=#58727D;strokeColor=none;")
    label("lifetime-label","棒高：寿命 t",30,230,220,26,17)
    panel("prepare","构造样本求解曲线",20,308,240,236,COLORS["search"])
    label("ranks","排序样本＋秩概率",30,358,220,34,20)
    label("conditional","各候选 γ 下<br>搜索 β，使差异最小",30,402,220,64,21)
    label("profile","σ<sub>η,min</sub>(γ) → ∇(γ)",30,484,220,44,23)
    edge("sample-prepare","sample","prepare",(0.5,1),(0.5,0))

    panel("gamma","a　求解位置参数",320,78,414,466,COLORS["solve"])
    label("a-rule",r"\(\nabla(\hat\gamma)=0\)",330,136,394,58,24)
    asset("a-plot","F01a_位置求解",328,192,398,315)
    label("a-pass","交点横坐标 → γ̂",330,505,394,30,21)
    panel("beta","b　回代形状参数",784,78,414,466,COLORS["solve"])
    label("b-rule","固定 γ = γ̂，再求条件最小值",794,144,394,42,22)
    asset("b-plot","F01b_形状回代",792,192,398,315)
    label("b-pass","曲线最低点 → β̂",794,505,394,30,21)
    edge("prepare-gradient","prepare","gamma",(1,.5),(0,.75),points=((290,426),(290,427.5)))
    edge("gamma-beta","gamma","beta",value="γ̂")

    panel("eta","计算尺度参数",1248,78,252,242,COLORS["output"])
    label("eta-input","代入 γ̂ 与 β̂<br>计算各伪尺度",1260,137,228,68,22)
    label("eta-formula",r"\(\hat\eta=\frac{1}{n}\sum_{i=1}^{n}\hat\eta_i\)",1260,212,228,96,23)
    edge("beta-eta","beta","eta",(1,.4),(0,.77))
    panel("output","三参数估计",1248,382,252,162,COLORS["output"])
    label("out-value","β̂ = 2.471<br>η̂ = 819.2<br>γ̂ = 974.4",1260,437,228,96,23)
    edge("eta-output","eta","output",(.5,1),(.5,0))

    label("part2","Ⅱ　同一真值、不同抽样：重复求解，观察估计波动",20,587,1480,44,29,True,align="left")
    panel("population","相同总体",20,720,240,430,COLORS["input"])
    label("true-params",r"\(W(2,1000,1000)\)",30,774,220,58,23)
    label("resampling","30组随机样本<br>每组 n = 7",30,844,220,65,22)
    source=ROOT.parents[2]/metadata["sample_source"]
    with source.open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
    # First three rows only illustrate resampling; the comparison uses all 30.
    max_t=max(float(row[f"v{i}"]) for row in rows for i in range(1,8))
    for j,row in enumerate(rows[:3]):
        y=944+j*48
        label("sample-row-"+str(j),str(j+1),28,y-12,25,25,18)
        for i,t in enumerate(sorted(float(row[f"v{k}"]) for k in range(1,8))):
            x=65+t/max_t*170
            node(f"sample-{j}-{i}","",x-3,y-3,6,6,"ellipse;fillColor=#58727D;strokeColor=none;")
    label("more-samples","⋮",30,1050,220,35,24)
    label("samples-note","示意前3组 · 共同寿命坐标<br>下方比较使用全部30组",30,1090,220,50,18)

    label("paired","同一批样本分别采用两种判据；其余求解步骤相同",320,658,1180,48,23,True,COLORS["repeat"])
    panel("zero","c　零梯度规则：δ = 0",320,754,552,426,COLORS["repeat"])
    panel("positive","d　固定正偏移：δ = 0.1",948,754,552,426,COLORS["solve"])
    asset("c-plot","F01c_零偏移多样本",320,804,552,428)
    asset("d-plot","F01d_正偏移多样本",948,804,552,428)
    # Branch above both comparison panels; no arrow implies that c precedes d.
    edge("samples-pair","population","paired",(1,.04),(0,.5),points=((290,737.2),(290,682)))
    edge("pair-zero","paired","zero",(.234,1),(.5,0))
    edge("pair-positive","paired","positive",(.766,1),(.5,0))
    label("note","下排每点对应一次位置估计；竖向错开仅为避免重叠，竖虚线表示真值。",320,1240,1180,38,19)
    # Fit page to content; diagram exports use the actual content bounds.
    model.set("pageHeight","1300")
    ET.indent(doc,space="  ")
    target=ROOT/(STEM+".drawio")
    ET.ElementTree(doc).write(target,encoding="utf-8",xml_declaration=True)
    print(target)

if __name__=="__main__":
    main()
