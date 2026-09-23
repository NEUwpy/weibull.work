/** F02: AMDM training and inference. Native editable shapes + MathType OLE.
 * This is a mechanism diagram, not an experimental result. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const RUNTIME=process.env.RUNTIME_NODE_MODULES||'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
process.env.RUNTIME_NODE_MODULES=RUNTIME;
const {Presentation,PresentationFile}=await import(pathToFileURL(path.join(RUNTIME,'@oai/artifact-tool/dist/artifact_tool.mjs')));
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),REPO=path.resolve(ROOT,'../../..');
const BUILD=path.join(REPO,'tmp/f02-v2');
const SKILL='C:/Users/36089/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
await fs.mkdir(BUILD,{recursive:true});
if(process.argv.includes('--finalize')){
 const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')));
 await finalizePresentation({workspaceDir:REPO,candidatePath:path.join(BUILD,'mathtype-candidate.pptx'),finalPath:path.join(ROOT,'F02_AMDM训练与估计流程-v2.pptx'),pythonExecutable:'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu',2340*9525+','+1450*9525,'--validate-heading-fit'],explicitTotalSlideCount:1,verifyArtifactToolImport:true,receiptPath:path.join(BUILD,'validation.json')});
 process.exit(0);
}
const D=JSON.parse(await fs.readFile(path.join(ROOT,'数据/F02_AMDM训练与估计流程.json'),'utf8'));
const P=Presentation.create({slideSize:{width:2340,height:1450}}),S=P.slides.add();S.background.fill='#FFFFFF';
const INK='#263238',BLUE='#147AAA',GRAY='#82878C',FONT='Microsoft YaHei';
function rect(name,x,y,w,h,fill='none',stroke='none',dash=false){return S.shapes.add({name,geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:stroke,width:1.3,style:dash?'dashed':'solid'}});}
function txt(name,text,x,y,w,h,size=24,color=INK,bold=false,align='center'){
 const sh=rect(name,x,y,w,h);sh.text=text;sh.text.style={typeface:FONT,fontSize:size,color,bold,alignment:align,verticalAlignment:'middle',wrap:'none',autoFit:'none',insets:{left:0,right:0,top:0,bottom:0}};return sh;
}
function line(name,pts,color=INK,width=1.5,dash=false){const x=Math.min(...pts.map(p=>p[0])),y=Math.min(...pts.map(p=>p[1])),w=Math.max(.1,Math.max(...pts.map(p=>p[0]))-x),h=Math.max(.1,Math.max(...pts.map(p=>p[1]))-y);return S.shapes.add({name,geometry:'custom',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:color,width,style:dash?'dashed':'solid'},customPaths:[{width:w,height:h,commands:pts.map((p,i)=>({[i?'lineTo':'moveTo']:{x:p[0]-x,y:p[1]-y}}))}]});}
function edge(name,pts,color=INK,dash=false){line(name,pts,color,1.6,dash);const a=pts.at(-2),b=pts.at(-1),ang=Math.atan2(b[1]-a[1],b[0]-a[0]),r=10;line(name+'.head',[[b[0]-r*Math.cos(ang-.45),b[1]-r*Math.sin(ang-.45)],b,[b[0]-r*Math.cos(ang+.45),b[1]-r*Math.sin(ang+.45)]],color,1.6);}
function arrow(name,x,y,w=55){S.shapes.add({name,geometry:'rightArrow',position:{left:x,top:y-10,width:w,height:20},fill:'#C6D9E7',line:{fill:'#73869A',width:1.2}});}
function circle(name,x,y,r,fill=BLUE){S.shapes.add({name,geometry:'ellipse',position:{left:x-r,top:y-r,width:r*2,height:r*2},fill,line:{fill:'#FFFFFF',width:1}});}
function region(name,title,x,y,w,h,kind='green'){const fill={blue:'#A8C0E5',green:'#EAF1D8',peach:'#FAEAD9'}[kind],border={blue:'#6A92BD',green:'#9FBAA5',peach:'#CFA582'}[kind];rect(name+'.boundary',x,y,w,h,'none',border,true);rect(name+'.header',x,y,w,42,fill);txt(name+'.title',title,x+10,y+2,w-20,38,24,INK,true);}
const specs=[];
function eq(id,tex,x,y,w,h,font=29){specs.push({id,remove:[id],tex,x,y,w,h,font});}
function sample(prefix,x,y,w){line(prefix+'.axis',[[x,y],[x+w,y]],'#B5BEC5',1);const a=D.sample_example.values,lo=Math.min(...a),hi=Math.max(...a);a.forEach((v,i)=>{const xx=x+15+(v-lo)/(hi-lo)*(w-30);line(prefix+'.stem'+i,[[xx,y],[xx,y-22]],BLUE,1.1);circle(prefix+'.dot'+i,xx,y-22,4.5);});}
function network(prefix,x,y,w,h){const layers=[3,4,4,3],xx=layers.map((_,i)=>x+i*w/3),ys=layers.map(n=>Array.from({length:n},(_,i)=>y+(i+.5)*h/n));for(let k=0;k<3;k++)for(let i=0;i<layers[k];i++)for(let j=0;j<layers[k+1];j++)line(prefix+'.weight'+k+'-'+i+'-'+j,[[xx[k],ys[k][i]],[xx[k+1],ys[k+1][j]]],'#C7D5DD',1);for(let k=0;k<4;k++)for(let i=0;i<layers[k];i++)circle(prefix+'.unit'+k+'-'+i,xx[k],ys[k][i],10,k===0?'#147AAA':k===3?'#D19B66':'#9FBAA5');}

txt('a.heading','a  离线学习：由模拟样本学习候选偏移的估计表现',40,22,2260,48,31,INK,true,'left');
region('a.sample','生成样本与构造学习输入',40,98,420,522,'blue');
txt('a.truthlabel','模拟真参数',70,161,360,32,23,INK,true);
eq('a.truth','W(\\beta,\\eta,\\gamma)',70,205,360,50,32);
edge('a.generate',[[250,265],[250,298]],GRAY);
sample('a.sample',95,361,310);
eq('a.samplevec','\\boldsymbol t_n=(t_{(1)},\\ldots,t_{(n)})^{\\mathsf T}',59,378,382,48,26);
txt('a.normal-label','排序 · 均值归一化 · 标准化',55,452,390,35,23);
eq('a.input','\\boldsymbol z_n=\\boldsymbol t_n/\\bar t',60,500,380,54,28);
txt('a.n','每个样本量分别构造训练集',65,576,370,27,21,GRAY);

region('a.candidates','各候选偏移下的 MDM 估计',540,98,470,345);
eq('a.grid','\\mathcal D=\\{0,0.02,\\ldots,0.50\\}',553,164,444,48,27);
const ys=[239,294,349];
for(let i=0;i<3;i++){rect('a.candidate-row'+i,565,ys[i],420,43,i===1?'#F3F6F7':'#F5F8F0');eq('a.candidate'+i,i===0?'\\delta_1\\colon(\\hat\\beta_1,\\hat\\eta_1,\\hat\\gamma_1)':i===1?'\\cdots\\qquad\\cdots':'\\delta_{26}\\colon(\\hat\\beta_{26},\\hat\\eta_{26},\\hat\\gamma_{26})',575,ys[i],400,43,25);}
arrow('a.sample-to-candidates',478,321,44);

region('a.targets','真参数构造联合损失',1090,98,560,345,'peach');
eq('a.loss1','\\ell_m=\\left(\\frac{\\hat\\beta_m-\\beta}{\\beta}\\right)^2+\\left(\\frac{\\hat\\eta_m-\\eta}{\\eta}\\right)^2',1110,164,520,89,29);
eq('a.loss2','+\\left(\\frac{\\hat\\gamma_m-\\gamma}{\\eta}\\right)^2',1160,253,420,80,29);
eq('a.target','\\boldsymbol\\ell=(\\ell_1,\\ldots,\\ell_{26})^{\\mathsf T}',1100,355,540,51,27);
txt('a.target-scale','目标按候选分量标准化',1120,407,500,27,21,GRAY);
arrow('a.candidates-to-loss',1026,300,46);
edge('a.truth-to-loss',[[380,204],[490,204],[490,80],[1368,80],[1368,97]],GRAY);
txt('a.truth-port','真参数',900,49,150,28,20,GRAY);

region('a.fit','样本 → 候选损失的多输出回归',1730,98,570,522,'blue');
network('a.mlp',1800,183,420,165);
txt('a.mlp-label','MLP（结构示意）',1810,353,400,30,22,GRAY);
eq('a.regression','\\boldsymbol f_{\\boldsymbol w_n}(\\boldsymbol u_n)\\approx\\tilde{\\boldsymbol\\ell}',1770,402,490,56,31);
txt('a.fit-note','预测向量与目标向量的平方误差',1750,474,530,34,23);
eq('a.model','\\boldsymbol w_n',1748,549,108,45,30);
txt('a.model-label','保存模型与输入／输出变换参数',1855,556,420,31,23);
edge('a.target-to-fit',[[1650,381],[1690,381],[1690,430],[1730,430]],'#B78D68');
edge('a.input-to-fit',[[460,520],[1730,520]],BLUE);
txt('a.input-route-label','归一化样本作为输入',855,550,450,34,25,BLUE);

// Frozen models are reused; this does not carry truth into inference.
edge('reuse.model',[[2015,620],[2015,750],[865,750],[865,830]],BLUE,true);
rect('reuse.label-bg',1270,729,580,41,'#FFFFFF');
txt('reuse.label','保存后复用：按观测样本量调用对应模型',1275,730,570,38,24,BLUE);

txt('b.heading','b  实际估计：依据当前样本选择偏移，再由 MDM 求解三参数',40,660,2260,48,31,INK,true,'left');
region('b.sample','当前观测样本',40,830,420,480,'blue');
sample('b.sample',95,960,310);
eq('b.samplevec','\\boldsymbol t_n=(t_{(1)},\\ldots,t_{(n)})^{\\mathsf T}',60,984,380,50,26);
edge('b.normalize',[[250,1044],[250,1073]],GRAY);
txt('b.normal-label','排序 · 均值归一化',70,1088,360,34,24);
eq('b.input','\\boldsymbol z_n=\\boldsymbol t_n/\\bar t',70,1143,360,48,29);
txt('b.standardize','使用已保存的输入标准化参数',58,1250,384,32,22,GRAY);
arrow('b.sample-to-predict',478,1102,44);

region('b.predict','预测 26 个候选的损失',540,830,650,480);
network('b.mlp',620,922,490,135);
eq('b.predictor','\\boldsymbol f_{\\boldsymbol w_n}(\\boldsymbol u_n)',590,1084,550,53,31);
edge('b.transform',[[865,1149],[865,1174]],GRAY);
txt('b.inverse','输出逆标准化 · 负预测值截为零',565,1187,600,34,24);
eq('b.lossvector','\\widehat{\\boldsymbol\\ell}=(\\widehat\\ell_1,\\ldots,\\widehat\\ell_{26})^{\\mathsf T}',563,1245,603,49,29);
arrow('b.predict-to-select',1209,1102,43);

region('b.select','选择预测损失最低的候选',1270,830,450,480,'peach');
txt('b.rank-label','比较同一样本的候选预测',1285,940,420,35,24);
eq('b.argmin','m^\\star=\\underset{m}{\\arg\\min}\\;\\widehat\\ell_m',1290,997,410,82,32);
edge('b.argmin-down',[[1495,1110],[1495,1144]],GRAY);
eq('b.delta','\\hat\\delta(\\boldsymbol t_n)=\\delta_{m^\\star}',1285,1167,420,65,32);
txt('b.tie','并列时选择较小偏移',1290,1261,410,30,22,GRAY);
arrow('b.select-to-mdm',1738,1102,44);

region('b.mdm','保留 MDM 结构的三参数求解',1800,830,500,480);
txt('b.gamma-label','以所选偏移确定位置参数',1815,909,470,32,24);
eq('b.root','\\nabla(\\hat\\gamma)=\\hat\\delta(\\boldsymbol t_n)',1820,961,460,62,31);
edge('b.solve',[[2050,1039],[2050,1068]],GRAY);
txt('b.backsolve','回代形状参数 · 伪尺度取均值',1813,1085,474,35,24);
rect('b.result-bg',1820,1163,460,122,'#FAEAD9');
txt('b.result-label','AMDM 三参数估计',1835,1172,430,33,25,INK,true);
eq('b.output','(\\hat\\beta_{\\mathrm{AMDM}},\\hat\\eta_{\\mathrm{AMDM}},\\hat\\gamma_{\\mathrm{AMDM}})',1830,1220,440,50,28);
edge('b.raw-to-mdm',[[250,1310],[250,1365],[2050,1365],[2050,1310]],BLUE);
rect('b.raw-labelbg',764,1344,734,42,'#FFFFFF');
txt('b.raw-label','原始寿命样本直接传入 MDM，保留寿命尺度',775,1346,712,38,24,BLUE);
S.speakerNotes.textFrame.setText('依据 Study01论文初稿-v0.1.md 2.4–2.5及原图2信息流。网络为结构示意，并非具体层数或宽度。观测散点复用F01 Sample-1-3，仅表示输入样本，不是AMDM性能证据。26个候选对应0到0.50步长0.02。真参数仅在离线训练中生成样本和计算监督目标；输入与输出标准化参数均由训练数据拟合保存。估计时原始寿命观测与所选偏移传入MDM。公式由F01_嵌入MathType.ps1生成MathType OLE对象。');
await fs.writeFile(path.join(ROOT,'数据/F02_MathType公式.json'),JSON.stringify(specs,null,2)+'\n');
await (await PresentationFile.exportPptx(P)).save(path.join(BUILD,'candidate.pptx'));
console.log('Built F02 candidate: 2340 x 1450; '+specs.length+' MathType equations.');

