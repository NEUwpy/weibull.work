import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(here,'../结果/W(2,1000,1000).xlsx')));
for (const [n,last] of [[7,'H'],[10,'K'],[15,'P'],[20,'U'],[50,'AY']]) {
  const preview=await workbook.render({sheetName:`生成样本_n${n}`,range:`A1:${last}13`,format:'png',scale:1});
  await fs.writeFile(path.join(here,`精简完整预览_生成样本_n${n}.png`),new Uint8Array(await preview.arrayBuffer()));
  console.log(`Reviewed saved sample sheet n=${n}, all ${n} observations.`);
}
