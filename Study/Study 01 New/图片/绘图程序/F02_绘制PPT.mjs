/** F02: AMDM estimator definition. Native editable shapes + MathType OLE.
 * This is a mechanism diagram, not an experimental result. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const RUNTIME=process.env.RUNTIME_NODE_MODULES||'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
process.env.RUNTIME_NODE_MODULES=RUNTIME;
const {Presentation,PresentationFile}=await import(pathToFileURL(path.join(RUNTIME,'@oai/artifact-tool/dist/artifact_tool.mjs')));
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),REPO=path.resolve(ROOT,'../../..');
const BUILD=path.join(REPO,'tmp/f02-v6');
const SKILL='C:/Users/36089/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
await fs.mkdir(BUILD,{recursive:true});
if(process.argv.includes('--finalize')){
 const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')));
 await finalizePresentation({workspaceDir:REPO,candidatePath:path.join(BUILD,'mathtype-candidate.pptx'),finalPath:path.join(ROOT,'F02_AMDM估计器流程-v6.pptx'),pythonExecutable:'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu',2340*9525+','+850*9525,'--validate-heading-fit'],explicitTotalSlideCount:1,verifyArtifactToolImport:true,receiptPath:path.join(BUILD,'validation.json')});
 process.exit(0);
}
const D=JSON.parse(await fs.readFile(path.join(ROOT,'数据/F02_AMDM训练与估计流程.json'),'utf8'));
const P=Presentation.create({slideSize:{width:2340,height:850}}),S=P.slides.add();S.background.fill='#FFFFFF';
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



// One continuous estimator: the observation is the first step of the MDM lane.
rect('main.boundary',30,30,2280,430,'#FCFDF9','#9FBAA5',true);
function step(name,label,x,w,kind='green'){
 const fill={blue:'#A8C0E5',green:'#EAF1D8',peach:'#FAEAD9'}[kind];
 rect(name+'.body',x,70,w,330,'#FFFFFF');
 rect(name+'.header',x,70,w,42,fill);
 txt(name+'.title',label,x+5,72,w-10,38,24,INK,true);
}
step('main.sample','观测样本',60,250,'blue');
sample('main.sample',84,214,202);
eq('main.sample-vector','\\boldsymbol t_n',95,253,180,55,33);
txt('main.sample-note','原始寿命观测',76,343,218,34,23);
arrow('main.sample-to-criterion',329,250,52);

step('main.criterion','构造求解准则',400,330);
txt('main.criterion-line1','由当前样本构造',420,191,290,38,25);
txt('main.criterion-line2','最小差异准则',420,244,290,38,25,INK,true);
txt('main.criterion-line3','形成位置参数搜索过程',411,343,308,34,23);
arrow('main.criterion-to-location',762,250,56);

step('main.location','位置参数求解',850,300,'peach');
rect('main.location-focus',850,70,300,330,'none','#D5AA85');
txt('main.location-description','按所选偏移确定',865,177,270,36,25);
txt('main.location-description2','位置求解落点',865,223,270,36,25);
eq('main.gamma','\\hat\\gamma',928,292,144,65,35);
arrow('main.location-to-shape',1182,250,56);

step('main.shape','形状参数回代',1270,260);
txt('main.shape-description','代入位置估计',1282,183,236,36,24);
txt('main.shape-description2','求条件最小差异',1282,229,236,36,24);
eq('main.beta','\\hat\\beta',1328,292,144,65,35);
arrow('main.shape-to-scale',1548,250,53);

step('main.scale','尺度参数计算',1620,300);
txt('main.scale-description','代入位置与形状估计',1630,183,280,36,23);
txt('main.scale-description2','伪尺度取均值',1630,229,280,36,24);
eq('main.eta','\\hat\\eta',1698,292,144,65,35);
arrow('main.scale-to-result',1940,250,57);
rect('main.result-bg',2020,70,250,330,'#FAEAD9');
txt('main.result-label','AMDM估计结果',2025,85,240,39,24,INK,true);
eq('main.parameters','(\\hat\\beta,\\hat\\eta,\\hat\\gamma)',2028,222,234,80,34);
txt('main.result-meaning','形状 · 尺度 · 位置',2028,344,234,34,22);

region('adapt','样本驱动的估计调节',400,570,1150,240,'blue');
rect('adapt.representation',433,649,193,102,'#F2F5F9');
txt('adapt.representation-title','样本表征',438,657,183,36,24,INK,true);
txt('adapt.representation-note','排序 · 归一化',438,704,183,31,22);
arrow('adapt.to-evaluation',649,698,44);
network('adapt.network',724,648,198,98);
txt('adapt.network-label','候选偏移评价',712,763,222,30,22);
arrow('adapt.to-choice',945,698,43);
rect('adapt.choice',1010,645,234,112,'#FAEAD9');
txt('adapt.choice-label','选择预测误差最低的偏移',1018,651,218,43,18);
eq('adapt.delta','\\hat\\delta(\\boldsymbol t_n)',1030,701,194,48,31);
line('adapt.chosen-delta',[[1244,698],[1425,698],[1425,570]],BLUE,1.6);
txt('adapt.output-label','样本自适应偏移',1268,756,250,32,22,BLUE);
edge('flow.sample-information',[[185,400],[185,698],[400,698]],BLUE);
txt('flow.sample-information-label','样本信息',220,655,150,32,23,BLUE);
edge('flow.adjust',[[1425,570],[1425,505],[1000,505],[1000,400]],BLUE);
rect('flow.adjust-label-bg',1050,483,323,42,'#FFFFFF');
txt('flow.adjust-label','调节位置参数求解判据',1054,485,315,38,24,BLUE);
S.speakerNotes.textFrame.setText('图2定义AMDM估计方法。上方完整MDM主流程从原始观测开始，构造样本求解准则，再依次求位置、形状和尺度参数，最终估计结果仍在同一流程内。下方支路利用同一观测进行样本表征与候选偏移评价，所选偏移明确进入位置参数求解步骤；不是预先处理完偏移再将观测传入一个独立MDM黑箱。网络只是已训练模型示意，不展开训练、梯度曲线或性能结果。输入散点来自图1既有样本；符号用MathType对象。');
await fs.writeFile(path.join(ROOT,'数据/F02_MathType公式.json'),JSON.stringify(specs,null,2)+'\n');
await (await PresentationFile.exportPptx(P)).save(path.join(BUILD,'candidate.pptx'));
console.log('Built F02 v6: 2340 x 850; '+specs.length+' MathType equations.');
