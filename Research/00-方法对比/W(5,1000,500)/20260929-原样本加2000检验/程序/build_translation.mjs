import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const here=path.dirname(fileURLToPath(import.meta.url));
const data=JSON.parse(await fs.readFile(path.join(here,'translation_data.json'),'utf8'));
const output='D:/weibull/docs/临时任务/临时任务-W2-1000-3000-MDM偏移量估计-20260825/260906-W5参数估计案例/W(5,1000,500)/原样本加2000_估计结果对照.xlsx';
try {await fs.access(output);throw new Error('Output exists; refusing to overwrite.');}catch(e){if(e.code!=='ENOENT')throw e;}
const wb=Workbook.create();
function base(s,lastCol,lastRow,title,source){
 s.showGridLines=false;
 s.getRange(`A1:${lastCol}${lastRow}`).format.font={name:'Microsoft YaHei',size:11,color:'#202020'};
 s.getRange(`A1:${lastCol}${lastRow}`).format.rowHeight=22;
 s.getRange('A1').values=[[title]];
 s.getRange('A1').format.font={name:'Microsoft YaHei',size:15,bold:true};
 s.getRange('A1').format.rowHeight=29;
 s.getRange('A2').values=[[source]];
 s.getRange('A2').format.font={name:'Microsoft YaHei',size:10,color:'#666666'};
 s.getRange('A3:B3').values=[['平移量',data.shift]];
 s.getRange(`A6:${lastCol}6`).format={fill:'#E8EDF3',font:{name:'Microsoft YaHei',size:11,bold:true,color:'#202020'},wrapText:true,rowHeight:35};
 s.freezePanes.freezeRows(6);
}
for(const n of [7,15]){
 const s=wb.worksheets.add(`估计结果_n${n}`);
 const rr=data.rows.filter(r=>r.n===n);
 base(s,'N',rr.length+6,`原样本加2000估计结果对照（样本量${n}）`,'来源：5,1000,500.xlsx 对应原始样本与估计记录；使用原权重，不重新抽样。');
 s.getRange('A4').values=[['β为形状、η为尺度、γ为位置（原交付表的α、β、γ分别对应形状、尺度、位置）。差值为平移后减原结果。']];
 s.getRange('A6:N6').values=[['样本组','方法','偏移量δ','原形状β','原尺度η','原位置γ','新形状β','新尺度η','新位置γ','形状差值','尺度差值','位置差值','位置差值−平移量','说明']];
 const vals=rr.map(r=>[r.id,r.method,r.delta,...(r.before??[null,null,null]),...(r.after??[null,null,null]),null,null,null,null,r.note]);
 s.getRange(`A7:N${6+rr.length}`).values=vals;
 s.getRange('A:A').format.columnWidth=9;
 s.getRange('B:C').format.columnWidth=10;
 s.getRange('D:L').format.columnWidth=17;
 s.getRange('M:M').format.columnWidth=24;
 s.getRange('N:N').format.columnWidth=47;
 s.getRange(`D7:L${6+rr.length}`).setNumberFormat('0.000000');
 s.getRange(`M7:M${6+rr.length}`).setNumberFormat('0.000000000');
 s.getRange(`C7:C${6+rr.length}`).setNumberFormat('0.00');
 s.getRange(`N7:N${6+rr.length}`).format.wrapText=true;
 for(let i=0;i<rr.length;i++){
  const row=i+7,r=rr[i];
  if(r.before&&r.after)s.getRange(`J${row}:M${row}`).formulas=[[`=G${row}-D${row}`,`=H${row}-E${row}`,`=I${row}-F${row}`,`=L${row}-$B$3`]];
  if(r.note)s.getRange(`A${row}:N${row}`).format.rowHeight=40;
  if(i%50===0)s.getRange(`A${row}:N${row}`).format.borders={top:{style:'thin',color:'#AAB5C2'}};
 }
 console.log((await wb.inspect({kind:'table',range:`估计结果_n${n}!D7:M9`,include:'values,formulas',tableMaxRows:3,tableMaxCols:10,maxChars:1800})).ndjson);
 const img=await wb.render({sheetName:s.name,range:'A1:N10',scale:1,format:'png'});
 await fs.writeFile(path.join(here,`preview_n${n}.png`),new Uint8Array(await img.arrayBuffer()));
}
const s=wb.worksheets.add('样本对照');
const samples=data.samples;
base(s,'F',samples.length+6,'原样本和平移后样本','原分布W(5,1000,500)，原样本整体＋2000，无重新抽样。');
s.getRange('A4').values=[['验证平移性质，不代表估计无偏；失败估计留空，不填零。']];
s.getRange('A6:F6').values=[['样本量','样本组','组内序号','原样本值','原样本值＋2000','差值']];
s.getRange(`A7:F${samples.length+6}`).values=samples.map(r=>[Number(r.sample_size),Number(r.sample_id),Number(r.observation_index),Number(r.value),null,null]);
s.getRange(`E7:F${samples.length+6}`).formulas=samples.map((_,i)=>[`=D${i+7}+$B$3`,`=E${i+7}-D${i+7}`]);
s.getRange('A:C').format.columnWidth=13;
s.getRange('D:F').format.columnWidth=23;
s.getRange(`D7:F${samples.length+6}`).setNumberFormat('0.000000');
console.log((await wb.inspect({kind:'table',range:'样本对照!A6:F9',include:'values,formulas',tableMaxRows:4,tableMaxCols:6,maxChars:1500})).ndjson);
const img=await wb.render({sheetName:'样本对照',range:'A1:F11',scale:1,format:'png'});
await fs.writeFile(path.join(here,'preview_samples.png'),new Uint8Array(await img.arrayBuffer()));
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},summary:'formula error scan'});
console.log(errors.ndjson);
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(output);
console.log('SAVED',output);
