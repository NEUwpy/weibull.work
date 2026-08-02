"""Top-level run manifest finalizer for the incremental B run.

Aggregates training/eval/analysis manifests plus frozen-matrix metadata into a
single run manifest, records input checkpoint fingerprints, dataset/fit counts,
elapsed times, output hashes and the normalized sequential workload estimate.

Usage:
    python -m study02b_inc.finalize --run-dir <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))

from study02b_inc import config as C
from study02b_inc import models as M


def _git_tip() -> str:
    import subprocess
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                       cwd=str(C.REPO_ROOT), timeout=5)
    return r.stdout.strip() or "unknown"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _normalized_workload() -> dict:
    """Sequential-equivalent hours from frozen matrix + measured throughput.

    Measured baseline (bench_inc.py + pilot on this machine, single-threaded):
      - P fit   ~110 s, D fit ~45 s, Dctrl fit ~75 s (train, real path)
      - eval (all 6 routes) ~0.132 s per dataset
    These are the observed sequential throughputs used to size the matrix.
    """
    n_missing = C.N_MISSING
    train_s = (len(n_missing) * len(C.P_FIT_SEEDS) * 110.0
               + len(n_missing) * len(C.D_FIT_SEEDS) * 45.0
               + len(n_missing) * len(C.DCTRL_FIT_SEEDS) * 75.0)
    core_rows = len(C.N_VALUES) * C.CORE_N_CLUSTERS * C.CORE_N_REPLICATES
    n_grid = len(C.PG_BETA) * len(C.PG_RHO) * len(C.PG_N) * C.PG_DRAWS
    eta_sweep = (len(C.PG_ETA_SWEEP["beta"]) * len(C.PG_ETA_SWEEP["rho"])
                 * len(C.PG_ETA_SWEEP["n"]) * len(C.PG_ETA_SWEEP["eta"]) * C.PG_DRAWS)
    eval_s = (core_rows + n_grid + eta_sweep) * 0.132
    total_s = train_s + eval_s
    return {
        "training_fits": int(len(n_missing) * (
            len(C.P_FIT_SEEDS) + len(C.D_FIT_SEEDS) + len(C.DCTRL_FIT_SEEDS))),
        "core_datasets": int(core_rows),
        "grid_datasets": int(n_grid + eta_sweep),
        "train_seconds_est": round(train_s, 1),
        "eval_seconds_est": round(eval_s, 1),
        "total_seconds_est": round(total_s, 1),
        "total_hours_est": round(total_s / 3600.0, 1),
        "measurement_note": (
            "sequential-equivalent workload from bench_inc.py + pilot "
            "measured throughput (P 110s, D 45s, Dctrl 75s per fit; "
            "eval 0.132 s/dataset all-routes)")
    }


def finalize(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    train_mf = run_dir / "training" / "manifest.json"
    eval_mf = run_dir / "eval" / "manifest.json"
    analysis_mf = run_dir / "analysis" / "analysis_summary.json"

    def _load(p: Path):
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    tm = _load(train_mf)
    em = _load(eval_mf)
    am = _load(analysis_mf)

    # Input checkpoint fingerprints
    p_index = M.build_p_index(run_dir)
    d_index = M.build_d_index(run_dir)
    ts = M.d_target_stats(run_dir)

    def _index_fp(index, route_key=None):
        entries = []
        for n, group_map in sorted(index.items()):
            for g, lst in group_map.items():
                if route_key and g != route_key:
                    continue
                for e in lst:
                    entries.append(f"{n}:{g}:{e['seed']}:{e['sha256']}")
        return hashlib.sha256("\n".join(sorted(entries)).encode()).hexdigest()

    p_entries = []
    for n, lst in sorted(p_index.items()):
        for e in lst:
            p_entries.append(f"{n}:P:{e['seed']}:{e['sha256']}")

    result = {
        "version": "1.0",
        "run_id": run_dir.name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_tip": _git_tip(),
        "config_hash": C.CONFIG_HASH,
        "frozen_matrix": {
            "n_values": C.N_VALUES,
            "n_existing": C.N_EXISTING,
            "n_missing": C.N_MISSING,
            "fit_seeds": {"P": C.P_FIT_SEEDS, "D": C.D_FIT_SEEDS, "Dctrl": C.DCTRL_FIT_SEEDS},
            "seed_namespaces": {
                "P_train_param": C.P_PARAM_SEED_BASE, "P_sample_train": C.P_SAMPLE_NS_TRAIN,
                "P_sample_val": C.P_SAMPLE_NS_VAL,
                "D_train_param": "n*100+1", "D_sample_train": C.D_SAMPLE_NS_TRAIN,
                "D_sample_val": C.D_SAMPLE_NS_VAL,
                "core_test": C.CORE_SAMPLE_NS, "grid_test": C.PG_SAMPLE_NS,
            },
            "core": {"clusters": C.CORE_N_CLUSTERS, "replicates": C.CORE_N_REPLICATES,
                     "sobol_m": C.CORE_SOBOL_M},
            "param_grid": {"beta": C.PG_BETA, "rho": C.PG_RHO, "eta": C.PG_ETA,
                           "n": C.PG_N, "draws": C.PG_DRAWS},
        },
        "input_checkpoint_fingerprints": {
            "P_A_E1_and_inc_count": len(p_entries),
            "P_fingerprint": hashlib.sha256("\n".join(sorted(p_entries)).encode()).hexdigest(),
            "D_selected_count": sum(len(g.get("selected", [])) for g in d_index.values()),
            "Dctrl_count": sum(len(g.get("controlled", [])) for g in d_index.values()),
        },
        "training": tm,
        "evaluation": em,
        "analysis": None if am is None else {
            "analysis_summary_sha256": _sha(analysis_mf),
        },
        "normalized_workload_estimate": _normalized_workload(),
    }

    mf = run_dir / "manifest.json"
    mf.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Top-level manifest: {mf}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()
    finalize(Path(args.run_dir))


if __name__ == "__main__":
    main()
