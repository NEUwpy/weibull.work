from pathlib import Path
import gzip
import json
import random
import string
import sys

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_CODE = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究" / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

from study02a.artifacts import append_ledger, write_csv_gz_shards, write_manifest


def test_ledger_append_preserves_failed_runs(tmp_path):
    ledger = tmp_path / "run_ledger.jsonl"
    append_ledger({"run_id": "failed-1", "exit_code": 1}, ledger)
    append_ledger({"run_id": "success-2", "exit_code": 0}, ledger)
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in rows] == ["failed-1", "success-2"]


def test_manifest_is_atomic_json(tmp_path):
    path = tmp_path / "manifest.json"
    write_manifest({"run_id": "pilot", "test_state": "sealed"}, path)
    assert json.loads(path.read_text(encoding="utf-8"))["test_state"] == "sealed"
    assert not list(tmp_path.glob("*.tmp"))


def test_gzip_shards_round_trip_in_deterministic_order(tmp_path):
    alphabet = string.ascii_letters + string.digits
    rows = [
        {"row_id": i, "text": "".join(random.Random(i).choices(alphabet, k=80))}
        for i in range(100)
    ]
    paths = write_csv_gz_shards(rows, tmp_path, stem="results", max_mib=0.002)
    assert len(paths) > 1
    recovered = pd.concat([pd.read_csv(path, compression="gzip") for path in paths], ignore_index=True)
    assert recovered["row_id"].tolist() == list(range(100))
    assert all(path.stat().st_size <= 0.002 * 1024 * 1024 for path in paths)
    with gzip.open(paths[0], "rt", encoding="utf-8") as handle:
        assert handle.readline().strip() == "row_id,text"
