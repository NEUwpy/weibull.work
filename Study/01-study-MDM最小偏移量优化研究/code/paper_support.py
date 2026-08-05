"""
Study/01 paper-evidence shared support (B1 unseen-beta / B2 traditional ref / B3 quantiles).

Reuses the sealed E6 Dimensional-RAW specialist pipeline for data loading,
raw-sample reconstruction, per-fold loss preparation, per-n MLP training and
selection evaluation (run_E6b_dimensional_raw_specialist).  Everything here is
a thin, reusable layer for the three support blocks; it does NOT rerun MDM and
does NOT reimplement the platform estimators.

Common helpers:
  - load_scan(): read the reused 160-combo MC scan (chunks), compute per-sample
    loss, rebuild the deterministic raw-sample map (same seed namespace).
  - default_and_l6(): per-sample Default (delta=0.1) loss and L6 hindsight loss
    / argmin delta from the 26-point grid.  These are fold-independent and are
    subset by test keys inside each block.
  - J1 / Bias / RMSE / MAE aggregations per the frozen Study01 contract.
  - provenance helpers: git metadata, code SHA256, LF-normalized SHA256SUMS.
"""

import hashlib
import json
import math
import os
import subprocess
import sys

import numpy as np
import pandas as pd

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")
for p in (STUDY_CODE_DIR, PYTHON_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import dim_raw_config as CFG
import run_E6b_dimensional_raw_specialist as E6

DELTA_GRID = list(CFG.DELTA_GRID)
DEFAULT_DELTA = CFG.DEFAULT_DELTA
SAMPLE_KEYS = E6.SAMPLE_KEYS
SEEDS = CFG.STABILITY_SEEDS

# Independent output roots under the sealed E6 artifact tree.
E6_DIR = os.path.join(STUDY_ROOT, "artifacts", "formal", "E6_dimensional_raw")
UNSEEN_BETA_DIR = os.path.join(E6_DIR, "unseen_beta")
TRADITIONAL_REF_DIR = os.path.join(E6_DIR, "traditional_ref")
QUANTILES_DIR = os.path.join(E6_DIR, "quantiles")
PAPER_DIR = os.path.join(E6_DIR, "paper")


# ============================================================
# Data loading (single shared entry for the three blocks)
# ============================================================

_scan_cache = None


def load_scan(verbose=True):
    """Load the reused 160-combo MC scan once, compute loss + raw sample map."""
    global _scan_cache
    if _scan_cache is not None:
        return _scan_cache
    if verbose:
        print("[paper-support] Loading MC scan chunks (reused 160-combo design)...")
    df_mc = E6.load_mc_scan()
    df_full = E6.compute_per_sample_loss(df_mc)
    raw_map, _ = E6.build_raw_sample_map(df_mc)
    _scan_cache = (df_mc, df_full, raw_map)
    return _scan_cache


def verify_design(df_full):
    """Fail-closed design check: 160 combos / 48,000 samples / 26 deltas."""
    expected_rows = 160 * 26 * CFG.REPEATS
    assert len(df_full) == expected_rows, f"rows {len(df_full)} != {expected_rows}"
    assert len(df_full[SAMPLE_KEYS].drop_duplicates()) == 48000
    assert sorted(df_full["delta"].unique()) == DELTA_GRID
    return True


# ============================================================
# Fold-independent per-sample Default / L6 baselines
# ============================================================

def default_and_l6(df_full):
    """Per-sample Default (delta=0.1) loss and L6 hindsight (argmin over grid).

    Returns a DataFrame with SAMPLE_KEYS plus:
      default_loss, l6_loss, l6_delta, default_valid, l6_valid.
    These baselines do not depend on any train/test fold.
    """
    d = df_full.copy()
    d["loss"] = d["loss"].astype(float)
    d["is_valid"] = (d.get("status", "success").eq("success")
                     & d["loss"].notna())
    default = d[d["delta"] == DEFAULT_DELTA][SAMPLE_KEYS + ["loss", "is_valid"]]
    default = default.rename(columns={"loss": "default_loss", "is_valid": "default_valid"})

    valid = d[d["loss"].notna()].copy()
    valid["l6_delta"] = valid.groupby(SAMPLE_KEYS)["delta"].transform("min")
    # argmin delta per sample (ties resolved by first occurrence in sorted grid)
    l6 = (valid.sort_values(SAMPLE_KEYS + ["delta"])
          .groupby(SAMPLE_KEYS, as_index=False)
          .apply(lambda g: g.loc[g["loss"].idxmin()], include_groups=False)
          .reset_index(drop=True))
    l6 = l6[SAMPLE_KEYS + ["loss", "delta"]].rename(
        columns={"loss": "l6_loss", "delta": "l6_delta"})
    l6["l6_valid"] = True

    out = default.merge(l6, on=SAMPLE_KEYS, how="outer")
    n_expected = d[SAMPLE_KEYS].drop_duplicates().shape[0]
    assert len(out) == n_expected, f"baseline rows {len(out)} != {n_expected}"
    return out


# ============================================================
# Metric aggregation (frozen Study01 contract)
# ============================================================

def j1_from_loss(loss_series):
    loss = pd.to_numeric(loss_series, errors="coerce").dropna()
    return math.sqrt(float(loss.mean()))


def failure_rate_from_valid(valid_series):
    v = pd.to_numeric(valid_series, errors="coerce")
    if v.empty:
        return float("nan")
    return float(1.0 - v.astype(bool).mean())


def per_n_breakdown(df, loss_col="true_loss", valid_col="is_valid"):
    rows = {}
    for n_val, g in df.groupby("n"):
        rows[int(n_val)] = {
            "J1": j1_from_loss(g[loss_col]),
            "failure_rate": failure_rate_from_valid(g[valid_col]),
            "n_samples": int(len(g)),
        }
    return rows


def param_bias_rmse_mae(df, beta_true_col="beta", eta_true_col="eta",
                        gamma_true_col="gamma"):
    """Bias/RMSE/MAE per parameter (absolute errors on the passed rows).

    The caller decides the row set (all-sample vs complete-case).  Errors are
    absolute in the parameter's own units, matching the Study01 per-parameter
    Bias/RMSE convention.
    """
    out = {}
    for name, true_col, hat_col in (
            ("beta", beta_true_col, "beta_hat"),
            ("eta", eta_true_col, "eta_hat"),
            ("gamma", gamma_true_col, "gamma_hat")):
        err = (df[hat_col] - df[true_col]).astype(float)
        out[name] = {
            "bias": float(err.mean()),
            "rmse": float(math.sqrt((err ** 2).mean())),
            "mae": float(err.abs().mean()),
        }
    return out


# ============================================================
# Provenance helpers
# ============================================================

def git_meta():
    def run(args):
        try:
            return subprocess.check_output(args, cwd=PROJECT_ROOT,
                                           stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return ""
    return {"git_commit": run(["git", "rev-parse", "HEAD"]),
            "git_commit_short": run(["git", "rev-parse", "--short", "HEAD"]),
            "git_branch": run(["git", "branch", "--show-current"]),
            "workspace_dirty": bool(run(["git", "status", "--short"]))}


def sha256_file_lf(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        prev = b""
        while True:
            block = f.read(1 << 20)
            if not block:
                break
            data = prev + block
            data = data.replace(b"\r\n", b"\n")
            prev = data[-1:] if data.endswith(b"\r") else b""
            h.update(data[:-1] if prev else data)
        if prev:
            h.update(prev)
    return h.hexdigest()


def code_sha256(*modules):
    """Per-file SHA256 for the entry script and its material dependencies.

    Returns {basename: sha256} so a manifest's `code_sha256` binds the exact
    committed content of every script that produced the artifacts.  Callers
    pass the entry module first, then each imported material dependency.
    """
    digests = {}
    for m in modules:
        p = os.path.abspath(m.__file__)
        digests[os.path.basename(p)] = sha256_file_lf(p)
    return {k: digests[k] for k in sorted(digests)}


def git_check_ignore(abs_path):
    """True when `abs_path` matches a .gitignore rule (local-only file)."""
    try:
        r = subprocess.run(["git", "check-ignore", "-q", abs_path],
                           cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def write_sha256sums(out_dir, exclude_endings=(".gitignore",)):
    """Split LF-normalized checksum ledgers for an output dir.

    - `SHA256SUMS`             covers only files that are NOT gitignored, so a
                               fresh clone can verify the tracked package.
    - `SHA256SUMS.local_not_in_git` covers gitignored/local-only raw files
                               (explicitly labeled; not part of the tracked
                               package).

    Returns (n_tracked, n_local).
    """
    tracked, local = [], []
    for root, _, files in os.walk(out_dir):
        for fn in files:
            if fn in ("SHA256SUMS", "SHA256SUMS.local_not_in_git"):
                continue
            if fn.endswith(exclude_endings):
                continue
            if fn.endswith((".log", ".err", "run_log.txt")):
                continue
            abs_path = os.path.join(root, fn)
            rel = os.path.relpath(abs_path, out_dir).replace(os.sep, "/")
            h = sha256_file_lf(abs_path)
            (local if git_check_ignore(abs_path) else tracked).append((rel, h))

    def _write(name, entries):
        entries = sorted(entries, key=lambda e: e[0])
        content = "".join(f"{h}  {p}\n" for p, h in entries)
        with open(os.path.join(out_dir, name), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(content)
        return len(entries)

    n_tracked = _write("SHA256SUMS", tracked)
    n_local = _write("SHA256SUMS.local_not_in_git", local)
    return n_tracked, n_local


def atomic_write_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def lf_normalize(path):
    with open(path, "rb") as f:
        data = f.read()
    if b"\r\n" in data:
        with open(path, "wb") as f:
            f.write(data.replace(b"\r\n", b"\n"))


if __name__ == "__main__":
    print("paper_support: import-only module (no main)")
