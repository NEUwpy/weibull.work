import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const out=path.resolve(here,'../结果');
const data=path.join(out,'中间数据');
const read=async name=>JSON.parse(await fs.readFile(path.join(data,name),'utf8'));
const [stats,fits,audit,verification]=await Promise.all(['汇总.json','实际估计.json','输入核验.json','复算核验.json'].map(read));
const independent=await read('独立剖面复核.json');
const wb=Workbook.create();
const labels={mdm:'MDM δ=0.10',lse:'LSE',lre:'LRE Bernard',lre_park:'LRE Park',wmle:'WMLE',mle:'MLE'};
function sheet(name,headers,rows,widths){
  const sh=wb.worksheets.add(name);sh.showGridLines=false;
  sh.getRangeByIndexes(0,0,rows.length+1,headers.length).values=[headers,...rows];
  sh.getRangeByIndexes(0,0,rows.length+1,headers.length).format.font={name:'Microsoft YaHei',size:10};
  sh.getRangeByIndexes(0,0,1,headers.length).format={fill:'#243746',font:{name:'Microsoft YaHei',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:36};
  sh.getRangeByIndexes(1,0,rows.length,headers.length).setNumberFormat('0.000');
  sh.getRangeByIndexes(1,0,rows.length,headers.length).format.rowHeight=21;
  headers.forEach((_,i)=>sh.getRangeByIndexes(0,i,rows.length+1,1).format.columnWidth=widths?.[i]??13);
  sh.freezePanes.freezeRows(1);sh.freezePanes.freezeColumns(3);
  return sh;
}
const summary=sheet('结果汇总',
  ['真β','样本量n','方法','成功组数','失败组数','β估计中位数','γ估计中位数','η估计中位数','γ高η低组数','γ+η中位数','尺度MAE_自由γ','尺度MAE_固定γ','配对组数'],
  stats.summary.map(s=>[s.beta_true,s.n,s.method,s.valid,s.failed,s.median_beta,s.median_gamma,s.median_eta,s.joint_gamma_high_eta_low,
    s.median_gamma_plus_eta,s.median_abs_error_eta_free_paired,s.median_abs_error_eta_fixed_gamma_paired,s.conditional_pairs]),
  [8,11,21,11,11,15,16,16,15,16,19,19,11]);
// These two columns intentionally show medians of absolute error, not MAE.
summary.getRange('K1:L1').values=[['尺度绝对误差中位数_自由γ','尺度绝对误差中位数_固定γ']];
summary.getRange('K1:L1').format.rowHeight=52;
for(const col of ['A','B','D','E','I','M'])summary.getRange(`${col}2:${col}25`).setNumberFormat('0');
const notes=[
  ['真参数','W(β,η,γ)：β=2或5，η=1000，γ=500。每条件50组，n=7或15。'],
  ['种子','β=2：20260826；β=5：20260906，复用原样本。'],
  ['同方向偏移','γ高η低组数按同时γ̂>500、η̂<1000统计，只统计成功估计。'],
  ['固定γ诊断','固定γ=500后条件估计β/η；WMLE只解形状方程。两列误差中位数使用同一批成功且有条件解的组。'],
  ['参数补偿','Q(1−exp(−1))=γ+η，真值1500。估计γ+η接近1500时，γ高可以由η低补偿。'],
  ['LRE版本','Bernard解释旧表；Park为同一输入上的当前版本敏感性检查，两版分列。'],
  ['MLE','当前实现返回β≥1的有限局部解；失败不补值。'],
  ['WMLE','保持本次快照权重与约束：β<10；β>5的J3按表端点取值。'],
  ['文献','https://onlinelibrary.wiley.com/doi/10.1155/2018/6056975'],
  ['文献','https://bpspsychub.onlinelibrary.wiley.com/doi/10.1348/000711007X270843'],
];
summary.getRange('A28:B37').values=notes;
summary.getRange('A28:A37').format.font={bold:true};
for(let row=28;row<=37;row++)summary.getRange(`B${row}:M${row}`).merge();
summary.getRange('A28:M37').format.wrapText=true;
summary.getRange('A28:M37').format.rowHeight=36;
const details=sheet('逐组估计',
  ['真β','n','方法','样本组号','估计状态','β估计','η估计','γ估计','Δγ','Δη','γ+η','γ+η误差','固定γ条件β','固定γ条件η','尺度绝对误差_自由γ','尺度绝对误差_固定γ'],
  fits.map(r=>[r.beta,r.n,labels[r.method],r.sample_id,r.converged?'成功':((r.extra?.solution_info?.status)??r.extra?.raw_status??'失败'),
    r.converged?r.beta_hat:null,r.converged?r.eta_hat:null,r.converged?r.gamma_hat:null,null,null,null,null,
    r.conditional_beta,r.conditional_eta,null,null]),[8,8,21,11,23,14,15,15,15,15,16,17,18,18,23,23]);
fits.forEach((r,i)=>{
  const row=i+2;
  if(r.converged){
    details.getRange(`I${row}:L${row}`).formulas=[[`=H${row}-500`,`=G${row}-1000`,`=G${row}+H${row}`,`=K${row}-1500`]];
    details.getRange(`O${row}`).formulas=[[`=ABS(G${row}-1000)`]];
  }
  if(r.conditional_eta!==null)details.getRange(`P${row}`).formulas=[[`=ABS(N${row}-1000)`]];
});
for(const col of ['A','B','D'])details.getRange(`${col}2:${col}${fits.length+1}`).setNumberFormat('0');
const sample=sheet('样本与核验',
  ['真β','n','组号','种子','最小观测','重生最大误差','交换参数重生误差',...Array.from({length:15},(_,i)=>`第${i+1}顺序统计量`)],
  audit.samples.map(s=>[s.beta_true,s.n,s.sample_id,s.seed,s.sample_min,s.regeneration_max_error,s.swapped_parameters_max_error,
    ...s.observations,...Array(15-s.n).fill(null)]),[8,8,9,15,17,20,22,...Array(15).fill(17)]);
for(const col of ['A','B','C','D'])sample.getRange(`${col}2:${col}201`).setNumberFormat('0');
const checks=sheet('过程复核',
 ['真β','n','方法','组号','γ估计','剖面在解处有效','β公式差','η公式差','解处准则值','网格改善','MLE局部极大'],
 verification.profile_checks.map(r=>[r.beta,r.n,labels[r.method],r.id,r.gamma_hat,r.profile_valid_at_fit,
   r.beta_formula_error,r.eta_formula_error,r.criterion_at_fit,r.grid_improvement_over_returned_loss??null,r.local_loglikelihood_maximum??null]),
 [8,8,21,10,17,19,18,18,19,18,20]);
checks.getRange(`G2:J${verification.profile_checks.length+1}`).setNumberFormat('0.000E+00');
for(const col of ['A','B','D'])checks.getRange(`${col}2:${col}${verification.profile_checks.length+1}`).setNumberFormat('0');
const missed=independent.failed_but_profile_candidate.flatMap(r=>r.profile_roots.map(p=>[r.beta,r.n,r.id,'原优化器失败，独立剖面有根',p.beta,p.gamma,p.eta,p.direct_T1,p.direct_T2]));
const missedSheet=sheet('漏解复核',['真β','n','组号','原结果与独立诊断','独立根β','独立根γ','独立根η','形状方程残差T1','位置方程残差T2'],missed,[8,8,10,34,17,17,17,23,23]);
for(const col of ['A','B','C'])missedSheet.getRange(''+col+'2:'+col+'9').setNumberFormat('0');
missedSheet.getRange('H2:I9').setNumberFormat('0.000E+00');
const previewDir=path.join(data,'表格预览');await fs.mkdir(previewDir,{recursive:true});
const previews=[['结果汇总','A1:J9'],['逐组估计','A1:H8'],['样本与核验','A1:J8'],['过程复核','A1:K8'],['漏解复核','A1:I9']];
for(const [name,range] of previews){
  const inspection=await wb.inspect({kind:'table',range:`'${name}'!${range}`,include:'values,formulas',tableMaxRows:8,tableMaxCols:11,maxChars:1200});
  await fs.writeFile(path.join(previewDir,name+'.ndjson'),inspection.ndjson);
  const png=await wb.render({sheetName:name,range,scale:1.1,format:'png'});
  await fs.writeFile(path.join(previewDir,name+'.png'),new Uint8Array(await png.arrayBuffer()));
}
const error=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1200});
await fs.writeFile(path.join(previewDir,'公式检查.ndjson'),error.ndjson);
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(path.join(out,'参数映射与位置尺度补偿核验.xlsx'));
console.log('EXPORTED',fits.length,'fit records,',stats.summary.length,'summary rows,',audit.samples.length,'sample groups');
