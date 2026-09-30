import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = String.raw`D:\weibull\docs\临时任务-W2-1000-3000-MDM偏移量估计-20260825\260826位置参数500\估计结果表.xlsx`;
const outputPath = String.raw`D:\weibull\outputs\20260826-gamma500-six-figures-table\all_n7_samples_for_check.json`;

const workbook = await SpreadsheetFile.importXlsx(
  await FileBlob.load(workbookPath),
);
const sheet = workbook.worksheets.getItem("生成样本_n7");
const inspected = await workbook.inspect({
  kind: "table",
  range: "生成样本_n7!A1:H51",
  include: "values,formulas",
  tableMaxRows: 51,
  tableMaxCols: 8,
  maxChars: 30000,
});
const rows = sheet.getRange("A2:H51").values.map((row) => ({
  sample_id: Number(row[0]),
  values: row.slice(1).map(Number),
}));

await fs.writeFile(
  outputPath,
  JSON.stringify({ workbook: workbookPath, sheet: "生成样本_n7", rows }, null, 2),
  "utf8",
);
console.log(inspected.ndjson);
console.log(JSON.stringify({ outputPath, rowCount: rows.length }));
