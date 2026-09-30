import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const workDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../结果/复算输出");
const deliveryDir = path.join(workDir, "交付");
const filename = "W(2,1000,3000)_n7_200组排序样本_种子20260826.xlsx";
const outputPath = path.join(workDir, filename);
const deliveryPath = path.join(deliveryDir, filename);

const payload = JSON.parse(await fs.readFile(path.join(workDir, "samples_200.json"), "utf8"));
if (payload.rows.length !== 200 || payload.rows.some((row) => row.length !== 9)) {
  throw new Error("Expected exactly 200 rows and 9 columns");
}

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("200组排序样本");
sheet.showGridLines = false;

sheet.getRange("A1:I201").values = [payload.headers, ...payload.rows];
sheet.getRange("A1:I1").format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF", size: 11 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: "#163A5C" },
};
sheet.getRange("A1:I1").format.rowHeight = 26;
sheet.getRange("A2:B201").format = {
  fill: "#EAF2F8",
  horizontalAlignment: "center",
  numberFormat: "0",
};
sheet.getRange("C2:I201").format = {
  horizontalAlignment: "right",
  numberFormat: "0.000000",
};
sheet.getRange("A2:I201").format.borders = {
  insideHorizontal: { style: "thin", color: "#E5E7EB" },
  bottom: { style: "thin", color: "#CBD5E1" },
};
sheet.getRange("A1:A201").format.columnWidth = 10;
sheet.getRange("B1:B201").format.columnWidth = 11;
sheet.getRange("C1:I201").format.columnWidth = 14;
sheet.getRange("J1:J9").format.columnWidth = 3;
sheet.getRange("K1:K9").format.columnWidth = 17;
sheet.getRange("L1:L9").format.columnWidth = 38;

const metadata = [
  ["生成参数", "取值"],
  ["分布", payload.parameters.distribution],
  ["形状参数 β", payload.parameters.beta],
  ["尺度参数 η", payload.parameters.eta],
  ["位置参数 γ", payload.parameters.gamma],
  ["样本量 n", payload.parameters.sample_size],
  ["样本组数", payload.parameters.groups],
  ["随机种子命名空间", payload.parameters.seed_namespace],
  ["数据说明", "每行均按从小到大排序；x_(1)为最小值，x_(7)为最大值。"],
];
sheet.getRange("K1:L9").values = metadata;
sheet.getRange("K1:L1").format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
};
sheet.getRange("K2:K9").format = {
  fill: "#D9EAF7",
  font: { bold: true, color: "#1F2937" },
};
sheet.getRange("K1:L9").format.borders = {
  preset: "outside",
  style: "thin",
  color: "#9CA3AF",
};
sheet.getRange("L2:L9").format.wrapText = true;
sheet.getRange("K9:L9").format.rowHeight = 34;

const table = sheet.tables.add("A1:I201", true, "SortedSamples200");
table.style = "TableStyleMedium2";
table.showFilterButton = true;

sheet.freezePanes.freezeRows(1);
sheet.freezePanes.freezeColumns(2);

const firstRows = await workbook.inspect({
  kind: "table",
  range: "200组排序样本!A1:I6",
  include: "values,formulas",
  tableMaxRows: 6,
  tableMaxCols: 9,
  maxChars: 8000,
});
const lastRows = await workbook.inspect({
  kind: "table",
  range: "200组排序样本!A197:I201",
  include: "values,formulas",
  tableMaxRows: 5,
  tableMaxCols: 9,
  maxChars: 8000,
});
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(firstRows.ndjson);
console.log(lastRows.ndjson);
console.log(errors.ndjson);

const topPreview = await workbook.render({
  sheetName: "200组排序样本",
  range: "A1:L25",
  scale: 1.4,
  format: "png",
});
await fs.writeFile(
  path.join(workDir, "preview_top.png"),
  new Uint8Array(await topPreview.arrayBuffer()),
);
const bottomPreview = await workbook.render({
  sheetName: "200组排序样本",
  range: "A180:I201",
  scale: 1.4,
  format: "png",
});
await fs.writeFile(
  path.join(workDir, "preview_bottom.png"),
  new Uint8Array(await bottomPreview.arrayBuffer()),
);

await fs.mkdir(deliveryDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
await fs.copyFile(outputPath, deliveryPath);
console.log(JSON.stringify({ outputPath, deliveryPath }, null, 2));
