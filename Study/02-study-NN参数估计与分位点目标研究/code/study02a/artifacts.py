"""Auditable artifact writers for Study/02."""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def append_ledger(entry: Mapping[str, Any], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (_canonical_json(entry) + "\n").encode("utf-8")
    with path.open("ab") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def write_manifest(manifest: Mapping[str, Any], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _gzip_csv(rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> bytes:
    binary = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=binary, mtime=0) as compressed:
        with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
            writer = csv.DictWriter(text, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    return binary.getvalue()


def _split_to_limit(rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str], max_bytes: int) -> list[bytes]:
    payload = _gzip_csv(rows, fieldnames)
    if len(payload) <= max_bytes:
        return [payload]
    if len(rows) <= 1:
        raise ValueError("A single compressed CSV row exceeds max_mib")
    midpoint = len(rows) // 2
    return _split_to_limit(rows[:midpoint], fieldnames, max_bytes) + _split_to_limit(rows[midpoint:], fieldnames, max_bytes)


def write_csv_gz_shards(
    rows: Sequence[Mapping[str, Any]],
    output_dir: Path,
    *,
    stem: str,
    max_mib: float = 20.0,
) -> list[Path]:
    if not rows:
        raise ValueError("Cannot shard an empty result set")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if list(output_dir.glob(f"{stem}-part-*.csv.gz")):
        raise FileExistsError(f"Existing {stem} shards would be overwritten")
    fieldnames = list(rows[0].keys())
    if any(list(row.keys()) != fieldnames for row in rows):
        raise ValueError("All rows must have identical ordered fields")
    payloads = _split_to_limit(list(rows), fieldnames, max(1, int(max_mib * 1024 * 1024)))
    paths = []
    for index, payload in enumerate(payloads, start=1):
        path = output_dir / f"{stem}-part-{index:04d}.csv.gz"
        path.write_bytes(payload)
        paths.append(path)
    return paths
