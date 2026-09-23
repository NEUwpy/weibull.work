/** F02: AMDM estimator definition. Native editable shapes + MathType OLE.
 * This is a mechanism diagram, not an experimental result. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const RUNTIME=process.env.RUNTIME_NODE_MODULES||'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
process.env.RUNTIME_NODE_MODULES=RUNTIME;
const {Presentation,PresentationFile}=await import(pathToFileURL(path.join(RUNTIME,'@oai/artifact-tool/dist/artifact_tool.mjs')));
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),REPO=path.resolve(ROOT,'../../..');
const BUILD=path.join(REPO,'tmp/f02-v7');
const SKILL='C:/Users/36089/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
await fs.mkdir(BUILD,{recursive:true});
if(process.argv.includes('--finalize')){
 const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')));
 await finalizePresentation({workspaceDir:REPO,candidatePath:path.join(BUILD,'mathtype-candidate.pptx'),finalPath:path.join(ROOT,'F02_AMDM估计器流程-v7.pptx'),pythonExecutable:'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu',2340*9525+','+960*9525,'--validate-heading-fit'],explicitTotalSlideCount:1,verifyArtifactToolImport:true,receiptPath:path.join(BUILD,'validation.json')});
 process.exit(0);
}
const D=JSON.parse(await fs.readFile(path.join(ROOT,'数据/F02_AMDM训练与估计流程.json'),'utf8'));
const P=Presentation.create({slideSize:{width:2340,height:960}}),S=P.slides.add();S.background.fill='#FFFFFF';
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




// The method is expressed through its calculation relations, not placeholder boxes.
rect('main.boundary',30,30,2280,570,'#FFFFFF','#9FBAA5',true);
function heading(name,label,x,w,kind='green'){
 rect(name+'.header',x,55,w,42,kind==='blue'?'#A8C0E5':'#EAF1D8');
 txt(name+'.title',label,x+5,57,w-10,38,24,INK,true);
}
heading('main.sample','观测样本',55,345,'blue');
sample('main.sample',88,194,279);
eq('main.sample-vector','\\boldsymbol t_n=(t_{(1)},\\ldots,t_{(n)})^{\\mathsf T}',65,232,325,58,27);
txt('main.rank-label','中位秩概率',65,346,325,35,23);
eq('main.rank','\\hat F(t_{(i)})=\\frac{i-0.3}{n+0.4}',70,406,315,89,31);
arrow('main.sample-to-criterion',414,307,38);

heading('main.criterion','由样本构造最小差异准则',465,640);
eq('main.pseudo','\\hat\\eta_i(\\gamma_j,\\beta_k)=\\frac{t_{(i)}-\\gamma_j}{[-\\ln(1-\\hat F(t_{(i)}))]^{1/\\beta_k}}',482,145,606,100,32);
edge('main.pseudo-to-sd',[[785,263],[785,288]],GRAY);
eq('main.sd','\\sigma_\\eta(\\gamma_j,\\beta_k)=\\mathrm{SD}(\\hat\\eta_1,\\ldots,\\hat\\eta_n)',484,307,602,62,31);
edge('main.sd-to-profile',[[785,394],[785,419]],GRAY);
eq('main.profile','\\sigma_{\\eta,\\min}(\\gamma_j)=\\min_{\\beta_k}\\sigma_\\eta(\\gamma_j,\\beta_k)',484,442,602,76,32);
arrow('main.criterion-to-location',1120,307,38);

heading('main.location','位置参数求解',1170,440);
eq('main.gradient','\\nabla(\\gamma)=\\frac{\\mathrm d\\sigma_{\\eta,\\min}(\\gamma)}{\\mathrm d\\gamma}',1182,149,416,114,33);
edge('main.gradient-to-root',[[1390,288],[1390,319]],GRAY);
rect('main.root-highlight',1182,342,416,98,'#FAEAD9','#D5AA85');
eq('main.root','\\nabla(\\hat\\gamma)=\\hat\\delta(\\boldsymbol t_n)',1193,358,394,66,33);
arrow('main.location-to-backsolve',1625,307,39);

heading('main.solve','形状、尺度回代与估计结果',1680,610);
eq('main.beta','\\hat\\beta=\\mathop{\\mathrm{arg\\,min}}\\limits_{\\beta_k}\\sigma_\\eta(\\hat\\gamma,\\beta_k)',1698,145,574,90,33);
edge('main.beta-to-eta',[[1985,257],[1985,283]],GRAY);
eq('main.eta','\\hat\\eta=\\frac1n\\sum_{i=1}^{n}\\hat\\eta_i(\\hat\\gamma,\\hat\\beta)',1698,304,574,93,33);
edge('main.eta-to-result',[[1985,420],[1985,445]],GRAY);
rect('main.result-bg',1755,465,460,102,'#FAEAD9');
txt('main.result-label','AMDM估计结果',1770,470,430,32,23,INK,true);
eq('main.parameters','(\\hat\\beta,\\hat\\eta,\\hat\\gamma)',1810,512,350,45,32);

region('adapt','当前样本给出位置求解所用的偏移',550,750,1050,170,'blue');
txt('adapt.prediction-label','候选损失预测',565,806,260,32,23);
eq('adapt.prediction','\\widehat{\\boldsymbol\\ell}(\\boldsymbol t_n)',568,847,254,52,31);
arrow('adapt.predict-to-select',845,853,45);
eq('adapt.argmin','m^\\star=\\mathop{\\mathrm{arg\\,min}}\\limits_m\\widehat\\ell_m(\\boldsymbol t_n)',912,809,395,84,29);
eq('adapt.delta','\\hat\\delta(\\boldsymbol t_n)=\\delta_{m^\\star}',1325,832,252,60,29);
edge('flow.sample-information',[[227,580],[227,853],[550,853]],BLUE);
txt('flow.sample-label','同一观测样本',255,810,250,32,23,BLUE);
edge('flow.offset',[[1600,862],[1640,862],[1640,660],[1390,660],[1390,440]],BLUE);
txt('flow.offset-label','样本自适应偏移',1440,618,240,34,23,BLUE);
S.speakerNotes.textFrame.setText('AMDM计算机制图，符号与稿件2.2–2.5一致。排序观测与中位秩概率给出伪尺度，标准差及对形状参数的条件最小值形成位置求解准则。位置求解判据中的偏移由当前样本的候选损失预测自适应确定，然后回代形状与尺度参数，输出完整三参数估计。位置约束与边界处理沿用2.3。下方仅给出预测与选择关系，不展开网络训练。各式为MathType对象。散点复用F01既有样本；无新模拟、梯度曲线或性能证据。');
await fs.writeFile(path.join(ROOT,'数据/F02_MathType公式.json'),JSON.stringify(specs,null,2)+'\n');
await (await PresentationFile.exportPptx(P)).save(path.join(BUILD,'candidate.pptx'));
console.log('Built F02 v7: 2340 x 960; '+specs.length+' MathType equations.');
