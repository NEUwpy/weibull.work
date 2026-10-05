import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const reference=(await fs.readFile(path.join(here,'Research00参照路径.txt'),'utf8')).trim();
const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(reference));
for(const sheetName of ['估计结果_n7','生成样本_n7']){
 const range=sheetName.startsWith('估计')?'A1:P12':'A1:H12';
 const preview=await workbook.render({sheetName,range,format:'png',scale:1});
 await fs.writeFile(path.join(here,`Research00_${sheetName}.png`),new Uint8Array(await preview.arrayBuffer()));
}
console.log((await workbook.inspect({kind:'computedStyle',sheetId:'估计结果_n7',range:'A3:B5',maxChars:2700})).ndjson);
