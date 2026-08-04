"""Engineering-life quantile derivation from sealed P4 per-sample estimates.

Reads artifacts/formal/p4_formal_compare/evaluation_all.csv (read-only) and
derives x_0.90 / x_0.95 / x_0.99 relative errors from the per-sample three-
parameter estimates (beta_hat, eta_hat, gamma_hat). No estimator is re-run.

Conventions mirror the P4 evaluation layer:
- one row per (track, method, fold, seed, sample);
- model-first aggregation: per-(fold, seed) model metrics, then a distribution
  across the 15 (5 folds x 3 seeds) models (median/mean/SD/min/max/quartiles);
- complete-case basis (all scoped methods have 0.0% failures on every track);
- J1 (from P4 result_tables.json) vs quantile-error ranking comparison.

Method scope and quantile levels come from quantile_config.py. MLE is excluded
(sealed-not-consumed; the only method with failures). Direct-MLP is tagged
research-only.

Run:  python code/run_quantile_derivation.py
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

_PYTHON_DIR = Path(__file__).resolve().parents[3] / "python"
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))

import quantile_config as cfg
from studies.common.metrics import quantile_true

_METRICS = ("bias", "rmse", "mae", "p95_abs")

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
            cwd=_CODE_DIR.parents[1],
        ).stdout.strip()
    except Exception:
        return "unknown"


def worktree_dirty() -> bool:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, check=True,
            cwd=_CODE_DIR.parents[1],
        ).stdout
        return bool(out.strip())
    except Exception:
        return True


def model_metrics(e: np.ndarray) -> dict:
    """Per-model quantile-error metrics over signed relative errors."""
    a = np.abs(e)
    return {
        "bias": float(np.mean(e)),
        "rmse": float(np.sqrt(np.mean(e**2))),
        "mae": float(np.mean(a)),
        "p95_abs": float(np.percentile(a, 95)),
        "n": int(len(e)),
    }


def aggregate_models(values: np.ndarray) -> dict:
    """Model-first aggregation of one metric across (fold, seed) models."""
    if len(values) == 0:
        return {"n_models": 0}
    return {
        "n_models": int(len(values)),
        "min": float(np.min(values)),
        "q1": float(np.percentile(values, 25)),
        "median": float(np.median(values)),
        "q3": float(np.percentile(values, 75)),
        "max": float(np.max(values)),
        "mean": float(np.mean(values)),
        "sd": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
    }


def per_model_metrics(long_df: pd.DataFrame, group_keys: list) -> pd.DataFrame:
    """Per-model metric rows, grouped by group_keys (must end with fold, seed)."""
    rows = []
    for keys, g in long_df.groupby(group_keys):
        keys = keys if isinstance(keys, tuple) else (keys,)
        e = g["rel_err"].to_numpy(dtype=float)
        m = model_metrics(e)
        rows.append({**dict(zip(group_keys, keys)), **m})
    return pd.DataFrame(rows)


def build_quantile_long(eval_all: pd.DataFrame) -> pd.DataFrame:
    """Vectorized per-sample signed relative quantile errors for each R."""
    scoped = eval_all[eval_all["method"].isin(cfg.METHOD_SCOPE)].copy()
    failed = scoped[scoped["failed"].astype(str).str.lower() == "true"]
    if len(failed) > 0:
        raise RuntimeError(
            f"scoped rows with failed=True: {len(failed)} "
            "(failure-free contract violated; complete-case basis undefined)"
        )
    beta = scoped["beta"].astype(float).to_numpy()
    gamma_over_eta = scoped["gamma_over_eta"].astype(float).to_numpy()
    beta_hat = scoped["beta_hat"].astype(float).to_numpy()
    eta_hat = scoped["eta_hat"].astype(float).to_numpy()
    gamma_hat = scoped["gamma_hat"].astype(float).to_numpy()

    frames = []
    for R in cfg.QUANTILE_LEVELS:
        df = scoped.copy()
        df["R"] = R
        ln = -np.log(R)
        # true quantile with eta = 1 (grid normalization), gamma = gamma_over_eta
        df["x_true"] = gamma_over_eta + 1.0 * ln ** (1.0 / beta)
        with np.errstate(invalid="ignore", divide="ignore"):
            x_hat = np.where(
                beta_hat > 0.0,
                gamma_hat + eta_hat * ln ** (1.0 / beta_hat),
                np.nan,
            )
        df["x_hat"] = x_hat
        df["rel_err"] = (df["x_hat"] - df["x_true"]) / df["x_true"]
        df["abs_rel_err"] = df["rel_err"].abs()
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main() -> int:
    t0 = time.time()
    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    eval_all = pd.read_csv(cfg.P4_INPUT_CSV, low_memory=False)
    result_tables = json.loads(cfg.P4_RESULT_TABLES.read_text(encoding="utf-8"))

    long_df = build_quantile_long(eval_all)

    # per-model metrics (track x method x R x fold x seed)
    model_df = per_model_metrics(long_df, ["track", "method", "R", "fold", "seed"])

    # model-first summary per (track, method, R)
    summary = {}
    for (track, method, R), g in model_df.groupby(["track", "method", "R"]):
        summary.setdefault(track, {}).setdefault(method, {})[float(R)] = {
            m: aggregate_models(g[m].to_numpy(dtype=float)) for m in _METRICS
        }
        src = eval_all[(eval_all["track"] == track) & (eval_all["method"] == method)]
        summary[track][method][float(R)]["failure_rate"] = 0.0
        summary[track][method][float(R)]["n_valid"] = int(
            src.groupby(["fold", "seed"]).size().max() if len(src) else 0
        )

    # stratification by n and by beta (per-model per stratum, then aggregate)
    strat_n, strat_beta = {}, {}
    for axis, target in (("n", strat_n), ("beta", strat_beta)):
        pm = per_model_metrics(long_df, ["track", "method", "R", axis, "fold", "seed"])
        for (track, method, R, stratum), g in pm.groupby(["track", "method", "R", axis]):
            target.setdefault(track, {}).setdefault(method, {})[str(float(stratum))] = {
                m: aggregate_models(g[m].to_numpy(dtype=float)) for m in _METRICS
            }

    # ranking comparison: median_J1 vs median x_0.95 RMSE per track
    ranking_rows = []
    for track in result_tables:
        j1 = {
            m: result_tables[track]["methods"][m]["j1_summary"]["median_J1"]
            for m in result_tables[track]["methods"]
            if m in cfg.METHOD_SCOPE
        }
        q_rmse = {
            m: summary[track][m][cfg.MAIN_QUANTILE_LEVEL]["rmse"]["median"]
            for m in j1
        }
        for m in j1:
            ranking_rows.append(
                {
                    "track": track,
                    "method": m,
                    "median_J1": j1[m],
                    "J1_rank": 1 + sum(1 for o in j1 if j1[o] < j1[m]),
                    "median_x095_rmse": q_rmse[m],
                    "quantile_rank": 1
                    + sum(1 for o in q_rmse if q_rmse[o] < q_rmse[m]),
                    "paper_role": cfg.METHOD_SCOPE[m],
                }
            )
    ranking = pd.DataFrame(ranking_rows)

    # ---- write outputs ------------------------------------------------ #
    model_df.to_csv(cfg.OUTPUT_DIR / "model_metrics.csv", index=False)
    ranking.to_csv(cfg.OUTPUT_DIR / "ranking_comparison.csv", index=False)
    payload = {
        "quantile_levels": list(cfg.QUANTILE_LEVELS),
        "main_quantile_level": cfg.MAIN_QUANTILE_LEVEL,
        "method_scope": cfg.METHOD_SCOPE,
        "failure_handling": (
            "complete-case; all scoped methods have 0.0% failures on every "
            "track, so complete case == full sample; failure_rate/n_valid "
            "reported per method"
        ),
        "aggregation": "model-first over 15 (5 folds x 3 seeds) models",
        "summary": summary,
        "stratification_by_n": strat_n,
        "stratification_by_beta": strat_beta,
    }
    (cfg.OUTPUT_DIR / "summary_quantile.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    out_files = ["model_metrics.csv", "ranking_comparison.csv", "summary_quantile.json"]
    manifest = {
        "manifest_version": "study01-quantile-derivation-v1",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000"),
        "git_commit": git_commit(),
        "worktree_dirty": worktree_dirty(),
        "script_sha256": sha256_file(Path(__file__)),
        "config_sha256": sha256_file(_CODE_DIR / "quantile_config.py"),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "input_sha256": {
            "evaluation_all.csv": sha256_file(cfg.P4_INPUT_CSV),
            "result_tables.json": sha256_file(cfg.P4_RESULT_TABLES),
        },
        "tracks": sorted(eval_all["track"].unique()),
        "methods": cfg.METHOD_SCOPE,
        "quantile_levels": list(cfg.QUANTILE_LEVELS),
        "main_quantile_level": cfg.MAIN_QUANTILE_LEVEL,
        "failure_handling": payload["failure_handling"],
        "aggregation": payload["aggregation"],
        "output_sha256": {f: sha256_file(cfg.OUTPUT_DIR / f) for f in out_files},
        "output_dir": str(cfg.OUTPUT_DIR),
    }
    (cfg.OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sums = [f"{sha256_file(cfg.OUTPUT_DIR / f)}  {f}" for f in sorted(out_files + ["manifest.json"])]
    (cfg.OUTPUT_DIR / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    (cfg.OUTPUT_DIR / "run_log.txt").write_text(
        "\n".join(
            [
                f"started_at: {datetime.now(timezone.utc).isoformat()}",
                f"duration_sec: {time.time() - t0:.1f}",
                f"input_rows: {len(eval_all)}",
                f"scoped_rows: {len(eval_all[eval_all['method'].isin(cfg.METHOD_SCOPE)])}",
                f"long_rows: {len(long_df)}",
                f"output_dir: {cfg.OUTPUT_DIR}",
                f"methods: {sorted(cfg.METHOD_SCOPE)}",
                f"quantile_levels: {cfg.QUANTILE_LEVELS}",
                f"git_commit: {manifest['git_commit']}",
                f"worktree_dirty: {manifest['worktree_dirty']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"done in {time.time()-t0:.1f}s -> {cfg.OUTPUT_DIR}")
    print(f"model_metrics rows: {len(model_df)}; ranking rows: {len(ranking)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
