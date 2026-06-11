// ===========================================================================
// build_report.js — 生成《三参数威布尔分布 MDM 方法最优梯度偏移量 δ 研究报告》
// ===========================================================================
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel, BorderStyle,
  WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak, TableOfContents,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const D = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "report_data.json"), "utf8"));
const FIG = path.join(ROOT, "figures");
const CONTENT_W = 9360;
const FONT = "Microsoft YaHei";

const fmt = (x, d = 3) => (x === null || x === undefined) ? "—" :
  (typeof x !== "number" ? String(x) : x.toFixed(d));
const pct = (x, d = 1) => (x >= 0 ? "+" : "") + x.toFixed(d) + "%";

function P(text, opts = {}) {
  const runs = Array.isArray(text) ? text : [new TextRun({ text, ...(opts.run || {}) })];
  return new Paragraph({
    spacing: { after: opts.after ?? 140, line: 300, ...(opts.spacing || {}) },
    alignment: opts.align, indent: opts.indent, children: runs,
  });
}
const R = (text, o = {}) => new TextRun({ text, ...o });
const V = (text) => new TextRun({ text, italics: true });
const B = (text) => new TextRun({ text, bold: true });

function Formula(children) {
  return new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 120, after: 120, line: 320 },
    children: Array.isArray(children) ? children : [children],
  });
}
function Bullet(children, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 90, line: 290 },
    children: Array.isArray(children) ? children : [new TextRun(children)],
  });
}
function NumItem(children, ref = "nums") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 90, line: 290 },
    children: Array.isArray(children) ? children : [new TextRun(children)],
  });
}
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });

function pngSize(buf) { return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) }; }
function Figure(file, caption, widthPx = 600) {
  const data = fs.readFileSync(path.join(FIG, file));
  const dim = pngSize(data);
  const w = widthPx, h = Math.round((dim.h / dim.w) * w);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 160, after: 60 },
      children: [new ImageRun({ type: "png", data,
        transformation: { width: w, height: h },
        altText: { title: caption, description: caption, name: file } })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 220 },
      children: [new TextRun({ text: caption, italics: true, size: 19, color: "555555" })],
    }),
  ];
}
function makeTable(headers, rows, widths, opts = {}) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: "BFBFBF" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const headFill = opts.headFill ?? "2E5A88", headColor = opts.headColor ?? "FFFFFF";
  const zebra = opts.zebra ?? "EEF3F8";
  const headRow = new TableRow({ tableHeader: true,
    children: headers.map((h, i) => new TableCell({ borders,
      width: { size: widths[i], type: WidthType.DXA },
      shading: { fill: headFill, type: ShadingType.CLEAR },
      margins: { top: 70, bottom: 70, left: 90, right: 90 },
      verticalAlign: VerticalAlign.CENTER,
      children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0, line: 250 },
        children: [new TextRun({ text: h, bold: true, color: headColor, size: 19 })] })] })) });
  const bodyRows = rows.map((r, ri) => new TableRow({
    children: r.map((cell, ci) => {
      const isObj = cell && typeof cell === "object" && !Array.isArray(cell);
      const txt = isObj ? cell.text : cell;
      const bold = isObj ? !!cell.bold : false;
      const color = isObj ? cell.color : undefined;
      const fill = isObj && cell.fill ? cell.fill : (ri % 2 === 1 ? zebra : "FFFFFF");
      const align = isObj && cell.align ? cell.align : (ci === 0 ? AlignmentType.LEFT : AlignmentType.CENTER);
      return new TableCell({ borders, width: { size: widths[ci], type: WidthType.DXA },
        shading: { fill, type: ShadingType.CLEAR },
        margins: { top: 55, bottom: 55, left: 90, right: 90 },
        verticalAlign: VerticalAlign.CENTER,
        children: [new Paragraph({ alignment: align, spacing: { after: 0, line: 250 },
          children: [new TextRun({ text: String(txt), bold, color, size: 19 })] })] });
    }) }));
  return new Table({ width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths, rows: [headRow, ...bodyRows] });
}
function Callout(title, lines, fill = "FFF4E5", bar = "E08A1E") {
  const border = { style: BorderStyle.SINGLE, size: 1, color: fill };
  const left = { style: BorderStyle.SINGLE, size: 18, color: bar };
  const kids = [];
  if (title) kids.push(new Paragraph({ spacing: { after: 80, line: 280 },
    children: [new TextRun({ text: title, bold: true, size: 21, color: "333333" })] }));
  lines.forEach((ln, i) => kids.push(new Paragraph({
    spacing: { after: i === lines.length - 1 ? 0 : 70, line: 280 },
    children: Array.isArray(ln) ? ln : [new TextRun({ text: ln, size: 20, color: "333333" })] })));
  return new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
    rows: [new TableRow({ children: [new TableCell({
      borders: { top: border, bottom: border, right: border, left },
      width: { size: CONTENT_W, type: WidthType.DXA },
      shading: { fill, type: ShadingType.CLEAR },
      margins: { top: 110, bottom: 110, left: 200, right: 160 }, children: kids })] })] });
}
const spacer = (h = 80) => new Paragraph({ spacing: { after: h }, children: [] });
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

// ===========================================================================
const styles = {
  default: { document: { run: { font: FONT, size: 22 } } },
  paragraphStyles: [
    { id: "Title", name: "Title", basedOn: "Normal", next: "Normal",
      run: { size: 48, bold: true, font: FONT, color: "1A1A1A" },
      paragraph: { spacing: { after: 120 }, alignment: AlignmentType.CENTER } },
    { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { size: 32, bold: true, font: FONT, color: "1B3A5C" },
      paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0,
        border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: "2E5A88", space: 6 } } } },
    { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { size: 26, bold: true, font: FONT, color: "23527C" },
      paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 1 } },
    { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { size: 23, bold: true, font: FONT, color: "2E5A88" },
      paragraph: { spacing: { before: 160, after: 90 }, outlineLevel: 2 } },
  ],
};
const numbering = { config: [
  { reference: "bullets", levels: [
    { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 620, hanging: 300 } } } },
    { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 1120, hanging: 300 } } } } ] },
  { reference: "nums", levels: [
    { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 620, hanging: 320 } } } } ] },
  { reference: "nums2", levels: [
    { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 620, hanging: 320 } } } } ] },
] };

// content 数组在 sections/*.js 之外，这里直接内联
const children = [];
require("./report_content.js")({
  children, D, fmt, pct, P, R, V, B, Formula, Bullet, NumItem, H1, H2, H3,
  Figure, makeTable, Callout, spacer, pageBreak,
  TextRun, Paragraph, AlignmentType, TableOfContents, PageBreak,
});

const doc = new Document({
  styles, numbering,
  sections: [{
    properties: { page: {
      size: { width: 12240, height: 15840 },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
    } },
    headers: { default: new Header({ children: [ new Paragraph({
      alignment: AlignmentType.RIGHT, spacing: { after: 0 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF", space: 4 } },
      children: [new TextRun({ text: "三参数威布尔分布 MDM 方法最优梯度偏移量 δ 研究", size: 16, color: "888888" })],
    }) ] }) },
    footers: { default: new Footer({ children: [ new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 0 },
      children: [ new TextRun({ text: "第 ", size: 18, color: "888888" }),
        new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "888888" }),
        new TextRun({ text: " 页 / 共 ", size: 18, color: "888888" }),
        new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: "888888" }),
        new TextRun({ text: " 页", size: 18, color: "888888" }) ],
    }) ] }) },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(ROOT, "MDM最优偏移量研究报告.docx");
  fs.writeFileSync(out, buf);
  console.log("WROTE", out, (buf.length / 1024).toFixed(0) + "KB");
});
