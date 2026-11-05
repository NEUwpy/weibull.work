#!/usr/bin/env python3
"""Build the public case catalog from an explicit, source-checked selection.

The selection file owns display names and grouping. Imported records, source
papers and the extraction index are read-only; unselected records stay in the
backstage inventory. Run without --apply to inspect, or --check for reproducibility.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys


PROJECT = Path(__file__).resolve().parents[1]
SELECTION = Path(__file__).with_name("case-catalog-selection.json")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def absolute_path(value):
    path = Path(value)
    return path if path.is_absolute() else PROJECT / path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def chinese_name(value):
    return isinstance(value, str) and re.search(r"[\u3400-\u9fff]", value) and not re.search(r"\b(?:Table|Figure|Fig|Example|Case)\b", value, re.I)


def build_catalog(cases, library, selection_path):
    selection = read_json(selection_path)
    manifest = read_json(library)
    require(manifest.get("mode") == "source", "需要当前 source 模式正式书单")
    papers = {}
    for source in manifest["sources"]:
        for paper in source["papers"]:
            ident = paper if isinstance(paper, str) else paper["id"]
            require(ident not in papers, f"正式书单编号重复：{ident}")
            papers[ident] = Path(source["root"])

    index_rows = read_json(cases / "index.json")["records"]
    records = {row["id"]: row for row in index_rows}
    require(len(records) == len(index_rows), "提取索引含重复编号")
    files = {path.stem for path in (cases / "records").glob("*.json")}
    require(files == records.keys(), "记录文件与索引不一致，请先运行 import-case-library.py --index-only")
    groups = selection["groups"]
    group_ids = [group["id"] for group in groups]
    require(len(set(group_ids)) == len(group_ids), "案例组编号重复")
    require(not set(group_ids) & records.keys(), "案例组编号不能与数据记录编号重合")
    excluded = selection["excluded_papers"]
    excluded_ids = {paper["paper_id"] for paper in excluded}
    require(len(excluded_ids) == len(excluded), "排除文献编号重复")
    require(excluded_ids <= papers.keys(), "排除清单包含已不在正式书单的文献，请重新选材")

    source_hashes = {}
    for paper_id, expected in selection["source_sha256"].items():
        require(paper_id in papers, f"选材来源已不在正式书单：{paper_id}")
        source = papers[paper_id] / f"{paper_id}-pdf原文.md"
        require(source.is_file(), f"选材原稿缺失：{source}")
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        require(actual == expected, f"选材原稿已变化，需重新核查：{paper_id}")
        source_hashes[paper_id] = actual

    selected = {}
    selected_papers = set()
    for group in groups:
        require(chinese_name(group["name"]), f"案例组名称须为规范中文：{group['id']}")
        require(group["kind"] in {"observed", "simulated", "result"}, f"案例组性质无效：{group['id']}")
        require(isinstance(group.get("tags", []), list) and all(isinstance(tag, str) and tag.strip() for tag in group.get("tags", [])), f"案例组性质标签无效：{group['id']}")
        require(group["members"], f"空案例组：{group['id']}")
        for member in group["members"]:
            ident, role = member["id"], member["role"]
            require(ident not in selected, f"同一记录出现在多个组：{ident}")
            require(ident in records, f"选材记录不存在：{ident}")
            require(chinese_name(member["name"]), f"子项名称须为规范中文：{ident}")
            require(role in {"sample", "derived", "table", "figure", "external"}, f"子项角色无效：{ident}")
            record = read_json(cases / "records" / f"{ident}.json")
            require(record["id"] == ident, f"记录内部编号不匹配：{ident}")
            paper_ids = {source["paper_id"] for source in record["sources"]}
            require(paper_ids <= papers.keys(), f"记录来源不在正式书单：{ident}")
            require(paper_ids <= source_hashes.keys(), f"记录来源未经本次选材核查：{ident}")
            require(not paper_ids & excluded_ids, f"选材记录引用被排除文献：{ident}")
            imported = record.get("_import", {})
            if imported.get("source_sha256"):
                require(imported["source_sha256"] in {source_hashes[paper] for paper in paper_ids}, f"记录原稿身份不匹配：{ident}")
            data = record["data"]
            if role in {"sample", "derived"}:
                require(isinstance(data, list) and data and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in data), f"样本数值无效：{ident}")
                require(record["nature"]["kind"] == group["kind"], f"实测和模拟样本混组：{ident}")
            else:
                require(isinstance(data, dict) and data.get("kind") == role, f"记录与子项角色不匹配：{ident}")
                if role == "figure":
                    require(any((papers[paper] / data["asset"]).is_file() for paper in paper_ids), f"图像资源缺失：{ident}")
            selected[ident] = record
            selected_papers.update(paper_ids)

    expected_samples = {ident for ident in records if ident.startswith("sample-")}
    actual_samples = {ident for ident, record in selected.items() if isinstance(record["data"], list)}
    require(expected_samples == actual_samples, "全部已核实 sample-* 必须有且仅有一个归属组")
    batches = [selected[f"sample-hirose-1996-case-{i}"]["data"] for i in range(1, 6)]
    require(all(len(batch) == 20 for batch in batches), "Hirose 五批样本必须各为20点")
    require(sum(batches, []) == selected["sample-hirose-1996-all"]["data"], "Hirose 合并视图必须逐批连接原始100点")
    for paper_id in selection["fully_pdf_reviewed_result_papers"]:
        coverage = read_json(cases / "coverage" / f"{paper_id}.json")
        require(coverage["status"] == "reviewed" and coverage["source"]["sha256"] == source_hashes[paper_id], f"完整PDF结果核查状态失效：{paper_id}")
        result_ids = {ident for ident, record in selected.items() if not isinstance(record["data"], list) and any(source["paper_id"] == paper_id for source in record["sources"])}
        require(result_ids <= set(coverage["review"]["record_ids"]), f"已选结果缺少逐项PDF核查记录：{paper_id}")

    unselected_by_paper = defaultdict(list)
    excluded_record_ids = []
    for ident, record in sorted(records.items()):
        if ident in selected:
            continue
        paper_ids = {source["paper_id"] for source in record["sources"]}
        require(paper_ids <= papers.keys(), f"后台记录来源不在正式书单：{ident}")
        if paper_ids & excluded_ids:
            excluded_record_ids.append(ident)
        else:
            for paper_id in sorted(paper_ids):
                unselected_by_paper[paper_id].append(ident)
    pending_ids = set().union(*map(set, unselected_by_paper.values())) if unselected_by_paper else set()
    kinds = Counter(group["kind"] for group in groups)
    roles = Counter(member["role"] for group in groups for member in group["members"])
    pending = {
        "source_papers_total": len(papers),
        "scanned_records_total": len(records),
        "published_groups": len(groups),
        "published_groups_by_kind": dict(sorted(kinds.items())),
        "published_records": len(selected),
        "published_sample_records": len(actual_samples),
        "published_records_by_role": dict(sorted(roles.items())),
        "published_papers": len(selected_papers),
        "excluded_papers": len(excluded),
        "excluded_records": len(excluded_record_ids),
        "unpublished_records": len(records) - len(selected),
        "awaiting_review_records": len(pending_ids),
        "fully_pdf_reviewed_result_papers": selection["fully_pdf_reviewed_result_papers"],
        "notes": selection["notes"],
        "specific_issues": selection["specific_issues"],
        "papers": [
            {"paper_id": paper_id,
             "selection_status": "partial" if paper_id in selected_papers else "pending",
             "record_ids": unselected_by_paper.get(paper_id, [])}
            for paper_id in sorted(papers) if paper_id not in excluded_ids
        ],
        "excluded_record_ids": excluded_record_ids,
    }
    require(len(selected) + len(excluded_record_ids) + len(pending_ids) == len(records), "后台与发布记录未形成完整分区")
    return {"schema_version": 1, "groups": groups, "excluded_papers": excluded, "pending": pending}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=absolute_path, default=absolute_path(os.environ.get("WEIBULL_DATA_ROOT", "../weibull-data")) / "cases")
    parser.add_argument("--library", type=absolute_path, default=absolute_path(os.environ.get("WEIBULL_LIBRARY_ROOT", "../weibull-data/literature-source")) / "library.json")
    parser.add_argument("--selection", type=absolute_path, default=SELECTION)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="只写入 cases/catalog.json")
    action.add_argument("--check", action="store_true", help="只读核对现行目录与显式选材一致")
    args = parser.parse_args()
    catalog = build_catalog(args.cases, args.library, args.selection)
    output = args.cases / "catalog.json"
    if args.check:
        require(output.is_file() and read_json(output) == catalog, "目录与选材不一致，请运行 --apply")
    if args.apply:
        temporary = output.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, output)
    print(json.dumps({key: value for key, value in catalog["pending"].items() if key not in {"papers", "excluded_record_ids", "notes", "specific_issues"}}, ensure_ascii=False))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
