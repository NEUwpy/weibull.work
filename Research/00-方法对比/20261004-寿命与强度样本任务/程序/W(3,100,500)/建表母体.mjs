import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';
import {buildSampleSheet, buildResultBlock} from './表格样式.mjs';

export async function buildCase(programDir) {
  const caseDir=path.join(path.dirname(path.dirname(programDir)),'结果',path.basename(programDir));
  const dataDir=path.join(programDir,'中间数据');
  const data=JSON.parse(await fs.readFile(path.join(dataDir,'results.json'),'utf8'));
  await fs.mkdir(caseDir,{recursive:true});
  const wb=Workbook.create();
  const names={mdm:'MDM',lse:'LS',lre:'LRE',wmle:'WMLM',mle:'MLM'};
  const mdm=new Map(), other=new Map();
  for (const r of data.results) {
    if (r.method_id==='mdm') mdm.set(`${r.n}|${r.id}|${data.offset.toFixed(2)}`,r);
    else other.set(`${r.n}|${r.id}|${names[r.method_id]}`,r);
  }
  const sampleRows=data.samples.flatMap(s=>s.values.map((value,index)=>({sampleSize:s.n,sampleId:s.id,observationIndex:index+1,value})));
  const previews=[];
  for (const n of data.n) {
    const sheet=wb.worksheets.add(`估计结果_n${n}`);
    sheet.showGridLines=false;
    buildResultBlock(sheet,n,data.offset,1,data.distribution,mdm,other);
    sheet.getRange('A1:A54').format.columnWidth=9;
    sheet.getRange('B1:P54').format.columnWidth=15;
    sheet.freezePanes.freezeRows(4); sheet.freezePanes.freezeColumns(1);
    // Preserve any numerical candidate even if the estimator reports failure.
    for (const r of data.results.filter(r=>r.n===n&&!r.converged)) {
      const start=['B','E','H','K','N'][['mdm','lse','lre','wmle','mle'].indexOf(r.method_id)];
      const end=['D','G','J','M','P'][['mdm','lse','lre','wmle','mle'].indexOf(r.method_id)];
      sheet.getRange(`${start}${r.id+4}:${end}${r.id+4}`).format.font.color='#B55E3E';
    }
    const actual=sheet.getRange('A5:P54').values;
    for (let sid=1;sid<=50;sid++) {
      const expected=[sid,...['mdm','lse','lre','wmle','mle'].flatMap(m=>{
        const r=data.results.find(r=>r.n===n&&r.id===sid&&r.method_id===m);
        return ['beta_hat','eta_hat','gamma_hat'].map(k=>r[k]??'—');
      })];
      if(JSON.stringify(actual[sid-1])!==JSON.stringify(expected)) throw new Error('Result row mismatch');
    }
  }
  for (const n of data.n) {
    const sheet=wb.worksheets.add(`生成样本_n${n}`);
    buildSampleSheet(sheet,n,data.distribution,sampleRows);
    const last=n===7?'H':n===15?'P':'AE';
    const actual=sheet.getRange(`A2:${last}51`).values;
    for(let sid=1;sid<=50;sid++) {
      const expected=[sid,...data.samples.find(s=>s.n===n&&s.id===sid).values];
      if(JSON.stringify(actual[sid-1])!==JSON.stringify(expected)) throw new Error('Sample row mismatch');
    }
    // Abbreviated headers keep the existing observation columns readable.
    sheet.getRange(`B1:${last}1`).values=[Array.from({length:n},(_,i)=>`t${i+1}`)];
  }
  const errorScan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:2000});
  if(/"(?:value|text)"\s*:\s*"#[A-Z]/.test(errorScan.ndjson)) throw new Error(errorScan.ndjson);
  const previewDir=path.join(dataDir,'表格预览');
  await fs.mkdir(previewDir,{recursive:true});
  for(const name of [...data.n.map(n=>`估计结果_n${n}`),...data.n.map(n=>`生成样本_n${n}`)]) {
    const last=name.startsWith('估计结果')?'P':name.endsWith('n7')?'H':name.endsWith('n15')?'P':'AE';
    const blob=await wb.render({sheetName:name,range:`A1:${last}10`,scale:1,format:'png'});
    const file=`${name}.png`;
    await fs.writeFile(path.join(previewDir,file),new Uint8Array(await blob.arrayBuffer()));
    previews.push(file);
  }
  const output=path.join(caseDir,`${data.distribution}.xlsx`);
  const xlsx=await SpreadsheetFile.exportXlsx(wb); await xlsx.save(output);
  try {
    await fs.copyFile(`${output}.inspect.ndjson`,path.join(dataDir,'表格检查.ndjson'));
    await fs.unlink(`${output}.inspect.ndjson`);
  } catch (error) { if(error.code!=='ENOENT') throw error; }
  await fs.writeFile(path.join(dataDir,'表格核验.json'),JSON.stringify({distribution:data.distribution,sheets:6,sample_rows_checked:150,result_rows_checked:150,parameter_values_checked:2250,full_precision_preserved:true,notes:0,comments:0,previews},null,2)+'\n');
  console.log('SAVED',data.distribution,'6 sheets; 150 sample rows and 2250 parameter values verified.');
}
