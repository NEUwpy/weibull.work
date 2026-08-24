"""Check whether the frozen L6 grid is truncated at delta=0.50.

This is a bounded diagnostic, not a new selector experiment.  It reuses the
48,000 frozen Study01 samples and evaluates delta=0.52,...,1.00 only for
samples whose realised loss is still decreasing from 0.48 to 0.50.  The
production sample generator, MDM implementation and Study01 loss are reused.

Outputs are written under artifacts/candidate/E12_delta_upper_boundary/.
They do not replace the frozen 0.00--0.50 results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
STUDY_ROOT = HERE.parent
REPO_ROOT = STUDY_ROOT.parents[1]
PYTHON_ROOT = REPO_ROOT / "python"
for path in (HERE, PYTHON_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import dim_raw_config as CFG
from methods.mdm import MDM
from studies.common.sample import generate_sample


CONTRACT = "E12_delta_upper_boundary_v1"
OUTPUT_DIR = STUDY_ROOT / "artifacts" / "candidate" / "E12_delta_upper_boundary"
SAMPLE_KEYS = ["beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id"]
CHECK_DELTAS = (0.48, 0.50)
EXTENDED_DELTAS = tuple(round(0.52 + 0.02 * i, 2) for i in range(25))
RUN_DELTAS = CHECK_DELTAS + EXTENDED_DELTAS
EXPECTED_SAMPLES = 48_000
EXPECTED_ROWS = EXPECTED_SAMPLES * len(CFG.DELTA_GRID)


def sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def sample_loss(frame: pd.DataFrame) -> pd.Series:
    """Frozen Study01 joint squared relative-error loss."""
    return (
        ((frame["beta_hat"] - frame["beta"]) / frame["beta"]) ** 2
        + ((frame["eta_hat"] - frame["eta"]) / frame["eta"]) ** 2
        + ((frame["gamma_hat"] - frame["gamma"]) / frame["eta"]) ** 2
    )


def load_frozen_scan() -> pd.DataFrame:
    path = Path(CFG.MC_SCAN_PATH)
    if not path.is_file():
        raise FileNotFoundError(path)
    columns = SAMPLE_KEYS + [
        "delta", "beta_hat", "eta_hat", "gamma_hat", "r_squared",
        "converged", "status",
    ]
    frame = pd.read_csv(path, usecols=columns, low_memory=False)
    if len(frame) != EXPECTED_ROWS:
        raise RuntimeError(f"expected {EXPECTED_ROWS} scan rows, got {len(frame)}")
    if frame.duplicated(SAMPLE_KEYS + ["delta"]).any():
        raise RuntimeError("frozen scan contains duplicate sample-delta rows")
    if frame[SAMPLE_KEYS].drop_duplicates().shape[0] != EXPECTED_SAMPLES:
        raise RuntimeError("frozen scan does not contain exactly 48,000 samples")
    if not np.allclose(sorted(frame["delta"].unique()), CFG.DELTA_GRID):
        raise RuntimeError("frozen delta grid drift")
    if not frame["status"].eq("success").all():
        raise RuntimeError("frozen scan contains failed estimates")
    frame["loss"] = sample_loss(frame)
    if not np.isfinite(frame["loss"]).all():
        raise RuntimeError("frozen scan contains non-finite loss")
    return frame


def select_boundary_samples(scan: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select samples whose loss is still falling at the current upper edge."""
    pivot = scan.pivot(index=SAMPLE_KEYS, columns="delta", values="loss")
    if 0.48 not in pivot or 0.50 not in pivot:
        raise RuntimeError("0.48/0.50 edge points are missing")
    base_delta = pivot.idxmin(axis=1)
    base_loss = pivot.min(axis=1)
    default_loss = pivot[float(CFG.DEFAULT_DELTA)]
    all_samples = pivot.reset_index()[SAMPLE_KEYS].copy()
    all_samples["default_loss"] = default_loss.to_numpy(dtype=float)
    all_samples["base_l6_delta"] = base_delta.to_numpy(dtype=float)
    all_samples["base_l6_loss"] = base_loss.to_numpy(dtype=float)
    all_samples["loss_048"] = pivot[0.48].to_numpy(dtype=float)
    all_samples["loss_050"] = pivot[0.50].to_numpy(dtype=float)
    selected = all_samples[all_samples["loss_050"] < all_samples["loss_048"]].copy()
    return all_samples.reset_index(drop=True), selected.reset_index(drop=True)


def _evaluate_one(task: tuple[float, float, float, float, int, int]) -> list[dict]:
    beta, eta, gamma, ratio, n_value, repeat_id = task
    sample = generate_sample(
        beta, eta, gamma, n_value, repeat_id, seed=CFG.SEED_NAMESPACE
    )
    rows = []
    for delta in RUN_DELTAS:
        row = {
            "beta": beta,
            "eta": eta,
            "gamma": gamma,
            "gamma_over_eta": ratio,
            "n": n_value,
            "repeat_id": repeat_id,
            "delta": delta,
            "beta_hat": np.nan,
            "eta_hat": np.nan,
            "gamma_hat": np.nan,
            "r_squared": np.nan,
            "converged": False,
            "status": "failure",
            "loss": np.nan,
        }
        try:
            beta_hat, eta_hat, gamma_hat, r_squared, converged = MDM(sample).run(
                offset=delta
            )
            valid = bool(converged) and beta_hat > 0 and eta_hat > 0
            row.update(
                beta_hat=float(beta_hat),
                eta_hat=float(eta_hat),
                gamma_hat=float(gamma_hat),
                r_squared=float(r_squared),
                converged=bool(converged),
                status="success" if valid else "failure",
            )
            if valid:
                row["loss"] = float(
                    ((beta_hat - beta) / beta) ** 2
                    + ((eta_hat - eta) / eta) ** 2
                    + ((gamma_hat - gamma) / eta) ** 2
                )
        except Exception as exc:  # preserved in the diagnostic row
            row["status"] = f"error:{type(exc).__name__}"
        rows.append(row)
    return rows


def run_extension(selected: pd.DataFrame, workers: int) -> pd.DataFrame:
    tasks = [
        (
            float(row.beta), float(row.eta), float(row.gamma),
            float(row.gamma_over_eta), int(row.n), int(row.repeat_id),
        )
        for row in selected.itertuples(index=False)
    ]
    rows: list[dict] = []
    with Pool(processes=workers) as pool:
        for index, result in enumerate(pool.imap_unordered(_evaluate_one, tasks), 1):
            rows.extend(result)
            if index % 100 == 0 or index == len(tasks):
                print(f"[E12] evaluated {index}/{len(tasks)} boundary samples", flush=True)
    return pd.DataFrame(rows).sort_values(SAMPLE_KEYS + ["delta"]).reset_index(drop=True)


def validate_reconstruction(selected: pd.DataFrame, extended: pd.DataFrame) -> dict:
    sealed = selected.set_index(SAMPLE_KEYS)
    rerun = extended[extended["delta"].isin(CHECK_DELTAS)].pivot(
        index=SAMPLE_KEYS, columns="delta", values="loss"
    )
    if len(rerun) != len(selected):
        raise RuntimeError("edge reconstruction is incomplete")
    diff_048 = np.abs(rerun[0.48] - sealed["loss_048"])
    diff_050 = np.abs(rerun[0.50] - sealed["loss_050"])
    maximum = float(max(diff_048.max(), diff_050.max()))
    if maximum > 1e-9:
        raise RuntimeError(f"reconstructed sealed-edge loss drift: {maximum}")
    return {
        "samples_checked": int(len(selected)),
        "points_per_sample": len(CHECK_DELTAS),
        "max_absolute_loss_difference": maximum,
        "tolerance": 1e-9,
    }


def derive_sample_summary(
    all_samples: pd.DataFrame, selected: pd.DataFrame, extended: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    new_rows = extended[extended["delta"].isin(EXTENDED_DELTAS)].copy()
    successful = new_rows[new_rows["status"].eq("success") & new_rows["loss"].notna()]
    if successful.empty:
        raise RuntimeError("no successful extended estimates")
    index = successful.groupby(SAMPLE_KEYS)["loss"].idxmin()
    new_best = successful.loc[index, SAMPLE_KEYS + ["delta", "loss"]].rename(
        columns={"delta": "new_grid_best_delta", "loss": "new_grid_best_loss"}
    )
    samples = selected.merge(new_best, on=SAMPLE_KEYS, how="left", validate="one_to_one")
    if samples["new_grid_best_loss"].isna().any():
        raise RuntimeError("at least one selected sample has no successful extended point")
    use_new = samples["new_grid_best_loss"] < samples["base_l6_loss"]
    samples["extended_l6_loss"] = np.where(
        use_new, samples["new_grid_best_loss"], samples["base_l6_loss"]
    )
    samples["extended_l6_delta"] = np.where(
        use_new, samples["new_grid_best_delta"], samples["base_l6_delta"]
    )
    samples["loss_reduction"] = samples["base_l6_loss"] - samples["extended_l6_loss"]
    samples["at_new_upper_boundary"] = np.isclose(samples["extended_l6_delta"], 1.0)

    replaced = all_samples.merge(
        samples[SAMPLE_KEYS + ["extended_l6_loss", "extended_l6_delta"]],
        on=SAMPLE_KEYS, how="left", validate="one_to_one",
    )
    replaced["extended_l6_loss"] = replaced["extended_l6_loss"].fillna(
        replaced["base_l6_loss"]
    )
    replaced["extended_l6_delta"] = replaced["extended_l6_delta"].fillna(
        replaced["base_l6_delta"]
    )

    by_group = (
        samples.groupby(["beta", "gamma_over_eta", "n"], as_index=False)
        .agg(
            selected_samples=("repeat_id", "size"),
            mean_loss_reduction=("loss_reduction", "mean"),
            median_extended_delta=("extended_l6_delta", "median"),
            new_upper_boundary_rate=("at_new_upper_boundary", "mean"),
        )
    )

    base_r = float(replaced["base_l6_loss"].mean())
    extended_r = float(replaced["extended_l6_loss"].mean())
    default_r = float(replaced["default_loss"].mean())
    summary = {
        "sample_counts": {
            "all_samples": int(len(replaced)),
            "selected_at_old_boundary": int(len(samples)),
            "selected_fraction": float(len(samples) / len(replaced)),
            "improved_beyond_050": int((samples["loss_reduction"] > 0).sum()),
            "best_at_new_upper_boundary_100": int(samples["at_new_upper_boundary"].sum()),
        },
        "risk": {
            "default_R": default_r,
            "default_J1": math.sqrt(default_r),
            "base_l6_R_000_050": base_r,
            "base_l6_J1_000_050": math.sqrt(base_r),
            "extended_l6_R_000_100": extended_r,
            "extended_l6_J1_000_100": math.sqrt(extended_r),
            "absolute_R_reduction": base_r - extended_r,
            "relative_R_reduction_vs_base_l6": (base_r - extended_r) / base_r,
            "default_to_l6_R_gap_base": default_r - base_r,
            "default_to_l6_R_gap_extended": default_r - extended_r,
        },
        "selected_sample_effect": {
            "mean_loss_reduction": float(samples["loss_reduction"].mean()),
            "median_loss_reduction": float(samples["loss_reduction"].median()),
            "q1_extended_delta": float(samples["extended_l6_delta"].quantile(0.25)),
            "median_extended_delta": float(samples["extended_l6_delta"].median()),
            "q3_extended_delta": float(samples["extended_l6_delta"].quantile(0.75)),
        },
        "interpretation_guard": (
            "This diagnostic tests truncation of the hindsight reference only. "
            "It does not change the trained selector or its 0.00--0.50 deployment grid."
        ),
    }
    return samples, by_group, summary


def git_metadata() -> dict:
    def run(*args: str) -> str:
        return subprocess.check_output(
            ["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()

    return {
        "head": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        "worktree_dirty": bool(run("status", "--short")),
    }


def write_outputs(
    output_dir: Path,
    extended: pd.DataFrame,
    samples: pd.DataFrame,
    by_group: pd.DataFrame,
    summary: dict,
    reconstruction: dict,
    runtime_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    extended.to_csv(output_dir / "extended_boundary_losses.csv", index=False, lineterminator="\n")
    samples.to_csv(output_dir / "selected_sample_summary.csv", index=False, lineterminator="\n")
    by_group.to_csv(output_dir / "by_parameter_group.csv", index=False, lineterminator="\n")
    source_path = Path(CFG.MC_SCAN_PATH)
    document = {
        "status": "CANDIDATE_BOUNDARY_DIAGNOSTIC",
        "contract": CONTRACT,
        "question": "Does delta=0.50 truncate the 26-point L6 hindsight reference?",
        "design": {
            "frozen_grid": list(CFG.DELTA_GRID),
            "selection_rule": "loss(delta=0.50) < loss(delta=0.48)",
            "check_deltas": list(CHECK_DELTAS),
            "extended_deltas": list(EXTENDED_DELTAS),
            "seed_namespace": CFG.SEED_NAMESPACE,
            "only_selected_samples_rerun": True,
        },
        "reconstruction_check": reconstruction,
        "result": summary,
        "provenance": {
            "source_scan": str(source_path.relative_to(STUDY_ROOT)).replace("\\", "/"),
            "source_scan_sha256_lf": sha256_lf(source_path),
            "analysis_code_sha256_lf": sha256_lf(Path(__file__)),
            "git": git_metadata(),
            "runtime_seconds": runtime_seconds,
        },
    }
    write_text(output_dir / "summary.json", json.dumps(document, indent=2, ensure_ascii=False) + "\n")

    counts = summary["sample_counts"]
    risk = summary["risk"]
    report = f"""# E12 delta candidate upper-bound diagnostic

## Scope

The frozen 0.00--0.50 scan is retained. Only the {counts['selected_at_old_boundary']:,}
samples whose loss was still decreasing from 0.48 to 0.50 were evaluated at
0.52--1.00 using the same sample generator, MDM implementation and loss.

## Result

- Selected at the old upper edge: {counts['selected_at_old_boundary']:,} / {counts['all_samples']:,}
  ({counts['selected_fraction']:.2%}).
- Improved beyond 0.50: {counts['improved_beyond_050']:,} samples.
- Still best at the new upper edge 1.00: {counts['best_at_new_upper_boundary_100']:,} samples.
- L6 J1 on the full 48,000 samples: {risk['base_l6_J1_000_050']:.9f}
  (0.00--0.50) -> {risk['extended_l6_J1_000_100']:.9f} (0.00--1.00).
- Relative reduction in L6 risk R: {risk['relative_R_reduction_vs_base_l6']:.3%}.

## Boundary of interpretation

This result diagnoses the hindsight reference. It does not alter the trained
selector, its deployment grid, or the already reported selector-versus-Default
comparison. If many samples remain best at 1.00, the extended reference is
still right-censored and 1.00 should not be called an unconstrained optimum.
"""
    write_text(output_dir / "diagnostic_report.md", report)

    entries = []
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            entries.append(f"{sha256_lf(path)}  {path.name}\n")
    write_text(output_dir / "SHA256SUMS", "".join(entries))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=max(1, min(16, (os.cpu_count() or 4) - 2)))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.workers < 1:
        raise ValueError("workers must be positive")
    started = time.perf_counter()
    print("[E12] loading and validating frozen scan...", flush=True)
    scan = load_frozen_scan()
    all_samples, selected = select_boundary_samples(scan)
    print(
        f"[E12] selected {len(selected)}/{len(all_samples)} samples; "
        f"running {len(RUN_DELTAS)} points with {args.workers} workers",
        flush=True,
    )
    extended = run_extension(selected, args.workers)
    reconstruction = validate_reconstruction(selected, extended)
    samples, by_group, summary = derive_sample_summary(all_samples, selected, extended)
    runtime = time.perf_counter() - started
    write_outputs(
        args.output_dir, extended, samples, by_group, summary,
        reconstruction, runtime,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    print(f"[E12] complete in {runtime:.1f}s -> {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
