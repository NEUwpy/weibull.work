import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const dataPath=process.argv[2];if(!dataPath)throw new Error('Provide saved table JSON path');
const out=path.resolve(process.argv[3]||path.join(here,'../结果'));await fs.mkdir(out,{recursive:true});
const cache=path.dirname(path.resolve(dataPath));
const data=JSON.parse(await fs.readFile(dataPath,'utf8'));
const workbook=Workbook.create(),font='Arial',blue='#20639B';
function col(n){let out='';for(;n;n=Math.floor((n-1)/26))out=String.fromCharCode(65+(n-1)%26)+out;return out;}
function header(sheet,range){sheet.getRange(range).format={fill:blue,font:{name:font,size:11,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',rowHeight:24};}
for(const n of [7,10,15,20,50])for(const kind of ['samples','estimates']){
 const item=data.sheets.find(s=>s.n===n && s.kind===kind);
 const sheet=workbook.worksheets.add(item.name),width=kind==='estimates'?10:item.n+1,last=col(width),start=2,end=1201;
 sheet.showGridLines=false;sheet.getRange(`A1:${last}${end}`).format.font={name:font,size:11,color:'#1F2937'};
 sheet.getRange(`A:${last}`).format.columnWidth=15;sheet.getRange('A:A').format.columnWidth=9;
 if(kind==='estimates'){
   sheet.getRange('A1:J1').values=[['样本','MLE β','MLE η','MLE γ','MMLE β','MMLE η','MMLE γ','WMLE β','WMLE η','WMLE γ']];
   header(sheet,'A1:J1');
 }else{
   sheet.getRange(`A1:${last}1`).values=[['样本',...Array.from({length:item.n},(_,i)=>`t${i+1}`)]];header(sheet,`A1:${last}1`);
 }
 sheet.getRange(`A${start}:${last}${end}`).values=item.rows;
 sheet.getRange(`A${start}:A${end}`).format={fill:'#EAF2F8',font:{name:font,size:11,bold:true,color:'#1F2937'},horizontalAlignment:'center'};
 sheet.getRange(`A${start}:A${end}`).setNumberFormat('0');sheet.getRange(`B${start}:${last}${end}`).setNumberFormat('0.000000');
 sheet.getRange(`B${start}:${last}${end}`).format.horizontalAlignment='right';
 sheet.getRange(`A${start}:${last}${end}`).format.rowHeight=21;
 sheet.getRange(`A${start}:${last}${end}`).format.borders={bottom:{style:'thin',color:'#E5E7EB'}};
 sheet.getRange(`A1:A${end}`).format.borders={right:{style:'medium',color:blue}};
 if(kind==='estimates')for(const c of ['D','G','J'])sheet.getRange(`${c}1:${c}${end}`).format.borders={right:{style:'thin',color:'#B7C9D6'}};
 sheet.freezePanes.freezeRows(start-1);sheet.freezePanes.freezeColumns(1);
 const range=`A1:${last}13`;
 const preview=await workbook.render({sheetName:sheet.name,range,format:'png',scale:1});
 await fs.writeFile(path.join(cache,`精简预览_${sheet.name}.png`),new Uint8Array(await preview.arrayBuffer()));
 console.log(`Built and rendered ${sheet.name}: 1200 rows.`);
}
const summary=workbook.worksheets.add('汇总');summary.showGridLines=false;
summary.getRange('A1:N16').format.font={name:font,size:11,color:'#1F2937'};
summary.getRange('A:N').format.columnWidth=13;summary.getRange('B:D').format.columnWidth=9;
summary.getRange('A1:N1').values=[['方法','n','总组数','有效解','有解率','β Bias','β SD','β RMSE','η Bias','η SD','η RMSE','γ Bias','γ SD','γ RMSE']];header(summary,'A1:N1');
summary.getRange('A2:N16').values=data.summary.rows;
summary.getRange('E2').formulas=[['=D2/C2']];summary.getRange('E2:E16').fillDown();
summary.getRange('B2:D16').setNumberFormat('0');summary.getRange('E2:E16').setNumberFormat('0.00%');
summary.getRange('F2:H16').setNumberFormat('0.000');summary.getRange('I2:N16').setNumberFormat('0.00');
summary.getRange('B2:N16').format.horizontalAlignment='right';summary.getRange('A2:N16').format.rowHeight=23;
summary.getRange('A7:N11').format.fill='#EAF2F8';summary.getRange('A2:N16').format.borders={bottom:{style:'thin',color:'#E5E7EB'}};
summary.freezePanes.freezeRows(1);
const preview=await workbook.render({sheetName:'汇总',range:'A1:N16',format:'png',scale:1});
await fs.writeFile(path.join(cache,'精简预览_汇总.png'),new Uint8Array(await preview.arrayBuffer()));
const inspect=await workbook.inspect({kind:'workbook,sheet',maxChars:5500,tableMaxRows:4,tableMaxCols:5});
await fs.writeFile(path.join(cache,'精简工作簿检查.ndjson'),inspect.ndjson);
const xlsx=await SpreadsheetFile.exportXlsx(workbook);await xlsx.save(path.join(out,'W(2,1000,500).xlsx'));
console.log('Workbook exported: 11 paired sheets, first row headers, no remarks or merged cells.');
