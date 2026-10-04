import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const program=path.dirname(fileURLToPath(import.meta.url));
const output=path.join(program,'复核与LRE对比');
const preview=path.join(program,'检查预览/复核对比');
const tables=JSON.parse(await fs.readFile(path.join(output,'比较表数据.json'),'utf8'));
const wb=Workbook.create();
const contexts={
  条件汇总:'逐组差异；β、η幅度除以旧估计，γ幅度除以真实η；旧版80d08ca，新版b3549598。',
  逐组对比:'同一组样本；Δ为新版减旧版，保留全部1200组。',
  工程分位点:'差异百分比除以真实分位点；p为累计概率。',
  异常记录:'保留失败及零位置候选；空白表示方法未返回参数。',
  WMLE失败核查:'独立消去形状参数后求根；与原方法使用同一权重和参数约束。',
};
const labels={unbounded:'未取得有限解',equation_residual:'加权方程残差超标',boundary_pathology:'MDM端点候选',gamma_zero:'零位置边界',likelihood_suboptimal:'似然优化未达最优',finite_difference_sensitivity:'梯度差分敏感'};
function col(index) { let value=''; for(;index;index=Math.floor((index-1)/26))value=String.fromCharCode(65+(index-1)%26)+value; return value; }
await fs.mkdir(preview,{recursive:true});
const checks=[];
for(const table of tables) {
  const sheet=wb.worksheets.add(table.name);
  const last=col(table.headers.length), end=table.rows.length+4;
  sheet.showGridLines=false;
  sheet.getRange(`A1:${last}${end}`).format.font={name:'Arial',size:11,color:'#1F2937'};
  sheet.getRange('A1').values=[[table.name]];
  sheet.getRange('A1').format.font={name:'Arial',bold:true,size:14,color:'#173F5F'};
  sheet.getRange('A2').values=[[contexts[table.name]]];
  sheet.getRange(`A2:${last}2`).format.font={name:'Arial',size:10,color:'#586575'};
  sheet.getRange(`A4:${last}4`).values=[table.headers];
  sheet.getRange(`A4:${last}4`).format={fill:'#20639B',font:{name:'Arial',bold:true,size:11,color:'#FFFFFF'},
    horizontalAlignment:'center',verticalAlignment:'center',wrapText:true,rowHeight:32};
  const values=table.rows.map(r=>r.map((value,i)=>table.name==='异常记录'&&i===4 ? labels[value] : value));
  sheet.getRange(`A5:${last}${end}`).values=values;
  sheet.getRange(`A5:${last}${end}`).format.rowHeight=22;
  sheet.getRange(`B5:${last}${end}`).format.numberFormat='0.000000';
  sheet.getRange(`B5:${last}${end}`).format.horizontalAlignment='right';
  sheet.getRange(`B5:B${end}`).format.numberFormat='0';
  sheet.getRange(`A1:A${end}`).format.columnWidthPx=174;
  sheet.getRange(`B1:B${end}`).format.columnWidthPx=45;
  sheet.getRange(`C1:${last}${end}`).format.columnWidthPx=112;
  if(table.name==='条件汇总') {
    sheet.getRange(`C1:C${end}`).format.columnWidthPx=50;
    sheet.getRange(`D5:L${end}`).format.numberFormat='0.0000';
  }
  if(table.name==='逐组对比') {
    sheet.getRange(`C1:C${end}`).format.columnWidthPx=55;
    sheet.getRange(`C5:C${end}`).format.numberFormat='0';
    for(const [target,formula] of [['F','=E5-D5'],['I','=H5-G5'],['L','=K5-J5']]) {
      sheet.getRange(`${target}5`).formulas=[[formula]];
      sheet.getRange(`${target}5:${target}${end}`).fillDown();
    }
  }
  if(table.name==='工程分位点') {
    sheet.getRange(`C5:C${end}`).format.numberFormat='0.00';
    sheet.getRange(`D5:J${end}`).format.numberFormat='0.0000';
  }
  if(table.name==='异常记录') {
    sheet.getRange(`C1:D${end}`).format.columnWidthPx=60;
    sheet.getRange(`C5:C${end}`).format.numberFormat='0';
    sheet.getRange(`E1:E${end}`).format.columnWidthPx=156;
  }
  if(table.name==='WMLE失败核查') {
    sheet.getRange(`C1:C${end}`).format.columnWidthPx=55;
    sheet.getRange(`C5:C${end}`).format.numberFormat='0';
    sheet.getRange(`D5:D${end}`).format.numberFormat='0.00E+00';
    sheet.getRange(`H5:H${end}`).format.numberFormat='0.00E+00';
    sheet.getRange(`I1:I${end}`).format.columnWidthPx=165;
  }
  sheet.getRange(`A4:${last}4`).format.borders={bottom:{style:'thin',color:'#CBD5E1'}};
  sheet.freezePanes.freezeRows(4);
  sheet.freezePanes.freezeColumns(1);
  const actual=sheet.getRange(`A5:${last}${end}`).values;
  for(let i=0;i<values.length;i++) for(let j=0;j<values[i].length;j++) {
    const expected=values[i][j], got=actual[i][j];
    if(typeof expected==='number' ? Math.abs(got-expected)>1e-10*Math.max(1,Math.abs(expected)) : got!==expected)
      throw new Error(`${table.name} row ${i+5} column ${j+1} mismatch`);
  }
  checks.push({sheet:table.name,rows:values.length,columns:table.headers.length});
  const blob=await wb.render({sheetName:table.name,range:`A1:${last}11`,scale:1,format:'png'});
  await fs.writeFile(path.join(preview,table.name+'.png'),new Uint8Array(await blob.arrayBuffer()));
}
const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:2000});
if(/"(?:value|text)"\s*:\s*"#[A-Z]/.test(scan.ndjson))throw new Error(scan.ndjson);
const view=await wb.inspect({kind:'table',range:'条件汇总!A4:L8',include:'values,formulas',tableMaxRows:5,tableMaxCols:12,maxChars:1800});
await fs.writeFile(path.join(output,'对比表核验.json'),JSON.stringify({checks,formula_error_scan:scan.ndjson,representative_range:view.ndjson},null,2)+'\n');
const file=path.join(output,'LRE新旧算法对比.xlsx');
const book=await SpreadsheetFile.exportXlsx(wb);await book.save(file);
try { await fs.unlink(file+'.inspect.ndjson'); } catch(error) { if(error.code!=='ENOENT')throw error; }
console.log(JSON.stringify(checks));
