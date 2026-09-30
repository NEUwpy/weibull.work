import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const out=path.resolve(here,'../结果'),data=path.join(out,'中间数据');
const read=async f=>JSON.parse(await fs.readFile(path.join(data,f),'utf8'));
const [stats,fits,samples,anomaly]=await Promise.all(['汇总.json','实际估计.json','样本.json','WMLE近似解诊断.json'].map(read));
const old=JSON.parse(await fs.readFile(path.join(here,'输入快照/原案例估计.json'),'utf8'));
const names={mdm:'MDM δ=0.10',lse:'LSE',lre:'LRE Bernard',wmle:'WMLE',mle:'MLE',lre_park:'LRE Park'};
const wb=Workbook.create();
const preview=path.join(data,'表格预览');await fs.mkdir(preview,{recursive:true});
const views=[];
function sheet(name,headers,rows,widths,integers=[]){
 const sh=wb.worksheets.add(name);sh.showGridLines=false;
 sh.getRangeByIndexes(0,0,rows.length+1,headers.length).values=[headers,...rows];
 sh.getRangeByIndexes(0,0,rows.length+1,headers.length).format.font={name:'Microsoft YaHei',size:10};
 sh.getRangeByIndexes(0,0,1,headers.length).format={fill:'#345D7E',font:{name:'Microsoft YaHei',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:45};
 sh.getRangeByIndexes(1,0,rows.length,headers.length).setNumberFormat('0.000');
 sh.getRangeByIndexes(1,0,rows.length,headers.length).format.rowHeight=22;
 headers.forEach((h,i)=>sh.getRangeByIndexes(0,i,rows.length+1,1).format.columnWidth=widths[i]??16);
 integers.forEach(i=>sh.getRangeByIndexes(1,i,rows.length,1).setNumberFormat('0'));
 sh.freezePanes.freezeRows(1);sh.freezePanes.freezeColumns(2);
 views.push([name,headers.length]);return sh;
}
function quantile(v,p){v.sort((a,b)=>a-b);const i=(v.length-1)*p,k=Math.floor(i);return v[k]+(v[Math.min(k+1,v.length-1)]-v[k])*(i-k);}
const historical=[];
for(const n of [7,15])for(const m of ['mdm','lse','lre','wmle','mle']){
 const rr=old.filter(r=>r.beta===5&&r.n===n&&r.method===m&&r.converged);
 historical.push([n,names[m],rr.length,...['beta_hat','eta_hat','gamma_hat'].flatMap(k=>[.25,.5,.75].map(p=>quantile(rr.map(r=>r[k]),p)))]);
}
sheet('原案例分布',['n','方法','成功组数/50','β第25百分位','β中位数','β第75百分位','η第25百分位','η中位数','η第75百分位','γ第25百分位','γ中位数','γ第75百分位'],historical,[8,21,15,...Array(9).fill(17)],[0,2]);
const summary=sheet('连续条件汇总',['真β','n','方法','成功组数','失败组数','γ零边界组数','β中位数','η中位数','γ中位数','γ第25百分位','γ第75百分位','γ高η低组数','γ+η中位数','固定γ配对组数','自由γ尺度误差中位数','固定γ尺度误差中位数'],
 stats.summary.map(s=>[s.beta,s.n,names[s.method],s.success,s.failed,s.boundary_zero,s.beta_hat_q[2],s.eta_hat_q[2],s.gamma_hat_q[2],s.gamma_hat_q[1],s.gamma_hat_q[3],s.joint,s.sum_q[2],s.conditional_pairs,s.eta_error_free_q[2],s.eta_error_fixed_q[2]]),
 [8,8,21,12,12,17,15,15,15,17,17,17,17,19,24,24],[1,3,4,5,11,13]);
const notes=[
 ['真参数','η=1000、γ=500；β=2、2.5、3、3.5、4、4.5、5；n=7或15，每条件50组。'],
 ['随机种子','20261001；共享抽样器生成单位指数E，同一n/组号跨β共用E，再按500+1000 E^(1/β)变换。'],
 ['统计口径','成功返回值的描述性统计；失败留空。各β成功子集可能不同，配对端点表使用两端均成功组。'],
 ['固定γ','已知真实γ=500的条件诊断；WMLE只解形状方程。不是可部署的性能提升。'],
 ['LRE','Bernard解释原历史版本；Park当前版单列，主报告不混用。'],
 ['数值边界','WMLE候选β<10，J3在β>5时夹表；MLE只分析有限局部分支和零边界。'],
 ['WMLE近似','β真3.5、n7、#39：原目标8.37e-9通过容差1e-8；精确根γ相差21.88，原候选保留。'],
 ['文献','https://onlinelibrary.wiley.com/doi/10.1155/2018/6056975'],
];
summary.getRangeByIndexes(88,0,notes.length,2).values=notes;
summary.getRangeByIndexes(88,0,notes.length,1).format.font={bold:true};
summary.getRangeByIndexes(88,1,notes.length,1).format.columnWidth=88;
summary.getRangeByIndexes(88,0,notes.length,2).format.wrapText=true;
summary.getRangeByIndexes(88,0,notes.length,2).format.rowHeight=40;
// Restore analytical n column width; note text is also saved in the report/README.
summary.getRange('B1:B85').format.columnWidth=8;
summary.getRange('A89:B96').format.wrapText=false;
const detail=sheet('连续逐组估计',['真β','n','组号','方法','状态','β估计','η估计','γ估计','位置误差','尺度误差','γ+η','固定γ条件β','固定γ条件η','真γ处准则值','真γ处驱动量','位置零边界'],
 fits.map(r=>[r.beta,r.n,r.sample_id,names[r.method],r.converged?'成功':'失败',r.converged?r.beta_hat:null,r.converged?r.eta_hat:null,r.converged?r.gamma_hat:null,null,null,null,r.conditional_beta,r.conditional_eta,r.criterion_at_truth,r.truth_drive,r.converged&&r.gamma_hat===0]),
 [8,8,10,21,12,...Array(3).fill(16),16,16,16,18,18,20,20,18],[1,2]);
fits.forEach((r,i)=>{if(r.converged){const j=i+2;detail.getRange(`I${j}:K${j}`).formulas=[[`=H${j}-500`,`=G${j}-1000`,`=G${j}+H${j}`]];}});
sheet('端点配对',['n','方法','两端均成功组','γ增加组数','η减少组数','Δγ第25百分位','Δγ中位数','Δγ第75百分位','Δη第25百分位','Δη中位数','Δη第75百分位'],
 stats.endpoint_pairs.map(s=>[s.n,names[s.method],s.paired_success,s.gamma_increased,s.eta_decreased,...s.delta_gamma_q.slice(1,4),...s.delta_eta_q.slice(1,4)]),
 [8,21,17,15,15,...Array(6).fill(19)],[0,2,3,4]);
const sampleSheet=sheet('生成样本',['真β','n','组号','种子','指数恢复最大差',...Array.from({length:15},(_,i)=>`第${i+1}顺序统计量`)],
 samples.map(s=>[s.beta,s.n,s.sample_id,s.seed,s.exponential_recovery_error,...s.observations,...Array(15-s.n).fill(null)]),
 [8,8,10,15,22,...Array(15).fill(17)],[1,2,3]);
sampleSheet.getRange('E2:E701').setNumberFormat('0.000E+00');
const diagnosis=sheet('数值近似',['真β','n','组号','方法','原β','原η','原γ','原T1','原T2','原平方残差','接受阈值','精确根γ','γ差'],
 [[anomaly.beta_true,anomaly.n,anomaly.sample_id,'WMLE',anomaly.saved_beta,anomaly.saved_eta,anomaly.saved_gamma,anomaly.raw_T1,anomaly.raw_T2,anomaly.raw_squared_residual,anomaly.optimizer_acceptance_threshold,anomaly.independently_refined_gamma,anomaly.gamma_difference]],
 [8,8,10,15,15,15,15,18,18,20,18,18,18],[1,2]);
diagnosis.getRange('H2:K2').setNumberFormat('0.000E+00');
for(const [name,cols] of views){
 const end=String.fromCharCode(64+Math.min(cols,10));const range=`A1:${end}${name==='数值近似'?2:7}`;
 const inspection=await wb.inspect({kind:'table',range:`'${name}'!${range}`,include:'values,formulas',tableMaxRows:7,tableMaxCols:10,maxChars:1000});
 await fs.writeFile(path.join(preview,name+'.ndjson'),inspection.ndjson);
 const imagePath=path.join(preview,name+'.png');
 const alreadyRendered=await fs.access(imagePath).then(()=>true,()=>false);
 if(!alreadyRendered||name==='生成样本'){
  const img=await wb.render({sheetName:name,range,scale:1,format:'png'});
  await fs.writeFile(imagePath,new Uint8Array(await img.arrayBuffer()));
 }
}
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1000});
await fs.writeFile(path.join(preview,'公式检查.ndjson'),errors.ndjson);
const output=await SpreadsheetFile.exportXlsx(wb);await output.save(path.join(out,'高形状参数补偿统计.xlsx'));
console.log('EXPORTED',fits.length,'fits;',samples.length,'samples;',stats.summary.length,'summary cells; 6 sheets');
