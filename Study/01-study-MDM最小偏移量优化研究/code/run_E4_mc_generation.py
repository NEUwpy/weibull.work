"""
Study/01 Formal E4 — MC Data Generation (subprocess-parallel version)

Spawns independent Python processes for parallel MDM generation.
Each worker handles a subset of combos and writes its own CSV chunk.
After all workers complete, chunks are merged into final output files.

Usage:
    python run_E4_mc_generation.py              # run all (spawns workers)
    python run_E4_mc_generation.py --worker 0   # run as worker 0
"""

import sys
import os
import csv
import json
import time
import argparse

# Path setup — must be at module level for subprocess import
STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")

sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

from config import DELTA_GRID, SEED_NAMESPACE, ARTIFACTS_DIR
from utils import get_git_info, now_iso
from studies.common.sample import generate_sample
from methods.mdm import MDM

# ============================================================
# Constants
# ============================================================

ETA = 1.0
R_FORMAL = 500
N_WORKERS = 4

E4_OUTPUT_DIR = os.path.join(ARTIFACTS_DIR, "E4_robustness")

E4B_BOUNDARY_COMBOS = [
    ("B01", 1.2, 0.0, 5), ("B02", 1.2, 0.0, 20), ("B03", 1.2, 0.5, 5),
    ("B04", 1.2, 0.5, 20), ("B05", 1.2, 1.0, 50), ("B06", 1.2, 0.1, 10),
    ("B07", 6.0, 0.0, 5), ("B08", 6.0, 0.0, 20), ("B09", 6.0, 0.5, 7),
    ("B10", 6.0, 0.5, 50), ("B11", 6.0, 1.0, 20), ("B12", 6.0, 0.1, 10),
    ("B13", 2.5, 0.0, 5), ("B14", 2.5, 0.0, 50), ("B15", 2.5, 0.5, 50),
    ("B16", 2.5, 1.0, 5), ("B17", 1.5, 0.0, 10), ("B18", 4.0, 0.0, 20),
    ("B19", 2.0, 0.1, 50), ("B20", 4.0, 1.0, 5),
]
E4C_OFFGRID_COMBOS = [
    ("O01", 1.8, 0.3, 12), ("O02", 3.3, 0.7, 15), ("O03", 5.5, 0.2, 30),
    ("O04", 1.3, 0.9, 8), ("O05", 4.7, 0.4, 25), ("O06", 2.2, 0.0, 6),
    ("O07", 5.8, 0.8, 45), ("O08", 1.6, 0.05, 50), ("O09", 3.8, 0.95, 5),
    ("O10", 2.8, 0.6, 18), ("O11", 4.4, 0.15, 35), ("O12", 1.25, 0.25, 7),
    ("O13", 5.9, 0.75, 20), ("O14", 3.6, 0.35, 10),
]

FIELDS = [
    "combo_id", "beta", "eta", "gamma", "gamma_over_eta", "n",
    "repeat_id", "delta",
    "beta_hat", "eta_hat", "gamma_hat", "r_squared", "converged",
    "time_ms", "status",
]


def process_combo_serial(combo_id, beta, gamma_over_eta, n, repeats):
    """Process one combo, return list of row dicts."""
    gamma = gamma_over_eta * ETA
    rows = []
    for rid in range(repeats):
        sample = generate_sample(beta, ETA, gamma, n, rid, seed=SEED_NAMESPACE)
        mdm = MDM(sample)
        for delta in DELTA_GRID:
            row = {
                "combo_id": combo_id,
                "beta": beta, "eta": ETA, "gamma": gamma,
                "gamma_over_eta": gamma_over_eta, "n": n,
                "repeat_id": rid, "delta": delta,
                "beta_hat": None, "eta_hat": None, "gamma_hat": None,
                "r_squared": None, "converged": False,
                "time_ms": 0.0, "status": "failure",
            }
            try:
                t0 = time.perf_counter()
                result = mdm.run(offset=delta)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                bh, eh, gh, r2, conv = result
                row["beta_hat"] = bh
                row["eta_hat"] = eh
                row["gamma_hat"] = gh
                row["r_squared"] = r2
                row["converged"] = bool(conv)
                row["time_ms"] = elapsed_ms
                row["status"] = "success" if conv and bh > 0 and eh > 0 else "failure"
            except Exception as e:
                row["status"] = f"error:{type(e).__name__}"
            rows.append(row)
    return rows


def worker_main(worker_id, all_combos):
    """Run as a worker process — handle a subset of combos."""
    os.makedirs(E4_OUTPUT_DIR, exist_ok=True)

    # Split combos among workers
    my_combos = [c for i, c in enumerate(all_combos) if i % N_WORKERS == worker_id]
    chunk_path = os.path.join(E4_OUTPUT_DIR, f"chunk_{worker_id:02d}.csv")

    total_calls = sum(R_FORMAL * len(DELTA_GRID) for _ in my_combos)
    print(f"[Worker {worker_id}] {len(my_combos)} combos, ~{total_calls:,} calls", flush=True)

    t0 = time.time()
    with open(chunk_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()

        for ci, (combo_id, beta, goe, n) in enumerate(my_combos):
            combo_t0 = time.time()
            rows = process_combo_serial(combo_id, beta, goe, n, R_FORMAL)
            for row in rows:
                writer.writerow(row)
            f.flush()
            combo_elapsed = time.time() - combo_t0
            total_elapsed = time.time() - t0
            print(f"[Worker {worker_id}] {combo_id} (beta={beta}, goe={goe}, n={n}) "
                  f"done in {combo_elapsed:.1f}s "
                  f"({ci+1}/{len(my_combos)}, total {total_elapsed:.0f}s)", flush=True)

    print(f"[Worker {worker_id}] COMPLETE in {time.time()-t0:.1f}s", flush=True)


def merge_chunks():
    """Merge all chunk files into boundary_risk_curves.csv and offgrid_risk_curves.csv."""
    import pandas as pd

    chunks = []
    for i in range(N_WORKERS):
        chunk_path = os.path.join(E4_OUTPUT_DIR, f"chunk_{i:02d}.csv")
        if os.path.exists(chunk_path):
            df = pd.read_csv(chunk_path)
            chunks.append(df)
            print(f"  Loaded chunk_{i:02d}.csv: {len(df)} rows")

    if not chunks:
        print("ERROR: No chunk files found!")
        return

    df_all = pd.concat(chunks, ignore_index=True)

    # Split by combo_id prefix
    boundary_ids = {c[0] for c in E4B_BOUNDARY_COMBOS}
    offgrid_ids = {c[0] for c in E4C_OFFGRID_COMBOS}

    df_boundary = df_all[df_all['combo_id'].isin(boundary_ids)].copy()
    df_offgrid = df_all[df_all['combo_id'].isin(offgrid_ids)].copy()

    boundary_path = os.path.join(E4_OUTPUT_DIR, "boundary_risk_curves.csv")
    offgrid_path = os.path.join(E4_OUTPUT_DIR, "offgrid_risk_curves.csv")

    df_boundary.to_csv(boundary_path, index=False)
    df_offgrid.to_csv(offgrid_path, index=False)

    print(f"\nMerged:")
    print(f"  Boundary: {len(df_boundary)} rows -> {boundary_path}")
    print(f"  Off-grid: {len(df_offgrid)} rows -> {offgrid_path}")
    print(f"  Boundary non-success: {(df_boundary['status']!='success').mean():.4f}")
    print(f"  Off-grid non-success: {(df_offgrid['status']!='success').mean():.4f}")

    # Clean up chunks
    for i in range(N_WORKERS):
        chunk_path = os.path.join(E4_OUTPUT_DIR, f"chunk_{i:02d}.csv")
        if os.path.exists(chunk_path):
            os.remove(chunk_path)
            print(f"  Removed chunk_{i:02d}.csv")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', type=int, default=None,
                        help='Run as worker N (0-3)')
    args = parser.parse_args()

    all_combos = E4B_BOUNDARY_COMBOS + E4C_OFFGRID_COMBOS

    if args.worker is not None:
        # Worker mode
        worker_main(args.worker, all_combos)
        return

    # Orchestrator mode
    import subprocess

    os.makedirs(E4_OUTPUT_DIR, exist_ok=True)

    print("=" * 70)
    print("Study/01 Formal E4 — MC Data Generation (subprocess-parallel)")
    print(f"Started: {now_iso()}")
    print(f"Workers: {N_WORKERS}")
    print(f"Total combos: {len(all_combos)} "
          f"({len(E4B_BOUNDARY_COMBOS)} boundary + {len(E4C_OFFGRID_COMBOS)} offgrid)")
    total_calls = len(all_combos) * R_FORMAL * len(DELTA_GRID)
    print(f"Total MDM calls: {total_calls:,}")
    print("=" * 70)

    script_path = os.path.abspath(__file__)
    t0 = time.time()

    # Spawn worker processes
    procs = []
    for wid in range(N_WORKERS):
        p = subprocess.Popen(
            [sys.executable, script_path, '--worker', str(wid)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=PROJECT_ROOT,
        )
        procs.append(p)
        print(f"Started worker {wid} (PID {p.pid})")

    # Wait for all workers and stream output
    for wid, p in enumerate(procs):
        p.wait()
        elapsed = time.time() - t0
        print(f"Worker {wid} finished (exit={p.returncode}, {elapsed:.0f}s elapsed)")
        # Print worker output
        if p.stdout:
            output = p.stdout.read().decode('utf-8', errors='replace')
            for line in output.strip().split('\n')[-5:]:  # last 5 lines
                print(f"  [W{wid}] {line}")

    total_elapsed = time.time() - t0
    print(f"\nAll workers done in {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")

    # Merge chunks
    print("\nMerging chunks...")
    merge_chunks()

    print(f"\n{'='*70}")
    print(f"MC GENERATION COMPLETE")
    print(f"Total elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
