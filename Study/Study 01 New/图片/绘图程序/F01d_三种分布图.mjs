/** Three editable alternatives for panel d; unchanged 30 paired estimates. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const RUNTIME='C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
process.env.RUNTIME_NODE_MODULES=RUNTIME;
const {Presentation,PresentationFile}=await import(pathToFileURL(path.join(RUNTIME,'@oai/artifact-tool/dist/artifact_tool.mjs')));
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const REPO=path.resolve(ROOT,'../../..'), BUILD=path.join(REPO,'tmp/f01d-styles-v19');
const SKILL='C:/Users/36089/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
await fs.mkdir(BUILD,{recursive:true});
if(process.argv.includes('--finalize')){
 const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')));
 await finalizePresentation({workspaceDir:REPO,candidatePath:path.join(BUILD,'candidate.pptx'),finalPath:path.join(ROOT,'F01d_三种分布图比较-v19.pptx'),pythonExecutable:'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu',1120*9525+','+600*9525,'--validate-heading-fit'],explicitTotalSlideCount:3,verifyArtifactToolImport:true,receiptPath:path.join(BUILD,'validation.json')});
 process.exit(0);
}
const M=JSON.parse(await fs.readFile(path.join(ROOT,'数据/F01_MDM原理联图.json'),'utf8'));
const vals=['0','0.1'].map(d=>Object.values(M.ensemble.estimates).map(v=>v[d].gamma).sort((a,b)=>a-b));
const P=Presentation.create({slideSize:{width:1120,height:600}});
const X=x=>x-1240+30,Y=y=>y-715+30,cx=v=>X(1408+(v+55)/1870*812);
const colors=['#7E8A94','#147AAA'],fills=['#E4E8EB','#CCE5F0'];
const grid=Array.from({length:351},(_,i)=>i*5),bw=150;
const normal=z=>Math.exp(-z*z/2)/Math.sqrt(2*Math.PI);
// Boundary solutions are discrete; preserve them as points, not as continuous KDE mass.
const densities=vals.map(a=>grid.map(x=>a.filter(v=>v>0).reduce((sum,v)=>sum+normal((x-v)/bw)+normal((x+v)/bw),0)/(30*bw)));
const maxD=Math.max(...densities.flat());
for(const [page,style] of ['violin','raincloud','beeswarm'].entries()){
 const S=P.slides.add();S.background.fill='#FFFFFF';
 function pathShape(name,pts,color,width=1.4,fill='none',closed=false){
  const l=Math.min(...pts.map(p=>p[0])),t=Math.min(...pts.map(p=>p[1]));
  const w=Math.max(.1,Math.max(...pts.map(p=>p[0]))-l),h=Math.max(.1,Math.max(...pts.map(p=>p[1]))-t);
  const commands=pts.map((p,i)=>({[i?'lineTo':'moveTo']:{x:p[0]-l,y:p[1]-t}}));
  if(closed)commands.push({close:{}});
  S.shapes.add({name,geometry:'custom',position:{left:l,top:t,width:w,height:h},fill,line:{fill:color,width},customPaths:[{width:w,height:h,commands}]});
 }
 function dot(name,x,y,size,color){S.shapes.add({name,geometry:'ellipse',position:{left:x-size/2,top:y-size/2,width:size,height:size},fill:color,line:{fill:'#FFFFFF',width:.7}});}
 function q(a,p){const i=(a.length-1)*p,l=Math.floor(i);return a[l]+(a[Math.ceil(i)]-a[l])*(i-l);}
 for(let g=0;g<2;g++){
  const yy=Y(g===0?855:965),color=colors[g];
  if(style!=='beeswarm'){
   const heights=densities[g].map(d=>d/maxD*(style==='violin'?37:36));
   const base=style==='violin'?yy:yy-8;
   const top=grid.map((v,i)=>[cx(v),base-heights[i]]);
   const bottom=grid.slice().reverse().map((v,i)=>[cx(v),base+(style==='violin'?heights[grid.length-1-i]:0)]);
   pathShape(style+'.density-'+g,[...top,...bottom],color,1.1,fills[g],true);
  }
  const baseline=style==='raincloud'?yy+29:yy;
  const levels=[0];for(let i=1;i<30;i++)levels.push(i*(style==='beeswarm'?10:6),-i*(style==='beeswarm'?10:6));
  const placed=[];
  for(const [i,v] of vals[g].entries()){
   const px=cx(v),diam=style==='beeswarm'?10:6;
   const dy=levels.find(h=>placed.every(p=>Math.hypot(px-p[0],h-p[1])>=diam));
   placed.push([px,dy]);dot(style+'.estimate-'+g+'-'+i,px,baseline+dy,diam,color);
  }
  if(style==='raincloud'){
   const a=vals[g],mid=yy+7;
   pathShape('box.range-'+g,[[cx(a[0]),mid],[cx(a.at(-1)),mid]],color,1);
   pathShape('box.iqr-'+g,[[cx(q(a,.25)),mid],[cx(q(a,.75)),mid]],color,6);
   pathShape('box.median-'+g,[[cx(q(a,.5)),mid-6],[cx(q(a,.5)),mid+6]],'#FFFFFF',2.2);
  }
 }
 S.speakerNotes.textFrame.setText('D图样式比较。数据与v18完全一致，每组30个位置估计，含δ=0的10个下界解。小提琴和云雨轮廓使用非零解高斯KDE，下界0反射修正，两组相同带宽150及相同密度缩放，分母为全部30例；下界原子质量仅以原始点表示。云雨箱线显示最小/最大、四分位范围和中位数。点的横坐标为原始估计值，纵向堆叠避免遮盖。');
}
await (await PresentationFile.exportPptx(P)).save(path.join(BUILD,'overlay.pptx'));
await fs.writeFile(path.join(BUILD,'style-spec.json'),JSON.stringify({bandwidth:bw,boundary:'zero-boundary solutions shown as points, omitted from continuous KDE',counts:vals.map(v=>v.length),zeroCounts:vals.map(a=>a.filter(v=>v===0).length),styles:['violin','raincloud','beeswarm']},null,2));
console.log('OVERLAY',BUILD);
