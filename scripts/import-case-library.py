#!/usr/bin/env python3
"""Extract selected literature tables and figure references into case records."""

import argparse
from bisect import bisect_right
from collections import Counter
import hashlib
import html
from html.parser import HTMLParser
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import unquote, urlsplit


GENERATOR = "import-case-library-v1"
TABLE = re.compile(r"<table\b[^>]*>.*?</table\s*>", re.I | re.S)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)")
CAPTION = re.compile(r"^(?:#{1,6}\s*)?(?:(?:Table|Tab\.?|Figure|Fig\.?)\s*\d+[A-Za-z]?(?:[.．:：\s].*)?|[表图]\s*[A-Za-z]?\d+.*)$", re.I)
FIGURE_CAPTION = re.compile(r"^(?:#{1,6}\s*)?(?:(?:Figure|Fig\.?)\s*\d+[A-Za-z]?(?:[.．:：\s].*)?|图\s*[A-Za-z]?\d+.*)$", re.I)
URL = re.compile(r"https?://[^\s<>\"{}|\\]+", re.I)
DATA_LINK = re.compile(r"dataset|data\s+availab|data\s+(?:are|is|can|set|repository)|supplement|数据|资料|zenodo|figshare|kaggle|archive\.ics\.uci|osf\.io|dataverse|dryad", re.I)
SECONDARY = re.compile(r"(?:data|dataset|sample|数据|样本).{0,70}(?:taken|from|reported|given|cited|provided|引用|转引|引自|来自|来源|取自)", re.I)
NUMBER = r"[+-]?(?:\d+\.\d+|\.\d+|\d+)(?:[eE][+-]?\d+)?"
SEQUENCE = re.compile(r"(?<![\w.])" + NUMBER + r"(?:(?:\s|[,;，；])+(?:" + NUMBER + r")){5,}(?![\w.])")
SAMPLE_WORDS = re.compile(r"\bsamples?\b|\bdatasets?\b|\bdata\b|\bvalues?\b|observations?|failure\s+times?|样本|数据|观测|寿命|失效", re.I)
FORMULA_WORDS = re.compile(r"\\(?:frac|sum|prod|int|sqrt|Gamma|log|exp|alpha|beta|gamma|mu|sigma|eta|theta|partial|operatorname)\b")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for attempt in range(15):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 14:
                raise
            time.sleep(.025)


class Cells(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"}:
            self.cell = []
        elif tag == "br" and self.cell is not None:
            self.cell.append("\n")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            if self.row is not None:
                self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def plain(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def label_key(label):
    label = re.sub(r"\s+", "", label).lower()
    return re.sub(r"^(?:table|tab\.?|表)", "table", re.sub(r"^(?:figure|fig\.?|图)", "figure", label))


@lru_cache(maxsize=4)
def labeled_paragraphs(document):
    result = {}
    pattern = re.compile(r"(?:Table|Tab\.?|Figure|Fig\.?)\s*\d+(?:\.\d+)*[A-Za-z]?|[表图]\s*\d+(?:\.\d+)*", re.I)
    for paragraph in re.split(r"\n\s*\n", document):
        for label in {label_key(match.group()) for match in pattern.finditer(paragraph)}:
            result.setdefault(label, []).append(paragraph)
    return result


def source_for(paper_id, location, context, document=None):
    source = {"paper_id": paper_id, "location": location, "relation": "direct"}
    label = re.match(r"((?:Table|Tab\.?|Figure|Fig\.?)\s*\d+(?:\.\d+)*[A-Za-z]?|[表图]\s*\d+(?:\.\d+)*)", location, re.I)
    paragraphs = re.split(r"\n\s*\n", context)
    if label and document:
        paragraphs = labeled_paragraphs(document).get(label_key(label.group(1)), [])
    clues = []
    for paragraph in paragraphs:
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\u3400-\u9fff])|\n", paragraph)
        anchored = not label
        for sentence in sentences:
            if label:
                labels = re.findall(r"(?:Table|Tab\.?|Figure|Fig\.?)\s*\d+(?:\.\d+)*[A-Za-z]?|[表图]\s*\d+(?:\.\d+)*", sentence, re.I)
                if labels:
                    anchored = label_key(label.group(1)) in {label_key(value) for value in labels}
                if not anchored:
                    continue
            credit = re.search(r"\bfrom\b.{0,100}(?:\b(?:19|20)\d{2}\b|\[\s*\d)", sentence, re.I)
            laboratory = re.search(r"(?:voltages?|data|test\s+pieces).{0,200}(?:tested|laboratory).{0,100}\[\s*\d", sentence, re.I)
            if (SECONDARY.search(sentence) or credit or laboratory) and re.search(r"\[\s*\d|\b(?:19|20)\d{2}\b|et\s+al|等", sentence, re.I):
                clues.append(plain(sentence))
    clues = list(dict.fromkeys(clues))
    if clues:
        source["relation"] = "secondary"
        references = []
        for number in re.findall(r"\[\s*(\d+)\s*\]", " ".join(clues)):
            found = re.search(r"^\s*\[\s*" + number + r"\s*\][^\n]*(?:\n(?!\s*\n|\s*\[\s*\d)[^\n]*)*", document or "", re.M)
            if found:
                references.append(plain(found.group()))
        source["original_reference"] = " ".join([*clues, *dict.fromkeys(references)])[:1800]
    return source


def caption_near(text, start, end, pattern=CAPTION, distance=800):
    before = text[max(0, start - distance):start].splitlines()
    after = text[end:min(len(text), end + distance)].splitlines()
    for line in reversed(before[-8:]):
        if pattern.match(line.strip()):
            return plain(line.lstrip("# "))
    for line in after[:10]:
        if pattern.match(line.strip()):
            return plain(line.lstrip("# "))
    return None


def table_blocks(text):
    blocks = [(match.start(), match.end(), match.group(), "html") for match in TABLE.finditer(text)]
    lines = text.splitlines(keepends=True)
    offsets = []
    position = 0
    for line in lines:
        offsets.append(position)
        position += len(line)
    index = 0
    fenced = False
    while index < len(lines) - 1:
        line = lines[index]
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
        separator = lines[index + 1].strip()
        if not fenced and "|" in line and re.fullmatch(r"\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?", separator):
            last = index + 2
            while last < len(lines) and "|" in lines[last] and lines[last].strip():
                last += 1
            start = offsets[index]
            end = offsets[last] if last < len(lines) else len(text)
            if not any(a <= start < b for a, b, _, _ in blocks):
                blocks.append((start, end, "".join(lines[index:last]), "markdown"))
            index = last
            continue
        index += 1
    return sorted(blocks)


def markdown_table(markup):
    lines = markup.strip().splitlines()
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in [lines[0], *lines[2:]]]
    result = "<table>" + "".join("<tr>" + "".join("<td>" + html.escape(cell) + "</td>" for cell in row) + "</tr>" for row in rows) + "</table>"
    return rows, result


def figure_asset(directory, paper_id, value):
    relative = unquote(value)
    if relative.startswith("./"):
        relative = relative[2:]
    prefix = paper_id + "-图片/"
    if relative.startswith(prefix):
        candidates = [relative]
    elif relative.startswith("images/"):
        candidates = [prefix + relative, prefix + relative[len("images/"):]]
    else:
        candidates = [relative]
    matches = [candidate for candidate in candidates if (directory / candidate).is_file()]
    return (matches[0] if len(matches) == 1 else value), len(matches)


def grouped_figure_caption(text, images, index):
    first = last = index
    panel_gap = re.compile(r"^[\s()（）a-zA-Z0-9.,_\-\\]*$")

    def same_panel_group(left, right):
        gap = text[images[left].end():images[right].start()]
        return len(gap.strip()) <= 80 and not any(CAPTION.match(line.strip()) for line in gap.splitlines()) and panel_gap.fullmatch(gap)

    while first > 0 and same_panel_group(first - 1, first):
        first -= 1
    while last + 1 < len(images) and same_panel_group(last, last + 1):
        last += 1
    before = [line.strip() for line in text[max(0, images[first].start() - 1500):images[first].start()].splitlines() if line.strip()]
    after = [line.strip() for line in text[images[last].end():images[last].end() + 1500].splitlines() if line.strip()]
    previous = before[-1] if before and FIGURE_CAPTION.match(before[-1]) else None
    following = after[0] if after and FIGURE_CAPTION.match(after[0]) else None
    if previous and following and previous != following:
        return None
    return plain((following or previous).lstrip("# ")) if following or previous else None


def text_sequences(text, blocks):
    excluded = [(start, end) for start, end, _, _ in blocks]
    excluded.extend((match.start(), match.end()) for match in re.finditer(r"^\s*(```|~~~).*?^\s*\1[^\n]*$", text, re.M | re.S))
    frontmatter = re.match(r"\A---\s*\n.*?\n---\s*(?:\n|$)", text, re.S)
    if frontmatter:
        excluded.append((0, frontmatter.end()))
    headings = [(match.start(), match.group(1)) for match in re.finditer(r"^#{1,6}\s+([^\n]+)", text, re.M)]
    positions = [position for position, _ in headings]
    candidates = []
    for match in re.finditer(r"\S[^\n]*(?:\n(?!\s*\n)[^\n]*)*", text):
        start, end = match.span()
        if any(a < end and start < b for a, b in excluded):
            continue
        heading_index = bisect_right(positions, start) - 1
        if heading_index >= 0 and re.search(r"references|bibliography|参考文献|\bindex\b|索引", headings[heading_index][1], re.I):
            continue
        paragraph = match.group()
        if "![" in paragraph or "http" in paragraph or "text_image" in paragraph or FORMULA_WORDS.search(paragraph):
            continue
        runs = list(SEQUENCE.finditer(paragraph))
        if not runs:
            continue
        longest = max(runs, key=lambda value: len(value.group()))
        values = re.findall(NUMBER, longest.group())
        context = text[max(0, start - 450):end]
        if re.search(r"(?:\bn\b|\br\b)\s*(?:=|\\in)|\b(?:sample\s+sizes?|design\s+values?|color\s*bar|stress\s+contour)\b|应力云图|色标", paragraph, re.I):
            continue
        if len(set(values)) < max(3, len(values) // 4):
            continue
        remainder = SEQUENCE.sub("", paragraph)
        pure = not re.search(r"[A-Za-z\u3400-\u9fff]", remainder) and len(values) >= 10
        if not pure and not SAMPLE_WORDS.search(context):
            continue
        if len(longest.group()) < len(paragraph) * .25:
            continue
        candidates.append((start, paragraph, values, plain(context)))
    return candidates


def table_nature(location, context, rows):
    summary = re.compile(r"\bbias\b|\b(?:rmse|mse|mae|mape)\b|estimat|\berrors?\b|performance|comparison|efficien|confidence|standard\s+deviation|coverage\s+probability|估计|误差|偏差|均方|比较|性能|覆盖率|置信", re.I)
    raw = re.compile(r"failure\s+(?:times?|data)|breakdown\s+voltage\s+data|lifetime\s+data|raw\s+data|sample\s+(?:data|values)|observations|原始数据|试验数据|样本数据|寿命数据|失效时间|击穿电压", re.I)
    headers = " ".join(" ".join(row) for row in rows[:2])
    if summary.search(location) or re.search(r"\b(?:bias|rmse|mse|mae|mape)\b|均方|偏差|误差", headers, re.I):
        kind, observation = "result", "summary"
        note = "按表题或统计指标识别为结果汇总，保留原表；仍待对照原论文核查。"
    elif raw.search(location):
        if re.search(r"simulat|generat|random\s+sample|模拟|生成|随机抽样", location + " " + context, re.I):
            kind = "simulated"
        elif re.search(r"real\s+data|observed|experiment|test\s+pieces|tested|failure\s+of|breakdown\s+voltage|实测|试验|实验|失效时间", location + " " + context, re.I):
            kind = "observed"
        else:
            kind = "unknown"
        observation = "unknown"
        if re.search(r"right[-\s]censor|右删失", location + " " + context, re.I):
            observation = "right_censored"
        elif re.search(r"interval[-\s]censor|区间删失", location + " " + context, re.I):
            observation = "interval_censored"
        elif re.search(r"grouped\s+(?:data|sample)|分组数据|频数数据", location + " " + context, re.I):
            observation = "grouped"
        elif re.search(r"complete\s+(?:data|sample)|uncensored|完全样本|完整样本|无删失", location + " " + context, re.I):
            observation = "complete"
        note = "按表题定位样本数据，保留原始表格；样本性质与观测规则仍待据原论文核实。"
    else:
        kind, observation = "unknown", "unknown"
        note = "现稿表格逐格提取；数据性质和观测规则尚待据表题、上下文及原论文确认。"
    return {"kind": kind, "observation": observation, "note": note}


def build_records(paper_id, text, root):
    records = []
    issues = []
    blocks = table_blocks(text)
    for number, (start, end, markup, style) in enumerate(blocks, 1):
        location = caption_near(text, start, end) or f"原文第 {text.count(chr(10), 0, start) + 1} 行，表格 {number}"
        if style == "html":
            parser = Cells()
            parser.feed(markup)
            rows, rendered = parser.rows, markup
        else:
            rows, rendered = markdown_table(markup)
        if not rows:
            issues.append({"kind": "table_parse", "location": location, "detail": "表格未提取到单元格"})
            continue
        ident = f"{paper_id}-table-{number:03}"
        context = text[max(0, start - 900):start] + "\n" + text[end:end + 400]
        data = {"kind": "table", "rows": rows, "html": rendered}
        if style == "markdown":
            data["markdown"] = markup
        records.append({"id": ident, "name": location, "data": data,
                        "nature": table_nature(location, context, rows),
                        "sources": [source_for(paper_id, location, context, text)]})
        if "\ufffd" in markup:
            issues.append({"kind": "ocr", "record_id": ident, "detail": "表格含 Unicode 替换字符，需据 PDF 校核"})
    raw_tables = len(re.findall(r"<table\b", text, re.I))
    if raw_tables != sum(style == "html" for _, _, _, style in blocks):
        issues.append({"kind": "table_markup", "detail": f"检测到 {raw_tables} 个 HTML 表格起始标记，完整闭合表格 {sum(style == 'html' for _, _, _, style in blocks)} 个"})

    sequences = text_sequences(text, blocks)
    for number, (start, paragraph, values, context) in enumerate(sequences, 1):
        ident = f"{paper_id}-text-{number:03}"
        location = f"原文第 {text.count(chr(10), 0, start) + 1} 行，数值段"
        records.append({"id": ident, "name": location + "（候选）",
                        "data": {"kind": "table", "rows": [[paragraph]],
                                 "html": "<table><tr><th>原文数值段（候选）</th></tr><tr><td><pre>" + html.escape(paragraph) + "</pre></td></tr></table>",
                                 "source_text": paragraph, "context": context},
                        "nature": {"kind": "unknown", "observation": "unknown", "note": "按连续数值及样本/数据上下文定位，尚待确认样本含义、单位与观测规则。"},
                        "sources": [source_for(paper_id, location, context, text)]})
    if sequences:
        issues.append({"kind": "text_sequence_review", "detail": "已保留原文数值段候选，需据上下文及 PDF 确认性质；尚未转成可计算样本", "record_ids": [f"{paper_id}-text-{number:03}" for number in range(1, len(sequences) + 1)]})

    figure_count = 0
    unmatched = []
    seen_assets = set()
    images = list(IMAGE.finditer(text))
    for image_index, match in enumerate(images):
        target = match.group(2).strip().split(' "', 1)[0].strip("<>")
        if target in seen_assets:
            continue
        seen_assets.add(target)
        caption = grouped_figure_caption(text, images, image_index)
        if not caption and FIGURE_CAPTION.match(match.group(1).strip()):
            caption = match.group(1).strip()
        if not caption:
            unmatched.append({"line": text.count("\n", 0, match.start()) + 1, "asset": target})
            continue
        if urlsplit(target).scheme:
            unmatched.append({"line": text.count("\n", 0, match.start()) + 1, "asset": target, "reason": "远程图片需单独核对"})
            continue
        figure_count += 1
        ident = f"{paper_id}-figure-{figure_count:03}"
        context = text[max(0, match.start() - 600):match.start()] + "\n" + text[match.end():match.end() + 600]
        asset, matches = figure_asset(root, paper_id, target)
        records.append({"id": ident, "name": caption, "data": {"kind": "figure", "asset": asset, "caption": caption},
                        "nature": {"kind": "unknown", "observation": "summary", "note": "原文数据图定位；原始数值和图像性质待核查。"},
                        "sources": [source_for(paper_id, caption, context, text)]})
        if not matches:
            issues.append({"kind": "missing_asset", "record_id": ident, "asset": target})
        elif matches > 1:
            issues.append({"kind": "ambiguous_asset", "record_id": ident, "asset": target})
    if unmatched:
        issues.append({"kind": "unclassified_images", "detail": "以下图片未能自动关联图题，需辨识数据图、示意图或公式", "items": unmatched})

    links = []
    for match in URL.finditer(text):
        link = match.group().rstrip(".,;:)）。，；")
        before = re.split(r"\r?\n\s*\r?\n", text[max(0, match.start() - 500):match.start()])[-1]
        after = re.split(r"\r?\n\s*\r?\n", text[match.end():match.end() + 500])[0]
        context = before + match.group() + after
        if link in links or not DATA_LINK.search(context):
            continue
        host = urlsplit(link).hostname or ""
        if "." not in host or host.endswith("."):
            issues.append({"kind": "link_ocr", "line": text.count("\n", 0, match.start()) + 1, "detail": "原文链接疑似断裂，待核对", "url": link})
            continue
        if host == "creativecommons.org" or host.endswith(".creativecommons.org"):
            continue
        if host in {"doi.org", "dx.doi.org"} and not re.search(r"data\s+availab|data(?:sets?)?\s+(?:are|is|can|availab)|deposited|repository|数据可|数据集可", context, re.I):
            continue
        links.append(link)
        line = text.count("\n", 0, match.start()) + 1
        location = f"原文第 {line} 行，数据或补充材料链接"
        records.append({"id": f"{paper_id}-external-{len(links):03}", "name": f"数据或补充材料 · {host}",
                        "data": {"kind": "external", "url": link, "description": plain(context)},
                        "nature": {"kind": "unknown", "observation": "external", "note": "按原文链接定位，链接内容与数据适用性待核查。"},
                        "sources": [source_for(paper_id, location, context)]})
    return records, issues, {"html_tables": raw_tables, "markdown_tables": sum(style == "markdown" for _, _, _, style in blocks), "text_sequences": len(sequences), "confirmed_text_sequences": 0, "image_references": len(list(IMAGE.finditer(text))), "unclassified_images": len(unmatched)}


def save_record(directory, record, source_hash):
    path = directory / (record["id"] + ".json")
    record_hash = digest(canonical(record))
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8-sig"))
        metadata = old.pop("_import", {})
        if metadata.get("generator") != GENERATOR or metadata.get("record_sha256") != digest(canonical(old)):
            return "preserved_manual"
        if metadata.get("record_sha256") == record_hash and metadata.get("source_sha256") == source_hash:
            return "unchanged"
    record["_import"] = {"generator": GENERATOR, "record_sha256": record_hash, "source_sha256": source_hash}
    atomic_json(path, record)
    return "written"


def material_identity(record):
    data = record.get("data", {})
    if not isinstance(data, dict):
        return digest(canonical(data))
    value = data.get("source_text") or data.get("markdown") or data.get("html") or data.get("asset") or data.get("url")
    return digest(canonical([data.get("kind"), value]))


def stabilize_ids(args, paper_id, records, source_hash):
    previous = {}
    by_identity = {}
    for file in (args.cases / "records").glob(paper_id + "-*.json"):
        if not re.fullmatch(re.escape(paper_id) + r"-(?:table|figure|text|external)-\d+", file.stem):
            continue
        old = json.loads(file.read_text(encoding="utf-8-sig"))
        previous[old["id"]] = (file, old)
        by_identity.setdefault(material_identity(old), []).append(old["id"])
    assigned = set()
    issues = []
    for record in records:
        matches = [ident for ident in by_identity.get(material_identity(record), []) if ident not in assigned]
        if matches:
            same_location = [ident for ident in matches if previous[ident][1].get("sources") == record.get("sources")]
            record["id"] = (same_location or matches)[0]
        elif record["id"] in previous or record["id"] in assigned:
            prefix = record["id"].rsplit("-", 1)[0]
            number = 1
            while f"{prefix}-{number:03}" in previous or f"{prefix}-{number:03}" in assigned:
                number += 1
            record["id"] = f"{prefix}-{number:03}"
        assigned.add(record["id"])
    if args.apply:
        for ident, (file, old) in previous.items():
            if ident in assigned:
                continue
            metadata = old.get("_import", {})
            payload = {key: value for key, value in old.items() if key != "_import"}
            untouched = metadata.get("generator") == GENERATOR and metadata.get("record_sha256") == digest(canonical(payload))
            if untouched and metadata.get("source_sha256") == source_hash:
                destination = args.cases / "superseded" / (file.stem + "-" + digest(file.read_bytes())[:12] + ".json")
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(file, destination)
            else:
                issues.append({"kind": "retained_previous_record", "record_id": ident, "detail": "旧条目已人工修订或源身份变化，保留原件待核对对应关系"})
    return issues


def write_index(cases):
    records = []
    for file in sorted((cases / "records").glob("*.json")):
        record = json.loads(file.read_text(encoding="utf-8-sig"))
        data = record.get("data")
        array = isinstance(data, list)
        kind = "sample" if array else data.get("kind", "external")
        scale = f"{len(data)} 点" if array else f"{len(data.get('rows', []))} 行表格" if kind == "table" else "数据图" if kind == "figure" else "外部数据"
        nature = record.get("nature", {})
        calculable = array and len(data) >= 3 and nature.get("observation") == "complete" and nature.get("kind") in {"observed", "simulated"} and all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0 for value in data)
        sources = []
        seen = set()
        for source in record.get("sources", []):
            key = canonical(source)
            if key not in seen:
                sources.append(source)
                seen.add(key)
        stat = file.stat()
        records.append({"id": record["id"], "name": record["name"], "nature": record["nature"], "sources": sources,
                        "file": file.name, "scale": scale, "can_calculate": calculable, "data_kind": kind,
                        "size": stat.st_size, "mtime_ms": stat.st_mtime * 1000})
    atomic_json(cases / "index.json", {"schema_version": 1, "records": records})
    return {"indexed_records": len(records), "bytes": (cases / "index.json").stat().st_size}


def run(args):
    manifest = json.loads(args.library.read_text(encoding="utf-8-sig"))
    if manifest.get("mode") != "source":
        raise ValueError("需要当前 source 模式正式书单")
    totals = Counter()
    for source in manifest["sources"]:
        directory = Path(source["root"])
        for paper in source["papers"]:
            ident = paper if isinstance(paper, str) else paper["id"]
            if args.paper and ident not in args.paper:
                continue
            totals["papers"] += 1
            originals = list(directory.glob(ident + "-pdf原文.md"))
            translations = list(directory.glob(ident + "-pdf翻译.md"))
            files = originals or translations
            if len(files) != 1:
                coverage = {"paper_id": ident, "status": "pending", "record_ids": [], "issues": [{"kind": "source_missing", "detail": "原文与译文均缺失或存在歧义"}]}
                totals["missing_sources"] += 1
            else:
                file = files[0]
                raw = file.read_bytes()
                text = raw.decode("utf-8-sig")
                records, issues, detected = build_records(ident, text, directory)
                issues.extend(stabilize_ids(args, ident, records, digest(raw)))
                if not originals:
                    issues.append({"kind": "translation_only", "detail": "原文稿缺失，本次依译稿提取，需核对原论文"})
                pdfs = [pdf for pdf in directory.glob(ident + "*.pdf") if re.match(re.escape(ident) + r"(?:[-_.\s]|$)", pdf.name)]
                if len(pdfs) != 1:
                    issues.append({"kind": "pdf_source", "detail": "PDF 未匹配" if not pdfs else "匹配多个 PDF，逐项核对时确定实际原稿", "files": [pdf.name for pdf in pdfs]})
                coverage = {"paper_id": ident, "status": "extracted", "source": {"file": str(file), "sha256": digest(raw), "pdf_files": [pdf.name for pdf in pdfs]},
                            "record_ids": [record["id"] for record in records], "detected": detected,
                            "issues": [{"kind": "pdf_review", "detail": "本次为源稿自动提取，逐表/图对照 PDF 及正文数据段检查尚待完成"}, *issues]}
                for record in records:
                    totals[record["data"]["kind"]] += 1
                    if args.apply:
                        status = save_record(args.cases / "records", record, digest(raw))
                        totals[status] += 1
                        if status == "preserved_manual":
                            coverage["issues"].append({"kind": status, "record_id": record["id"], "detail": "保留已有人工修订，本次未覆盖"})
                totals["unclassified_images"] += detected["unclassified_images"]
                totals["text_sequences"] += detected["text_sequences"]
            if args.apply:
                target = args.cases / "coverage" / (ident + ".json")
                if target.exists():
                    previous = json.loads(target.read_text(encoding="utf-8-sig"))
                    if previous.get("status") in {"reviewed", "complete", "no_data"} and previous.get("source", {}).get("sha256") == coverage.get("source", {}).get("sha256"):
                        totals["preserved_reviews"] += 1
                        continue
                    if previous.get("status") in {"reviewed", "complete", "no_data"}:
                        coverage["previous_review"] = {key: previous[key] for key in ("status", "source", "review") if key in previous}
                        coverage["issues"].append({"kind": "review_source_changed", "detail": "核查依据的源稿身份已改变，保留原核查记录，当前材料需重新核对"})
                atomic_json(target, coverage)
    if args.apply:
        totals.update(write_index(args.cases))
    return dict(totals)


def check_existing(args):
    manifest = json.loads(args.library.read_text(encoding="utf-8-sig"))
    sources = {}
    issues = []
    for source in manifest["sources"]:
        for paper in source["papers"]:
            ident = paper if isinstance(paper, str) else paper["id"]
            directory = Path(source["root"])
            files = list(directory.glob(ident + "-pdf原文.md")) or list(directory.glob(ident + "-pdf翻译.md"))
            if len(files) != 1:
                issues.append({"kind": "source_missing", "paper_id": ident})
                continue
            raw = files[0].read_bytes()
            sources[ident] = (directory, raw.decode("utf-8-sig"), digest(raw))
    totals = Counter()
    observed = set()
    for file in sorted((args.cases / "records").glob("*.json")):
        record = json.loads(file.read_text(encoding="utf-8-sig"))
        refs = record.get("sources", [])
        if args.paper and not any(ref.get("paper_id") in args.paper for ref in refs):
            continue
        ident = record.get("id")
        totals["checked_records"] += 1
        if ident in observed:
            issues.append({"kind": "duplicate_id", "record_id": ident, "file": file.name})
        observed.add(ident)
        if not isinstance(ident, str) or not record.get("name") or not refs:
            issues.append({"kind": "record_shape", "file": file.name})
        primary = sources.get(refs[0].get("paper_id")) if refs else None
        for ref in refs:
            if ref.get("paper_id") not in sources:
                issues.append({"kind": "unknown_source", "record_id": ident, "paper_id": ref.get("paper_id")})
        if not primary:
            continue
        directory, text, source_hash = primary
        imported = record.get("_import", {})
        if imported.get("generator") == GENERATOR and imported.get("source_sha256") != source_hash:
            issues.append({"kind": "source_hash_changed", "record_id": ident})
        data = record.get("data")
        if not isinstance(data, dict):
            totals["other_data_records"] += 1
            continue
        if data.get("kind") == "table":
            markup = data.get("source_text") or data.get("markdown") or data.get("html", "")
            if not markup or markup not in text:
                issues.append({"kind": "markup_not_found", "record_id": ident})
            else:
                totals["source_markup_matched"] += 1
        elif data.get("kind") == "figure":
            asset = data.get("asset", "")
            candidate = directory / unquote(asset)
            try:
                candidate.resolve().relative_to(directory.resolve())
            except ValueError:
                issues.append({"kind": "asset_outside_source", "record_id": ident, "asset": asset})
                continue
            if not candidate.is_file():
                issues.append({"kind": "missing_asset", "record_id": ident, "asset": asset})
            else:
                totals["figure_assets_matched"] += 1
    totals["issues"] = len(issues)
    return {"summary": dict(totals), "issues": issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=Path(os.environ.get("WEIBULL_LIBRARY_ROOT", "../weibull-data/literature-source")) / "library.json")
    parser.add_argument("--cases", type=Path, default=Path(os.environ.get("WEIBULL_DATA_ROOT", "../weibull-data")) / "cases")
    parser.add_argument("--paper", action="append", help="只处理指定文献编号，可重复")
    parser.add_argument("--apply", action="store_true", help="写入数据；省略时只盘点")
    parser.add_argument("--check", action="store_true", help="只读核对现有记录的源身份、原表格、图资源、编号和来源")
    parser.add_argument("--index-only", action="store_true", help="只刷新包括人工样本在内的派生索引")
    args = parser.parse_args()
    if args.apply and args.check:
        parser.error("--check 为只读核对，不能同时使用 --apply")
    print(json.dumps(write_index(args.cases) if args.index_only else check_existing(args) if args.check else run(args), ensure_ascii=False))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
