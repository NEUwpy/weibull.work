from pathlib import Path
import xml.etree.ElementTree as E
O=Path(__file__).resolve().parent
def build(en=False):
 x=E.Element('mxfile',host='app.diagrams.net',agent='Codex',version='26.0.9');d=E.SubElement(x,'diagram',id='study02',name='Study02 framework');g=E.SubElement(d,'mxGraphModel',page='1',pageWidth='1600',pageHeight='870',grid='1',gridSize='10');r=E.SubElement(g,'root');E.SubElement(r,'mxCell',id='0');E.SubElement(r,'mxCell',id='1',parent='0')
 def box(i,t,a,b,w,h,fill='#F2F4F5',stroke='#647078',size=26,bold=False):
  c=E.SubElement(r,'mxCell',id=i,value=t,vertex='1',parent='1',style=f'rounded=1;arcSize=10;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=2;fontColor=#202A32;fontFamily=Microsoft YaHei;fontSize={size};fontStyle={1 if bold else 0};spacing=12;');E.SubElement(c,'mxGeometry',x=str(a),y=str(b),width=str(w),height=str(h),attrib={'as':'geometry'})
 def text(i,t,a,b,w,h,size=25,bold=False):box(i,t,a,b,w,h,'none','none',size,bold)
 def edge(i,s,t):
  c=E.SubElement(r,'mxCell',id=i,edge='1',parent='1',source=s,target=t,style='edgeStyle=orthogonalEdgeStyle;exitX=1;exitY=0.5;entryX=0;entryY=0.5;endArrow=block;endFill=1;strokeWidth=2;strokeColor=#43525C;');E.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
 def tr(z,e):return e if en else z
 text('a',tr('(a) 共同预测流程','(a) Shared prediction pipeline'),35,20,1530,50,36,True)
 items=[('sample',tr('寿命样本 X<br>排序与标准化','Lifetime sample X<br>Sort and standardize'),40,330),('net',tr('三输出 MLP<br>n → 256 → 128 → 64 → 3','Three-output MLP<br>n → 256 → 128 → 64 → 3'),420,400),('params',tr('合法参数解码<br>形状 · 尺度 · 位置','Decode parameters<br>Shape, scale, location'),870,300),('life',tr('Weibull 公式<br>可靠度寿命点','Weibull formula<br>Reliability life points'),1220,340)]
 for i,t,a,w in items:box(i,t,a,95,w,125,'#EDF2F5')
 for a,b in [('sample','net'),('net','params'),('params','life')]:edge(a+'_'+b,a,b)
 text('infer',tr('固定网络推理仅输入样本；真参数用于仿真监督与阈值确定。','Inference uses samples only. Truth supplies simulation labels and reference thresholds.'),40,235,1520,65,24)
 text('b',tr('(b) 训练与验证目标：三条路线分别训练','(b) Training and validation: separately trained procedures'),35,310,1530,55,36,True)
 cards=[('P','#F0F0F0','#737373',tr('P  参数恢复参照','P  Parameter reference'),tr('训练：最小化参数误差<br>验证：选择参数误差最小者','Train: minimize parameter loss<br>Validate: select lowest parameter loss'),tr('参数恢复基准','Reference for parameter recovery')),
 ('Q','#E5F1F8','#0072B2',tr('Q  单寿命点监督','Q  Single-point supervision'),tr('训练：最小化目标寿命点误差<br>验证：选择目标误差最小者','Train: minimize target life-point loss<br>Validate: select lowest target loss'),tr('检验目标收益与跨点代价','Test target gains and cross-point costs')),
 ('QCP','#E5F2EC','#178064',tr('QCP  加入参数恢复约束','QCP  Add parameter constraint'),tr('训练：目标损失 + 参数约束惩罚<br>验证：可行点中目标误差最小者','Train: target loss + constraint penalty<br>Validate: lowest target loss if feasible'),tr('检验收益保留与代价修复','Test retained gains and repair'))]
 for j,(i,f,s,title,body,role) in enumerate(cards):
  a=40+j*520
  if i=='Q':title=tr('Q  单点监督（R = 0.95）','Q  Target supervision (R = 0.95)')
  box(i,'<b>'+title+'</b><br><br>'+body+'<br><br>'+role,a,390,480,235,f,s,24)
 text('tau',tr('QCP 阈值：早期 P 参考模型的验证参数损失 × 1.5；可行性针对验证集平均损失。','QCP threshold: 1.5 × earlier P reference validation loss; feasibility concerns the validation-set mean.'),40,640,1520,55,24)
 box('controls',tr('补充对照  |  QP：固定加权    ·    P_QSELECT：共同验证    ·    Q_FEAS：可行选点    ·    QMULTI：三点监督','Controls  |  QP: fixed weighting  ·  P_QSELECT: common validation  ·  Q_FEAS: feasible selection  ·  QMULTI: three-point loss'),40,725,1520,85,'#FAFAFA','#B7BFC5',23)
 E.indent(x);E.ElementTree(x).write(O/('study02-framework-en.drawio' if en else 'study02-framework-zh.drawio'),encoding='utf-8',xml_declaration=True)
for en in [False,True]:build(en)
