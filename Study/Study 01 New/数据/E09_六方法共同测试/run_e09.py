"""Complete the six-method comparison on E05's frozen samples.

Run from repository root: python "Study/Study 01 New/数据/E09_六方法共同测试/run_e09.py"
The manuscript uses this 48-cell common-test design.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "python"))
from studies.common.sample import generate_sample  # noqa: E402
from studies.common.runner import run_method  # noqa: E402
from wmle_solver import run_wmle_checked

DATA = HERE.parent
E01 = DATA / "E01_固定偏移作用" / "候选扫描" / "mc_scan_raw.csv"
E05 = DATA / "E05_冻结模型独立测试" / "cells"
NAMESPACE = "study01_selector_confirmation_20260922_v1"
BETA = {1.5, 2.0, 3.0, 5.0}
RATIO = {0.1, 0.5, 1.0}
N = {7, 10, 15, 20}
KEYS = ["beta", "gamma_over_eta", "n", "repeat_id"]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def implementation_tag() -> str:
    files = ["python/studies/common/sample.py", "python/studies/common/runner.py",
             "python/methods/mdm.py", "python/methods/wmle.py",
             "python/methods/lse.py", "python/methods/j3_weights.tsv"]
    hashes = [sha(REPO / p) for p in files]
    hashes.extend([sha(HERE/'wmle_solver.py'), sha(HERE/'run_e09.py'),
                   sha(HERE/'fixed_choices.json')])
    return hashlib.sha256("|".join(hashes).encode()).hexdigest()


def validation_choices() -> dict[int, float]:
    """Select one fixed delta per n using only the 48-cell development scan."""
    pieces = []
    for chunk in pd.read_csv(E01, chunksize=100_000):
        part = chunk[chunk.beta.isin(BETA) & chunk.gamma_over_eta.isin(RATIO) & chunk.n.isin(N)].copy()
        if len(part):
            loss = ((part.beta_hat - part.beta) / part.beta) ** 2
            loss += ((part.eta_hat - part.eta) / part.eta) ** 2
            loss += ((part.gamma_hat - part.gamma) / part.eta) ** 2
            valid = part.converged.astype(str).str.lower().eq("true")
            valid &= np.isfinite(loss) & (part.beta_hat > 0) & (part.eta_hat > 0) & (part.gamma_hat >= 0)
            part["score"] = np.where(valid, loss, 3.0)
            pieces.append(part[[*KEYS, "delta", "score"]])
    scan = pd.concat(pieces, ignore_index=True)
    assert len(scan) == 48 * 300 * 26, len(scan)
    assert not scan.duplicated([*KEYS, "delta"]).any()
    curve = scan.groupby(["n", "delta"], as_index=False).score.agg(["mean", "count"])
    assert curve["count"].eq(3600).all()
    choices = {int(n): float(g.sort_values(["mean", "delta"]).iloc[0].delta)
               for n, g in curve.groupby("n")}
    HERE.mkdir(parents=True, exist_ok=True)
    curve.to_csv(HERE / "validation_curve.csv", index=False)
    (HERE / "fixed_choices.json").write_text(json.dumps(choices, indent=2) + "\n", encoding="utf-8")
    return choices


def evaluate_cell(cell_id: int, choice: dict[int, float]) -> tuple[int, int]:
    source = E05 / f"cell_{cell_id:03d}.csv"
    target = HERE / "cells" / f"cell_{cell_id:03d}.csv"
    marker = target.with_suffix(".version")
    version = implementation_tag()
    if target.exists() and marker.exists() and marker.read_text(encoding="utf-8") == version:
        old = pd.read_csv(target)
        assert len(old) == 400 and old.sample_sha256.nunique() == 100
        return cell_id, 0
    original = pd.read_csv(source)
    fixed = original[original.policy == "fixed_010"].sort_values("repeat_id")
    assert len(fixed) == 100 and fixed.repeat_id.tolist() == list(range(100))
    b, e, g, ratio, n = (float(fixed.iloc[0][x]) for x in ["beta", "eta", "gamma", "gamma_over_eta", "n"])
    n = int(n)
    assert b in BETA and ratio in RATIO and n in N
    rows = []
    for row in fixed.itertuples():
        sample = generate_sample(b, e, g, n, int(row.repeat_id), seed=NAMESPACE)
        sample_hash = hashlib.sha256(sample.astype("<f8").tobytes()).hexdigest()
        assert sample_hash == row.sample_sha256
        for label, method, kwargs in (
            ("MDM-0", "mdm", {"offset": 0.0, "gamma_steps": 60}),
            ("MDM-opt-n", "mdm", {"offset": choice[n], "gamma_steps": 60}),
            ("WMLE", "wmle", {}),
            ("LSE", "lse", {}),
        ):
            # Fixed conversion of hours to thousands of hours is part of the
            # traditional-method numerical protocol and uses no true parameter.
            input_sample = sample / 1000.0 if method in {"wmle", "lse"} else sample
            result = run_wmle_checked(input_sample) if method == 'wmle' else run_method(method, input_sample, **kwargs)
            bh, eh, gh = (result.get(x) for x in ("beta_hat", "eta_hat", "gamma_hat"))
            valid = bool(result.get("converged")) and all(v is not None and math.isfinite(v) for v in (bh, eh, gh))
            if valid and method in {"wmle", "lse"}:
                eh, gh = eh * 1000.0, gh * 1000.0
            valid = valid and bh > 0 and eh > 0 and gh >= 0
            extra = result.get("extra") or {}
            rows.append({"cell_id": cell_id, "beta": b, "eta": e, "gamma": g,
                         "gamma_over_eta": ratio, "n": n, "repeat_id": int(row.repeat_id),
                         "sample_sha256": sample_hash, "method": label,
                         "delta": 0.0 if label == "MDM-0" else choice[n] if label == "MDM-opt-n" else np.nan,
                         "beta_hat": bh if valid else np.nan, "eta_hat": eh if valid else np.nan,
                         "gamma_hat": gh if valid else np.nan, "valid": valid,
                         "failure_reason": "" if valid else str(extra.get("raw_status") or "not_converged")})
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    pd.DataFrame(rows).to_csv(temp, index=False)
    os.replace(temp, target)
    marker.write_text(version, encoding="utf-8")
    return cell_id, len(rows)


def collect() -> None:
    source = pd.concat((pd.read_csv(p) for p in sorted(E05.glob("cell_*.csv"))), ignore_index=True)
    source = source[source.beta.isin(BETA) & source.gamma_over_eta.isin(RATIO)]
    assert len(source) == 48 * 100 * 3
    source = source[source.policy.isin(["fixed_010", "frozen_final_seed1"])].copy()
    source["method"] = source.policy.map({"fixed_010": "MDM-0.1", "frozen_final_seed1": "AMDM"})
    source["failure_reason"] = np.where(source.valid, "", "E05_original_invalid")
    cols = ["cell_id", "beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id",
            "sample_sha256", "method", "delta", "beta_hat", "eta_hat", "gamma_hat", "valid", "failure_reason"]
    additions = pd.concat((pd.read_csv(p) for p in sorted((HERE / "cells").glob("cell_*.csv"))), ignore_index=True)
    assert len(additions) == 48 * 100 * 4
    df = pd.concat([source[cols], additions[cols]], ignore_index=True)
    assert len(df) == 48 * 100 * 6
    assert not df.duplicated(["cell_id", "repeat_id", "method"]).any()
    assert df.groupby(["cell_id", "repeat_id"]).sample_sha256.nunique().eq(1).all()
    df["valid"] = df.valid.astype(str).str.lower().eq("true")
    for name, denom in [("beta", df.beta), ("eta", df.eta), ("gamma", df.eta)]:
        df[f"err_{name}"] = (df[f"{name}_hat"] - df[name]) / denom
    df["squared_loss"] = df[["err_beta", "err_eta", "err_gamma"]].pow(2).sum(axis=1, min_count=3)
    df["score"] = np.where(df.valid, df.squared_loss, 3.0)
    df.to_csv(HERE / "per_sample.csv.gz", index=False, compression="gzip")
    groups = []
    for (method, n), part in df.groupby(["method", "n"]):
        valid = part[part.valid]
        out = {"method": method, "n": int(n), "samples": len(part),
               "failures": int((~part.valid).sum()), "failure_rate": float((~part.valid).mean()),
               "J1_failure3": float(np.sqrt(part.score.mean())),
               "J1_complete_case": float(np.sqrt(valid.squared_loss.mean()))}
        for p in ("beta", "eta", "gamma"):
            e = valid[f"err_{p}"]
            out[f"bias_{p}"] = float(e.mean())
            out[f"sd_{p}"] = float(e.std(ddof=1))
            out[f"rmse_{p}"] = float(np.sqrt(e.pow(2).mean()))
            out[f"mae_{p}"] = float(e.abs().mean())
        groups.append(out)
    pd.DataFrame(groups).to_csv(HERE / "by_n.csv", index=False)
    pooled = []
    for method, part in df.groupby("method"):
        valid = part[part.valid]
        pooled.append({"method": method, "samples": len(part), "failures": int((~part.valid).sum()),
                       "failure_rate": float((~part.valid).mean()),
                       "J1_failure3": float(np.sqrt(part.score.mean())),
                       "J1_complete_case": float(np.sqrt(valid.squared_loss.mean()))})
    pd.DataFrame(pooled).to_csv(HERE / "pooled.csv", index=False)
    pooled_params = []
    for method, part in df.groupby("method"):
        valid = part[part.valid]
        item = {"method": method, "valid_samples": len(valid)}
        for p in ("beta", "eta", "gamma"):
            err = valid[f"err_{p}"]
            item[f"bias_{p}"] = float(err.mean())
            item[f"sd_{p}"] = float(err.std(ddof=1))
            item[f"rmse_{p}"] = float(np.sqrt(err.pow(2).mean()))
            item[f"mae_{p}"] = float(err.abs().mean())
        pooled_params.append(item)
    pd.DataFrame(pooled_params).to_csv(HERE / "pooled_parameter_metrics.csv", index=False)
    manifest = {"status": "completed", "design_status": "48-cell common test adopted for current manuscript on 2026-09-23",
                "evaluation": "same 4800 E05 samples; valid-row normalized parameter bias/SD/RMSE/MAE; failures reported and assigned joint squared score 3",
                "test_status": "reused E05 test outcomes; not a never-seen test to this project",
                "validation": "E01 full 300 repeats per selected cell, independent of E05 sample namespace",
                "source_hashes": {str(p.relative_to(REPO)): sha(p) for p in [E01, DATA / "E05_冻结模型独立测试" / "contract.json",
                    REPO / "python/studies/common/sample.py", REPO / "python/methods/mdm.py",
                    REPO / "python/studies/common/runner.py", REPO / "python/methods/wmle.py",
                    REPO / "python/methods/lse.py", REPO / "python/methods/j3_weights.tsv",
                    HERE/'wmle_solver.py', HERE/'run_e09.py']},
                "output_hashes": {p.name: sha(p) for p in [HERE / "fixed_choices.json", HERE / "validation_curve.csv", HERE / "per_sample.csv.gz", HERE / "by_n.csv", HERE / "pooled.csv", HERE / "pooled_parameter_metrics.csv"]}}
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    choice = validation_choices()
    print("frozen fixed choices", choice, flush=True)
    selected = []
    for i, path in enumerate(sorted(E05.glob("cell_*.csv"))):
        first = pd.read_csv(path, nrows=1).iloc[0]
        if float(first.beta) in BETA and float(first.gamma_over_eta) in RATIO:
            selected.append(i)
    assert len(selected) == 48, len(selected)
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(evaluate_cell, i, choice) for i in selected]
        for k, future in enumerate(as_completed(futures), 1):
            cell, rows = future.result()
            print(f"{k}/48 cell {cell:03d}: {rows} new rows", flush=True)
    collect()
    print((HERE / "pooled.csv").read_text(encoding="utf-8"), flush=True)


if __name__ == "__main__":
    main()
