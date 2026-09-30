import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const files = [
  "D:/weibull/docs/临时任务/临时任务-W2-1000-3000-MDM偏移量估计-20260825/260907-W3参数估计案例/W(3,1000,500)/3,1000,500.xlsx",
  "D:/weibull/docs/临时任务/临时任务-W2-1000-3000-MDM偏移量估计-20260825/260907-W3参数估计案例/W(3,1000,1000)/3,1000,1000.xlsx",
  "D:/weibull/docs/临时任务/临时任务-W2-1000-3000-MDM偏移量估计-20260825/260907-W3参数估计案例/W(3,1000,3000)/3,1000,3000.xlsx",
];

for (const file of files) {
  const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(file));
  const matches = await wb.inspect({
    kind: "match",
    searchTerm: "3\\.164177|1561\\.374420|119\\.079585|3\\.568228|991\\.799060|402\\.495884",
    options: { useRegex: true, maxResults: 100 },
    maxChars: 12000,
  });
  console.log(JSON.stringify({ file, matches: matches.ndjson }));
  if (file.includes("W(3,1000,500)")) {
    for (const [sheetId, range] of [
      ["估计结果_n7", "A1:P20"],
      ["生成样本_n7", "A10:H18"],
    ]) {
      const table = await wb.inspect({
        kind: "table",
        sheetId,
        range,
        include: "values,formulas",
        tableMaxRows: 30,
        tableMaxCols: 20,
        maxChars: 20000,
      });
      console.log(JSON.stringify({ file, sheetId, range, table: table.ndjson }));
    }
  }
}
