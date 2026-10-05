import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = String.raw`D:\weibull\docs\临时任务-W2-1000-3000-MDM偏移量估计-20260825\260826位置参数500\估计结果表.xlsx`;
const outputPath = String.raw`D:\weibull\outputs\20260826-gamma500-six-figures-table\step_sensitivity_samples.json`;

const workbook = await SpreadsheetFile.importXlsx(
  await FileBlob.load(workbookPath),
);
const sheet = workbook.worksheets.getItem("生成样本_n7");

const cases = [4, 32].map((sampleId) => ({
  sample_id: sampleId,
  source_sheet: "生成样本_n7",
  source_range: `B${sampleId + 1}:H${sampleId + 1}`,
  values: sheet
    .getRange(`B${sampleId + 1}:H${sampleId + 1}`)
    .values[0]
    .map(Number),
}));

await fs.writeFile(
  outputPath,
  JSON.stringify({ workbook: workbookPath, cases }, null, 2),
  "utf8",
);
console.log(JSON.stringify({ outputPath, cases }));
