import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root='D:/weibull';
const isN30=process.argv.includes('--n30');
const sizes=isN30?[30]:[7,15];
const work=root+'/docs/临时任务/工作输出/20260929-W5新样本'+(isN30?'-n30':'');
const data=JSON.parse(await fs.readFile(work+'/results.json','utf8'));
const dest=root+'/docs/临时任务/临时任务-W2-1000-3000-MDM偏移量估计-20260825/260906-W5参数估计案例/260929-W5-1000-500新样本';
const wb=Workbook.create();
// Reuse only the established pure formatting functions, not the old runner or paths.
const source=await fs.readFile(root+'/docs/临时任务/工作输出/20260906-W5-parameters/build_w5_workbooks.mjs','utf8');
const start=source.indexOf('const COLORS =');
const end=source.indexOf('async function buildCase(');
const template=source.slice(start,end).replace('n === 7 ? "H" : "P"','n === 7 ? "H" : n === 30 ? "AE" : "P"');
const {buildSampleSheet,buildResultBlock}=new Function(template+'\nreturn {buildSampleSheet,buildResultBlock};')();
const names={mdm:'MDM',lse:'LS',lre:'LRE',wmle:'WMLM',mle:'MLM'};
const mdm=new Map(),other=new Map();
for(const r of data.results){
 const row={...r,display_name:names[r.method_id]};
 if(r.method_id==='mdm')mdm.set(`${r.n}|${r.id}|${r.delta.toFixed(2)}`,row);
 else other.set(`${r.n}|${r.id}|${names[r.method_id]}`,row);
}
const sampleRows=data.samples.flatMap(s=>s.values.map((v,i)=>({sampleSize:s.n,sampleId:s.id,repeatId:s.id-1,observationIndex:i+1,value:v})));
for(const n of sizes){
 const sh=wb.worksheets.add(`估计结果_n${n}`);sh.showGridLines=false;
 for(const [delta,row] of [[.1,1],[.15,59],[.2,117]])buildResultBlock(sh,n,delta,row,'W(5,1000,500)',mdm,other);
 sh.getRange('A1:A172').format.columnWidth=9;sh.getRange('B1:P172').format.columnWidth=15;
 sh.getRange('A174').values=[['新种子命名空间：'+data.seed+'；样本量'+n+'，50组；当前平台实现，估计数值为程序计算结果。']];
 sh.getRange('A175').values=[['LRE采用更新后的Park(2017) Proposed+Plot；WMLE使用原J权重，未使用试验权重。']];
 sh.getRange('A176').values=[['“—”表示当前求解器未返回有效估计，不代表数学上已证明无解。']];
 const failures=data.results.filter(r=>r.n===n&&!r.converged);
 failures.forEach((r,i)=>{sh.getRange(`A${178+i}`).values=[[`样本${r.id}，${names[r.method_id]}：${r.extra?.solution_info?.status??r.extra?.raw_status??r.extra?.error??'failed'}`]];});
 sh.freezePanes.freezeRows(4);sh.freezePanes.freezeColumns(1);
}
for(const n of sizes){
 const sh=wb.worksheets.add(`生成样本_n${n}`);buildSampleSheet(sh,n,'W(5,1000,500)',sampleRows);
 sh.getRange('A54').values=[['生成参数：形状5、尺度1000、位置500；种子命名空间'+data.seed+'；每行是一组排序样本。']];
}
wb.recalculate();
for(const name of [...sizes.map(n=>`估计结果_n${n}`),...sizes.map(n=>`生成样本_n${n}`)]){
 const last=name==='生成样本_n7'?'H':name==='生成样本_n30'?'AE':'P';
 console.log((await wb.inspect({kind:'table',range:`${name}!A1:${last}7`,include:'values,formulas',tableMaxRows:7,tableMaxCols:16,maxChars:900})).ndjson);
 const preview=await wb.render({sheetName:name,range:`A1:${last}10`,scale:1,format:'png'});
 await fs.writeFile(work+`/${name}.png`,new Uint8Array(await preview.arrayBuffer()));
}
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:20}})).ndjson);
await fs.mkdir(dest,{recursive:true});
const file=dest+(isN30?'/估计结果表_样本量30.xlsx':'/估计结果表.xlsx');
const out=await SpreadsheetFile.exportXlsx(wb);await out.save(file);
console.log('SAVED',file);
