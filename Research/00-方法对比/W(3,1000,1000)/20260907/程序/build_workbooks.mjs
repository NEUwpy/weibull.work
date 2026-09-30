import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";


const programDir = path.dirname(fileURLToPath(import.meta.url));
const workDir = path.resolve(programDir, "../结果/复算输出");
const payload = JSON.parse(await fs.readFile(path.join(workDir, "payload.json"), "utf8"));
const templatePath = path.resolve(programDir, "../结果/3,1000,1000.xlsx");
if (payload.cases.length !== 1 || payload.cases[0].shape !== 3 || payload.cases[0].scale !== 1000 || payload.cases[0].location !== 1000) throw new Error("Wrong batch payload");
const qaDir = path.join(workDir, "qa");
await fs.mkdir(qaDir, { recursive: true });

function colName(index) {
  let value = index + 1;
  let label = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    value = Math.floor((value - 1) / 26);
  }
  return label;
}

function estimateValues(row) {
  if (!row || row.converged !== true) return ["—", "—", "—"];
  return [row.shape_hat, row.scale_hat, row.location_hat];
}

for (const caseData of payload.cases) {
  const input = await FileBlob.load(templatePath);
  const workbook = await SpreadsheetFile.importXlsx(input);
  const sample7 = workbook.worksheets.getItemAt(0);
  const sample15 = workbook.worksheets.getItemAt(1);
  const result7 = workbook.worksheets.getItemAt(2);
  const result15 = workbook.worksheets.getItemAt(3);

  for (const [n, sheet] of [[7, sample7], [15, sample15]]) {
    const headers = ["样本", ...Array.from({ length: n }, (_, i) => `第${i + 1}顺序统计量`)];
    const rows = caseData.samples[String(n)].map((sample, index) => [index + 1, ...sample]);
    const endCol = colName(n);
    sheet.getRange(`A1:${endCol}51`).values = [headers, ...rows];
  }

  for (const [n, sheet] of [[7, result7], [15, result15]]) {
    for (const [offset, startRow] of [["0.10", 1], ["0.15", 59], ["0.20", 117]]) {
      sheet.getRange(`A${startRow}`).values = [[
        `${caseData.label} · n=${n} · 第1—50组估计结果 · MDM δ=${offset}`,
      ]];
      const rows = caseData.results[String(n)][offset].map((row) => [
        row.sample_id,
        ...estimateValues(row.MDM),
        ...estimateValues(row.LS),
        ...estimateValues(row.LRE),
        ...estimateValues(row.WMLM),
        ...estimateValues(row.MLM),
      ]);
      sheet.getRange(`A${startRow + 4}:P${startRow + 53}`).values = rows;
      sheet.getRange(`A${startRow + 55}`).values = [[
        "α=形状参数，β=尺度参数，γ=位置参数；LS=LSE，WMLM=WMLE，MLM=MLE；“—”表示未收敛。",
      ]];
    }
  }

  const inspections = [];
  for (const [sheet, range] of [
    [sample7, "A1:H8"], [sample15, "A1:P8"],
    [result7, "A1:P10"], [result7, "A59:P68"], [result7, "A117:P126"],
    [result15, "A1:P10"], [result15, "A59:P68"], [result15, "A117:P126"],
  ]) {
    inspections.push((await workbook.inspect({
      kind: "table",
      sheetId: sheet.name,
      range,
      include: "values,formulas",
      tableMaxRows: 10,
      tableMaxCols: 16,
    })).ndjson);
  }
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 300 },
    summary: "final formula error scan",
  });
  await fs.writeFile(
    path.join(qaDir, `${caseData.label}.inspect.ndjson`),
    `${inspections.join("\n")}\n${errors.ndjson}\n`,
    "utf8",
  );

  for (const [sheet, range, suffix] of [
    [sample7, "A1:H16", "样本_n7"],
    [sample15, "A1:P12", "样本_n15"],
    [result7, "A1:P18", "结果_n7_d010"],
    [result7, "A59:P76", "结果_n7_d015"],
    [result7, "A117:P134", "结果_n7_d020"],
    [result15, "A1:P18", "结果_n15_d010"],
    [result15, "A59:P76", "结果_n15_d015"],
    [result15, "A117:P134", "结果_n15_d020"],
  ]) {
    const preview = await workbook.render({ sheetName: sheet.name, range, scale: 1.2, format: "png" });
    await fs.writeFile(
      path.join(qaDir, `${caseData.label}-${suffix}.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }

  const caseDir = path.join(workDir, "outputs", caseData.label);
  await fs.mkdir(caseDir, { recursive: true });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(path.join(caseDir, `${caseData.shape},${caseData.scale},${caseData.location}.xlsx`.replaceAll(".0", "")));
  console.log(`workbook complete: ${caseData.label}`);
}
