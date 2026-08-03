"""Evaluation runner for the incremental B run.

Two evaluation blocks:
- dense-n core: 19 n x 64 Sobol clusters x 20 replicates, all routes
  (P 10 seeds, D 10, Dctrl 5, MDM/MLE/LRE). Shared n are bit-identical to B4
  so the run reproduces B4 numbers there (validation).
- parameter grid: fixed (beta, rho, eta, n) cells x PG_DRAWS common-RN draws,
  all routes.

Per-seed predictions are persisted to per_seed npz for mechanism analysis.

Resumable: per-block CSV + npz are the artifacts; re-running recomputes the
block only if its CSV is missing. Deterministic given the frozen CONFIG_HASH
and input checkpoints.

Usage:
    python -m study02b_inc.evaluate_inc --run-dir <dir> [--block core|grid|all]
        [--workers 8]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import torch

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON = _REPO_ROOT / "python"
if str(_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PYTHON))

from studies.common.metrics import quantile_true
from studies.common.runner import run_method
from study02a.models import decode_model_output
from study02a.representations import anchor_sample
from study02b.representations import DTrainingStats, decode_d_target, unstandardize_d

from study02b_inc import config as C
from study02b_inc import data as D
from study02b_inc import models as M

TRAD = [("mdm", {"offset": 0.1}, "MDM"), ("mle", {}, "MLE"), ("lre", {}, "LRE")]
MAX_SEED = {"P": len(C.P_FIT_SEEDS), "D": len(C.D_FIT_SEEDS), "Dctrl": len(C.DCTRL_FIT_SEEDS)}

_WORKER_MODELS: dict | None = None
_WORKER_INIT: tuple | None = None


def _git_tip() -> str:
    import subprocess
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                       cwd=str(C.REPO_ROOT), timeout=5)
    return r.stdout.strip() or "unknown"


# ---------------------------------------------------------------------------
# Worker process: load all models once, evaluate datasets
# ---------------------------------------------------------------------------

def _worker_init(run_dir_str: str, p_index_json: str, d_index_json: str, ts_json: str,
                 p_scaler_json: str):
    global _WORKER_MODELS
    p_index = {int(k): v for k, v in json.loads(p_index_json).items()}
    d_index = {int(k): v for k, v in json.loads(d_index_json).items()}
    ts = {int(k): v for k, v in json.loads(ts_json).items()}
    p_scalers = {int(k): v for k, v in json.loads(p_scaler_json).items()}

    models = {"P": {}, "D": {}, "Dctrl": {}}
    for n, entries in p_index.items():
        sc = p_scalers.get(n, {"mean": None, "sd": None})
        models["P"][n] = [(e["seed"], (M.load_model("P", n, e["seed"], e), sc))
                          for e in entries]
    for group, key in (("selected", "D"), ("controlled", "Dctrl")):
        for n, grp in d_index.items():
            for e in grp.get(group, []):
                st = ts.get(n, {"mean": 0.0, "sd": 1.0})
                models[key].setdefault(n, []).append((
                    e["seed"],
                    (M.load_model(key, n, e["seed"], e),
                     DTrainingStats(mean=st["mean"], sd=st["sd"]))))
    _WORKER_MODELS = models


def _infer_p(entries, sample):
    a = anchor_sample(sample)
    z = a.z.astype(np.float32)
    if entries:
        sc = entries[0][1][1]  # (model, scaler)
        mean = np.array(sc["mean"], dtype=np.float32)
        sd = np.array(sc["sd"], dtype=np.float32)
        if mean.size == z.shape[0] and sd.size == z.shape[0]:
            safe = np.where(sd != 0, sd, 1.0)
            z = np.where(sd != 0, (z - mean) / safe, 0.0)
    zt = torch.from_numpy(z).unsqueeze(0)
    vals = []
    for _, (m, _sc) in entries:
        with torch.no_grad():
            raw = m(zt)
        dec = decode_model_output(raw, torch.tensor([a.location]),
                                  torch.tensor([a.scale]))
        bf, ef, gf = float(dec[0, 0]), float(dec[0, 1]), float(dec[0, 2])
        vals.append(quantile_true(bf, ef, gf, 0.95)
                    if (bf > 0 and ef > 0 and np.isfinite([bf, ef, gf]).all()) else np.nan)
    return np.array(vals)


def _infer_d(entries, sample):
    a = anchor_sample(sample)
    z = torch.from_numpy(a.z.astype(np.float32)).unsqueeze(0)
    vals = []
    for _, (m, st) in entries:
        with torch.no_grad():
            raw = float(m(z).item())
        vals.append(decode_d_target(unstandardize_d(np.array([raw]), st)[0], a))
    return np.array(vals)


def _infer_trad(mid, kw, sample):
    r = run_method(mid, sample, **kw)
    bh, eh, gh = r["beta_hat"], r["eta_hat"], r["gamma_hat"]
    if bh is None or eh is None or gh is None:
        return np.nan
    if not (bh > 0 and eh > 0 and np.isfinite([bh, eh, gh]).all()):
        return np.nan
    return quantile_true(float(bh), float(eh), float(gh), 0.95)


def _worker_eval(job: tuple) -> dict:
    n, sample, beta, eta, gamma, true_x095 = job
    m = _WORKER_MODELS
    p_seed = _infer_p(m["P"].get(n, []), sample)
    d_seed = _infer_d(m["D"].get(n, []), sample)
    dc_seed = _infer_d(m["Dctrl"].get(n, []), sample)
    trad = {lbl: _infer_trad(mid, kw, sample) for mid, kw, lbl in TRAD}
    return {"p_seed": p_seed, "d_seed": d_seed, "dc_seed": dc_seed,
            "trad": trad, "true_x095": true_x095}


def _serialize_indexes(run_dir: Path):
    extras = list(C.SUPERSEDED_RUNS)
    p_index = M.build_p_index(run_dir)
    d_index = M.build_d_index(run_dir, extras)
    ts = M.d_target_stats(run_dir, extras)
    p_sc = M.p_scalers(run_dir)
    return (str(run_dir), json.dumps(p_index), json.dumps(d_index), json.dumps(ts),
            json.dumps(p_sc))


def _ensure_worker_init(run_dir: Path):
    global _WORKER_MODELS
    if _WORKER_MODELS is None:
        _worker_init(*_serialize_indexes(run_dir))


# ---------------------------------------------------------------------------
# Block runners
# ---------------------------------------------------------------------------

CHUNK = 8192


def _row_csv(r, res, block: str) -> dict:
    xt = float(r.true_x095)
    if block == "core":
        row = {"row_idx": 0, "cluster": r.meta["cluster"], "replicate": r.meta["replicate"],
               "n": r.n, "beta": r.beta, "eta": r.eta, "gamma": r.gamma, "true_x095": xt}
    else:
        row = {"row_idx": 0, "cell": r.meta["cell"], "draw": r.meta["draw"], "n": r.n,
               "beta": r.beta, "rho": r.rho, "eta": r.eta, "gamma": r.gamma, "true_x095": xt}
    for lbl, arr in (("P_mean", res["p_seed"]), ("D_mean", res["d_seed"]),
                     ("Dctrl_mean", res["dc_seed"])):
        m = float(np.nanmean(arr)) if np.isfinite(arr).any() else ""
        row[lbl] = m
        row[lbl.replace("_mean", "_rel_err")] = (m - xt) / xt if m != "" and xt != 0 else ""
    for lbl in ("MDM", "MLE", "LRE"):
        row[lbl] = res["trad"][lbl]
    return row


def _cols(block: str) -> list[str]:
    if block == "core":
        cols = ["row_idx", "cluster", "replicate", "n", "beta", "eta", "gamma", "true_x095"]
    else:
        cols = ["row_idx", "cell", "draw", "n", "beta", "rho", "eta", "gamma", "true_x095"]
    for lbl in ("P_mean", "D_mean", "Dctrl_mean", "P_rel_err", "D_rel_err",
                "Dctrl_rel_err", "MDM", "MLE", "LRE"):
        cols.append(lbl)
    return cols


def _run_block(run_dir: Path, rows: list[D.TestRow], block: str, workers: int) -> dict:
    out = run_dir / "eval"
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / f"{block}_results.csv"
    npz_path = out / f"{block}_per_seed.npz"
    prog_path = out / f"{block}_progress.json"

    # Resumable: completed chunks are recorded in progress + chunk npz.
    done_chunks: set[int] = set()
    if prog_path.exists():
        done_chunks = set(json.loads(prog_path.read_text(encoding="utf-8")).get("done", []))

    n_chunks = (len(rows) + CHUNK - 1) // CHUNK
    if len(done_chunks) == n_chunks and npz_path.exists():
        print(f"[{block}] already complete ({len(rows)} datasets)")
        return _block_manifest(run_dir, block, csv_path, npz_path)

    print(f"[{block}] evaluating {len(rows)} datasets in {n_chunks} chunks "
          f"({len(done_chunks)} done) ...")
    t0 = time.perf_counter()
    jobs = [(r.n, r.sample, r.beta, r.eta, r.gamma, r.true_x095) for r in rows]

    # Reuse a persistent pool across chunks so models load once.
    pool = None
    if workers > 1 and len(jobs) >= 2 * workers:
        pool = Pool(processes=workers, initializer=_worker_init,
                    initargs=_serialize_indexes(run_dir))
    else:
        _ensure_worker_init(run_dir)

    p_s, d_s, dc_s, keys = [], [], [], []
    first_write = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_cols(block))
        if first_write:
            w.writeheader()
        for ci in range(n_chunks):
            start, end = ci * CHUNK, min((ci + 1) * CHUNK, len(rows))
            if ci in done_chunks:
                # load per-seed from chunk npz
                ck = out / f"{block}_chunk_{ci:04d}.npz"
                if ck.exists():
                    cnpz = np.load(ck)
                    for k in cnpz["keys"]:
                        keys.append(k)
                    p_s.extend(cnpz["p_seeds"]); d_s.extend(cnpz["d_seeds"])
                    dc_s.extend(cnpz["dctrl_seeds"])
                continue
            chunk_jobs = jobs[start:end]
            if pool is not None:
                res = pool.map(_worker_eval, chunk_jobs, chunksize=128)
            else:
                res = [_worker_eval(j) for j in chunk_jobs]
            # write CSV rows + accumulate per-seed
            ck_p, ck_d, ck_dc, ck_keys = [], [], [], []
            for local_i, (r, rres) in enumerate(zip(rows[start:end], res)):
                out_row = _row_csv(r, rres, block)
                out_row["row_idx"] = start + local_i
                w.writerow(out_row)
                ck_p.append(_pad(rres["p_seed"], MAX_SEED["P"]))
                ck_d.append(_pad(rres["d_seed"], MAX_SEED["D"]))
                ck_dc.append(_pad(rres["dc_seed"], MAX_SEED["Dctrl"]))
                ck_keys.append(str(start + local_i))
            np.savez_compressed(out / f"{block}_chunk_{ci:04d}.npz",
                                keys=np.array(ck_keys, dtype=object),
                                p_seeds=np.array(ck_p, dtype=np.float32),
                                d_seeds=np.array(ck_d, dtype=np.float32),
                                dctrl_seeds=np.array(ck_dc, dtype=np.float32))
            keys.extend(ck_keys); p_s.extend(ck_p); d_s.extend(ck_d); dc_s.extend(ck_dc)
            done_chunks.add(ci)
            prog_path.write_text(json.dumps({"done": sorted(done_chunks)}), encoding="utf-8")
            print(f"  chunk {ci + 1}/{n_chunks} done "
                  f"({time.perf_counter() - t0:.0f}s elapsed)")
    if pool is not None:
        pool.close(); pool.join()

    np.savez_compressed(npz_path, keys=np.array(keys, dtype=object),
                        p_seeds=np.array(p_s, dtype=np.float32),
                        d_seeds=np.array(d_s, dtype=np.float32),
                        dctrl_seeds=np.array(dc_s, dtype=np.float32))
    # remove chunk npz (merged)
    for ci in range(n_chunks):
        ck = out / f"{block}_chunk_{ci:04d}.npz"
        if ck.exists():
            ck.unlink()

    print(f"[{block}] wrote {csv_path} and {npz_path} in {time.perf_counter() - t0:.1f}s")
    return _block_manifest(run_dir, block, csv_path, npz_path)


def _pad(arr, size):
    v = np.asarray(arr, dtype=np.float32)
    return np.pad(v, (0, max(0, size - len(v))), constant_values=np.nan)


def _block_manifest(run_dir: Path, block: str, csv_path: Path, npz_path: Path) -> dict:
    return {
        "block": block,
        "results_csv": {"path": str(csv_path),
                        "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest()},
        "per_seed_npz": {"path": str(npz_path),
                         "sha256": hashlib.sha256(npz_path.read_bytes()).hexdigest()},
    }


def evaluate_inc(run_dir: Path, block: str = "all", workers: int = 8) -> dict:
    run_dir = Path(run_dir)
    out = run_dir / "eval"
    out.mkdir(parents=True, exist_ok=True)
    print(f"=== Incremental evaluation (block={block}) ===")
    print(f"run_dir: {run_dir}")
    print(f"config_hash: {C.CONFIG_HASH}")
    code_tip = _git_tip()

    blocks = []
    if block in ("core", "all"):
        rows = D.generate_core_rows()
        blocks.append(_run_block(run_dir, rows, "core", workers))
    if block in ("grid", "all"):
        rows = D.generate_grid_rows()
        blocks.append(_run_block(run_dir, rows, "grid", workers))

    manifest = {
        "version": "1.0",
        "run_id": run_dir.name,
        "kind": "evaluation",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_tip": code_tip,
        "config_hash": C.CONFIG_HASH,
        "blocks": blocks,
    }
    mf = out / "manifest.json"
    mf.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Evaluation manifest: {mf}")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--block", choices=["core", "grid", "all"], default="all")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    evaluate_inc(Path(args.run_dir), block=args.block, workers=args.workers)


if __name__ == "__main__":
    main()
