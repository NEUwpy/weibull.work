"""
Study/01 Formal E6a — 复用数据清单（manifest + data_sha256sums）

Dimensional-RAW 路线复用上一轮已生成并校验的 160 组合新设计 MDM 损失数据
（artifacts/formal/E5_normalized_raw/shared_data/）。本脚本只对既有分片做
fail-closed 校验，并重新生成数据清单：

  - manifest.json          （设计、规模、分片状态、must-include 组合）
  - data_sha256sums.txt    （全部分片/元数据/manifest 的 LF 稳定哈希）

不重跑 MDM、不复制分片。分片本体 gitignore，哈希记录可追溯。

用法：
    python run_E6a_data_inventory.py          # 校验 + 写清单
    python run_E6a_data_inventory.py --hash   # 只重写 data_sha256sums.txt
"""

import sys
import os
import json
import hashlib
import subprocess
from datetime import datetime, timezone
from itertools import product

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")
sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

import dim_raw_config as CFG


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def sha256_file_lf(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        prev = b''
        while True:
            block = f.read(1 << 20)
            if not block:
                break
            data = prev + block
            data = data.replace(b'\r\n', b'\n')
            prev = data[-1:] if data.endswith(b'\r') else b''
            h.update(data[:-1] if prev else data)
        if prev:
            h.update(prev)
    return h.hexdigest()


def chunk_paths(idx):
    name = f"chunk_{idx:04d}"
    return (os.path.join(CFG.CHUNKS_DIR, f"{name}_mdm.csv"),
            os.path.join(CFG.CHUNKS_DIR, f"{name}_meta.json"))


def validate_all_chunks():
    """fail-closed：校验 160 个分片（行数、组合键、repeat/delta 覆盖、元数据）。"""
    import pandas as pd
    combos = CFG.build_combos()
    assert len(combos) == 160
    status = []
    for idx in range(160):
        mdm_p, meta_p = chunk_paths(idx)
        if not (os.path.isfile(mdm_p) and os.path.isfile(meta_p)):
            raise FileNotFoundError(f"chunk_{idx:04d} or meta missing")
        df = pd.read_csv(mdm_p)
        b, goe, n = combos[idx]
        gamma = CFG.get_gamma(goe)
        expected = CFG.REPEATS * len(CFG.DELTA_GRID)
        if len(df) != expected:
            raise ValueError(f"chunk_{idx:04d}: {len(df)} rows != {expected}")
        keys_ok = (df['beta'].eq(b).all() and df['eta'].eq(CFG.ETA).all()
                   and df['gamma'].eq(gamma).all()
                   and df['gamma_over_eta'].eq(goe).all() and df['n'].eq(n).all())
        if not keys_ok:
            raise ValueError(f"chunk_{idx:04d}: combo keys mismatch")
        if df['repeat_id'].nunique() != CFG.REPEATS:
            raise ValueError(f"chunk_{idx:04d}: repeat coverage")
        if sorted(df['delta'].unique()) != CFG.DELTA_GRID:
            raise ValueError(f"chunk_{idx:04d}: delta coverage")
        if df.duplicated(subset=['repeat_id', 'delta']).any():
            raise ValueError(f"chunk_{idx:04d}: duplicate keys")
        status.append({"combo_idx": idx, "beta": b, "gamma_over_eta": goe, "n": n,
                       "mdm_rows": expected, "status": "done"})
    return status


def write_data_sha256sums():
    entries = []
    for idx in range(160):
        mdm_p, meta_p = chunk_paths(idx)
        entries.append((os.path.relpath(mdm_p, CFG.SHARED_DATA_DIR).replace(os.sep, '/'),
                        sha256_file_lf(mdm_p)))
        entries.append((os.path.relpath(meta_p, CFG.SHARED_DATA_DIR).replace(os.sep, '/'),
                        sha256_file_lf(meta_p)))
    entries.append(('manifest.json', sha256_file_lf(CFG.MC_MANIFEST_PATH)))
    entries.sort(key=lambda e: e[0])
    content = ''.join(f"{h}  {p}\n" for p, h in entries)
    out = os.path.join(CFG.SHARED_DATA_DIR, 'data_sha256sums.txt')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f"Wrote {out} ({len(entries)} entries)")
    return out


def write_manifest(unit_status):
    manifest = {
        "run_id": "E6a_dimensional_raw_data_v1",
        "created_at": _now_iso(),
        "code_entry": "code/run_E6a_data_inventory.py",
        "git_commit": _git_commit(),
        "note": ("Dimensional-RAW 复用上一轮已生成并校验的新设计 MDM 损失数据 "
                 "（E5_normalized_raw/shared_data，160 组合 x 300 重复 x 26 delta，"
                 "eta=1000）。不重跑 MDM，不复制分片；本清单记录设计与哈希。"),
        "design": CFG.design_summary(),
        "must_include_combo": {"beta": 2.0, "eta": 1000.0, "gamma": 1000.0},
        "unit_status": unit_status,
        "output_files": [
            "manifest.json", "data_sha256sums.txt (分片 LF 稳定哈希)",
            "chunks/（分片本体，gitignore）", "mc_scan_raw.csv（合并，gitignore）",
        ],
    }
    with open(CFG.MC_MANIFEST_PATH, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Wrote {CFG.MC_MANIFEST_PATH}")


def main():
    only_hash = '--hash' in sys.argv[1:]
    if only_hash:
        if not os.path.isdir(CFG.CHUNKS_DIR):
            sys.exit("no chunks dir; cannot hash")
        write_data_sha256sums()
        return
    os.makedirs(CFG.SHARED_DATA_DIR, exist_ok=True)
    unit_status = validate_all_chunks()
    write_manifest(unit_status)
    write_data_sha256sums()
    print("Data inventory complete: 160 chunks validated.")


if __name__ == "__main__":
    main()
