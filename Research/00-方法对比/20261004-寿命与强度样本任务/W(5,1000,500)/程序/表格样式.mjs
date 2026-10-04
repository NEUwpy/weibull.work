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
  return ["beta_hat", "eta_hat", "gamma_hat"].map(k => row?.[k] ?? "—");
}

function buildSampleSheet(sheet, n, distribution, sampleRows) {
  const lastColumn = n === 7 ? "H" : n === 15 ? "P" : "AE";
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

  sheet.mergeCells(`A${titleRow}:P${titleRow}`);
  sheet.getRange(`A${titleRow}`).values = [[
    `${distribution} · n=${n} · MDM δ=${offset.toFixed(2)}`,
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
  sheet.getRange(`E${groupRow}`).values = [["LSE"]];
  sheet.getRange(`H${groupRow}`).values = [["LRE"]];
  sheet.getRange(`K${groupRow}`).values = [["WMLE"]];
  sheet.getRange(`N${groupRow}`).values = [["MLE"]];
  sheet.getRange(`B${symbolRow}:P${symbolRow}`).values = [[
    "β", "η", "γ", "β", "η", "γ", "β", "η", "γ",
    "β", "η", "γ", "β", "η", "γ",
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
}

export {buildSampleSheet,buildResultBlock};
