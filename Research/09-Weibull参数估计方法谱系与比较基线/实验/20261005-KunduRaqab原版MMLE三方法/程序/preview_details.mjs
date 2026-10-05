import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {FileBlob,Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(here,'../结果/W(2,1000,1000)_完整样本与估计.xlsx')));
const preview=await workbook.render({sheetName:'样本',range:'AT4806:BE4813',format:'png',scale:1});
await fs.writeFile(path.join(here,'n50末尾观测预览.png'),new Uint8Array(await preview.arrayBuffer()));
console.log('Saved workbook n50 last observation columns rendered; workbook not edited.');
