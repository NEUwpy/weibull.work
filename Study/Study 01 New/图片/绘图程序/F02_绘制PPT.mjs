/** F02: AMDM estimator definition. Native editable shapes + MathType OLE.
 * This is a mechanism diagram, not an experimental result. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const RUNTIME=process.env.RUNTIME_NODE_MODULES||'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
process.env.RUNTIME_NODE_MODULES=RUNTIME;
const {Presentation,PresentationFile}=await import(pathToFileURL(path.join(RUNTIME,'@oai/artifact-tool/dist/artifact_tool.mjs')));
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),REPO=path.resolve(ROOT,'../../..');
const BUILD=path.join(REPO,'tmp/f02-v5');
const SKILL='C:/Users/36089/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
await fs.mkdir(BUILD,{recursive:true});
if(process.argv.includes('--finalize')){
 const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')));
 await finalizePresentation({workspaceDir:REPO,candidatePath:path.join(BUILD,'mathtype-candidate.pptx'),finalPath:path.join(ROOT,'F02_AMDM估计器流程-v5.pptx'),pythonExecutable:'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu',2340*9525+','+600*9525,'--validate-heading-fit'],explicitTotalSlideCount:1,verifyArtifactToolImport:true,receiptPath:path.join(BUILD,'validation.json')});
 process.exit(0);
}
const D=JSON.parse(await fs.readFile(path.join(ROOT,'数据/F02_AMDM训练与估计流程.json'),'utf8'));
const P=Presentation.create({slideSize:{width:2340,height:600}}),S=P.slides.add();S.background.fill='#FFFFFF';
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


region('sample','观测样本',40,108,390,418,'blue');
sample('sample',92,278,286);
eq('sample.vector','\\boldsymbol t_n=(t_{(1)},\\ldots,t_{(n)})^{\\mathsf T}',52,305,366,60,29);
txt('sample.label','当前寿命观测',66,420,338,40,25);
arrow('flow.sample-to-select',449,316,52);
txt('flow.sample-label','样本信息',433,265,85,30,19,GRAY);

region('select','样本自适应偏移选择',520,108,760,418,'blue');
rect('select.representation',544,261,176,105,'#F2F5F9');
txt('select.representation-title','样本表征',552,272,160,35,25,INK,true);
txt('select.representation-note','排序 · 归一化',550,316,164,30,22);
arrow('select.to-network',735,316,32);
network('select.network',795,259,185,113);
txt('select.network-title','候选评价',784,210,209,33,25,INK,true);
txt('select.network-note','已训练模型',780,392,220,30,21,GRAY);
arrow('select.to-choice',1004,316,32);
rect('select.choice',1051,249,205,174,'#FAEAD9');
txt('select.choice-title','选择偏移',1061,264,185,34,25,INK,true);
eq('select.delta','\\hat\\delta(\\boldsymbol t_n)',1061,322,185,68,33);
txt('select.rule','根据预测误差选择偏移',570,451,660,37,24);
arrow('flow.select-to-mdm',1299,316,52);
txt('flow.delta-label','所选偏移',1281,265,87,30,19,GRAY);

region('mdm','MDM完整求解流程',1370,108,930,418);
rect('mdm.location-bg',1420,204,360,66,'#F3F7EB');
txt('mdm.location','按所选偏移求解位置参数',1430,216,340,40,25,INK,true);
edge('mdm.to-beta',[[1600,279],[1600,304]],GRAY);
rect('mdm.beta-bg',1420,316,360,58,'#F3F7EB');
txt('mdm.beta','回代求解形状参数',1430,326,340,38,25);
edge('mdm.to-eta',[[1600,382],[1600,407]],GRAY);
rect('mdm.eta-bg',1420,418,360,64,'#F3F7EB');
txt('mdm.eta','伪尺度取均值，得到尺度参数',1428,431,344,38,23);

// The three-parameter result belongs to the MDM solve, not an external module.
edge('mdm.to-result',[[1780,450],[1855,450],[1855,343],[1918,343]],GRAY);
rect('mdm.result-bg',1920,212,345,266,'#FAEAD9');
txt('mdm.result-label','AMDM三参数估计',1930,231,325,42,25,INK,true);
eq('mdm.parameters','(\\hat\\beta,\\hat\\eta,\\hat\\gamma)',1935,299,315,81,39);
txt('mdm.result-meaning','形状 · 尺度 · 位置',1932,416,321,38,24);
edge('flow.raw-sample',[[235,526],[235,590],[1600,590],[1600,526]],BLUE);
rect('flow.raw-label-bg',801,568,240,43,'#FFFFFF');
txt('flow.raw-label','原始寿命样本',803,570,236,39,25,BLUE);
S.speakerNotes.textFrame.setText('图2用于2.5定义AMDM估计器。沿用v2下半部的观测样本、网络示意、偏移选择、MDM回代与输出组件，删除离线训练细节并合并候选预测和偏移选择。网络只代表已训练的候选损失评价模型，节点数量不代表实际结构。散点复用F01 Sample-1-3，不是新增实验。输入表征及损失反变换等细节见2.4。原始样本与所选偏移共同进入MDM；三参数估计结果位于MDM完整求解流程内部，不存在独立输出模块。MathType仅保留输入、所选偏移和输出符号。');
// Remove the slide-style heading and close the vacated top margin.
for(const sh of S.shapes.items){const p=sh.position;sh.position={left:p.left,top:p.top-70,width:p.width,height:p.height,rotation:p.rotation||0};}
for(const spec of specs)spec.y-=70;
await fs.writeFile(path.join(ROOT,'数据/F02_MathType公式.json'),JSON.stringify(specs,null,2)+'\n');
await (await PresentationFile.exportPptx(P)).save(path.join(BUILD,'candidate.pptx'));
console.log('Built F02 v5: 2340 x 600; '+specs.length+' MathType equations.');
