/** Sample index -> angle; absolute location error -> radius. No resampling. */
import fs from 'node:fs/promises';import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const RUNTIME='C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';process.env.RUNTIME_NODE_MODULES=RUNTIME;
const {Presentation,PresentationFile}=await import(pathToFileURL(path.join(RUNTIME,'@oai/artifact-tool/dist/artifact_tool.mjs')));
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),REPO=path.resolve(ROOT,'../../..'),BUILD=path.join(REPO,'tmp/f01d-radial-v20');
const SKILL='C:/Users/36089/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';await fs.mkdir(BUILD,{recursive:true});
if(process.argv.includes('--finalize')){
 const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')));
 await finalizePresentation({workspaceDir:REPO,candidatePath:path.join(BUILD,'full-candidate.pptx'),finalPath:path.join(ROOT,'F01_MDM流程与圆周误差-v21.pptx'),pythonExecutable:'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu',2340*9525+','+1220*9525,'--validate-heading-fit'],explicitTotalSlideCount:1,verifyArtifactToolImport:true,receiptPath:path.join(BUILD,'validation-v21.json')});process.exit(0);
}
const M=JSON.parse(await fs.readFile(path.join(ROOT,'数据/F01_MDM原理联图.json'),'utf8'));
const ids=M.ensemble.sample_ids,truth={beta:2,eta:1000,gamma:1000};
const P=Presentation.create({slideSize:{width:1060,height:520}}),S=P.slides.add();S.background.fill='#FFFFFF';
const colors=['#7E8A94','#147AAA'],light=['#D6DDE2','#C9E0EC'],INK='#263238';
function rect(name,x,y,w,h,fill='none',stroke='none'){return S.shapes.add({name,geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:stroke,width:1.2}});}
function text(name,str,x,y,w,h,size=20,color=INK,bold=false){const sh=rect(name,x,y,w,h);sh.text=str;sh.text.style={typeface:'Microsoft YaHei',fontSize:size,color,bold,alignment:'center',verticalAlignment:'middle',wrap:'none',autoFit:'none',insets:{left:0,right:0,top:0,bottom:0}};return sh;}
function line(name,pts,color,width=1,dashed=false){const x=Math.min(...pts.map(p=>p[0])),y=Math.min(...pts.map(p=>p[1])),w=Math.max(.1,Math.max(...pts.map(p=>p[0]))-x),h=Math.max(.1,Math.max(...pts.map(p=>p[1]))-y);S.shapes.add({name,geometry:'custom',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:color,width,style:dashed?'dashed':'solid'},customPaths:[{width:w,height:h,commands:pts.map((p,i)=>({[i?'lineTo':'moveTo']:{x:p[0]-x,y:p[1]-y}}))}]});}
function circle(name,x,y,r,fill,stroke,width=1){S.shapes.add({name,geometry:'ellipse',position:{left:x-r,top:y-r,width:r*2,height:r*2},fill,line:{fill:stroke,width}});}
rect('radial.boundary',0,0,1060,520,'none','#9FBAA5');rect('radial.header',0,0,1060,42,'#EAF1D8');
text('radial.title','d  逐样本位置误差与三参数RMSE',10,2,1040,38,24,INK,true);
const specs=[];function eq(id,tex,x,y,w,h,font=25){text(id,tex,x,y,w,h,font);specs.push({id,remove:[id],tex,x,y,w,h,font});}
const summary={source:'F01_MDM原理联图.json / ensemble.estimates',sampleOrder:ids,angle:'clockwise, sample 1 at top, equal 12-degree intervals',radius:'absolute gamma error; shared 0 to 1000 linear scale',truth,metrics:{},samples:[]};
for(const [g,d] of ['0','0.1'].entries()){
 const cy=g===0?148:362,cx=210,R=78,base=colors[g];
 for(const v of [250,500,750,1000])circle('radial.ring-'+g+'-'+v,cx,cy,R*v/1000,'none',v===1000?'#AAB6BC':'#E1E6E9',v===1000?1.1:.7);
 for(let i=0;i<30;i++){
  const ang=-Math.PI/2+i*2*Math.PI/30;
  const px=r=>cx+r*Math.cos(ang),py=r=>cy+r*Math.sin(ang);
  line('radial.spoke-'+g+'-'+i,[[cx,cy],[px(R),py(R)]],'#E4E8EB',.65);
  text('radial.index-'+g+'-'+i,String(i+1),px(R+15)-11,py(R+15)-9,22,18,10,'#66737B');
  const e=M.ensemble.estimates[ids[i]][d],err=Math.abs(e.gamma-1000),r=R*err/1000;
  line('radial.error-ray-'+g+'-'+i,[[cx,cy],[px(r),py(r)]],light[g],1);
  circle('radial.sample-'+g+'-'+i,px(r),py(r),2.8,base,'#FFFFFF',.4);
  summary.samples.push({sampleIndex:i+1,sampleId:ids[i],delta:+d,gamma:e.gamma,absoluteGammaError:err,angleRadians:ang,radiusPx:r});
 }
 circle('radial.center-'+g,cx,cy,1.8,INK,INK,.2);
 for(const v of [0,500,1000]){const rr=v===1000?R-10:R*v/1000; text('radial.scale-'+g+'-'+v,String(v),cx+rr/Math.sqrt(2)-14,cy+rr/Math.sqrt(2)+(v===0?8:-5),28,12,8,'#A66A32');}
 eq('radial.delta'+g,'\\delta='+d,12,cy-20,96,40,27);
 summary.metrics[d]={};
 for(const p of ['beta','eta','gamma']){const a=ids.map(id=>M.ensemble.estimates[id][d][p]);summary.metrics[d][p]={rmse:Math.sqrt(a.reduce((s,v)=>s+(v-truth[p])**2,0)/a.length),n:a.length};}
}
text('radial.index-explain','圆周编号 1–30：抽样序号',105,467,250,24,17);
eq('radial.error-formula','r=|\\hat\\gamma-\\gamma|',110,491,240,26,21);
line('radial.divider',[[392,62],[392,490]],'#D6DEE2',1);
text('rmse.explain','三参数RMSE（各参数独立纵轴）',440,55,580,28,22,INK,true);
for(let g=0;g<2;g++){rect('rmse.legend-mark'+g,515+g*230,104,15,15,colors[g]);eq('rmse.legend'+g,'\\delta='+(g===0?'0':'0.1'),540+g*230,94,115,33,23);}
const ps=['beta','eta','gamma'],maxima=[2.7,800,700],ticks=[[0,1,2],[0,400,800],[0,350,700]],centers=[520,725,930];
for(let k=0;k<3;k++){
 const p=ps[k],cx=centers[k],left=cx-60,right=cx+72,top=154,bottom=411;
 const yy=v=>bottom-v/maxima[k]*(bottom-top);
 line('rmse.axis-y'+k,[[left,top],[left,bottom]],'#7B8991',1);line('rmse.axis-x'+k,[[left,bottom],[right,bottom]],'#7B8991',1);
 for(const v of ticks[k]){line('rmse.grid-'+k+'-'+v,[[left,yy(v)],[right,yy(v)]],'#E6EBEE',.7);text('rmse.tick-'+k+'-'+v,String(v),left-40,yy(v)-11,33,22,14,'#66737B');}
 for(let g=0;g<2;g++){
  const d=g===0?'0':'0.1',v=summary.metrics[d][p].rmse,x=left+20+g*60;
  rect('rmse.bar-'+p+'-'+g,x,yy(v),34,bottom-yy(v),colors[g]);
  text('rmse.value-'+p+'-'+g,v.toFixed(k===0?3:1),x-16,yy(v)-27,66,24,16,colors[g],true);
 }
 eq('rmse.parameter'+k,'\\'+p,cx-32,428,80,35,29);
 const improve=(1-summary.metrics['0.1'][p].rmse/summary.metrics['0'][p].rmse)*100;
 text('rmse.reduction'+k,'降低 '+improve.toFixed(1)+'%',cx-75,476,165,26,18,colors[1]);
}
S.speakerNotes.textFrame.setText('依据用户修改的v19第一页布局：左侧上下两个圆周散点图，右侧三参数RMSE对比。左侧圆周是原始样本序号，半径为位置参数绝对误差，两种判据使用相同0–1000刻度，保留所有30组样本及零边界估计。右侧原始单位RMSE，三个参数独立纵轴；符号β、η、γ沿用MDM正文。统计仅基于当前30组示例。');
await fs.writeFile(path.join(ROOT,'数据/F01d_圆周误差图.json'),JSON.stringify(summary,null,2)+'\n');
await fs.writeFile(path.join(ROOT,'数据/F01d_圆周误差公式.json'),JSON.stringify(specs,null,2)+'\n');
await (await PresentationFile.exportPptx(P)).save(path.join(BUILD,'radial-base.pptx'));
console.log('Built radial-base.pptx');
