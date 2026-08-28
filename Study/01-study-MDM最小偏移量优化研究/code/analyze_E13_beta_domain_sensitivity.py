"""Study01 E13: sensitivity of the best uniform offset to the beta domain.

The experiment keeps gamma/eta, n, delta, repeat weighting and the MDM
implementation fixed.  It densifies beta from a 0.50 to a 0.25 grid, then
slides a fixed-width beta domain across that grid.  Each domain contains five
consecutive beta levels (width 1.0) and contributes one 26-point J1 curve.

Existing beta levels reuse repeats 0--99 from the frozen E5 scan.  Only the
seven interleaved beta levels are newly simulated.  Large per-combination
chunks stay local; compact derived tables, a manifest and figures are written
under artifacts/formal/E13_beta_domain_sensitivity/ as bounded supporting
evidence.  The experiment does not replace the frozen main-method evaluation.
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
from studies.common.sample import generate_sample
from studies.common.runner import run_method


CONTRACT = "E13_beta_domain_sensitivity_v1"
OUTPUT_DIR = STUDY_ROOT / "artifacts" / "formal" / "E13_beta_domain_sensitivity"
CHUNK_DIR = OUTPUT_DIR / "chunks"
EXISTING_BETAS = tuple(float(x) for x in CFG.BETA_GRID)
FULL_BETA_GRID = tuple(round(1.50 + 0.25 * i, 2) for i in range(15))
NEW_BETAS = tuple(x for x in FULL_BETA_GRID if x not in EXISTING_BETAS)
WINDOW_CENTERS = tuple(round(2.00 + 0.25 * i, 2) for i in range(11))
WINDOW_WIDTH = 1.00
WINDOW_LEVELS = 5
REPEATS = 100
BOOTSTRAP_REPS = 5_000
BOOTSTRAP_SEED = 20260828
DELTA_GRID = tuple(float(x) for x in CFG.DELTA_GRID)
SAMPLE_KEYS = ["beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id"]
SCAN_COLUMNS = SAMPLE_KEYS + [
    "delta", "beta_hat", "eta_hat", "gamma_hat", "r_squared",
    "converged", "time_ms", "status", "loss",
]


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False, lineterminator="\n")
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def joint_loss(beta_hat: float, eta_hat: float, gamma_hat: float,
               beta: float, eta: float, gamma: float) -> float:
    return float(
        ((beta_hat - beta) / beta) ** 2
        + ((eta_hat - eta) / eta) ** 2
        + ((gamma_hat - gamma) / eta) ** 2
    )


def chunk_path(beta: float, ratio: float, n_value: int) -> Path:
    return CHUNK_DIR / (
        f"beta_{beta:.2f}_goe_{ratio:.2f}_n_{int(n_value):02d}.csv"
    )


def expected_chunk_keys(beta: float, ratio: float, n_value: int) -> pd.MultiIndex:
    return pd.MultiIndex.from_product(
        [range(REPEATS), DELTA_GRID], names=["repeat_id", "delta"]
    )


def validate_chunk(path: Path, beta: float, ratio: float, n_value: int) -> tuple[bool, str]:
    if not path.is_file():
        return False, "missing"
    try:
        frame = pd.read_csv(path, low_memory=False)
    except Exception as exc:
        return False, f"read:{type(exc).__name__}"
    required = set(SCAN_COLUMNS)
    if not required.issubset(frame.columns):
        return False, "schema"
    if len(frame) != REPEATS * len(DELTA_GRID):
        return False, "row_count"
    if not np.allclose(frame["beta"], beta):
        return False, "beta"
    if not np.allclose(frame["gamma_over_eta"], ratio):
        return False, "gamma_over_eta"
    if not frame["n"].eq(n_value).all():
        return False, "n"
    if frame.duplicated(["repeat_id", "delta"]).any():
        return False, "duplicate_keys"
    actual = pd.MultiIndex.from_frame(frame[["repeat_id", "delta"]])
    if not actual.equals(expected_chunk_keys(beta, ratio, n_value)):
        return False, "key_grid"
    if not frame["status"].eq("success").all():
        return False, "failed_estimate"
    if not np.isfinite(frame["loss"]).all():
        return False, "nonfinite_loss"
    return True, "ok"


def evaluate_combo(task: tuple[float, float, int]) -> dict:
    beta, ratio, n_value = task
    path = chunk_path(beta, ratio, n_value)
    valid, reason = validate_chunk(path, beta, ratio, n_value)
    if valid:
        return {"task": task, "status": "skipped", "seconds": 0.0, "path": str(path)}
    if path.exists():
        raise RuntimeError(f"invalid existing chunk {path}: {reason}")

    eta = float(CFG.ETA)
    gamma = float(ratio * eta)
    rows: list[dict] = []
    started = time.perf_counter()
    for repeat_id in range(REPEATS):
        sample = generate_sample(
            beta, eta, gamma, n_value, repeat_id, seed=CFG.SEED_NAMESPACE
        )
        for delta in DELTA_GRID:
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
                "time_ms": np.nan,
                "status": "failure",
                "loss": np.nan,
            }
            try:
                estimate = run_method("mdm", sample, offset=delta)
                bh = estimate["beta_hat"]
                eh = estimate["eta_hat"]
                gh = estimate["gamma_hat"]
                r_squared = estimate["r_squared"]
                converged = estimate["converged"]
                row["time_ms"] = float(estimate["time"]) * 1000
                good = (
                    bool(converged)
                    and bh is not None
                    and eh is not None
                    and gh is not None
                    and bh > 0
                    and eh > 0
                )
                row.update(
                    beta_hat=float(bh) if bh is not None else np.nan,
                    eta_hat=float(eh) if eh is not None else np.nan,
                    gamma_hat=float(gh) if gh is not None else np.nan,
                    r_squared=float(r_squared) if r_squared is not None else np.nan,
                    converged=bool(converged),
                    status="success" if good else "failure",
                )
                if good:
                    row["loss"] = joint_loss(bh, eh, gh, beta, eta, gamma)
            except Exception as exc:
                row["status"] = f"error:{type(exc).__name__}"
            rows.append(row)

    frame = pd.DataFrame(rows, columns=SCAN_COLUMNS).sort_values(
        ["repeat_id", "delta"]
    ).reset_index(drop=True)
    if not frame["status"].eq("success").all():
        failures = frame.loc[frame["status"] != "success", "status"].value_counts().to_dict()
        raise RuntimeError(f"MDM failure for {(beta, ratio, n_value)}: {failures}")
    atomic_csv(frame, path)
    valid, reason = validate_chunk(path, beta, ratio, n_value)
    if not valid:
        raise RuntimeError(f"written chunk failed validation {path}: {reason}")
    return {
        "task": task,
        "status": "written",
        "seconds": time.perf_counter() - started,
        "path": str(path),
    }


def generate_new_scan(workers: int) -> list[dict]:
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [
        (beta, float(ratio), int(n_value))
        for beta in NEW_BETAS
        for ratio in CFG.GAMMA_OVER_ETA_GRID
        for n_value in CFG.N_GRID
    ]
    receipts: list[dict] = []
    with Pool(processes=workers) as pool:
        for index, receipt in enumerate(pool.imap_unordered(evaluate_combo, tasks), 1):
            receipts.append(receipt)
            if index % 5 == 0 or index == len(tasks):
                written = sum(r["status"] == "written" for r in receipts)
                print(
                    f"[E13] combinations {index}/{len(tasks)}; new={written}; "
                    f"last={receipt['task']}",
                    flush=True,
                )
    return receipts


def load_existing_scan() -> pd.DataFrame:
    path = Path(CFG.MC_SCAN_PATH)
    usecols = [
        "beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id",
        "delta", "beta_hat", "eta_hat", "gamma_hat", "r_squared",
        "converged", "time_ms", "status",
    ]
    frame = pd.read_csv(path, usecols=usecols, low_memory=False)
    frame = frame[frame["repeat_id"] < REPEATS].copy()
    expected = len(EXISTING_BETAS) * len(CFG.GAMMA_OVER_ETA_GRID) * len(CFG.N_GRID) * REPEATS * len(DELTA_GRID)
    if len(frame) != expected:
        raise RuntimeError(f"existing scan expected {expected} rows, got {len(frame)}")
    if frame.duplicated(SAMPLE_KEYS + ["delta"]).any():
        raise RuntimeError("existing scan has duplicate sample-delta rows")
    if not frame["status"].eq("success").all():
        raise RuntimeError("existing scan contains failed estimates")
    frame["loss"] = (
        ((frame["beta_hat"] - frame["beta"]) / frame["beta"]) ** 2
        + ((frame["eta_hat"] - frame["eta"]) / frame["eta"]) ** 2
        + ((frame["gamma_hat"] - frame["gamma"]) / frame["eta"]) ** 2
    )
    return frame[SCAN_COLUMNS]


def load_new_scan() -> tuple[pd.DataFrame, list[dict]]:
    frames = []
    receipts = []
    for beta in NEW_BETAS:
        for ratio in CFG.GAMMA_OVER_ETA_GRID:
            for n_value in CFG.N_GRID:
                path = chunk_path(beta, float(ratio), int(n_value))
                valid, reason = validate_chunk(path, beta, float(ratio), int(n_value))
                if not valid:
                    raise RuntimeError(f"new chunk invalid {path}: {reason}")
                frame = pd.read_csv(path, low_memory=False)
                frames.append(frame)
                receipts.append(
                    {
                        "path": str(path.relative_to(OUTPUT_DIR)).replace("\\", "/"),
                        "sha256": sha256_file(path),
                        "rows": len(frame),
                    }
                )
    return pd.concat(frames, ignore_index=True), receipts


def validate_combined(frame: pd.DataFrame) -> dict:
    expected_rows = len(FULL_BETA_GRID) * len(CFG.GAMMA_OVER_ETA_GRID) * len(CFG.N_GRID) * REPEATS * len(DELTA_GRID)
    expected_samples = len(FULL_BETA_GRID) * len(CFG.GAMMA_OVER_ETA_GRID) * len(CFG.N_GRID) * REPEATS
    if len(frame) != expected_rows:
        raise RuntimeError(f"combined rows: expected {expected_rows}, got {len(frame)}")
    if frame.duplicated(SAMPLE_KEYS + ["delta"]).any():
        raise RuntimeError("combined scan has duplicate sample-delta rows")
    if frame[SAMPLE_KEYS].drop_duplicates().shape[0] != expected_samples:
        raise RuntimeError("combined sample count drift")
    if not np.allclose(sorted(frame["beta"].unique()), FULL_BETA_GRID):
        raise RuntimeError("combined beta grid drift")
    if not np.allclose(sorted(frame["delta"].unique()), DELTA_GRID):
        raise RuntimeError("combined delta grid drift")
    if not frame["status"].eq("success").all():
        raise RuntimeError("combined scan contains failed estimates")
    return {
        "rows": int(len(frame)),
        "samples": int(expected_samples),
        "parameter_conditions": int(
            len(FULL_BETA_GRID) * len(CFG.GAMMA_OVER_ETA_GRID) * len(CFG.N_GRID)
        ),
        "failures": 0,
    }


def derive_curves(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    curve_rows = []
    summary_rows = []
    for window_id, center in enumerate(WINDOW_CENTERS, 1):
        lower = round(center - WINDOW_WIDTH / 2, 2)
        upper = round(center + WINDOW_WIDTH / 2, 2)
        beta_levels = [x for x in FULL_BETA_GRID if lower - 1e-9 <= x <= upper + 1e-9]
        if len(beta_levels) != WINDOW_LEVELS:
            raise RuntimeError(f"window {center} contains {beta_levels}")
        subset = frame[frame["beta"].isin(beta_levels)]
        curve = subset.groupby("delta", as_index=False, sort=True)["loss"].mean()
        curve["J1"] = np.sqrt(curve["loss"])
        if len(curve) != len(DELTA_GRID):
            raise RuntimeError(f"window {center} delta grid incomplete")
        minimum = float(curve["J1"].min())
        best_delta = float(curve.loc[curve["J1"].idxmin(), "delta"])
        default_j1 = float(curve.loc[np.isclose(curve["delta"], 0.10), "J1"].iloc[0])
        near = curve[curve["J1"] <= 1.01 * minimum + 1e-15]
        for row in curve.itertuples(index=False):
            curve_rows.append(
                {
                    "window_id": window_id,
                    "beta_center": center,
                    "beta_lower": lower,
                    "beta_upper": upper,
                    "beta_levels": ";".join(f"{x:.2f}" for x in beta_levels),
                    "delta": float(row.delta),
                    "mean_loss": float(row.loss),
                    "J1": float(row.J1),
                    "excess_J1_pct": 100 * (float(row.J1) / minimum - 1),
                }
            )
        summary_rows.append(
            {
                "window_id": window_id,
                "beta_center": center,
                "beta_lower": lower,
                "beta_upper": upper,
                "n_beta_levels": len(beta_levels),
                "n_parameter_conditions": len(beta_levels) * len(CFG.GAMMA_OVER_ETA_GRID) * len(CFG.N_GRID),
                "n_samples": int(subset[SAMPLE_KEYS].drop_duplicates().shape[0]),
                "best_delta": best_delta,
                "best_J1": minimum,
                "default_delta": 0.10,
                "default_J1": default_j1,
                "default_excess_J1_pct": 100 * (default_j1 / minimum - 1),
                "near_optimal_1pct_lower": float(near["delta"].min()),
                "near_optimal_1pct_upper": float(near["delta"].max()),
            }
        )
    return pd.DataFrame(curve_rows), pd.DataFrame(summary_rows)


def bootstrap_best_deltas(frame: pd.DataFrame, n_bootstrap: int) -> pd.DataFrame:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rows = []
    for window_id, center in enumerate(WINDOW_CENTERS, 1):
        lower, upper = center - 0.5, center + 0.5
        subset = frame[(frame["beta"] >= lower - 1e-9) & (frame["beta"] <= upper + 1e-9)]
        block = (
            subset.groupby(["repeat_id", "delta"], sort=True)["loss"]
            .mean().unstack("delta").reindex(index=range(REPEATS), columns=DELTA_GRID)
        )
        values = block.to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise RuntimeError(f"bootstrap matrix incomplete for center {center}")
        counts = np.zeros(len(DELTA_GRID), dtype=int)
        batch = 250
        completed = 0
        while completed < n_bootstrap:
            current = min(batch, n_bootstrap - completed)
            indices = rng.integers(0, REPEATS, size=(current, REPEATS))
            boot_means = values[indices].mean(axis=1)
            winners = np.argmin(boot_means, axis=1)
            counts += np.bincount(winners, minlength=len(DELTA_GRID))
            completed += current
        probabilities = counts / n_bootstrap
        draws = np.repeat(np.asarray(DELTA_GRID), counts)
        rows.append(
            {
                "window_id": window_id,
                "beta_center": center,
                "bootstrap_reps": n_bootstrap,
                "bootstrap_modal_delta": float(DELTA_GRID[int(np.argmax(counts))]),
                "bootstrap_delta_q025": float(np.quantile(draws, 0.025)),
                "bootstrap_delta_q975": float(np.quantile(draws, 0.975)),
                "prob_delta_0.10": float(probabilities[list(DELTA_GRID).index(0.10)]),
                "prob_point_estimate": np.nan,
                "selection_probabilities": json.dumps(
                    {f"{d:.2f}": float(p) for d, p in zip(DELTA_GRID, probabilities) if p > 0},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    result = pd.DataFrame(rows)
    return result


def add_point_estimate_probability(bootstrap: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    out = bootstrap.merge(summary[["window_id", "best_delta"]], on="window_id", how="left")
    probabilities = []
    for row in out.itertuples(index=False):
        mapping = json.loads(row.selection_probabilities)
        probabilities.append(float(mapping.get(f"{row.best_delta:.2f}", 0.0)))
    out["prob_point_estimate"] = probabilities
    return out.drop(columns=["best_delta"])


def plot_results(curves: pd.DataFrame, summary: pd.DataFrame) -> None:
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "Arial", "DejaVu Sans", "sans-serif"],
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 7.5,
            "axes.linewidth": 0.8,
        }
    )
    ink, grid = "#26343F", "#D7DEE5"
    cmap = mpl.colormaps["viridis"]
    fig = plt.figure(figsize=(10.8, 4.5))
    gs = fig.add_gridspec(1, 2, width_ratios=[0.94, 1.30], left=0.07, right=0.97,
                          bottom=0.13, top=0.91, wspace=0.15)

    ax_a = fig.add_subplot(gs[0, 0])
    y = np.arange(len(WINDOW_CENTERS))
    for index, row in summary.iterrows():
        color = cmap(index / max(1, len(summary) - 1))
        ax_a.add_patch(
            Rectangle((row.beta_lower, index - 0.33), WINDOW_WIDTH, 0.66,
                      facecolor=color, edgecolor=color, alpha=0.65, linewidth=0.7)
        )
        levels = np.arange(row.beta_lower, row.beta_upper + 0.001, 0.25)
        ax_a.scatter(levels, np.full_like(levels, index), s=8, color="white",
                     edgecolor=ink, linewidth=0.35, zorder=3)
    ax_a.set_xlim(1.42, 5.08)
    ax_a.set_ylim(-0.7, len(summary) - 0.3)
    ax_a.set_xticks(np.arange(1.5, 5.01, 0.5))
    ax_a.set_yticks(y)
    ax_a.set_yticklabels([f"{c:.2f}" for c in WINDOW_CENTERS])
    ax_a.set_xlabel(r"形状参数 $\beta$")
    ax_a.set_ylabel(r"区间中心 $c$")
    ax_a.set_title("a   固定宽度参数域的平移", loc="left", fontweight="bold")
    ax_a.spines[["top", "right"]].set_visible(False)
    ax_a.grid(axis="x", color=grid, linewidth=0.55, zorder=0)

    ax_b = fig.add_subplot(gs[0, 1], projection="3d")
    best_x, best_y, best_z = [], [], []
    default_x, default_y, default_z = [], [], []
    for index, center in enumerate(WINDOW_CENTERS):
        sub = curves[np.isclose(curves["beta_center"], center)].sort_values("delta")
        color = cmap(index / max(1, len(WINDOW_CENTERS) - 1))
        ax_b.plot(sub["delta"], np.full(len(sub), center), sub["J1"],
                  color=color, lw=1.3)
        ax_b.scatter(sub["delta"], np.full(len(sub), center), sub["J1"],
                     color=color, s=4, depthshade=False)
        best = summary[np.isclose(summary["beta_center"], center)].iloc[0]
        best_x.append(float(best.best_delta))
        best_y.append(float(center))
        best_z.append(float(best.best_J1))
        default_row = sub[np.isclose(sub["delta"], 0.10)].iloc[0]
        default_x.append(0.10)
        default_y.append(float(center))
        default_z.append(float(default_row.J1))
    ax_b.plot(best_x, best_y, best_z, color="#C8483C", lw=1.35, marker="o",
              markersize=4.2, markeredgecolor="white", markeredgewidth=0.45,
              label="离散最低点")
    ax_b.plot(default_x, default_y, default_z, color="#6F7B83", lw=1.05,
              linestyle="--", marker="s", markersize=3.0, label=r"$\delta=0.10$")
    ax_b.set_xlabel(r"偏移量 $\delta$", labelpad=6)
    ax_b.set_ylabel(r"$\beta$ 区间中心 $c$", labelpad=7)
    ax_b.set_zlabel(r"$J_1(\delta\mid B(c))$", labelpad=6)
    ax_b.set_xlim(0, 0.5)
    ax_b.set_ylim(min(WINDOW_CENTERS), max(WINDOW_CENTERS))
    ax_b.set_xticks(np.arange(0, 0.51, 0.1))
    ax_b.set_yticks(np.arange(2.0, 4.51, 0.5))
    ax_b.view_init(elev=24, azim=-60)
    ax_b.set_box_aspect((1.25, 1.05, 0.68))
    ax_b.text2D(0.02, 0.97, "b   滑动参数域的 26 点风险曲线",
                transform=ax_b.transAxes, ha="left", va="top", fontweight="bold")
    ax_b.legend(loc="upper right", bbox_to_anchor=(0.98, 0.94), frameon=False,
                fontsize=7, handlelength=2.1)
    for axis in (ax_b.xaxis, ax_b.yaxis, ax_b.zaxis):
        axis.pane.set_facecolor((1, 1, 1, 0))
        axis.pane.set_edgecolor(grid)

    for extension in ("png", "pdf", "svg", "tiff"):
        target = OUTPUT_DIR / f"beta_domain_sensitivity.{extension}"
        save_kwargs = {
            "dpi": 400 if extension in {"png", "tiff"} else None,
            "facecolor": "white",
            "bbox_inches": "tight",
        }
        if extension == "tiff":
            save_kwargs["pil_kwargs"] = {"compression": "tiff_lzw"}
        fig.savefig(target, **save_kwargs)
        if extension == "svg":
            svg_text = target.read_text(encoding="utf-8")
            target.write_text(
                "\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n",
                encoding="utf-8",
                newline="\n",
            )
    plt.close(fig)


def git_metadata() -> dict:
    def run(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()

    return {
        "head": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        "worktree_porcelain": run("status", "--porcelain"),
    }


def write_report(summary: pd.DataFrame, bootstrap: pd.DataFrame) -> None:
    merged = summary.merge(bootstrap, on=["window_id", "beta_center"], how="left")
    lines = [
        "# E13 beta-domain sensitivity",
        "",
        "Status: formal supporting analysis; does not replace the frozen Study01 main-method results.",
        "",
        "The beta domain has fixed width 1.0 and contains five equally spaced levels. "
        "Its center moves from 2.00 to 4.50 in steps of 0.25. All gamma/eta levels, "
        "sample sizes, repeats, candidate offsets and equal-condition weighting remain fixed.",
        "",
        "| beta domain | center | best delta | best J1 | delta=0.10 excess J1 | 1% near-optimal interval | bootstrap 95% selected-delta interval |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in merged.itertuples(index=False):
        lines.append(
            f"| [{row.beta_lower:.2f}, {row.beta_upper:.2f}] | {row.beta_center:.2f} | "
            f"{row.best_delta:.2f} | {row.best_J1:.6f} | {row.default_excess_J1_pct:.2f}% | "
            f"[{row.near_optimal_1pct_lower:.2f}, {row.near_optimal_1pct_upper:.2f}] | "
            f"[{row.bootstrap_delta_q025:.2f}, {row.bootstrap_delta_q975:.2f}] |"
        )
    lines.extend(
        [
            "",
            "Interpretation is intentionally deferred until the numeric and visual QA checks pass.",
        ]
    )
    atomic_text(OUTPUT_DIR / "report.md", "\n".join(lines) + "\n")


def write_manifest(receipts: list[dict], validation: dict, runtime_seconds: float,
                   n_bootstrap: int) -> None:
    chunk_digest = hashlib.sha256(
        "\n".join(f"{x['sha256']}  {x['path']}" for x in receipts).encode("utf-8")
    ).hexdigest()
    manifest = {
        "contract": CONTRACT,
        "status": "formal_supporting_complete",
        "question": (
            "Does moving a fixed-width beta parameter domain change the risk curve "
            "and the best uniform MDM offset?"
        ),
        "design": {
            "full_beta_grid": FULL_BETA_GRID,
            "existing_beta_grid_reused": EXISTING_BETAS,
            "new_beta_grid_simulated": NEW_BETAS,
            "beta_step": 0.25,
            "window_centers": WINDOW_CENTERS,
            "window_width": WINDOW_WIDTH,
            "levels_per_window": WINDOW_LEVELS,
            "gamma_over_eta_grid": CFG.GAMMA_OVER_ETA_GRID,
            "n_grid": CFG.N_GRID,
            "repeats": REPEATS,
            "delta_grid": DELTA_GRID,
            "seed_namespace": CFG.SEED_NAMESPACE,
            "weighting": "equal parameter conditions and equal repeats within each window",
        },
        "inputs": {
            "frozen_scan": str(Path(CFG.MC_SCAN_PATH).relative_to(STUDY_ROOT)).replace("\\", "/"),
            "frozen_scan_sha256": sha256_file(Path(CFG.MC_SCAN_PATH)),
            "new_chunk_count": len(receipts),
            "new_chunks_combined_sha256": chunk_digest,
        },
        "validation": validation,
        "bootstrap": {
            "repeat_block_reps": n_bootstrap,
            "seed": BOOTSTRAP_SEED,
            "purpose": "descriptive stability of the discrete best-delta selection",
        },
        "runtime_seconds": runtime_seconds,
        "git": git_metadata(),
    }
    atomic_text(
        OUTPUT_DIR / "manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )


def write_checksums() -> None:
    names = [
        "window_risk_curves.csv",
        "window_summary.csv",
        "bootstrap_best_delta.csv",
        "report.md",
        "manifest.json",
        "beta_domain_sensitivity.png",
        "beta_domain_sensitivity.pdf",
        "beta_domain_sensitivity.svg",
        "beta_domain_sensitivity.tiff",
    ]
    lines = []
    for name in names:
        path = OUTPUT_DIR / name
        if not path.is_file():
            raise FileNotFoundError(path)
        lines.append(f"{sha256_file(path)}  {name}")
    atomic_text(OUTPUT_DIR / "SHA256SUMS", "\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    # scipy/pandas imports are memory-heavy on Windows spawn; four workers fit
    # the ordinary workstation memory envelope used for this experiment.
    parser.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 4) - 2)))
    parser.add_argument("--bootstrap", type=int, default=BOOTSTRAP_REPS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.workers < 1 or args.bootstrap < 1:
        raise ValueError("workers and bootstrap must be positive")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    print(
        f"[E13] new beta levels={NEW_BETAS}; combinations="
        f"{len(NEW_BETAS) * len(CFG.GAMMA_OVER_ETA_GRID) * len(CFG.N_GRID)}; "
        f"MDM estimates={len(NEW_BETAS) * len(CFG.GAMMA_OVER_ETA_GRID) * len(CFG.N_GRID) * REPEATS * len(DELTA_GRID):,}",
        flush=True,
    )
    generate_new_scan(args.workers)
    existing = load_existing_scan()
    new, receipts = load_new_scan()
    combined = pd.concat([existing, new], ignore_index=True)
    validation = validate_combined(combined)
    curves, summary = derive_curves(combined)
    bootstrap = bootstrap_best_deltas(combined, args.bootstrap)
    bootstrap = add_point_estimate_probability(bootstrap, summary)
    atomic_csv(curves, OUTPUT_DIR / "window_risk_curves.csv")
    atomic_csv(summary, OUTPUT_DIR / "window_summary.csv")
    atomic_csv(bootstrap, OUTPUT_DIR / "bootstrap_best_delta.csv")
    plot_results(curves, summary)
    write_report(summary, bootstrap)
    write_manifest(receipts, validation, time.perf_counter() - started, args.bootstrap)
    write_checksums()
    print(f"[E13] completed in {time.perf_counter() - started:.1f}s: {OUTPUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
