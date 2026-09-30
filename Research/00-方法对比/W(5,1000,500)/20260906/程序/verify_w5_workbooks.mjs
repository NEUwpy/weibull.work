import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";


const workDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(workDir, "..", "..", "..", "..");
const deliveryRoot = path.join(
  repoRoot,
  "docs",
  "临时任务",
  "临时任务-W2-1000-3000-MDM偏移量估计-20260825",
  "260906-W5参数估计案例",
);
const cases = [
  { slug: "W5-1000-500", deliveryName: "W(5,1000,500)" },
  { slug: "W5-1000-3000", deliveryName: "W(5,1000,3000)" },
];
const selectedIds = [1, 17, 50];
const starts = new Map([[0.10, 5], [0.15, 63], [0.20, 121]]);

function closeEnough(actual, expected) {
  if (actual === "—" || expected === "—") return actual === expected;
  const scale = Math.max(1, Math.abs(Number(expected)));
  return Math.abs(Number(actual) - Number(expected)) <= 5e-10 * scale;
}

for (const caseInfo of cases) {
  const caseWorkDir = path.join(workDir, caseInfo.slug);
  const payload = JSON.parse(
    await fs.readFile(path.join(caseWorkDir, "workbook_data.json"), "utf8"),
  );
  const workbookPath = path.join(deliveryRoot, caseInfo.deliveryName, "估计结果表.xlsx");
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
  const sheetNames = workbook.worksheets.items.map((sheet) => sheet.name);
  const expectedSheets = ["生成样本_n7", "生成样本_n15", "估计结果_n7", "估计结果_n15"];
  if (JSON.stringify(sheetNames) !== JSON.stringify(expectedSheets)) {
    throw new Error(`${caseInfo.deliveryName}: unexpected sheets ${JSON.stringify(sheetNames)}`);
  }

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

  let checkedCells = 0;
  for (const n of [7, 15]) {
    const resultSheet = workbook.worksheets.getItem(`估计结果_n${n}`);
    for (const offset of [0.10, 0.15, 0.20]) {
      const firstRow = starts.get(offset);
      for (const sampleId of selectedIds) {
        const rowNumber = firstRow + sampleId - 1;
        const actual = resultSheet.getRange(`B${rowNumber}:P${rowNumber}`).values[0];
        const mdm = mdmByKey.get(`${n}|${sampleId}|${offset.toFixed(2)}`);
        const rows = [
          mdm,
          otherByKey.get(`${n}|${sampleId}|LS`),
          otherByKey.get(`${n}|${sampleId}|LRE`),
          otherByKey.get(`${n}|${sampleId}|WMLM`),
          otherByKey.get(`${n}|${sampleId}|MLM`),
        ];
        const expected = rows.flatMap((row) => (
          row?.converged === true
            ? [row.beta_hat, row.eta_hat, row.gamma_hat]
            : ["—", "—", "—"]
        ));
        for (let index = 0; index < expected.length; index += 1) {
          if (!closeEnough(actual[index], expected[index])) {
            throw new Error(
              `${caseInfo.deliveryName} n=${n} delta=${offset} sample=${sampleId} `
              + `column=${index + 2}: ${actual[index]} != ${expected[index]}`,
            );
          }
          checkedCells += 1;
        }
      }
    }
  }
  console.log(JSON.stringify({
    distribution: caseInfo.deliveryName,
    sheets: sheetNames,
    checkedResultCells: checkedCells,
    status: "ok",
  }));
}
