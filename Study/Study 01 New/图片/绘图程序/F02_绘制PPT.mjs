/** F02: AMDM estimator definition. Native editable shapes + MathType OLE.
 * This is a mechanism diagram, not an experimental result. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const RUNTIME=process.env.RUNTIME_NODE_MODULES||'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
process.env.RUNTIME_NODE_MODULES=RUNTIME;
const {Presentation,PresentationFile}=await import(pathToFileURL(path.join(RUNTIME,'@oai/artifact-tool/dist/artifact_tool.mjs')));
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),REPO=path.resolve(ROOT,'../../..');
const BUILD=path.join(REPO,'tmp/f02-v8');
const SKILL='C:/Users/36089/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
await fs.mkdir(BUILD,{recursive:true});
if(process.argv.includes('--finalize')){
 const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')));
 await finalizePresentation({workspaceDir:REPO,candidatePath:path.join(BUILD,'mathtype-candidate.pptx'),finalPath:path.join(ROOT,'F02_AMDM估计器流程-v8.pptx'),pythonExecutable:'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu',2340*9525+','+800*9525,'--validate-heading-fit'],explicitTotalSlideCount:1,verifyArtifactToolImport:true,receiptPath:path.join(BUILD,'validation.json')});
 process.exit(0);
}
const D=JSON.parse(await fs.readFile(path.join(ROOT,'数据/F02_AMDM训练与估计流程.json'),'utf8'));
const P=Presentation.create({slideSize:{width:2340,height:800}}),S=P.slides.add();S.background.fill='#FFFFFF';
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
// Four-stage estimator definition; original observations also enter MDM directly.
region('input','当前寿命样本',30,150,330,600,'blue');
sample('input.sample',66,343,258);
eq('input.sample-vector','\\boldsymbol t_n=(t_{(1)},\\ldots,t_{(n)})^{\\mathsf T}',45,400,300,64,29);
txt('input.description','排序后的寿命观测',48,500,294,38,24);
arrow('flow.sample-to-adapt',380,450,42);

region('adapt','样本自适应偏移选择',440,150,570,600,'blue');
txt('adapt.feature-label','样本特征构造',470,222,510,36,25,INK,true);
txt('adapt.preprocessing','排序、均值归一化',470,267,510,34,24);
eq('adapt.normalized','\\boldsymbol z_n=\\boldsymbol t_n/\\bar t',520,308,410,49,29);
edge('adapt.feature-to-model',[[725,370],[725,405]],GRAY);
txt('adapt.standardize','标准化',753,367,145,30,21,GRAY);
rect('adapt.model-box',505,418,440,123,'#EEF4FB','#8FAED0');
txt('adapt.model-label','偏移选择模型',520,427,410,32,25,INK,true);
eq('adapt.model','\\boldsymbol f_{\\boldsymbol w_n}(\\boldsymbol u_n)',610,461,230,45,29);
txt('adapt.prediction','预测候选偏移损失',520,510,410,28,22);
edge('adapt.model-to-delta',[[725,553],[725,583]],GRAY);
txt('adapt.selection','选择预测损失最低的偏移',470,594,510,35,24);
eq('adapt.delta','\\hat\\delta(\\boldsymbol t_n)',580,651,290,55,33);

region('main','MDM参数求解',1110,150,690,600,'green');
rect('main.location-box',1150,245,610,128,'#FAEAD9','#CFA582');
txt('main.location-label','位置参数求解',1170,257,570,34,25,INK,true);
eq('main.gamma','\\hat\\gamma',1335,306,240,52,33);
edge('main.gamma-to-beta',[[1455,385],[1455,423]],GRAY);
txt('main.beta-label','形状参数求解',1190,443,530,35,25,INK,true);
eq('main.beta','\\hat\\beta',1335,495,240,53,33);
edge('main.beta-to-eta',[[1455,560],[1455,598]],GRAY);
txt('main.eta-label','尺度参数计算',1190,617,530,35,25,INK,true);
eq('main.eta','\\hat\\eta',1335,670,240,53,33);

region('output','AMDM估计结果',1900,150,410,600,'peach');
eq('output.parameters','(\\hat\\beta_{\\mathrm{AMDM}},\\hat\\eta_{\\mathrm{AMDM}},\\hat\\gamma_{\\mathrm{AMDM}})',1918,400,374,83,29);

// Dedicated routing lanes keep the adaptive input separate from raw observations.
edge('flow.raw-sample',[[195,150],[195,75],[1455,75],[1455,150]],GRAY);
txt('flow.raw-label','原始寿命样本进入MDM求解',600,28,520,36,23,GRAY);
edge('flow.adaptive-offset',[[1010,680],[1060,680],[1060,310],[1150,310]],BLUE);
txt('flow.offset-label','自适应偏移',1025,210,160,30,21,BLUE);
edge('flow.result',[[1800,695],[1847,695],[1847,450],[1900,450]],GRAY);
S.speakerNotes.textFrame.setText('图2定义AMDM的在线估计流程。当前排序寿命样本经均值归一化和已保存的标准化变换，输入对应样本量的偏移选择模型，按逆变换后的预测候选损失选择偏移。所选偏移进入MDM位置求解，随后按原结构完成形状和尺度估计，输出三参数结果。原始寿命样本沿上方连线同时提供给MDM，归一化仅用于偏移选择。符号与正文2.4–2.5一致，图不展开MDM推导、训练结构或性能结果。输入散点复用F01 Sample-1-3。全部数学表达为MathType对象。');
await fs.writeFile(path.join(ROOT,'数据/F02_MathType公式.json'),JSON.stringify(specs,null,2)+'\n');
await (await PresentationFile.exportPptx(P)).save(path.join(BUILD,'candidate.pptx'));
console.log('Built F02 v8: 2340 x 800; '+specs.length+' MathType equations.');