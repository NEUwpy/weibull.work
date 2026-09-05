"""Editable neural architecture, loss paths and schematic validation selection."""
from pathlib import Path
import xml.etree.ElementTree as E
O=Path(__file__).resolve().parent
def build(en=False):
 x=E.Element('mxfile',host='app.diagrams.net',agent='Codex',version='26.0.9');d=E.SubElement(x,'diagram',id='study02',name='Network and supervision');g=E.SubElement(d,'mxGraphModel',page='1',pageWidth='1900',pageHeight='1440',grid='1',gridSize='10');r=E.SubElement(g,'root');E.SubElement(r,'mxCell',id='0');E.SubElement(r,'mxCell',id='1',parent='0');geo={}
 def tr(z,e):return e if en else z
 def box(i,t,a,b,w,h,fill='#F0F4F7',stroke='#657785',size=26,bold=False,extra=''):
  if fill in ['#DCE7EF','#E3EDF3','#CEE4DE','#EAF1F5','#EAF3EF','#F4F0E5']:fill='#F0F0F0'
  if stroke in ['#68879C','#8194A1','#497E6C','#9F8C58']:stroke='#737373'
  c=E.SubElement(r,'mxCell',id=i,value=t,vertex='1',parent='1',style=f'rounded=1;arcSize=12;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=2;fontColor=#24333D;fontFamily=Microsoft YaHei;fontSize={size};fontStyle={1 if bold else 0};spacing=6;'+extra);E.SubElement(c,'mxGeometry',x=str(a),y=str(b),width=str(w),height=str(h),attrib={'as':'geometry'});geo[i]=(a,b,w,h)
 def text(i,t,a,b,w,h,size=25,bold=False,color='#24333D'):box(i,t,a,b,w,h,'none','none',size,bold,'fontColor='+color+';')
 def line(i,points,color='#536773',width=2,dash=False,arrow=False):
  c=E.SubElement(r,'mxCell',id=i,edge='1',parent='1',style=f'edgeStyle=none;rounded=0;html=1;endArrow={"block" if arrow else "none"};endFill=1;strokeColor={color};strokeWidth={width};dashed={int(dash)};dashPattern=6 4;');z=E.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
  for p,which in [(points[0],'sourcePoint'),(points[-1],'targetPoint')]:E.SubElement(z,'mxPoint',x=str(p[0]),y=str(p[1]),attrib={'as':which})
  if len(points)>2:
   arr=E.SubElement(z,'Array',attrib={'as':'points'})
   for a,b in points[1:-1]:E.SubElement(arr,'mxPoint',x=str(a),y=str(b))
 def connect(i,s,t,sp=(1,.5),tp=(0,.5),way=None,color='#536773',dash=False,arrow=True,width=2):
  a,b,w,h=geo[s];u,v,ww,hh=geo[t];p=(a+w*sp[0],b+h*sp[1]);q=(u+ww*tp[0],v+hh*tp[1]);line(i,[p]+(way or [])+[q],color,width,dash,arrow);c=r[-1];c.set('source',s);c.set('target',t);c.set('style',c.get('style')+f'exitX={sp[0]};exitY={sp[1]};entryX={tp[0]};entryY={tp[1]};')
 def node(i,a,b,diam=28,fill='#DCE7EF',stroke='#68879C'):box(i,'',a-diam/2,b-diam/2,diam,diam,fill,stroke,20,extra='ellipse;aspect=fixed;')
 def bind(s,t,sp=(1,.5),tp=(0,.5)):
  c=r[-1];c.set('source',s);c.set('target',t);c.set('style',c.get('style')+f'exitX={sp[0]};exitY={sp[1]};entryX={tp[0]};entryY={tp[1]};')
 text('titleA',tr('(a) 三参数输出神经网络与寿命点计算','(a) Three-parameter neural estimator and life-point calculation'),25,10,1850,60,38,True)
 text('sampletitle',tr('排序寿命样本','Sorted sample'),30,92,230,45,28,True)
 for j,lab in enumerate(['x<sub>(1)</sub>','x<sub>(2)</sub>','⋮','x<sub>(n)</sub>']):box('sample'+str(j),lab,85,155+j*43,100,38,'#EAF1F5','#8194A1',24)
 text('standardize',tr('训练集标准化','Training scaler'),25,348,230,48,25)
 xs=[330,475,620,765,910];counts=[4,5,5,4,3];layers=[]
 for k,(cx,count) in enumerate(zip(xs,counts)):
  yy=[240+(j-(count-1)/2)*47 for j in range(count)];layers.append([(f'neuron_{k}_{j}',cx,cy) for j,cy in enumerate(yy)])
 for k in range(4):
  for i,cx,cy in layers[k]:
   for j,dx,dy in layers[k+1]:
    line('weight_'+i+'_'+j,[(cx+14,cy),(dx-14,dy)],'#CAD5DD',1);bind(i,j)
 for k,layer in enumerate(layers):
  for i,cx,cy in layer:node(i,cx,cy,28,'#E3EDF3' if k<4 else '#CEE4DE')
 for k,(cx,lab) in enumerate(zip(xs,['n','256','128','64','3'])):text('width'+str(k),lab,cx-55,100,110,43,29,True)
 text('hidden',tr('全连接隐藏层 · ReLU','Dense hidden layers · ReLU'),405,361,430,48,27)
 line('inputbrace',[(307,145),(299,145),(299,335),(307,335)],'#737373',1.5)
 line('inputflow',[(195,240),(299,240)],arrow=True)
 for j in range(3):
  text('raw'+str(j),f'o<sub>{j+1}</sub>',941,151+j*47,60,34,24);line('rawedge'+str(j),[(925,193+j*47),(1006,193+j*47)],arrow=True);bind(f'neuron_4_{j}','decode',(1,.5),(0,(56+47*j)/211))
 box('decode',tr('<b>参数解码</b><br><br>β̂ = softplus(o₁) + ε<br>η̂ = softplus(o₂) + ε<br>γ̂ = min(X) · s(o₃)','<b>Parameter decoding</b><br><br>β̂ = softplus(o₁) + ε<br>η̂ = softplus(o₂) + ε<br>γ̂ = min(X) · s(o₃)'),1010,137,400,211,'#EAF3EF','#497E6C',27)
 text('decodenote',tr('s：有边界余量的 sigmoid','s: sigmoid with boundary margin'),1000,360,420,46,23)
 line('minpath',[(85,174),(15,174),(15,451),(1440,451),(1440,330),(1410,330)],color='#708A81',arrow=True);bind('sample0','decode',(0,.5),(1,.915))
 text('minlabel',tr('原始样本最小值','Raw sample minimum'),1000,412,400,33,23)
 box('weibull','<b>Weibull</b><br><br>x̂<sub>R</sub> = γ̂ + η̂(−ln R)<sup>1/β̂</sup><br><br>R = 0.90, 0.95, 0.99',1500,140,365,205,'#F4F0E5','#9F8C58',27)
 connect('param_to_life','decode','weibull')
 text('titleB',tr('(b) P、Q与QCP的监督路径','(b) Supervision paths for P, Q, and QCP'),25,530,1850,60,38,True)
 for route,base,color,fill,title in [('P',30,'#737373','#F0F0F0',tr('P  逐参数误差监督','P  Parameter-error supervision')),('Q',660,'#0072B2','#E5F1F8',tr('Q  单寿命点监督','Q  Single-life-point supervision')),('QCP',1290,'#178064','#E5F2EC',tr('QCP  目标监督＋参数约束','QCP  Constrained target loss'))]:
  text(route+'title',title,base,600,580,45,31,True,color)
  for j in range(3):
   for k in range(3):
    line(f'{route}_mini_w{j}{k}',[(base+49,675+j*40),(base+91,675+k*40)],'#BCCBD3',1.3);bind(f'{route}_mini_i{j}',f'{route}_mini_o{k}')
  for j in range(3):node(f'{route}_mini_i{j}',base+40,675+j*40,18)
  for j in range(3):node(f'{route}_mini_o{j}',base+100,675+j*40,18,fill,color)
  text(route+'theta','θ',base+123,736,65,40,28,True)
  box(route+'params','β̂ &nbsp; η̂ &nbsp; γ̂',base+205,683,340,64,fill,color,31)
  connect(route+'out',route+'_mini_o1',route+'params',color=color)
  if route=='P':
   for j,formula in enumerate(['((β̂−β)/β)²','((η̂−η)/η)²','((γ̂−γ)/η)²']):
    a=base+20+j*190;box('P_error'+str(j),formula,a,834,170,72,fill,color,25)
    connect('P_branch'+str(j),'Pparams','P_error'+str(j),sp=(.15+.35*j,1),tp=(.5,0),way=[(base+256+119*j,786),(a+85,786)],color=color)
   box('P_loss','L<sub>P</sub> = mean(Σ)',base+205,972,340,68,fill,color,29,True)
   for j in range(3):connect('P_sum'+str(j),'P_error'+str(j),'P_loss',sp=(.5,1),tp=(.15+.35*j,0),way=[(base+105+190*j,941),(base+256+119*j,941)],color=color)
   text('Ptruth',tr('β、η、γ：<br>仿真真参数标签','β, η, γ:<br>simulated ground truth'),base+10,1060,340,70,24);loss='P_loss'
  elif route=='Q':
   box('Q_function','x̂<sub>0.95</sub> = γ̂ + η̂(−ln 0.95)<sup>1/β̂</sup>',base+170,834,410,75,fill,color,27)
   connect('Q_formula','Qparams','Q_function',sp=(.5,1),tp=(.5,0),color=color)
   box('Q_loss','L<sub>Q</sub> = mean[((x̂<sub>0.95</sub>−x<sub>0.95</sub>)/x<sub>0.95</sub>)²]',base+170,972,410,80,fill,color,26)
   connect('Q_target','Q_function','Q_loss',sp=(.5,1),tp=(.5,0),color=color)
   text('Qtruth',tr('真寿命点<br>x<sub>0.95</sub>','True life<br>x<sub>0.95</sub>'),base+10,944,145,90,25)
   connect('Q_label','Qtruth','Q_loss',color=color)
   loss='Q_loss'
  else:
   box('QCP_p','L<sub>P,b</sub><br>'+tr('参数误差','Parameter loss'),base+20,820,235,78,fill,color,26)
   box('QCP_q','L<sub>Q,b</sub><br>'+tr('经 x̂<sub>0.95</sub> 计算','Via x̂<sub>0.95</sub>'),base+335,820,235,78,'#E5F1F8','#0072B2',26)
   connect('QCP_Pbranch','QCPparams','QCP_p',sp=(.2,1),tp=(.5,0),way=[(base+273,785),(base+137.5,785)],color=color)
   connect('QCP_Qbranch','QCPparams','QCP_q',sp=(247.5/340,1),tp=(.5,0),color='#0072B2')
   box('QCP_penalty',tr('约束惩罚 Ψ<br>g<sub>b</sub> = L<sub>P,b</sub> − τ','Penalty Ψ<br>g<sub>b</sub> = L<sub>P,b</sub> − τ'),base+20,939,235,85,fill,color,25)
   connect('QCP_violation','QCP_p','QCP_penalty',sp=(.5,1),tp=(.5,0),color=color)
   box('QCP_loss','L<sub>AL,b</sub> = L<sub>Q,b</sub> + Ψ',base+310,1055,270,65,fill,color,27,True)
   connect('QCP_taskloss','QCP_q','QCP_loss',sp=(.5,1),tp=(142.5/270,0),color='#0072B2')
   connect('QCP_add','QCP_penalty','QCP_loss',way=[(base+280,981.5),(base+280,1087.5)],color=color)
   text('QCP_tau','τ = 1.5 L<sub>P,ref</sub>',base+20,1070,235,50,25)
   connect('QCP_ref','QCP_tau','QCP_penalty',sp=(.5,0),tp=(.5,1),color=color,dash=True);loss='QCP_loss'
  a,b,w,h=geo[loss];line(route+'backprop',[(a+w*.5,b+h),(a+w*.5,1163),(base+2,1163),(base+2,715),(base+31,715)],color,2.2,True,True);bind(loss,route+'_mini_i1',(.5,1),(0,.5))
  text(route+'gradlabel',tr('反向传播','Backpropagation'),base+125,1165,430,40,23,False,color)
 for route,base,color in [('P',30,'#737373'),('Q',660,'#0072B2'),('QCP',1290,'#178064')]:
  text(route+'valtitle',tr('验证检查点选择（示意）','Validation selection (schematic)'),base+10,1225,560,43,25,True)
  ox=base+105;oy=1430;line(route+'xaxis',[(ox,oy),(base+555,oy)],'#67737A',1.5,arrow=True);line(route+'yaxis',[(ox,oy),(ox,1290)],'#67737A',1.5,arrow=True)
  text(route+'ylab','L<sub>P</sub>' if route=='P' else 'L<sub>Q</sub>',base+15,1310,80,60,26)
  if route!='QCP':
   ys=[1306,1340,1374,1395,1410,1396,1388] if route=='P' else [1318,1361,1398,1385,1408,1390,1374]
   pts=[(ox+28+j*58,y) for j,y in enumerate(ys)];k=ys.index(max(ys));cx,cy=pts[k]
   line(route+'curve_before',pts[:k+1],color,3);r[-1].set('target',route+'selected')
   line(route+'curve_after',pts[k:],color,3);r[-1].set('source',route+'selected')
   node(route+'selected',cx,cy,17,color,color)
   text(route+'seltext',tr('最低验证损失','Lowest validation loss'),base+230,1280,320,43,23,False,color);text(route+'xlab',tr('训练轮次','Epoch'),base+215,1433,220,38,24)
  else:
   boundary=ox+245;line('QCP_boundary',[(boundary,1290),(boundary,1430)],'#A9B3B8',2,True)
   text('QCP_feasible',tr('可行','Feasible'),ox+20,1279,160,40,23,True,color);text('QCP_one','1',boundary-25,1432,50,35,23);text('QCP_xlab','L<sub>P</sub> / τ',base+405,1441,170,38,25)
   text('QCP_pick',tr('○ 选中','○ Selected'),base+375,1280,200,42,23,False,color)
   pts=[(ox+30,1330),(ox+86,1364),(ox+140,1385),(ox+207,1407),(ox+305,1420),(ox+362,1412)]
   for j,(a,b) in enumerate(pts):
    if j!=3:node('QCP_checkpoint'+str(j),a,b,14,color if a<boundary else '#B2B9BD',color if a<boundary else '#B2B9BD')
   node('QCP_chosen',pts[3][0],pts[3][1],27,'none',color)
 for cell in r.findall('mxCell'):
  geom=cell.find('mxGeometry')
  if geom is None: continue
  if cell.get('vertex')=='1' and float(geom.get('y','0'))>=530: geom.set('y',str(float(geom.get('y'))-50))
  if cell.get('edge')=='1':
   for point in geom.iter('mxPoint'):
    if float(point.get('y','0'))>=530: point.set('y',str(float(point.get('y'))-50))
 E.indent(x);E.ElementTree(x).write(O/('study02-framework-en.drawio' if en else 'study02-framework-zh.drawio'),encoding='utf-8',xml_declaration=True)
for en in [False,True]:build(en)
