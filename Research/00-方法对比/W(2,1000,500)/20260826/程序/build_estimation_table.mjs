import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const workDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../结果/复算输出");
const deliveryDir = path.join(workDir, "交付");
const outputPath = path.join(workDir, "估计结果表.xlsx");
const deliveryPath = path.join(deliveryDir, "估计结果表.xlsx");
const payload = JSON.parse(await fs.readFile(path.join(workDir, "workbook_data.json"), "utf8"));
const sampleCsv = (await fs.readFile(path.join(workDir, "samples.csv"), "utf8"))
  .replace(/^\uFEFF/, "")
  .trim()
  .split(/\r?\n/)
  .slice(1)
  .map((line) => {
    const [sampleSize, sampleId, repeatId, observationIndex, value] = line.split(",");
    return {
      sampleSize: Number(sampleSize),
      sampleId: Number(sampleId),
      repeatId: Number(repeatId),
      observationIndex: Number(observationIndex),
      value: Number(value),
    };
  });

const workbook = Workbook.create();
const sampleSheets = {
  7: workbook.worksheets.add("生成样本_n7"),
  15: workbook.worksheets.add("生成样本_n15"),
};
const sheets = {
  7: workbook.worksheets.add("估计结果_n7"),
  15: workbook.worksheets.add("估计结果_n15"),
};

const COLORS = {
  title: "#173F5F",
  header: "#20639B",
  light: "#EAF2F8",
  line: "#CBD5E1",
  text: "#1F2937",
  white: "#FFFFFF",
};

const mdmByKey = new Map(
  payload.mdm_rows.map((row) => [
    `${row.sample_size}|${row.sample_id}|${Number(row.offset).toFixed(2)}`,
    row,
  ]),
);
const otherByKey = new Map(
  payload.other_rows.map((row) => [
    `${row.sample_size}|${row.sample_id}|${row.display_name}`,
    row,
  ]),
);

function estimateValues(row) {
  if (!row || row.converged !== true) return ["—", "—", "—"];
  return [row.beta_hat, row.eta_hat, row.gamma_hat];
}

function buildSampleSheet(sheet, n) {
  const lastColumn = n === 7 ? "H" : "P";
  const headers = ["样本", ...Array.from({ length: n }, (_, i) => `第${i + 1}顺序统计量`)];
  const rows = [];
  for (let sampleId = 1; sampleId <= 50; sampleId += 1) {
    const observations = sampleCsv
      .filter((row) => row.sampleSize === n && row.sampleId === sampleId)
      .sort((a, b) => a.observationIndex - b.observationIndex)
      .map((row) => row.value);
    if (observations.length !== n) {
      throw new Error(`n=${n}, sample=${sampleId}: expected ${n} observations, got ${observations.length}`);
    }
    rows.push([sampleId, ...observations]);
  }

  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastColumn}1`).values = [headers];
  sheet.getRange(`A1:${lastColumn}1`).format = {
    fill: COLORS.header,
    font: { bold: true, color: COLORS.white, size: 11 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: "#B7C9D6" },
  };
  sheet.getRange(`A1:${lastColumn}1`).format.rowHeight = 26;
  sheet.getRange(`A2:${lastColumn}51`).values = rows;
  sheet.getRange("A2:A51").format = {
    fill: COLORS.light,
    font: { bold: true, color: COLORS.text },
    horizontalAlignment: "center",
    numberFormat: "0",
  };
  sheet.getRange(`B2:${lastColumn}51`).format = {
    numberFormat: "0.000000",
    horizontalAlignment: "right",
  };
  sheet.getRange(`A2:${lastColumn}51`).format.borders = {
    insideHorizontal: { style: "thin", color: "#E5E7EB" },
    insideVertical: { style: "thin", color: "#E5E7EB" },
    bottom: { style: "thin", color: COLORS.line },
  };
  sheet.getRange("A1:A51").format.columnWidth = 9;
  sheet.getRange(`B1:${lastColumn}51`).format.columnWidth = 15;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(1);
}

function buildResultBlock(sheet, n, offset, startRow) {
  const titleRow = startRow;
  const groupRow = startRow + 2;
  const symbolRow = startRow + 3;
  const firstDataRow = startRow + 4;
  const lastDataRow = startRow + 53;
  const noteRow = startRow + 55;

  sheet.mergeCells(`A${titleRow}:P${titleRow}`);
  sheet.getRange(`A${titleRow}`).values = [[
    `W(2,1000,500) · n=${n} · 第1—50组估计结果 · MDM δ=${offset.toFixed(2)}`,
  ]];
  sheet.getRange(`A${titleRow}:P${titleRow}`).format = {
    fill: COLORS.title,
    font: { bold: true, color: COLORS.white, size: 15 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  sheet.getRange(`A${titleRow}:P${titleRow}`).format.rowHeight = 30;

  sheet.mergeCells(`A${groupRow}:A${symbolRow}`);
  for (const range of [
    `B${groupRow}:D${groupRow}`,
    `E${groupRow}:G${groupRow}`,
    `H${groupRow}:J${groupRow}`,
    `K${groupRow}:M${groupRow}`,
    `N${groupRow}:P${groupRow}`,
  ]) {
    sheet.mergeCells(range);
  }
  sheet.getRange(`A${groupRow}`).values = [["样本"]];
  sheet.getRange(`B${groupRow}`).values = [["MDM"]];
  sheet.getRange(`E${groupRow}`).values = [["LS"]];
  sheet.getRange(`H${groupRow}`).values = [["LRE"]];
  sheet.getRange(`K${groupRow}`).values = [["WMLM"]];
  sheet.getRange(`N${groupRow}`).values = [["MLM"]];
  sheet.getRange(`B${symbolRow}:P${symbolRow}`).values = [[
    "α", "β", "γ", "α", "β", "γ", "α", "β", "γ",
    "α", "β", "γ", "α", "β", "γ",
  ]];
  sheet.getRange(`A${groupRow}:P${symbolRow}`).format = {
    fill: COLORS.header,
    font: { bold: true, color: COLORS.white, size: 11 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: "#B7C9D6" },
  };
  sheet.getRange(`A${groupRow}:P${symbolRow}`).format.rowHeight = 24;

  const rows = [];
  for (let sampleId = 1; sampleId <= 50; sampleId += 1) {
    rows.push([
      sampleId,
      ...estimateValues(mdmByKey.get(`${n}|${sampleId}|${offset.toFixed(2)}`)),
      ...estimateValues(otherByKey.get(`${n}|${sampleId}|LS`)),
      ...estimateValues(otherByKey.get(`${n}|${sampleId}|LRE`)),
      ...estimateValues(otherByKey.get(`${n}|${sampleId}|WMLM`)),
      ...estimateValues(otherByKey.get(`${n}|${sampleId}|MLM`)),
    ]);
  }
  sheet.getRange(`A${firstDataRow}:P${lastDataRow}`).values = rows;
  sheet.getRange(`A${firstDataRow}:A${lastDataRow}`).format = {
    fill: COLORS.light,
    font: { bold: true, color: COLORS.text },
    horizontalAlignment: "center",
    numberFormat: "0",
  };
  sheet.getRange(`B${firstDataRow}:P${lastDataRow}`).format = {
    numberFormat: "0.000000",
    horizontalAlignment: "right",
  };
  sheet.getRange(`A${firstDataRow}:P${lastDataRow}`).format.borders = {
    insideHorizontal: { style: "thin", color: "#E5E7EB" },
    insideVertical: { style: "thin", color: "#E5E7EB" },
    bottom: { style: "thin", color: COLORS.line },
  };
  for (const boundary of ["A", "D", "G", "J", "M", "P"]) {
    sheet.getRange(`${boundary}${groupRow}:${boundary}${lastDataRow}`).format.borders = {
      right: { style: "medium", color: COLORS.header },
    };
  }
  sheet.mergeCells(`A${noteRow}:P${noteRow}`);
  sheet.getRange(`A${noteRow}`).values = [[
    "α=形状参数，β=尺度参数，γ=位置参数；LS=LSE，WMLM=WMLE，MLM=MLE；“—”表示未收敛。",
  ]];
  sheet.getRange(`A${noteRow}:P${noteRow}`).format = {
    fill: "#F8FAFC",
    font: { italic: true, color: "#475569", size: 10 },
    horizontalAlignment: "left",
  };
}

for (const n of [7, 15]) {
  buildSampleSheet(sampleSheets[n], n);
  const sheet = sheets[n];
  sheet.showGridLines = false;
  buildResultBlock(sheet, n, 0.10, 1);
  buildResultBlock(sheet, n, 0.15, 59);
  buildResultBlock(sheet, n, 0.20, 117);
  sheet.getRange("A1:A172").format.columnWidth = 9;
  sheet.getRange("B1:P172").format.columnWidth = 14;
  sheet.freezePanes.freezeColumns(1);
}

for (const [sheetName, ranges] of [
  ["生成样本_n7", ["A1:H10"]],
  ["生成样本_n15", ["A1:P10"]],
  ["估计结果_n7", ["A1:P10", "A59:P68", "A117:P126"]],
  ["估计结果_n15", ["A1:P10", "A59:P68", "A117:P126"]],
]) {
  for (const range of ranges) {
    const inspection = await workbook.inspect({
      kind: "table",
      range: `${sheetName}!${range}`,
      include: "values,formulas",
      tableMaxRows: 10,
      tableMaxCols: 16,
      maxChars: 12000,
    });
    console.log(inspection.ndjson);
  }
}
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

for (const [sheetName, ranges] of [
  ["生成样本_n7", ["A1:H20"]],
  ["生成样本_n15", ["A1:P20"]],
  ["估计结果_n7", ["A1:P18", "A59:P76", "A117:P134"]],
  ["估计结果_n15", ["A1:P18", "A59:P76", "A117:P134"]],
]) {
  for (let index = 0; index < ranges.length; index += 1) {
    const preview = await workbook.render({
      sheetName,
      range: ranges[index],
      scale: 1.2,
      format: "png",
    });
    await fs.writeFile(
      path.join(workDir, `qa_${sheetName}_${index + 1}.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }
}

await fs.mkdir(deliveryDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
await fs.copyFile(outputPath, deliveryPath);
console.log(JSON.stringify({ outputPath, deliveryPath }, null, 2));
