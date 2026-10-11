// Append MMLE evidence without rebuilding the existing six worksheets.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const here=path.dirname(fileURLToPath(import.meta.url));
const dependencies=process.env.CODEX_DEPENDENCIES_NODE ||
  'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node';
const require=createRequire(path.join(dependencies,'runtime-entry.mjs'));
const {FileBlob,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const cache=JSON.parse(await fs.readFile(path.join(here,'20261011-MMLE估计与曲线.json'),'utf8'));
const input=path.resolve(process.env.R00_OUTPUT_DIR || path.resolve(here,'../../结果'),
                         '报告1/高形状参数补偿统计.xlsx');
const scratch=path.join(os.tmpdir(),'r00-report1-mmle');
await fs.mkdir(scratch,{recursive:true});
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(input));
const before=await wb.render({sheetName:'原案例分布',range:'A1:F7',scale:1,format:'png'});
await fs.writeFile(path.join(scratch,'原表预览.png'),new Uint8Array(await before.arrayBuffer()));
if(process.argv.includes('--preview')){
  console.log(path.join(scratch,'原表预览.png'));
  process.exit(0);
}
const headers=['样本批次','真β','n','成功组数','β第25百分位','β中位数','β第75百分位',
               'η第25百分位','η中位数','η第75百分位','γ第25百分位','γ中位数','γ第75百分位'];
function quantile(v,p){
  v=[...v].sort((a,b)=>a-b);
  const i=(v.length-1)*p,k=Math.floor(i);
  return v[k]+(v[Math.min(k+1,v.length-1)]-v[k])*(i-k);
}
const summary=[];
for(const n of [7,15,30]){
  const rr=cache.original_records.filter(r=>r.n===n&&r.converged);
  summary.push(['原案例',5,n,rr.length,
    ...['beta_hat','eta_hat','gamma_hat'].flatMap(k=>[.25,.5,.75].map(p=>quantile(rr.map(r=>r[k]),p)))]);
}
for(const s of cache.summary){
  summary.push(['配对实验',s.beta,s.n,s.success,
    ...['beta_hat','eta_hat','gamma_hat'].flatMap(k=>s[k+'_q'].slice(1,4))]);
}
const names=(await wb.inspect({kind:'sheet',include:'name',maxChars:2000})).ndjson;
// A replay replaces only the dedicated MMLE sheet.
let sh;
if(names.includes('"MMLE"')) sh=wb.worksheets.getItem('MMLE');
else sh=wb.worksheets.add('MMLE');
sh.showGridLines=false;
sh.getRange('A1:M18').values=[headers,...summary];
const start=21;
const detailHeaders=['样本批次','真β','n','组号','状态','β估计','η估计','γ估计',
                     '位置误差','尺度误差','固定γ条件β','固定γ条件η'];
const rows=[...cache.original_records.map(r=>({...r,batch:'原案例'})),
            ...cache.paired_records.map(r=>({...r,batch:'配对实验'}))];
sh.getRangeByIndexes(start,0,rows.length+1,detailHeaders.length).values=[detailHeaders,
  ...rows.map(r=>[r.batch,r.beta,r.n,r.sample_id,r.converged?'成功':'失败',
    r.beta_hat,r.eta_hat,r.gamma_hat,null,null,
    r.fixed_truth?.beta??null,r.fixed_truth?.eta??null])];
sh.getRangeByIndexes(0,0,start+rows.length+1,13).format.font={name:'Microsoft YaHei',size:10};
sh.getRangeByIndexes(0,0,start+rows.length+1,13).format.rowHeight=22;
for(const top of [0,start]){
  const cols=top===0?13:12;
  sh.getRangeByIndexes(top,0,1,cols).format={fill:'#345D7E',
    font:{name:'Microsoft YaHei',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:45};
}
sh.getRange('A:A').format.columnWidth=14;
sh.getRange('B:D').format.columnWidth=10;
sh.getRange('E:M').format.columnWidth=18;
sh.getRange('E2:M18').setNumberFormat('0.000');
sh.getRangeByIndexes(start+1,5,rows.length,7).setNumberFormat('0.000');
rows.forEach((r,i)=>{
  if(r.converged){const j=start+i+2;
    sh.getRange(`I${j}:J${j}`).formulas=[[`=H${j}-500`,`=G${j}-1000`]];
  }
});
sh.freezePanes.freezeRows(1);sh.freezePanes.freezeColumns(4);
const checks=await wb.inspect({kind:'table',range:'MMLE!A1:M5',include:'values,formulas',
                              tableMaxRows:5,tableMaxCols:13,maxChars:3500});
const errors=await wb.inspect({kind:'match',
  searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',
  options:{useRegex:true,maxResults:30},maxChars:3000});
await fs.writeFile(path.join(scratch,'统计表核验.ndjson'),checks.ndjson+'\n'+errors.ndjson);
for(const [label,range] of [['汇总','A1:M7'],['估计','A22:L27']]){
  const img=await wb.render({sheetName:'MMLE',range,scale:1,format:'png'});
  await fs.writeFile(path.join(scratch,label+'.png'),new Uint8Array(await img.arrayBuffer()));
}
const output=await SpreadsheetFile.exportXlsx(wb);
const target=path.join(scratch,'高形状参数补偿统计.xlsx');
await output.save(target);
console.log(JSON.stringify({output:target,summaryRows:summary.length,detailRows:rows.length,
                            errors:errors.ndjson}));
