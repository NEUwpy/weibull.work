from pathlib import Path
import xml.etree.ElementTree as E
import math

out=Path(__file__).resolve().parent
mx=E.Element('mxfile',host='app.diagrams.net',agent='Codex',version='26.0.9')
dia=E.SubElement(mx,'diagram',id='study01-fig1',name='样本自适应偏移量选择')
model=E.SubElement(dia,'mxGraphModel',dx='1280',dy='800',grid='1',gridSize='8',page='0',pageWidth='1280',pageHeight='800',math='1',background='#ffffff')
root=E.SubElement(model,'root')
E.SubElement(root,'mxCell',id='0')
E.SubElement(root,'mxCell',id='1',parent='0')
BASE='html=1;fontFamily=Microsoft YaHei;fontColor=#26343C;whiteSpace=wrap;'
nodes={}
def node(i,x,y,w,h,value='',style='',parent='1'):
 c=E.SubElement(root,'mxCell',id=i,value=value,style=BASE+style,vertex='1',parent=parent)
 E.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
 nodes[i]=(x,y,w,h)
 return c
def label(i,x,y,w,h,value,size=24,bold=False,parent='1',color='#26343C',align='center'):
 return node(i,x,y,w,h,value,f'text;fillColor=none;strokeColor=none;fontSize={size};fontStyle={1 if bold else 0};align={align};verticalAlign=middle;spacing=0;fontColor={color};',parent)
def box(i,x,y,w,h,title,sub='',blue=False):
 node(i,x,y,w,h,'',f'rounded=1;arcSize=12;fillColor={"#ECF3F8" if blue else "#F7F8F9"};strokeColor={"#426F94" if blue else "#ADB8C0"};strokeWidth={2 if blue else 1.6};container=1;collapsible=0;')
 label(i+'_title',8,12,w-16,36,title,24,True,i,color='#315E82' if blue else '#26343C')
 if sub:label(i+'_sub',8,50,w-16,h-56,sub,21,parent=i,color='#456477' if blue else '#53616B')
 return i
def edge(i,source,target,points=(),blue=False,dashed=False,ports=(1,.5,0,.5),value=''):
 ex,ey,ix,iy=ports
 style=BASE+f'edgeStyle=orthogonalEdgeStyle;rounded=0;endArrow=block;endSize=8;strokeWidth=2;strokeColor={"#426F94" if blue else "#596773"};fontSize=20;exitX={ex};exitY={ey};entryX={ix};entryY={iy};exitPerimeter=1;entryPerimeter=1;'
 if dashed:style+='dashed=1;dashPattern=6 5;'
 c=E.SubElement(root,'mxCell',id=i,value=value,style=style,edge='1',parent='1',source=source,target=target)
 g=E.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
 if points:
  a=E.SubElement(g,'Array',attrib={'as':'points'})
  for x,y in points:E.SubElement(a,'mxPoint',x=str(x),y=str(y))
def line(i,pts,color='#596773',parent='1',width=2,dashed=False):
 c=E.SubElement(root,'mxCell',id=i,value='',style=BASE+f'endArrow=none;startArrow=none;strokeWidth={width};strokeColor={color};'+('dashed=1;dashPattern=5 4;' if dashed else ''),edge='1',parent=parent)
 g=E.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
 E.SubElement(g,'mxPoint',x=str(pts[0][0]),y=str(pts[0][1]),attrib={'as':'sourcePoint'})
 E.SubElement(g,'mxPoint',x=str(pts[-1][0]),y=str(pts[-1][1]),attrib={'as':'targetPoint'})
 a=E.SubElement(g,'Array',attrib={'as':'points'})
 for x,y in pts[1:-1]:E.SubElement(a,'mxPoint',x=str(x),y=str(y))
def plot(i,x,y,w,h,title,pred=True,select=False):
 node(i,x,y,w,h,'','fillColor=none;strokeColor=none;container=1;collapsible=0;')
 label(i+'_title',0,0,w,36,title,23,True,i,color='#315E82' if pred else '#53616B')
 left,right,top,bottom=20,w-20,47,h-40
 line(i+'_axes',[(left,top-2),(left,bottom),(right,bottom)],'#A7B1B8',i,1.3)
 ys=[.18+1.4*(j/25-.44)**2+.015*math.sin(j*.5) for j in range(26)] if pred else [.15+1.6*(j/25-.36)**2+.035*math.sin(j*.46) for j in range(26)]
 pts=[(left+(right-left)*j/25,bottom-9-v*(bottom-top-10)/.8) for j,v in enumerate(ys)]
 line(i+'_curve',pts,'#426F94' if pred else '#697A84',i,3)
 label(i+'_left',left-8,bottom+3,45,30,'0',18,parent=i,align='left',color='#6A757D')
 label(i+'_right',right-44,bottom+3,52,30,'0.50',18,parent=i,align='right',color='#6A757D')
 label(i+'_axis',w/2-35,bottom+3,70,30,r'\(\delta\)',20,parent=i)
 if select:
  j=min(range(26),key=lambda z:ys[z]);px,py=pts[j]
  line(i+'_guide',[(px,py+7),(px,bottom)],'#B57729',i,1.6,True)
  node(i+'_min',px-5,py-5,10,10,'','ellipse;fillColor=#B57729;strokeColor=#B57729;',i)
  label(i+'_delta',px-27,py-65,55,36,r'\(\hat\delta\)',24,parent=i,color='#A66A20')
 return i

label('panel_a',28,18,690,48,'a  离线训练：学习候选偏移量的损失',28,True,align='left')
box('simulated',28,155,210,116,'模拟样本',r'\(X_n;\ \beta,\eta,\gamma\)')
label('true_note',28,277,210,36,'真参数仅用于标签',20,color='#6A757D')
box('label_builder',304,82,250,102,'逐候选运行 MDM','26 点实际联合损失')
box('train_predictor',304,256,250,112,'损失曲线预测','均值归一化与标准化<br>分样本量 MLP',True)
plot('actual',614,70,250,150,'实际损失',False)
plot('predicted',614,256,250,150,'预测损失',True)
box('training_loss',958,164,262,118,'曲线预测误差','标准化损失曲线间<br>的平方误差',True)
edge('sample_to_targets','simulated','label_builder',[(270,186),(270,133)],ports=(1,.27,0,.5))
edge('sample_to_model','simulated','train_predictor',[(270,244),(270,312)],True,ports=(1,.77,0,.5))
label('sample_only',240,319,64,32,'仅样本',19,color='#426F94')
edge('targets_to_curve','label_builder','actual',ports=(1,.5,0,.5))
edge('model_to_curve','train_predictor','predicted',blue=True)
edge('actual_to_loss','actual','training_loss',[(913,145),(913,194)],ports=(1,.5,0,.25))
edge('predicted_to_loss','predicted','training_loss',[(913,331),(913,253)],True,ports=(1,.5,0,.75))
edge('update','training_loss','train_predictor',[(1180,420),(429,420)],True,True,ports=(.85,1,.5,1))
label('update_label',940,348,210,36,'更新网络参数',20,color='#426F94')
line('separator',[(28,442),(1252,442)],'#D6DDE2',width=1.3)
label('panel_b',28,458,760,48,'b  实际估计：按当前样本选择偏移量',28,True,align='left')
box('observed',28,552,155,112,'当前样本',r'\(X_n\)')
box('normalization',224,552,183,112,'均值归一化','沿用训练期<br>标准化变换')
box('fixed_predictor',448,552,170,112,'已训练 MLP','分样本量模型',True)
plot('selection',650,523,230,169,'预测损失与选点',True,True)
box('mdm',924,552,130,112,'MDM','参数拟合')
box('estimates',1096,552,156,112,'参数估计',r'\(\hat\beta,\hat\eta,\hat\gamma\)')
edge('obs_to_norm','observed','normalization')
edge('norm_to_fixed','normalization','fixed_predictor',blue=True)
edge('fixed_to_curve','fixed_predictor','selection',blue=True)
edge('delta_to_mdm','selection','mdm',blue=True)
edge('mdm_to_estimates','mdm','estimates')
edge('raw_sample','observed','mdm',[(105.5,724),(989,724)],ports=(.5,1,.5,1))
label('raw_note',335,684,460,38,'原始样本直接进入 MDM',21,color='#53616B')
# Model reuse is encoded by the trained MLP label in panel b; no crossing arrow.

label('legend',28,756,1224,36,'蓝色：损失预测与选点　　虚线：网络参数更新　　曲线为示意',20,color='#6A757D',align='left')
E.indent(mx)
E.ElementTree(mx).write(out/'fig1_adaptive_selection.drawio',encoding='utf-8',xml_declaration=True)
print('Editable draw.io XML created')
