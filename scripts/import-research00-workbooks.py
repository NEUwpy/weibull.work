"""Register frozen Research00 workbooks and provenance in external data.

No sampling, estimation, or edits to research sources occur. Existing registered
files are immutable: a differing file aborts instead of overwriting a batch.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOFTWARE / "python"))
from data_paths import data_root
from studies.common.workbook import parse_workbook


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def register(research_root: Path, target_root: Path, index_path: Path):
    delivery = research_root / "Research/00-方法对比/交付"
    program_root = delivery / "程序"
    catalog = json.loads((program_root / "跨参数对比/13组合取数.json").read_text(encoding="utf-8"))
    entries = []
    for row in catalog["sources"]:
        original = delivery / "结果" / row["program"] / (row["program"] + ".xlsx")
        raw = original.read_bytes()
        if sha(raw) != row["workbook_sha256"]:
            raise ValueError("Original workbook identity changed: " + original.name)
        matrix_path = program_root / row["matrix"]
        matrix_raw = matrix_path.read_bytes()
        if sha(matrix_raw) != row["matrix_sha256"]:
            raise ValueError("Original matrix identity changed: " + row["matrix"])
        config = json.loads(matrix_raw)["config"]
        for relative, identity in config.get("dependency_hashes", {}).items():
            source = program_root / row["snapshot"] / relative
            if not source.is_file() or sha(source.read_bytes()) != identity:
                raise ValueError("Dependency identity differs: " + str(source))
        book = parse_workbook(raw, original.name, {"kind": "archive"})
        if book["truth"] != config["truth"]:
            raise ValueError("Workbook filename and stored truth disagree")
        book_id = "r00-" + row["program"].lower().replace(",", "-").replace(".", "p")
        directory = f"monte-carlo/research00/{book_id}-{sha(raw)[:12]}"
        batch = (target_root / directory).resolve()
        if not batch.is_relative_to(target_root.resolve()):
            raise ValueError("Invalid batch destination")
        files = {}

        def put(relative, content, role):
            destination = (batch / relative).resolve()
            if not destination.is_relative_to(batch):
                raise ValueError("File escapes batch")
            if destination.exists():
                if destination.read_bytes() != content:
                    raise ValueError("Registered file differs; retain old batch: " + str(destination))
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            files[relative] = dict(sha256=sha(content), bytes=len(content), role=role)

        book["id"] = book_id
        put("workbook.xlsx", raw, "workbook")
        put("workbook.json", encoded(book), "view")
        source_dir = (program_root / row["program"]).resolve()
        for source in sorted(source_dir.rglob("*")):
            if not source.is_file() or "__pycache__" in source.parts or source.suffix == ".pyc":
                continue
            if not source.resolve().is_relative_to(source_dir):
                raise ValueError("Research snapshot contains an external link")
            relative = "source/" + row["program"] + "/" + source.relative_to(source_dir).as_posix()
            put(relative, source.read_bytes(), "code" if source.suffix in {".py", ".mjs", ".ps1", ".tsv"} else "input")
        for source in sorted(program_root.iterdir()):
            if source.is_file() and source.suffix in {".py", ".mjs", ".ps1"}:
                put("source/" + source.name, source.read_bytes(), "code")
        manifest_path = batch / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest["files"] != files or manifest["configuration"] != config:
                raise ValueError("Registered manifest differs")
        else:
            manifest = dict(schemaVersion=1, id=book_id, title=row["combination"], filename=original.name,
                            importedAt=datetime.now(timezone.utc).isoformat(), calculationTime=None,
                            collection="Research00", protocol=row["protocol"], configuration=config,
                            origin=dict(workbook="交付/结果/" + row["program"] + "/" + original.name,
                                        matrix="交付/程序/" + row["matrix"], workbookSha256=sha(raw), matrixSha256=sha(matrix_raw)),
                            files=files)
            manifest_path.write_bytes(encoded(manifest))
        groups = book["groups"]
        blocks = next(iter(groups.values()))["blocks"]
        entries.append(dict(id=book_id, title=row["combination"], truth=book["truth"],
                            ns=list(map(int, groups)), methods=list(dict.fromkeys(b["method"] for b in blocks)),
                            offsets=list(dict.fromkeys(b["delta"] for b in blocks if b["method"] == "mdm")),
                            protocol=row["protocol"], filename=original.name, workbookSha256=sha(raw),
                            directory=directory, manifestSha256=sha(manifest_path.read_bytes())))
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_bytes(encoded(dict(schemaVersion=1, collection="Research00", entries=entries)))
    return entries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-root", required=True, type=Path)
    parser.add_argument("--data-root", type=Path, default=data_root())
    parser.add_argument("--index", type=Path, default=SOFTWARE / "src/content/monte-carlo/research00.json")
    args = parser.parse_args()
    records = register(args.research_root.resolve(), args.data_root.resolve(), args.index.resolve())
    print(json.dumps(dict(registered=len(records), dataRoot=str(args.data_root), index=str(args.index))))
