import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';
const directory=path.dirname(fileURLToPath(import.meta.url));
const matrix=JSON.parse(await fs.readFile(path.join(directory,'数据','matrix.json'),'utf8'));
const cfg=JSON.parse(await fs.readFile(path.join(directory,'config.json'),'utf8'));
const wb=Workbook.create();
const groups=[['MDM δ=0.10','mdm',.10],['MDM δ=0.15','mdm',.15],['MDM δ=0.20','mdm',.20],
              ['LS','lse',null],['LRE','lre',null],['WMLM','wmle',null],['MLM','mle',null],['MMLE','mmle',null]];
const key=(n,id,method,delta)=>`${n}|${id}|${method}|${delta}`;
const rowsByKey=new Map(matrix.results.map(r=>[key(r.n,r.id,r.method_id,r.delta),r]));
const col=index=>{let s='';for(let n=index+1;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const blue='#20639B',line='#CBD5E1',light='#EAF2F8';
function header(sheet,range){sheet.getRange(range).format={fill:blue,font:{name:'Arial',bold:true,color:'#FFFFFF',size:11},horizontalAlignment:'center',verticalAlignment:'center',borders:{preset:'all',style:'thin',color:line}};}
const verification=[];
const qa=path.join(directory,'复核');
await fs.mkdir(qa,{recursive:true});
for(const n of [7,15,30]){
  const sample=wb.worksheets.add(`${cfg.sample_sheet_prefix}_n${n}`);
  sample.showGridLines=false;
  const data=matrix.samples.filter(s=>s.n===n).sort((a,b)=>a.id-b.id);
  if(data.length!==50)throw Error('sample count');
  sample.getRange(`A1:${col(n)}51`).values=[['样本',...Array.from({length:n},(_,i)=>`第${i+1}顺序统计量`)],...data.map(s=>[s.id,...s.values])];
  header(sample,`A1:${col(n)}1`);
  sample.getRange(`A1:${col(n)}1`).format.rowHeight=26;
  sample.getRange('A2:A51').format={fill:light,horizontalAlignment:'center',numberFormat:'0'};
  sample.getRange(`B2:${col(n)}51`).format.numberFormat='0.000000';
  sample.getRange('A1:A51').format.columnWidth=9;
  sample.getRange(`B1:${col(n)}51`).format.columnWidth=18;
  sample.freezePanes.freezeRows(1);sample.freezePanes.freezeColumns(1);
  const result=wb.worksheets.add(`${cfg.result_sheet_prefix}_n${n}`);
  result.showGridLines=false;
  result.mergeCells('A1:A2');result.getRange('A1').values=[['样本']];
  for(let i=0;i<groups.length;i++){
    const start=1+3*i,end=start+2;
    result.mergeCells(`${col(start)}1:${col(end)}1`);
    result.getRange(`${col(start)}1`).values=[[groups[i][0]]];
    result.getRange(`${col(start)}2:${col(end)}2`).values=[['α','β','γ']];
  }
  header(result,'A1:Y2');result.getRange('A1:Y2').format.rowHeight=24;
  const values=[];
  for(let id=1;id<=50;id++){
    const row=[id];
    for(const [,method,delta] of groups){
      const r=rowsByKey.get(key(n,id,method,delta));
      if(!r)throw Error(`Missing ${n}/${id}/${method}/${delta}`);
      row.push(...(r.converged?[r.beta_hat,r.eta_hat,r.gamma_hat]:['—','—','—']));
    }
    values.push(row);
  }
  result.getRange('A3:Y52').values=values;
  result.getRange('A3:A52').format={fill:light,font:{bold:true,color:'#1F2937'},horizontalAlignment:'center',numberFormat:'0'};
  result.getRange('B3:Y52').format={numberFormat:'0.000000',horizontalAlignment:'right'};
  result.getRange('A1:A52').format.columnWidth=9;
  result.getRange('B1:Y52').format.columnWidth=17;
  result.getRange('A3:Y52').format.borders={insideHorizontal:{style:'thin',color:'#E5E7EB'}};
  for(const boundary of ['A','D','G','J','M','P','S','V','Y'])result.getRange(`${boundary}1:${boundary}52`).format.borders={right:{style:'thin',color:blue}};
  result.freezePanes.freezeRows(2);result.freezePanes.freezeColumns(1);
  for(const [sheet,range,suffix] of [[sample,`A1:${col(n)}6`,'样本'],[result,'A1:Y7','结果']]){
    verification.push((await wb.inspect({kind:'table',range:`${sheet.name}!${range}`,include:'values',tableMaxRows:7,tableMaxCols:31,maxChars:1000})).ndjson);
    const preview=await wb.render({sheetName:sheet.name,range,scale:.8,format:'png'});
    await fs.writeFile(path.join(qa,`n${n}_${suffix}.png`),new Uint8Array(await preview.arrayBuffer()));
  }
}
verification.push((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:50}})).ndjson);
await fs.writeFile(path.join(qa,'excel-inspection.ndjson'),verification.join('\n'),'utf8');
const target=path.resolve(directory,'../../结果',cfg.workbook);
const output=await SpreadsheetFile.exportXlsx(wb);
const staged=path.join(qa,'导出.xlsx');
await output.save(staged);
await fs.copyFile(staged,target);
await fs.unlink(staged);
console.log('EXCEL',cfg.combination,target);
