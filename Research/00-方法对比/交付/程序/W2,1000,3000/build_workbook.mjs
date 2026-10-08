import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const taskDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../结果/复算输出");
const finalDir = path.join(taskDir, "最终交付");
const qaDir = path.join(os.tmpdir(), "weibull-simple-workbook-qa-20260825");

function parseCsvLine(line) {
  const fields = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (character === '"') {
      if (quoted && line[index + 1] === '"') {
        field += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (character === "," && !quoted) {
      fields.push(field);
      field = "";
    } else {
      field += character;
    }
  }
  fields.push(field);
  return fields;
}

function typedValue(value) {
  if (value === "") return null;
  if (value === "True" || value === "true") return true;
  if (value === "False" || value === "false") return false;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : value;
}

async function readCsv(filename) {
  const raw = (await fs.readFile(path.join(taskDir, filename), "utf8")).replace(/^\uFEFF/, "");
  const lines = raw.trim().split(/\r?\n/);
  const headers = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    return Object.fromEntries(headers.map((header, index) => [header, typedValue(values[index] ?? "")]));
  });
}

function columnName(index) {
  let value = index + 1;
  let label = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    value = Math.floor((value - 1) / 26);
  }
  return label;
}

const samples = await readCsv("samples.csv");
const mdmRows = await readCsv("parameter_estimates.csv");
const otherRows = await readCsv("other_method_estimates.csv");

const mdmByKey = new Map(
  mdmRows.map((row) => [
    `${row.sample_size}|${row.sample_id}|${Number(row.offset).toFixed(2)}`,
    row,
  ]),
);
const otherByKey = new Map(
  otherRows.map((row) => [`${row.sample_size}|${row.sample_id}|${row.display_name}`, row]),
);

const workbook = Workbook.create();
const sample7 = workbook.worksheets.add("生成样本_n7");
const result7 = workbook.worksheets.add("估计结果_n7");
const sample15 = workbook.worksheets.add("生成样本_n15");
const result15 = workbook.worksheets.add("估计结果_n15");

const COLORS = {
  title: "#173F5F",
  header: "#20639B",
  light: "#EAF2F8",
  line: "#CBD5E1",
  text: "#1F2937",
  white: "#FFFFFF",
};

for (const sheet of [sample7, result7, sample15, result15]) {
  sheet.showGridLines = false;
}

function buildSampleSheet(sheet, n) {
  const headers = ["样本", "repeat_id", ...Array.from({ length: n }, (_, index) => `x${index + 1}`)];
  const rows = [];
  for (let sampleId = 1; sampleId <= 50; sampleId += 1) {
    const observations = samples
      .filter((row) => row.sample_size === n && row.sample_id === sampleId)
      .sort((left, right) => left.observation_index - right.observation_index);
    rows.push([sampleId, sampleId - 1, ...observations.map((row) => row.value)]);
  }
  const endColumn = columnName(headers.length - 1);
  sheet.mergeCells(`A1:${endColumn}1`);
  sheet.getRange("A1").values = [[`W(2,1000,3000) · n=${n} · 50组样本`]];
  sheet.getRange(`A1:${endColumn}1`).format = {
    fill: COLORS.title,
    font: { bold: true, color: COLORS.white, size: 15 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  sheet.getRange(`A1:${endColumn}1`).format.rowHeight = 30;
  sheet.getRange(`A3:${endColumn}53`).values = [headers, ...rows];
  sheet.getRange(`A3:${endColumn}3`).format = {
    fill: COLORS.header,
    font: { bold: true, color: COLORS.white },
    horizontalAlignment: "center",
  };
  sheet.getRange(`A4:B53`).format = {
    fill: COLORS.light,
    horizontalAlignment: "center",
    numberFormat: "0",
  };
  sheet.getRange(`C4:${endColumn}53`).format.numberFormat = "0.000000";
  sheet.getRange(`A3:${endColumn}53`).format.borders = {
    insideHorizontal: { style: "thin", color: "#E5E7EB" },
    bottom: { style: "thin", color: COLORS.line },
  };
  sheet.getRange("A:B").format.columnWidth = 11;
  sheet.getRange(`C:${endColumn}`).format.columnWidth = 14;
  sheet.freezePanes.freezeRows(3);
  sheet.freezePanes.freezeColumns(2);
  sheet.tables.add(`A3:${endColumn}53`, true, `SamplesN${n}Table`).style = "TableStyleMedium2";
}

function estimateValues(row) {
  if (!row || row.converged !== true) return ["—", "—", "—"];
  return [row.beta_hat, row.eta_hat, row.gamma_hat];
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
    `W(2,1000,3000) · n=${n} · 第1—50组估计结果 · MDM δ=${offset.toFixed(2)}`,
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
    const mdm = mdmByKey.get(`${n}|${sampleId}|${offset.toFixed(2)}`);
    const ls = otherByKey.get(`${n}|${sampleId}|LS`);
    const lre = otherByKey.get(`${n}|${sampleId}|LRE`);
    const wmlm = otherByKey.get(`${n}|${sampleId}|WMLM`);
    const mlm = otherByKey.get(`${n}|${sampleId}|MLM`);
    rows.push([
      sampleId,
      ...estimateValues(mdm),
      ...estimateValues(ls),
      ...estimateValues(lre),
      ...estimateValues(wmlm),
      ...estimateValues(mlm),
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

function buildResultSheet(sheet, n) {
  buildResultBlock(sheet, n, 0.10, 1);
  buildResultBlock(sheet, n, 0.15, 59);
  buildResultBlock(sheet, n, 0.20, 117);
  sheet.getRange("A:A").format.columnWidth = 9;
  sheet.getRange("B:P").format.columnWidth = 14;
  sheet.freezePanes.freezeColumns(1);
}

buildSampleSheet(sample7, 7);
buildResultSheet(result7, 7);
buildSampleSheet(sample15, 15);
buildResultSheet(result15, 15);

const inspections = [];
for (const [sheetName, range] of [
  ["生成样本_n7", "A1:I8"],
  ["估计结果_n7", "A1:P10"],
  ["估计结果_n7", "A59:P68"],
  ["估计结果_n7", "A117:P126"],
  ["生成样本_n15", "A1:Q8"],
  ["估计结果_n15", "A1:P10"],
  ["估计结果_n15", "A59:P68"],
  ["估计结果_n15", "A117:P126"],
]) {
  inspections.push((await workbook.inspect({
    kind: "table",
    range: `${sheetName}!${range}`,
    include: "values,formulas",
    tableMaxRows: 10,
    tableMaxCols: 17,
  })).ndjson);
}
const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});

await fs.mkdir(qaDir, { recursive: true });
await fs.writeFile(
  path.join(qaDir, "inspection.ndjson"),
  `${inspections.join("\n")}\n${formulaErrors.ndjson}\n`,
  "utf8",
);
for (const [sheetName, range, filename] of [
  ["生成样本_n7", "A1:I18", "样本_n7.png"],
  ["生成样本_n15", "A1:Q14", "样本_n15.png"],
  ["估计结果_n7", "A1:P20", "结果_n7_d010.png"],
  ["估计结果_n7", "A59:P78", "结果_n7_d015.png"],
  ["估计结果_n7", "A117:P136", "结果_n7_d020.png"],
  ["估计结果_n15", "A1:P20", "结果_n15_d010.png"],
  ["估计结果_n15", "A59:P78", "结果_n15_d015.png"],
  ["估计结果_n15", "A117:P136", "结果_n15_d020.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.4, format: "png" });
  await fs.writeFile(path.join(qaDir, filename), new Uint8Array(await preview.arrayBuffer()));
}

await fs.mkdir(finalDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.join(finalDir, "样本与估计结果.xlsx"));
console.log(`Workbook created: ${path.join(finalDir, "样本与估计结果.xlsx")}`);
