import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const workbook=Workbook.create();const font='Arial';
function columnName(value){let out='';for(let n=value;n;n=Math.floor((n-1)/26))out=String.fromCharCode(65+(n-1)%26)+out;return out;}
async function read(name){return JSON.parse(await fs.readFile(path.join(here,name),'utf8'));}
const samples=await read('样本数据.json');const estimates=await read('估计明细数据.json');const summary=await read('汇总表数据.json');
function populate(name,title,context,data,tableName){
  const sheet=workbook.worksheets.add(name),last=columnName(data.columns.length),end=data.rows.length+5;
  sheet.showGridLines=false;
  sheet.getRange(`A1:${last}${end}`).format.font={name:font,size:10,color:'#26313A'};
  sheet.getRange('A1').values=[[title]];sheet.getRange('A1').format.font={name:font,size:14,bold:true};
  sheet.getRange('A2').values=[[context]];sheet.getRange('A2').format.font={name:font,size:10,color:'#5F6570'};
  sheet.getRange(`A3:${last}3`).format.borders={bottom:{style:'thin',color:'#B8C2CA'}};
  sheet.getRange(`A5:${last}5`).values=[data.columns];
  for(let start=0;start<data.rows.length;start+=1000){
    const batch=data.rows.slice(start,start+1000);sheet.getRange(`A${start+6}:${last}${start+5+batch.length}`).values=batch;
  }
  const table=sheet.tables.add(`A5:${last}${end}`,true,tableName);table.showFilterButton=true;
  sheet.getRange(`A5:${last}5`).format={fill:'#3D4A56',font:{name:font,size:10,color:'#FFFFFF',bold:true},
    horizontalAlignment:'center',verticalAlignment:'center',rowHeight:30};
  sheet.getRange(`A6:${last}${end}`).format.rowHeight=32;
  sheet.getRange(`A6:${last}${end}`).format.verticalAlignment='center';
  sheet.getRange(`A6:${last}${end}`).format.horizontalAlignment='right';
  sheet.getRange(`A:${last}`).format.columnWidthPx=105;
  sheet.freezePanes.freezeRows(5);sheet.freezePanes.freezeColumns(name==='估计明细'?6:2);
  return sheet;
}
const sampleSheet=populate('样本','W(2,1000,1000) 完整排序样本','每行一组，n = 7 / 10 / 15 / 20 / 50，各1200组。x(1)至x(n)为全部观测，之后空白。',samples,'SampleGroups');
sampleSheet.getRange('A:A').format.columnWidthPx=50;sampleSheet.getRange('B:B').format.columnWidthPx=100;
sampleSheet.getRange('C:E').format.columnWidthPx=64;sampleSheet.getRange('F:F').format.columnWidthPx=290;
sampleSheet.getRange('G:G').format.columnWidthPx=290;
sampleSheet.getRange('B6:B6005').format.horizontalAlignment='left';sampleSheet.getRange('F6:G6005').format.horizontalAlignment='left';
sampleSheet.getRange('F6:G6005').format.wrapText=true;sampleSheet.getRange('A6:A6005').setNumberFormat('0');
sampleSheet.getRange('C6:E6005').setNumberFormat('0');sampleSheet.getRange('H6:BE6005').setNumberFormat('0.000000');
console.log('6000 sample rows populated.');
const estimateSheet=populate('估计明细','MLE、MMLE、WMLE 完整估计明细','每行一个方法×样本组，包含失败。MMLE删除原最小观测，支持检查最小值为剩余样本最小值。',estimates,'EstimateDetails');
estimateSheet.getRange('A:A').format.columnWidthPx=50;estimateSheet.getRange('B:B').format.columnWidthPx=100;
estimateSheet.getRange('C:E').format.columnWidthPx=64;estimateSheet.getRange('F:F').format.columnWidthPx=75;
estimateSheet.getRange('G:L').format.columnWidthPx=110;estimateSheet.getRange('M:N').format.columnWidthPx=64;
estimateSheet.getRange('O:O').format.columnWidthPx=250;estimateSheet.getRange('P:P').format.columnWidthPx=330;
estimateSheet.getRange('Q:R').format.columnWidthPx=130;estimateSheet.getRange('S:S').format.columnWidthPx=100;
estimateSheet.getRange('T:T').format.columnWidthPx=105;estimateSheet.getRange('U:U').format.columnWidthPx=290;
for(const range of ['B6:B18005','F6:F18005','N6:P18005','U6:U18005'])estimateSheet.getRange(range).format.horizontalAlignment='left';
for(const range of ['O6:P18005','U6:U18005'])estimateSheet.getRange(range).format.wrapText=true;
for(const range of ['A6:A18005','C6:E18005','S6:S18005'])estimateSheet.getRange(range).setNumberFormat('0');
for(const range of ['G6:L18005','Q6:R18005','T6:T18005'])estimateSheet.getRange(range).setNumberFormat('0.000000');
console.log('18000 estimate rows populated.');
const headers=['方法','n','总组数','有效解','有解率','β Bias','β SD','β RMSE','η Bias','η SD','η RMSE','γ Bias','γ SD','γ RMSE'];
const summarySheet=populate('汇总','MLE、MMLE、WMLE 汇总','真值 β = 2，η = 1000，γ = 1000；精度使用各方法全部成功估计，不裁剪。',{columns:headers,rows:summary.rows},'MethodSummary');
summarySheet.freezePanes.unfreeze();summarySheet.getRange('A:N').format.columnWidthPx=95;summarySheet.getRange('B:D').format.columnWidthPx=64;
summarySheet.getRange('A6:A20').format.horizontalAlignment='left';summarySheet.getRange('B6:D20').setNumberFormat('0');
summarySheet.getRange('E6').formulas=[['=D6/C6']];summarySheet.getRange('E6:E20').fillDown();summarySheet.getRange('E6:E20').setNumberFormat('0.00%');
summarySheet.getRange('F6:H20').setNumberFormat('0.000');summarySheet.getRange('I6:N20').setNumberFormat('0.00');
summarySheet.getRange('A22').values=[['Bias = mean(估计−真值)，有符号平均偏差；SD = std(估计，ddof=0)。']];
summarySheet.getRange('A23').values=[['RMSE = √mean((估计−真值)²)；RMSE² = Bias² + SD²。失败不进入精度统计，有解率分母始终1200。']];
summarySheet.getRange('A24').values=[['成功要求收敛、形状和尺度正且有限、位置有限并小于实际保留观测的最小值。MMLE删一个最小观测。']];
summarySheet.getRange('A25').values=[['方法来源：Kundu & Raqab (2009) §2构造的单样本形式。所有估计均复用已保存结果，未重新拟合。']];
summarySheet.getRange('A22:N25').format.font={name:font,size:10,color:'#5F6570'};
console.log('15 summary rows populated.');
const inspectRanges=[['样本','A5:K10'],['样本','AU5999:BE6005'],['估计明细','A5:N11'],['估计明细','O5:U10'],['估计明细','A18000:U18005'],['汇总','A5:N20']];
let inspection='';for(const [sheetId,range] of inspectRanges){
  const result=await workbook.inspect({kind:'region',sheetId,range,maxChars:4500,tableMaxRows:6,tableMaxCols:14});inspection+=result.ndjson+'\n';
}
await fs.writeFile(path.join(here,'完整工作簿检查.ndjson'),inspection);
const previews=[['样本','A1:Q13','样本预览.png'],['样本','AT5:BE13','样本尾列预览.png'],
 ['估计明细','A1:N13','估计预览.png'],['估计明细','O5:U13','失败与支持列预览.png'],['汇总','A1:N25','完整汇总预览.png']];
for(const [sheetName,range,name] of previews){
 const preview=await workbook.render({sheetName,range,format:'png',scale:1});await fs.writeFile(path.join(here,name),new Uint8Array(await preview.arrayBuffer()));
 console.log(`Rendered ${sheetName} ${range}.`);
}
const output=await SpreadsheetFile.exportXlsx(workbook);await output.save(path.join(here,'../结果/W(2,1000,1000)_完整样本与估计.xlsx'));
console.log('Complete 3-sheet XLSX exported.');
