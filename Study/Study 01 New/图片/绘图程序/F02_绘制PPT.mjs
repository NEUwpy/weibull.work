/** F02: AMDM estimator definition. Native editable shapes + MathType OLE.
 * This is a mechanism diagram, not an experimental result. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const RUNTIME=process.env.RUNTIME_NODE_MODULES||'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
process.env.RUNTIME_NODE_MODULES=RUNTIME;
const {Presentation,PresentationFile}=await import(pathToFileURL(path.join(RUNTIME,'@oai/artifact-tool/dist/artifact_tool.mjs')));
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),REPO=path.resolve(ROOT,'../../..');
const BUILD=path.join(REPO,'tmp/f02-v9');
const SKILL='C:/Users/36089/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
await fs.mkdir(BUILD,{recursive:true});
if(process.argv.includes('--finalize')){
 const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')));
 await finalizePresentation({workspaceDir:REPO,candidatePath:path.join(BUILD,'mathtype-candidate.pptx'),finalPath:path.join(ROOT,'F02_AMDM估计器流程-v9.pptx'),pythonExecutable:'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu',2340*9525+','+1000*9525,'--validate-heading-fit'],explicitTotalSlideCount:1,fontPolicy:{basis:"design",families:["Microsoft YaHei"]},verifyArtifactToolImport:true,receiptPath:path.join(BUILD,'validation.json')});
 process.exit(0);
}
const D=JSON.parse(await fs.readFile(path.join(ROOT,'数据/F02_AMDM训练与估计流程.json'),'utf8'));
const P=Presentation.create({slideSize:{width:2340,height:1000}}),S=P.slides.add();S.background.fill='#FFFFFF';
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
// Parallel pathways share the same observed sample; delta enters only the location rule.
region('input','当前寿命样本',30,450,300,450,'blue');
sample('input.sample',57,610,246);
eq('input.sample-vector','\\boldsymbol t_n=(t_{(1)},\\ldots,t_{(n)})^{\\mathsf T}',42,660,276,68,28);
txt('input.description','排序后的寿命观测',45,782,270,36,23);

region('adapt','样本自适应偏移选择',460,50,1390,290,'blue');
txt('adapt.feature-label','样本特征构造',480,121,380,34,25,INK,true);
txt('adapt.preprocessing','均值归一化与标准化',480,169,380,32,23);
eq('adapt.normalized','\\boldsymbol z_n=\\boldsymbol t_n/\\bar t',480,222,380,55,30);
arrow('adapt.feature-to-model',880,211,46);
rect('adapt.model-box',950,120,405,180,'#EEF4FB','#8FAED0');
txt('adapt.model-label','偏移选择模型',968,134,369,34,25,INK,true);
eq('adapt.model','\\boldsymbol f_{\\boldsymbol w_n}(\\boldsymbol u_n)',1000,184,305,48,30);
txt('adapt.prediction','预测候选偏移损失',968,249,369,32,23);
arrow('adapt.model-to-delta',1380,211,46);
txt('adapt.selection','选择预测损失最低的偏移',1450,134,370,34,23);
eq('adapt.delta','\\hat\\delta(\\boldsymbol t_n)',1500,217,270,59,34);

region('main','MDM参数求解',460,450,1390,450,'green');
rect('main.location-box',500,550,390,154,'#FAEAD9','#CFA582');
txt('main.location-label','位置参数求解',515,565,360,34,25,INK,true);
eq('main.root','\\nabla(\\hat\\gamma)=\\hat\\delta(\\boldsymbol t_n)',515,624,360,60,31);
txt('main.gradient-label','由样本构造梯度判据',500,746,390,31,22);
eq('main.gradient','\\nabla(\\gamma)=\\frac{\\mathrm d\\sigma_{\\eta,\\min}(\\gamma)}{\\mathrm d\\gamma}',500,791,390,80,30);
arrow('main.gamma-to-beta',909,646,40);
txt('main.beta-label','形状参数求解',966,565,389,34,25,INK,true);
eq('main.beta','\\hat\\beta=\\mathop{\\mathrm{arg\\,min}}\\limits_{\\beta_k}\\sigma_\\eta(\\hat\\gamma,\\beta_k)',966,623,389,88,30);
txt('main.beta-note','在所求位置下最小化差异',966,772,389,34,22);
arrow('main.beta-to-eta',1375,646,40);
txt('main.eta-label','尺度参数计算',1434,565,390,34,25,INK,true);
eq('main.eta','\\hat\\eta=\\frac1n\\sum_{i=1}^{n}\\hat\\eta_i(\\hat\\gamma,\\hat\\beta)',1434,623,390,88,30);
txt('main.eta-note','取对应伪尺度的均值',1434,772,390,34,22);

region('output','AMDM估计结果',1950,450,360,450,'peach');
eq('output.parameters','(\\hat\\beta_{\\mathrm{AMDM}},\\hat\\eta_{\\mathrm{AMDM}},\\hat\\gamma_{\\mathrm{AMDM}})',1964,623,332,88,28);

// One input junction fans out into the parallel modules.
line('flow.shared-input',[[330,675],[395,675]],GRAY,1.6);
circle('flow.junction',395,675,4,GRAY);
edge('flow.sample-to-mdm',[[395,675],[460,675]],GRAY);
edge('flow.sample-to-adapt',[[395,675],[395,211],[460,211]],BLUE);
// Offset descends through the gap, then reaches the highlighted location criterion.
edge('flow.adaptive-offset',[[1635,340],[1635,393],[695,393],[695,550]],BLUE);
txt('flow.offset-label','所选偏移用于位置求解',965,350,390,32,23,BLUE);
edge('flow.result',[[1850,667],[1950,667]],GRAY);
S.speakerNotes.textFrame.setText('依据作者在v8 PPT中的手改草图重排：左侧同一观测样本分别进入上方样本自适应偏移选择和下方MDM参数求解。归一化及标准化仅用于选择模型；原始寿命样本直接用于MDM。蓝色偏移连线进入位置求解判据，随后按MDM原有结构完成形状参数的条件最小差异求解与尺度参数的伪尺度均值计算。梯度定义为辅助说明，不是额外求解步骤。各数学表达均为MathType对象，符号与正文2.2–2.5一致。边界处理见2.3；不展开训练或报告性能。输入散点复用F01 Sample-1-3。');
await fs.writeFile(path.join(ROOT,'数据/F02_MathType公式.json'),JSON.stringify(specs,null,2)+'\n');
await (await PresentationFile.exportPptx(P)).save(path.join(BUILD,'candidate.pptx'));
console.log('Built F02 v9: 2340 x 1000; '+specs.length+' MathType equations.');