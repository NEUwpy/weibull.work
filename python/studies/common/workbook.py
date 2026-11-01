"""Read archived Research00 numeric workbooks without executing formulas.

The original XLSX remains the export. This reader only builds a view model;
it never rewrites cells, styles, missing values, or historical estimates.
"""
from __future__ import annotations

import hashlib
import io
import math
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

MAX_WORKBOOK_BYTES = 12 * 1024 * 1024
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ALIASES = {"LS": "lse", "LSE": "lse", "LRE": "lre", "WMLM": "wmle", "WMLE": "wmle", "MLM": "mle", "MLE": "mle", "MMLE": "mmle"}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _position(address):
    match = re.fullmatch(r"([A-Z]+)([1-9]\d*)", address)
    if not match:
        raise ValueError("工作表包含无效的单元格地址。")
    col = 0
    for letter in match[1]:
        col = col * 26 + ord(letter) - 64
    row = int(match[2])
    if row > 10000 or col > 501:
        raise ValueError("工作表超出可读取范围。")
    return row - 1, col - 1


def _read_sheets(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        entries = package.infolist()
        if len(entries) > 3000 or sum(i.file_size for i in entries) > 64 * 1024 * 1024:
            raise ValueError("工作簿展开后过大。")
        names = set(package.namelist())
        strings = []
        if "xl/sharedStrings.xml" in names:
            strings = ["".join(t.text or "" for t in item.iter(f"{{{NS}}}t")) for item in ET.fromstring(package.read("xl/sharedStrings.xml"))]
        formats = {0: "General", 1: "0", 2: "0.00", 3: "#,##0", 4: "#,##0.00"}
        cell_formats = ["General"]
        if "xl/styles.xml" in names:
            style = ET.fromstring(package.read("xl/styles.xml"))
            for node in style.findall(f"{{{NS}}}numFmts/{{{NS}}}numFmt"):
                formats[int(node.attrib["numFmtId"])] = node.attrib["formatCode"]
            xfs = style.find(f"{{{NS}}}cellXfs")
            if xfs is not None:
                cell_formats = [formats.get(int(x.attrib.get("numFmtId", 0)), "General") for x in xfs]
        book = ET.fromstring(package.read("xl/workbook.xml"))
        rels = {r.attrib["Id"]: r for r in ET.fromstring(package.read("xl/_rels/workbook.xml.rels"))}
        sheets = []
        total_cells = 0
        for item in book.findall(f"{{{NS}}}sheets/{{{NS}}}sheet"):
            rel = rels[item.attrib[f"{{{REL}}}id"]]
            if rel.attrib.get("TargetMode") == "External":
                raise ValueError("不读取外部工作表链接。")
            target = rel.attrib["Target"]
            target = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
            if not target.startswith("xl/worksheets/"):
                raise ValueError("工作表路径无效。")
            xml = ET.fromstring(package.read(target))
            cells = {}
            for cell in xml.findall(f"{{{NS}}}sheetData/{{{NS}}}row/{{{NS}}}c"):
                r, c = _position(cell.attrib["r"])
                if cell.find(f"{{{NS}}}f") is not None:
                    raise ValueError("当前读取数值结果表，不执行Excel公式。请先提供已保存的数值结果。")
                value = cell.findtext(f"{{{NS}}}v")
                kind = cell.attrib.get("t")
                if kind == "inlineStr":
                    value = "".join(t.text or "" for t in cell.iter(f"{{{NS}}}t"))
                elif kind == "s":
                    value = strings[int(value)] if value is not None else None
                elif kind == "b":
                    value = value == "1"
                elif kind not in {"str", "e"} and value is not None:
                    value = float(value)
                    if not math.isfinite(value):
                        raise ValueError("工作簿含非有限数值。")
                    if value.is_integer() and abs(value) < 2 ** 53:
                        value = int(value)
                style_index = int(cell.attrib.get("s", 0))
                cells[r, c] = (value, cell_formats[style_index])
            merges = []
            for merge in xml.findall(f"{{{NS}}}mergeCells/{{{NS}}}mergeCell"):
                start, end = merge.attrib["ref"].split(":")
                merges.append([*_position(start), *_position(end)])
            height = max((r for r, _ in cells), default=0) + 1
            width = max((c for _, c in cells), default=0) + 1
            for r, c, rr, cc in merges:
                height, width = max(height, rr + 1), max(width, cc + 1)
            total_cells += height * width
            if total_cells > 250000 or len(sheets) >= 50:
                raise ValueError("工作簿超出可读取范围。")
            rows = [[cells.get((r, c), (None, "General"))[0] for c in range(width)] for r in range(height)]
            fmts = [[cells.get((r, c), (None, "General"))[1] for c in range(width)] for r in range(height)]
            sheets.append(dict(name=item.attrib["name"], rows=rows, formats=fmts, merges=merges))
        return sheets


def parse_workbook(raw: bytes, filename: str, source=None):
    if not raw or len(raw) > MAX_WORKBOOK_BYTES:
        raise ValueError("请选择小于12MB的xlsx结果表。")
    filename = filename.replace("\\", "/").split("/")[-1]
    if not filename.lower().endswith(".xlsx"):
        raise ValueError("请选择xlsx工作簿。")
    try:
        sheets = _read_sheets(raw)
        pairs = {}
        for sheet in sheets:
            match = re.fullmatch(r"(生成样本|估计结果)_n(\d+)", sheet["name"])
            if match:
                pairs.setdefault(int(match[2]), {})["samples" if match[1] == "生成样本" else "results"] = sheet
        if not pairs or any(set(p) != {"samples", "results"} for p in pairs.values()):
            raise ValueError("需要成对的“生成样本_n…”和“估计结果_n…”工作表。")
        groups = {}
        for n, pair in sorted(pairs.items()):
            samples, results = pair["samples"]["rows"], pair["results"]["rows"]
            if samples[0][0] != "样本" or len(samples[0]) != n + 1 or results[0][0] != "样本" or len(results) < 3:
                raise ValueError("工作表表头与Research00结果表不一致。")
            samples = [row for row in samples[1:] if any(v is not None for v in row)]
            ids = [row[0] for row in samples]
            if len(set(ids)) != len(ids) or any(not _number(row[0]) or not all(_number(v) for v in row[1:]) for row in samples):
                raise ValueError("样本编号重复或观测值不完整。")
            blocks = []
            for c in range(1, len(results[0]), 3):
                label = str(results[0][c] or "")
                delta = None
                if label.upper().startswith("MDM"):
                    match = re.search(r"[δΔ=\s]+([0-9]+(?:\.[0-9]+)?)", label)
                    if not match:
                        raise ValueError("MDM表头缺少偏移量。")
                    method, delta = "mdm", float(match[1])
                else:
                    method = ALIASES.get(label.upper())
                if not method or results[1][c:c + 3] not in [["α", "β", "γ"], ["β", "η", "γ"]]:
                    raise ValueError("估计方法或三参数列顺序无法识别。")
                blocks.append(dict(method=method, delta=delta, label=label, column=c, parameterLabels=results[1][c:c+3]))
            result_rows = [row for row in results[2:] if any(v is not None for v in row)]
            if len(result_rows) != len(ids) or {r[0] for r in result_rows} != set(ids):
                raise ValueError("样本与估计记录不能一一对应。")
            groups[str(n)] = dict(samples=samples, resultRows=result_rows, blocks=blocks, sampleSheet=pair["samples"]["name"], resultSheet=pair["results"]["name"])
        truth = re.search(r"W\(?([\d.]+),([\d.]+),([\d.]+)\)?", filename)
        sha = hashlib.sha256(raw).hexdigest()
        return dict(schemaVersion=1, id="excel-" + sha[:20], filename=filename, title=filename[:-5], truth=[float(v) for v in truth.groups()] if truth else None, sha256=sha, groups=groups, sheets=sheets, source=source or dict(kind="imported", calculationTime=None, codeVersion=None))
    except (zipfile.BadZipFile, ET.ParseError, KeyError, IndexError, TypeError, OverflowError) as exc:
        raise ValueError("无法读取该工作簿，请选择Research00格式的数值结果表。") from exc
