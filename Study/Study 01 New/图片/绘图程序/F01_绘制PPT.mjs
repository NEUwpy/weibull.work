/** F01 editable PowerPoint mechanism figure. Reuses saved MDM data, no new fitting. */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const RUNTIME = process.env.RUNTIME_NODE_MODULES || 'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
process.env.RUNTIME_NODE_MODULES=RUNTIME;
const { Presentation, PresentationFile } = await import(pathToFileURL(path.join(RUNTIME,'@oai/artifact-tool/dist/artifact_tool.mjs')));
const {createCanvas}=await import(pathToFileURL(path.join(RUNTIME,'@napi-rs/canvas/index.js')));
const measure=createCanvas(10,10).getContext('2d');
const SKILL='C:/Users/36089/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')));
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const REPO=path.resolve(ROOT,'../../..');
const BUILD=path.join(REPO,'tmp','f01-base');
await fs.mkdir(BUILD,{recursive:true});
const M=JSON.parse(await fs.readFile(path.join(ROOT,'数据/F01_MDM原理联图.json'),'utf8'));
const csv=(await fs.readFile(path.join(ROOT,'数据/F01_MDM原理联图.csv'),'utf8')).trim().split(/\r?\n/);
const keys=csv.shift().split(',');
const rows=csv.map(line=>Object.fromEntries(line.split(',').map((v,i)=>[keys[i],['x','y','beta','gamma'].includes(keys[i])?Number(v):v])));
const P=Presentation.create({slideSize:{width:2340,height:1290}});
const S=P.slides.add(); S.background.fill='#FFFFFF';
const INK='#263238', BLUE='#147AAA', GRAY='#82878C', EDGE='#73869A', FONT='Microsoft YaHei';
let id=0;
function rect(name,x,y,w,h,fill='none',stroke='none',lw=1,dashed=false){
 return S.shapes.add({name,geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,
 line:{fill:stroke,width:lw,style:dashed?'dashed':'solid'}});
}
function txt(name,text,x,y,w,h,size=23,color=INK,bold=false,align='center',font=FONT){
 const sh=rect(name,x,y,w,h);
 sh.text=text;
 sh.text.style={typeface:font,fontSize:size,color,bold,alignment:align,verticalAlignment:'middle',autoFit:'none',wrap:'none',insets:{left:0,right:0,top:0,bottom:0}};
 return sh;
}
function line(name,pts,color=INK,width=1.5,dashed=false){
 let x0=Math.min(...pts.map(p=>p[0])),y0=Math.min(...pts.map(p=>p[1]));
 let w=Math.max(.1,Math.max(...pts.map(p=>p[0]))-x0),h=Math.max(.1,Math.max(...pts.map(p=>p[1]))-y0);
 return S.shapes.add({name,geometry:'custom',position:{left:x0,top:y0,width:w,height:h},fill:'none',
 line:{fill:color,width,style:dashed?'dashed':'solid'},
 customPaths:[{width:w,height:h,commands:pts.map((p,i)=>({[i?'lineTo':'moveTo']:{x:p[0]-x0,y:p[1]-y0}}))}]});
}
function arrow(name,x,y,w=55,rotation=0){
 return S.shapes.add({name,geometry:'rightArrow',position:{left:x,top:y,width:w,height:20,rotation},
 fill:'#C6D9E7',line:{fill:EDGE,width:1.2}});
}
function downArrow(name,cx,y,h=20){
 return S.shapes.add({name,geometry:'downArrow',position:{left:cx-10,top:y,width:20,height:h},fill:'#C6D9E7',line:{fill:EDGE,width:1.2}});
}
function dot(name,x,y,size=8,color=INK,filled=false,square=false){
 return S.shapes.add({name,geometry:square?'rect':'ellipse',position:{left:x-size/2,top:y-size/2,width:size,height:size},
 fill:filled?color:'#FFFFFF',line:{fill:color,width:1.4}});
}
function region(prefix,title,x,y,w,h){
 const fill=prefix==='criterion'?'#A8C0E5':prefix==='result'?'#FAEAD9':'#EAF1D8';
 const stroke=prefix==='criterion'?'#6A92BD':prefix==='result'?'#CFA582':'#9FBAA5';
 rect(prefix+'.boundary',x,y,w,h,'none',stroke,1.3,true);
 rect(prefix+'.header',x,y,w,42,fill);
 txt(prefix+'.title',title,x+10,y+2,w-20,38,24,INK,true);
}
function math(name,text,x,y,w,h,size=29){
 const tokens=[];let pos=0;const pattern=/([_^])\{([^}]+)\}/g;
 for(const m of text.matchAll(pattern)){if(m.index>pos)tokens.push({text:text.slice(pos,m.index),type:'base'});tokens.push({text:m[2],type:m[1]});pos=m.index+m[0].length;}
 if(pos<text.length)tokens.push({text:text.slice(pos),type:'base'});
 const widths=tokens.map(t=>{measure.font=(t.type==='base'?size:size*.65)+'px "Cambria Math"';return measure.measureText(t.text).width;});
 let left=x+(w-widths.reduce((a,b)=>a+b,0))/2;
 return tokens.map((t,i)=>{const sz=t.type==='base'?size:size*.65;
 const sh=txt(name+'.'+i,t.text,left,y+(h-size*1.4)/2+(t.type==='_'?size*.32:t.type==='^'?-size*.32:0),widths[i]+3,size*1.4,sz,INK,false,'left','Cambria Math');left+=widths[i];return sh;});
}
function fraction(name,num,den,x,y,w,size=27){
 math(name+'.numerator',num,x,y,w,36,size);
 line(name+'.bar',[[x+5,y+38],[x+w-5,y+38]],INK,1.6);
 math(name+'.denominator',den,x,y+42,w,38,size);
}
function simpleSub(name,base,sub,x,y,size=30){
 math(name+'.base',base,x,y,size*.95,40,size);
 math(name+'.sub',sub,x+size*.72,y+19,size*2,25,size*.60);
}
function axis(prefix,x,y,w,h,xrange,yrange,xticks,yticks,xlabel,ylabel){
 const px=v=>x+(v-xrange[0])/(xrange[1]-xrange[0])*w;
 const py=v=>y+h-(v-yrange[0])/(yrange[1]-yrange[0])*h;
 line(prefix+'.axisx',[[x,y+h],[x+w,y+h]],INK,1.3);
 line(prefix+'.axisy',[[x,y],[x,y+h]],INK,1.3);
 for(const v of xticks){line(prefix+'.xtick'+v,[[px(v),y+h],[px(v),y+h+6]],INK,1);
 txt(prefix+'.xtxt'+v,String(v),px(v)-35,y+h+9,70,27,18);}
 for(const v of yticks){line(prefix+'.ytick'+v,[[x-6,py(v)],[x,py(v)]],INK,1);
 txt(prefix+'.ytxt'+v,String(v),x-62,py(v)-13,48,27,18,INK,false,'right');}
 if(xlabel)txt(prefix+'.xlabel',xlabel,x,y+h+43,w,31,21);
 if(ylabel){const sh=txt(prefix+'.ylabel',ylabel,x-153,y+h/2-18,160,36,21);sh.position={left:x-153,top:y+h/2-18,width:160,height:36,rotation:270};}
 return {px,py,x,y,w,h,xrange,yrange};
}
function clipSegment(a,b,x0,x1,y0,y1){
 let [ax,ay]=a,[bx,by]=b,dx=bx-ax,dy=by-ay,t0=0,t1=1;
 const ps=[-dx,dx,-dy,dy],qs=[ax-x0,x1-ax,ay-y0,y1-ay];
 for(let i=0;i<4;i++){if(ps[i]===0){if(qs[i]<0)return null;}else{
 const t=qs[i]/ps[i];if(ps[i]<0)t0=Math.max(t0,t);else t1=Math.min(t1,t);if(t0>t1)return null;}}
 return [[ax+t0*dx,ay+t0*dy],[ax+t1*dx,ay+t1*dy]];
}
function curve(prefix,data,a,color=INK,width=2){
 let pts=[],k=0;
 function flush(){if(pts.length>1)line(prefix+'.segment'+k++,pts,color,width);pts=[];}
 for(let i=1;i<data.length;i++){
  const c=clipSegment(data[i-1],data[i],...a.xrange,...a.yrange);
  if(!c){flush();continue;}
  const p=c.map(([x,y])=>[a.px(x),a.py(y)]);
  if(pts.length&&Math.hypot(pts.at(-1)[0]-p[0][0],pts.at(-1)[1]-p[0][1])>.1)flush();
  if(!pts.length)pts.push(p[0]);pts.push(p[1]);
 }flush();
}
function eqBox(name,plain,x,y,w,h){return math(name,plain,x,y,w,h,28);}

region('criterion','样本如何形成求解准则',40,96,500,500);
// Actual sample marks, not an icon standing in for data.
rect('criterion.input-region',53,144,474,137,'#F5F5F5');
txt('criterion.input-label','排序观测',62,150,160,34,22,INK,true);
line('criterion.sample-baseline',[[69,224],[252,224]],GRAY,1);
M.samples_sorted.forEach((t,i)=>{
 const x=69+(t-1200)/1200*183;
 line('criterion.sample-stem'+i,[[x,224],[x,204]],BLUE,1.2);
 dot('criterion.sample-dot'+i,x,204,7,BLUE,true);
});
math('criterion.sorted','t₍₁₎, …, t₍ₙ₎',58,230,200,38,27);
math('criterion.rank-left','F̂(t₍ᵢ₎) =',270,182,130,42,27);
fraction('criterion.rank','i − 0.3','n + 0.4',407,160,106,25);
txt('criterion.rank-label','秩概率',303,144,170,30,21);
downArrow('flow.input-pseudo',290,288,17);
math('criterion.pseudo-left','η̂ᵢ(γⱼ, βₖ) =',52,332,195,50,28);
fraction('criterion.pseudo','t₍ᵢ₎ − γⱼ','[−ln(1 − F̂(t₍ᵢ₎))]^{1/βₖ}',250,306,270,25);
txt('criterion.pseudo-label','由每个观测得到伪尺度',79,386,414,30,21);
math('criterion.discrepancy','σ_{η}(γⱼ, βₖ) = SD(η̂₁, …, η̂ₙ)',61,448,457,42,28);
math('criterion.minimum','σ_{η,min}(γⱼ) = min σ_{η}(γⱼ, βₖ)',63,525,453,42,28);
math('criterion.minimum-index','βₖ',281,561,32,22,17);
downArrow('flow.pseudo-difference',290,424,16);
downArrow('flow.difference-minimum',290,498,16);

region('gamma','a  梯度交点确定位置参数',630,96,500,500);
math('gamma.gradient-name','∇(γ) =',650,164,165,65,34);
fraction('gamma.derivative','dσ_{η,min}(γ)','dγ',825,145,264,30);
txt('gamma.meaning','条件最小差异随 γ 的变化率',660,242,440,30,21,GRAY);
const ga=axis('gamma',744,302,324,185,[700,1250],[-.075,.55],[800,1000,1200],[0,.2,.4],'位置参数 γⱼ','梯度 ∇(γⱼ)');
curve('gamma.curve',rows.filter(r=>r.panel==='a'&&r.kind==='gradient').map(r=>[r.x,r.y]),ga);
line('gamma.zero',[[ga.px(700),ga.py(0)],[ga.px(1250),ga.py(0)]],GRAY,1.2,true);
const g=M.estimates['0'].gamma;
dot('gamma.selected',ga.px(g),ga.py(0),10);
line('gamma.projection',[[ga.px(g),ga.py(0)],[ga.px(g),ga.py(-.075)]],GRAY,1.1,true);
txt('gamma.root-label','∇(γ̂) = 0',710,407,170,30,23);
line('gamma.root-leader',[[914,421],[ga.px(g)-5,ga.py(0)-7]],INK,1);
txt('gamma.estimate','γ̂ = 974.4',867,271,190,30,23,BLUE);
arrow('flow.criterion-gamma',552,339,62);
txt('flow.criterion-transfer','求导',553,299,68,32,20,GRAY);

region('beta','b  代入位置，回代形状参数',1240,96,520,500);
math('beta.minimum','β̂ = arg min σ_{η}(γ̂, βₖ)',1254,166,492,50,32);
math('beta.argmin-index','βₖ',1452,207,38,24,18);
txt('beta.fixed','固定 γ̂ = 974.4',1270,241,460,33,23,GRAY);
const ba=axis('beta',1360,302,330,185,[1.5,4],[0,350],[1.5,2.5,3.5],[0,100,200,300],'形状参数 βₖ','差异 ση(γ̂, βₖ)');
const bc=rows.filter(r=>r.panel==='b'&&r.kind==='conditional_curve');
curve('beta.curve',bc.map(r=>[r.x,r.y]),ba);
const bm=rows.find(r=>r.panel==='b'&&r.kind==='minimum');
dot('beta.selected',ba.px(bm.x),ba.py(bm.y),10);
line('beta.projection',[[ba.px(bm.x),ba.py(bm.y)],[ba.px(bm.x),ba.py(0)]],GRAY,1.1,true);
txt('beta.estimate','β̂ = 2.471',1510,364,185,32,25,BLUE);
line('beta.minimum-leader',[[1530,397],[ba.px(bm.x)+7,ba.py(bm.y)-6]],INK,1);
arrow('flow.gamma-beta',1150,339,70);
txt('flow.gamma-transfer','γ̂',1150,299,70,34,28,BLUE);

region('result','尺度计算与三参数输出',1870,96,430,500);
txt('eta.title','伪尺度取均值',1884,193,400,36,24,INK,true);
math('eta.formula','η̂ = (1/n) Σᵢ η̂ᵢ(γ̂, β̂) = 819.2',1878,247,414,88,29);
arrow('flow.beta-eta',1782,339,66);
downArrow('flow.eta-output',2085,362,26);
txt('output.title','输出三参数估计',1884,404,400,36,24,INK,true);
math('output.result','(β̂, η̂, γ̂) = (2.471, 819.2, 974.4)',1878,456,414,60,28);
// Repeated sampling branches from the sample/criterion block.
downArrow('flow.criterion-repeat',290,609,87);
txt('repeat.branch-label','同一总体下重复抽样',322,631,300,34,24,INK,true,'left');
region('repeat','同一总体，30组随机样本',40,715,500,520);
math('repeat.truth','W(β = 2, η = 1000, γ = 1000)',60,794,460,45,27);
txt('repeat.n','每组 n = 7',64,854,450,34,23);
for(let j=0;j<3;j++){
 const name=M.ensemble.sample_ids[j];
 const vals=rows.filter(r=>r.panel==='input_ensemble'&&r.series===name).map(r=>r.y);
 txt('repeat.sample-label'+j,'样本 '+(j+1),69,925+j*58,100,32,22);
 vals.forEach((t,i)=>dot('repeat.sample-'+j+'-'+i,186+t/4200*306,941+j*58,7,GRAY,true));
}
txt('repeat.ellipsis','⋮',70,1103,438,28,27);
txt('repeat.rebuild','每组样本重新构造梯度曲线',60,1181,460,33,23);
arrow('flow.repeat-curves',552,969,62);
region('ensemble','c  30条样本梯度曲线',630,715,500,520);
txt('ensemble.explain','每条曲线对应一组随机样本',647,784,466,32,23,GRAY);
const ea=axis('ensemble',744,857,324,246,[-45,1800],[-.035,.34],[0,500,1000,1500],[0,.1,.2,.3],'位置参数 γⱼ','梯度 ∇(γⱼ)');
for(const name of M.ensemble.sample_ids){
 curve('ensemble.curve-'+name,rows.filter(r=>r.panel==='cd'&&r.series===name).map(r=>[r.x,r.y]),ea,'#AEB6BC',1.05);
}
for(const delta of ['0','0.1']){
 const color=delta==='0'?GRAY:BLUE;
 line('ensemble.rule'+delta,[[ea.px(-45),ea.py(+delta)],[ea.px(1800),ea.py(+delta)]],color,1.8,true);
 for(const [name,all] of Object.entries(M.ensemble.estimates)){
  const e=all[delta];
  if(!e.boundary)dot('ensemble.root-'+delta+'-'+name,ea.px(e.gamma),ea.py(+delta),6,color,delta!=='0',delta!=='0');
 }
}
txt('ensemble.delta0','δ = 0',752,1050,105,27,23);
txt('ensemble.delta01','δ = 0.1',752,984,105,27,23);
txt('ensemble.note','按两种判据分别求解位置参数',648,1190,464,29,21,GRAY);
arrow('flow.curves-comparison',1150,969,70);
S.speakerNotes.textFrame.setText('图1。上方单样本MDM求解流程，零梯度判据；从样本准则框向下引出同一总体参数下30组随机样本，c叠加全部30条梯度曲线及0和0.1判据，d由圆周误差图程序生成后合并。依据MDM原理重绘；来源 DOI 10.1142/S0219455423500852、10.12068/j.issn.1005-3026.2025.20240194。数据：public/case-studies/mdm/verification-182-046/data.csv中的Sample-1-3，7个排序观测；重复抽样来自同一文件全部30行，零梯度下10个边界估计不伪画成交点。曲线为既有F01 CSV的真实轨迹，无新模拟。秩概率(i−0.3)/(n+0.4)，标准差ddof=1。公式底稿为文本，随后由F01_嵌入MathType.ps1替换为MathType OLE对象；曲线为可编辑自由曲线。');
const candidate=path.join(BUILD,'candidate.pptx');
await (await PresentationFile.exportPptx(P)).save(candidate);
const preview=await P.export({slide:S,format:'png',scale:1.5});
await fs.writeFile(path.join(BUILD,'preview.png'),new Uint8Array(await preview.arrayBuffer()));
const layout=await S.export({format:'layout'});
await fs.writeFile(path.join(BUILD,'layout.json'),await layout.text());
await fs.writeFile(path.join(BUILD,'presentation.json'),JSON.stringify(P.toProto()));
console.log('DRAFT',candidate);
