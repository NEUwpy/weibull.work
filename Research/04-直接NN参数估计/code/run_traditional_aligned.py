"""Add production WMLE/LSE to the existing Research04 test protocol.

Reuse deterministic samples, status checks, and summaries. Historical neural
results are read from their sealed summaries, not retrained or reconstructed.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import multiprocessing as mp
import os
from pathlib import Path
import subprocess
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
ROOT = Path(__file__).resolve().parents[3]
RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import numpy as np
import pandas as pd
from studies.common.sample import generate_sample
from studies.common.runner import run_method

SOURCE = RESEARCH / "artifacts/study01_aligned_generalization_v1"
KEYS = ["beta", "gamma_over_eta", "n", "repeat_id"]
METHODS = ("WMLE", "LSE")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def estimate_pair(task):
    beta, ratio, n, repeat, eta, namespace = task
    sample = generate_sample(float(beta), float(eta), float(ratio * eta),
                             int(n), int(repeat), seed=namespace)
    return task, sample, [run_method(method.lower(), sample) for method in METHODS]


def validate(frame, expected_samples):
    if len(frame) != expected_samples * len(METHODS):
        raise ValueError("wrong result count")
    if frame.duplicated(["method", *KEYS]).any():
        raise ValueError("duplicate method/sample keys")
    sets = [set(map(tuple, frame.loc[frame.method.eq(m), KEYS].to_numpy()))
            for m in METHODS]
    if any(len(keys) != expected_samples for keys in sets) or sets[0] != sets[1]:
        raise ValueError("methods do not share the full sample set")
    if not np.isfinite(frame.loss_primary).all():
        raise ValueError("nonfinite primary loss")
    failed = frame.status.ne("success")
    if frame.loc[failed, "failure_reason"].fillna("").eq("").any():
        raise ValueError("failure without reason")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["smoke", "formal"], required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("use one to four workers")
    import run_study01_aligned_generalization as base
    from analyze_study01_aligned_generalization import summarize
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    design = manifest["test_design"]
    penalty = max(row["failure_penalty"] for row in manifest["model_training"].values())
    # The formal source runner uses the MAX across n, not a separate penalty per n.
    repeats = 2 if args.mode == "smoke" else design["repeats"]
    output = RESEARCH / "artifacts" / ("smoke/traditional_aligned_v1" if args.mode == "smoke"
                                        else "traditional_aligned_v1")
    if output.exists():
        raise FileExistsError(f"preserve existing run: {output}")
    sources = [Path(__file__), Path(base.__file__),
               Path(sys.modules["analyze_study01_aligned_generalization"].__file__),
               SOURCE / "manifest.json", SOURCE / "analysis/domain_summary.csv",
               SOURCE / "analysis/overall_summary.csv"]
    sources += list((ROOT / "python/methods").glob("*.py"))
    sources += list((ROOT / "python/studies/common").glob("*.py"))
    hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in sources if p.exists()}
    output.mkdir(parents=True)
    (output / ".gitignore").write_text("per_sample_results.csv.gz\n*.tmp\n", encoding="utf-8")
    tasks = [(float(b), float(g), int(n), int(r), float(design["eta"]), design["seed_namespace"])
             for b, g, n, r in itertools.product(design["beta"], design["gamma_over_eta"],
                                                design["n"], range(repeats))]
    rows = []
    started = time.perf_counter()
    with mp.Pool(args.workers) as pool:
        for i, (task, sample, estimates) in enumerate(pool.imap(estimate_pair, tasks, chunksize=16), 1):
            b, g, n, r, _, _ = task
            for method, estimate in zip(METHODS, estimates):
                row = base.result_row(method, b, g, n, r, sample,
                                      estimate.get("beta_hat"), estimate.get("eta_hat"),
                                      estimate.get("gamma_hat"), bool(estimate.get("converged")),
                                      base._failure_reason(estimate), None, penalty)
                if row["status"] != "success" and not row["failure_reason"]:
                    row["failure_reason"] = "shared_parameter_or_support_check"
                row["sample_sha256"] = hashlib.sha256(np.round(sample, 12).tobytes()).hexdigest()
                rows.append(row)
            if i % 3000 == 0 or i == len(tasks):
                print(f"{i}/{len(tasks)} samples, {time.perf_counter()-started:.1f}s", flush=True)
    frame = pd.DataFrame(rows)
    validate(frame, len(tasks))
    temp = output / "per_sample_results.tmp"
    frame.to_csv(temp, index=False, compression="gzip")
    temp.replace(output / "per_sample_results.csv.gz")
    for name, groups in [("overall", ["method"]), ("domain", ["method", "beta_group"]),
                         ("n", ["method", "n"]), ("beta", ["method", "beta"]),
                         ("cell", ["method", "beta", "gamma_over_eta", "n"])]:
        summary = summarize(frame, groups)
        summary.to_csv(output / f"{name}_summary.csv", index=False)
        old = SOURCE / "analysis" / f"{name}_summary.csv"
        if args.mode == "formal" and old.exists():
            pd.concat([pd.read_csv(old), summary], ignore_index=True).to_csv(
                output / f"combined_{name}_summary.csv", index=False)
    frame.loc[frame.status.ne("success")].groupby(["method", "failure_reason"]).size().rename(
        "count").reset_index().to_csv(output / "failure_reasons.csv", index=False)
    if any(sha(ROOT / p) != h for p, h in hashes.items()):
        raise RuntimeError("source changed during execution")
    run = {
        "status": "complete", "mode": args.mode, "test_design": {**design, "repeats": repeats},
        "n_samples": len(tasks), "n_rows": len(frame), "methods": METHODS,
        "failure_penalty": penalty, "failure_policy": "same shared status and global training-P99 maximum as source run",
        "standard_metrics": "successful estimates only; failure rate reported separately",
        "source_hashes": hashes, "code_base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "command": [sys.executable, *sys.argv], "elapsed_seconds": time.perf_counter()-started,
        "workers": args.workers, "historical_rows_available": (SOURCE / "per_sample_results.csv.gz").exists(),
        "comparison": "old methods use sealed summaries; no new cross-method paired CI is claimed",
    }
    (output / "manifest.json").write_text(json.dumps(run, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(summarize(frame, ["method"])[["method", "n_total", "failure_rate", "J1"]].to_string(index=False))
    print(f"COMPLETE {output}", flush=True)


if __name__ == "__main__":
    main()
