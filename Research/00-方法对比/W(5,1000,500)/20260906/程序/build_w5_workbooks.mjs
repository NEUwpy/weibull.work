import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const programDir = path.dirname(fileURLToPath(import.meta.url));
const workDir = path.resolve(programDir, "../结果/复算输出");
const deliveryRoot = workDir;
const cases = [{ slug: "W5-1000-500", deliveryName: "W(5,1000,500)" }];

const COLORS = {
  title: "#173F5F",
  header: "#20639B",
  light: "#EAF2F8",
  line: "#CBD5E1",
  text: "#1F2937",
  white: "#FFFFFF",
};

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

async function readSamples(caseWorkDir) {
  const raw = (await fs.readFile(path.join(caseWorkDir, "samples.csv"), "utf8"))
    .replace(/^\uFEFF/, "")
    .trim()
    .split(/\r?\n/);
  const headers = parseCsvLine(raw[0]);
  return raw.slice(1).map((line) => {
    const values = parseCsvLine(line);
    const row = Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]));
    return {
      sampleSize: Number(row.sample_size),
      sampleId: Number(row.sample_id),
      repeatId: Number(row.repeat_id),
      observationIndex: Number(row.observation_index),
      value: Number(row.value),
    };
  });
}

function estimateValues(row) {
  if (!row || row.converged !== true) return ["—", "—", "—"];
  return [row.beta_hat, row.eta_hat, row.gamma_hat];
}

function buildSampleSheet(sheet, n, distribution, sampleRows) {
  const lastColumn = n === 7 ? "H" : "P";
  const headers = ["样本", ...Array.from({ length: n }, (_, i) => `第${i + 1}顺序统计量`)];
  const rows = [];
  for (let sampleId = 1; sampleId <= 50; sampleId += 1) {
    const observations = sampleRows
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
    font: { name: "Arial", bold: true, color: COLORS.white, size: 11 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: "#B7C9D6" },
  };
  sheet.getRange(`A1:${lastColumn}1`).format.rowHeight = 26;
  sheet.getRange(`A2:${lastColumn}51`).values = rows;
  sheet.getRange("A2:A51").format = {
    fill: COLORS.light,
    font: { name: "Arial", bold: true, color: COLORS.text },
    horizontalAlignment: "center",
    numberFormat: "0",
  };
  sheet.getRange(`B2:${lastColumn}51`).format = {
    font: { name: "Arial", color: COLORS.text },
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

function buildResultBlock(sheet, n, offset, startRow, distribution, mdmByKey, otherByKey) {
  const titleRow = startRow;
  const groupRow = startRow + 2;
  const symbolRow = startRow + 3;
  const firstDataRow = startRow + 4;
  const lastDataRow = startRow + 53;
  const noteRow = startRow + 55;

  sheet.mergeCells(`A${titleRow}:P${titleRow}`);
  sheet.getRange(`A${titleRow}`).values = [[
    `${distribution} · n=${n} · 第1—50组估计结果 · MDM δ=${offset.toFixed(2)}`,
  ]];
  sheet.getRange(`A${titleRow}:P${titleRow}`).format = {
    fill: COLORS.title,
    font: { name: "Arial", bold: true, color: COLORS.white, size: 15 },
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
    font: { name: "Arial", bold: true, color: COLORS.white, size: 11 },
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
    font: { name: "Arial", bold: true, color: COLORS.text },
    horizontalAlignment: "center",
    numberFormat: "0",
  };
  sheet.getRange(`B${firstDataRow}:P${lastDataRow}`).format = {
    font: { name: "Arial", color: COLORS.text },
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
    font: { name: "Arial", italic: true, color: "#475569", size: 10 },
    horizontalAlignment: "left",
  };
}

async function buildCase(caseInfo) {
  const caseWorkDir = path.join(workDir, caseInfo.slug);
  const payload = JSON.parse(
    await fs.readFile(path.join(caseWorkDir, "workbook_data.json"), "utf8"),
  );
  const sampleRows = await readSamples(caseWorkDir);
  const distribution = payload.parameters.distribution;
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

  const workbook = Workbook.create();
  const sampleSheets = {
    7: workbook.worksheets.add("生成样本_n7"),
    15: workbook.worksheets.add("生成样本_n15"),
  };
  const resultSheets = {
    7: workbook.worksheets.add("估计结果_n7"),
    15: workbook.worksheets.add("估计结果_n15"),
  };

  for (const n of [7, 15]) {
    buildSampleSheet(sampleSheets[n], n, distribution, sampleRows);
    const sheet = resultSheets[n];
    sheet.showGridLines = false;
    buildResultBlock(sheet, n, 0.10, 1, distribution, mdmByKey, otherByKey);
    buildResultBlock(sheet, n, 0.15, 59, distribution, mdmByKey, otherByKey);
    buildResultBlock(sheet, n, 0.20, 117, distribution, mdmByKey, otherByKey);
    sheet.getRange("A1:A172").format.columnWidth = 9;
    sheet.getRange("B1:P172").format.columnWidth = 14;
    sheet.freezePanes.freezeColumns(1);
  }

  const inspections = [];
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
      inspections.push(inspection.ndjson);
    }
  }
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 100 },
    summary: "final formula error scan",
  });

  const qaDir = path.join(caseWorkDir, "qa");
  await fs.mkdir(qaDir, { recursive: true });
  await fs.writeFile(
    path.join(qaDir, "inspection.ndjson"),
    `${inspections.join("\n")}\n${errors.ndjson}\n`,
    "utf8",
  );
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
        path.join(qaDir, `${sheetName}_${index + 1}.png`),
        new Uint8Array(await preview.arrayBuffer()),
      );
    }
  }

  const deliveryDir = path.join(deliveryRoot, caseInfo.deliveryName);
  await fs.mkdir(deliveryDir, { recursive: true });
  const deliveryPath = path.join(deliveryDir, "估计结果表.xlsx");
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(deliveryPath);
  return {
    distribution,
    deliveryPath,
    sheets: ["生成样本_n7", "生成样本_n15", "估计结果_n7", "估计结果_n15"],
    errorScan: errors.ndjson,
  };
}

const results = [];
for (const caseInfo of cases) {
  results.push(await buildCase(caseInfo));
}
console.log(JSON.stringify(results, null, 2));
