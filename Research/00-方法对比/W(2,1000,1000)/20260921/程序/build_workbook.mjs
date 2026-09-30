import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const programDir = path.dirname(fileURLToPath(import.meta.url));
const workDir = path.resolve(programDir, "../结果/复算输出");
const payload = JSON.parse(await fs.readFile(path.join(workDir, "payload.json"), "utf8"));
const templatePath = path.resolve(programDir, "../结果/2,1000,1000.xlsx");
const fallbackTemplate = templatePath;
const qaDir = path.join(workDir, "qa");
await fs.mkdir(qaDir, { recursive: true });

function colName(index) {
  let value = index + 1;
  let label = "";
  while (value > 0) { const remainder = (value - 1) % 26; label = String.fromCharCode(65 + remainder) + label; value = Math.floor((value - 1) / 26); }
  return label;
}
function estimateValues(row) { return row && row.converged === true ? [row.shape_hat, row.scale_hat, row.location_hat] : ["—", "—", "—"]; }
function copySheetFormat(source, target, sourceRange, targetRange = sourceRange) { target.getRange(targetRange).copyFrom(source.getRange(sourceRange), "all"); }

for (const caseData of payload.cases) {
  let input;
  try { input = await FileBlob.load(templatePath); } catch { input = await FileBlob.load(fallbackTemplate); }
  const workbook = await SpreadsheetFile.importXlsx(input);
  const sample7 = workbook.worksheets.getItemAt(0);
  const sample15 = workbook.worksheets.getItemAt(1);
  const result7 = workbook.worksheets.getItemAt(2);
  const result15 = workbook.worksheets.getItemAt(3);
  const sample30 = workbook.worksheets.getItem("生成样本_n30");
  const result30 = workbook.worksheets.getItem("估计结果_n30");
  copySheetFormat(sample15, sample30, "A1:P51");
  for (let col = 16; col < 31; col++) copySheetFormat(sample15, sample30, "P1:P51", `${colName(col)}1:${colName(col)}51`);
  copySheetFormat(result15, result30, "A1:P174");

  for (const [n, sheet] of [[7, sample7], [15, sample15], [30, sample30]]) {
    const headers = ["样本", ...Array.from({ length: n }, (_, i) => `第${i + 1}顺序统计量`)];
    const rows = caseData.samples[String(n)].map((sample, index) => [index + 1, ...sample]);
    sheet.getRange(`A1:${colName(n)}51`).values = [headers, ...rows];
    sheet.getRange(`A1:${colName(n)}51`).format.font = {name: "Arial", size: 11};
    sheet.getRange(`B1:${colName(n)}51`).format.columnWidth = 20;
    sheet.getRange("A1:A51").format.columnWidth = 9;
    sheet.getRange(`B2:${colName(n)}51`).setNumberFormat("0.000000");
    sheet.getRange("A2:A51").setNumberFormat("0");
    sheet.getRange(`A1:${colName(n)}1`).format.font.bold = true;
    sheet.freezePanes.freezeRows(1);
  }
  for (const [n, sheet] of [[7, result7], [15, result15], [30, result30]]) {
    for (const [offset, startRow] of [["0.10", 1], ["0.15", 59], ["0.20", 117]]) {
      sheet.getRange(`A${startRow}`).values = [[`${caseData.label} · n=${n} · 第1—50组估计结果 · MDM δ=${offset}`]];
      const rows = caseData.results[String(n)][offset].map((row) => [row.sample_id, ...estimateValues(row.MDM), ...estimateValues(row.LS), ...estimateValues(row.LRE), ...estimateValues(row.WMLM), ...estimateValues(row.MLM)]);
      sheet.getRange(`A${startRow + 4}:P${startRow + 53}`).values = rows;
      sheet.getRange(`A${startRow + 55}`).values = [["α=形状参数，β=尺度参数，γ=位置参数；LS=LSE，WMLM=WMLE，MLM=MLE；“—”表示未收敛。"]];
      sheet.getRange(`B${startRow + 4}:P${startRow + 53}`).setNumberFormat("0.000000");
      sheet.getRange(`A${startRow + 4}:A${startRow + 53}`).setNumberFormat("0");
      if(n === 30) {
        sheet.mergeCells(`A${startRow}:P${startRow}`);
        sheet.mergeCells(`A${startRow + 55}:P${startRow + 55}`);
        for(const [a,b] of [["B","D"],["E","G"],["H","J"],["K","M"],["N","P"]]) sheet.mergeCells(`${a}${startRow+2}:${b}${startRow+2}`);
      }
    }
    sheet.getRange("A1:P174").format.font = {name: "Arial", size: 11};
    sheet.getRange("B1:P174").format.columnWidth = 17;
    sheet.getRange("A1:A174").format.columnWidth = 9;
  }
  const inspections = [];
  for (const [sheet, range] of [[sample7,"A1:H8"],[sample15,"A1:P8"],[sample30,"A1:AE8"],[result7,"A1:P10"],[result15,"A1:P10"],[result30,"A1:P10"]]) inspections.push((await workbook.inspect({kind:"table",sheetId:sheet.name,range,include:"values,formulas",tableMaxRows:10,tableMaxCols:31})).ndjson);
  const errors = await workbook.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",options:{useRegex:true,maxResults:300},summary:"final formula error scan"});
  await fs.writeFile(path.join(qaDir, `${caseData.label}.inspect.ndjson`), `${inspections.join("\n")}\n${errors.ndjson}\n`, "utf8");
  for (const [sheet, range, suffix] of [[sample7,"A1:H16","样本_n7"],[sample15,"A1:P12","样本_n15"],[sample30,"A1:AE12","样本_n30"],[result7,"A1:P18","结果_n7_d010"],[result15,"A1:P18","结果_n15_d010"],[result30,"A1:P18","结果_n30_d010"]]) {
    const preview = await workbook.render({sheetName:sheet.name,range,scale:1.2,format:"png"});
    await fs.writeFile(path.join(qaDir, `${caseData.label}-${suffix}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
  const caseDir = path.join(workDir, "outputs", caseData.label);
  await fs.mkdir(caseDir, { recursive: true });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(path.join(caseDir, "2,1000,1000.xlsx"));
  console.log(`workbook complete: ${caseData.label}`);
}
