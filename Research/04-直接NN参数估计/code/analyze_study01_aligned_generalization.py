"""Analyze and visualize the Study01-aligned Research04 experiment.

The formal runner writes one row per method and shared physical sample.  This
script keeps that pairing, produces domain- and beta-level summaries, computes
stratified paired bootstrap confidence intervals, and exports publication-ready
figures.  Numerical tables remain CSV/Markdown rather than being rasterized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve()
RESEARCH_ROOT = HERE.parents[1]
PROJECT_ROOT = HERE.parents[3]
PYTHON_ROOT = PROJECT_ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from studies.common.sample import generate_sample  # noqa: E402

RUN_ROOT = RESEARCH_ROOT / "artifacts" / "study01_aligned_generalization_v1"
RESULTS_PATH = RUN_ROOT / "per_sample_results.csv.gz"
MANIFEST_PATH = RUN_ROOT / "manifest.json"
ANALYSIS_DIR = RUN_ROOT / "analysis"
FIGURE_DIR = RUN_ROOT / "figures"
GROUP_ASSET_DIR = (
    PROJECT_ROOT
    / "docs"
    / "组会汇报"
    / "2026-08-组会阶段汇报"
    / "三部分Markdown稿"
    / "assets"
    / "part2"
)

METHOD_ORDER = ["Direct-P", "Adaptive-MDM", "MDM-0.1"]
GROUP_ORDER = ["seen_grid", "in_domain_unseen", "near_ood", "far_ood"]
GROUP_LABELS = {
    "seen_grid": "已见网格",
    "in_domain_unseen": "域内未见",
    "near_ood": "近域外",
    "far_ood": "远域外",
}
METHOD_LABELS = {
    "Direct-P": "直接估计",
    "Adaptive-MDM": "自适应 MDM",
    "MDM-0.1": "固定 MDM-0.1",
}
COLORS = {
    "Direct-P": "#0072B2",
    "Adaptive-MDM": "#D55E00",
    "MDM-0.1": "#009E73",
}
LINESTYLES = {"Direct-P": "-", "Adaptive-MDM": "--", "MDM-0.1": ":"}
MARKERS = {"Direct-P": "o", "Adaptive-MDM": "s", "MDM-0.1": "^"}
BOOTSTRAP_SEED = 20260830
BOOTSTRAP_REPS = 3000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_inputs(frame: pd.DataFrame, manifest: dict) -> None:
    required = {
        "method", "beta_group", "beta", "gamma_over_eta", "n", "repeat_id",
        "status", "loss_primary", "beta_rel_error", "eta_rel_error",
        "gamma_rel_error", "x0.95_rel_error",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise RuntimeError(f"missing result columns: {missing}")
    expected_rows = int(manifest["validation"]["n_rows"])
    if len(frame) != expected_rows:
        raise RuntimeError(f"row count {len(frame)} != manifest {expected_rows}")
    if sorted(frame["method"].unique()) != sorted(METHOD_ORDER):
        raise RuntimeError("method set does not match frozen protocol")
    key = ["beta", "gamma_over_eta", "n", "repeat_id"]
    counts = frame.groupby(key)["method"].nunique()
    if not counts.eq(len(METHOD_ORDER)).all():
        raise RuntimeError("methods do not share every physical test sample")


def standard_stats(values: pd.Series) -> dict[str, float]:
    x = values.dropna().to_numpy(dtype=float)
    if x.size == 0:
        return {"bias": math.nan, "sd": math.nan, "rmse": math.nan}
    return {
        "bias": float(np.mean(x)),
        "sd": float(np.std(x, ddof=1)) if x.size > 1 else 0.0,
        "rmse": float(np.sqrt(np.mean(np.square(x)))),
    }


def summarize(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict] = []
    error_columns = {
        "beta": "beta_rel_error",
        "eta": "eta_rel_error",
        "gamma": "gamma_rel_error",
        "x0.95": "x0.95_rel_error",
    }
    for keys, group in frame.groupby(group_cols, sort=True, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        losses = group["loss_primary"].to_numpy(dtype=float)
        tail = np.sqrt(np.maximum(losses, 0.0))
        row.update(
            n_total=int(len(group)),
            n_valid=int(group["status"].eq("success").sum()),
            failure_rate=float(1.0 - group["status"].eq("success").mean()),
            J1=float(np.sqrt(np.mean(losses))),
            P95_joint_error=float(np.percentile(tail, 95)),
            CVaR95_joint_error=float(tail[tail >= np.percentile(tail, 95)].mean()),
        )
        for label, column in error_columns.items():
            for metric, value in standard_stats(group[column]).items():
                row[f"{label}_{metric}"] = value
        for label in ("beta", "eta", "gamma"):
            absolute_error = group[f"{label}_hat"] - group[label]
            for metric, value in standard_stats(absolute_error).items():
                row[f"{label}_abs_{metric}"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def paired_arrays(frame: pd.DataFrame, scope_col: str, scope_value: object,
                  comparator: str) -> tuple[np.ndarray, np.ndarray, int]:
    subset = frame[frame[scope_col].eq(scope_value)]
    keys = ["beta", "gamma_over_eta", "n", "repeat_id"]
    wide = subset.pivot(index=keys, columns="method", values="loss_primary")
    direct = wide["Direct-P"]
    baseline = wide[comparator]
    cells = wide.index.droplevel("repeat_id")
    unique_cells = cells.unique()
    repeats = sorted(wide.index.get_level_values("repeat_id").unique())
    direct_matrix = np.empty((len(unique_cells), len(repeats)), dtype=float)
    baseline_matrix = np.empty_like(direct_matrix)
    for i, cell in enumerate(unique_cells):
        direct_matrix[i] = direct.xs(cell, level=["beta", "gamma_over_eta", "n"]).reindex(repeats)
        baseline_matrix[i] = baseline.xs(cell, level=["beta", "gamma_over_eta", "n"]).reindex(repeats)
    if not np.isfinite(direct_matrix).all() or not np.isfinite(baseline_matrix).all():
        raise RuntimeError(f"non-finite paired loss in {scope_col}={scope_value}")
    return direct_matrix, baseline_matrix, len(unique_cells)


def stratified_paired_bootstrap(
    direct: np.ndarray,
    baseline: np.ndarray,
    rng: np.random.Generator,
    reps: int,
) -> tuple[float, float, float]:
    point = float(np.sqrt(direct.mean()) - np.sqrt(baseline.mean()))
    n_cells, n_repeats = direct.shape
    estimates = np.empty(reps, dtype=float)
    chunk = 25
    for start in range(0, reps, chunk):
        stop = min(start + chunk, reps)
        indices = rng.integers(
            0, n_repeats, size=(stop - start, n_cells, n_repeats)
        )
        direct_sample = np.take_along_axis(direct[None, :, :], indices, axis=2)
        baseline_sample = np.take_along_axis(baseline[None, :, :], indices, axis=2)
        estimates[start:stop] = (
            np.sqrt(direct_sample.mean(axis=(1, 2)))
            - np.sqrt(baseline_sample.mean(axis=(1, 2)))
        )
    low, high = np.percentile(estimates, [2.5, 97.5])
    return point, float(low), float(high)


def bootstrap_contrasts(frame: pd.DataFrame, reps: int) -> pd.DataFrame:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rows: list[dict] = []
    scopes = [("beta_group", group) for group in GROUP_ORDER]
    scopes += [("beta", beta) for beta in sorted(frame["beta"].unique())]
    for scope_col, scope_value in scopes:
        for comparator in ("Adaptive-MDM", "MDM-0.1"):
            direct, baseline, n_cells = paired_arrays(
                frame, scope_col, scope_value, comparator
            )
            point, low, high = stratified_paired_bootstrap(
                direct, baseline, rng, reps
            )
            j_direct = float(np.sqrt(direct.mean()))
            j_baseline = float(np.sqrt(baseline.mean()))
            rows.append(
                {
                    "scope": scope_col,
                    "scope_value": scope_value,
                    "contrast": f"Direct-P minus {comparator}",
                    "n_cells": n_cells,
                    "n_samples": int(direct.size),
                    "J1_direct": j_direct,
                    "J1_comparator": j_baseline,
                    "delta_J1": point,
                    "ci95_low": low,
                    "ci95_high": high,
                    "relative_change_percent": 100.0 * point / j_baseline,
                    "bootstrap_reps": reps,
                    "bootstrap_seed": BOOTSTRAP_SEED,
                }
            )
    seen = frame[frame["beta_group"].eq("seen_grid")]
    for n_value in sorted(seen["n"].unique()):
        for comparator in ("Adaptive-MDM", "MDM-0.1"):
            direct, baseline, n_cells = paired_arrays(
                seen, "n", n_value, comparator
            )
            point, low, high = stratified_paired_bootstrap(
                direct, baseline, rng, reps
            )
            j_direct = float(np.sqrt(direct.mean()))
            j_baseline = float(np.sqrt(baseline.mean()))
            rows.append(
                {
                    "scope": "seen_grid_n",
                    "scope_value": int(n_value),
                    "contrast": f"Direct-P minus {comparator}",
                    "n_cells": n_cells,
                    "n_samples": int(direct.size),
                    "J1_direct": j_direct,
                    "J1_comparator": j_baseline,
                    "delta_J1": point,
                    "ci95_low": low,
                    "ci95_high": high,
                    "relative_change_percent": 100.0 * point / j_baseline,
                    "bootstrap_reps": reps,
                    "bootstrap_seed": BOOTSTRAP_SEED,
                }
            )
    return pd.DataFrame(rows)


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 10,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 120,
            "savefig.dpi": 300,
        }
    )


def save_figure(fig: plt.Figure, stem: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    GROUP_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    png = FIGURE_DIR / f"{stem}.png"
    pdf = FIGURE_DIR / f"{stem}.pdf"
    fig.savefig(png, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    shutil.copy2(png, GROUP_ASSET_DIR / png.name)


def plot_domain_risk(beta_summary: pd.DataFrame, contrasts: pd.DataFrame) -> None:
    configure_style()
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.35), constrained_layout=True)
    ax = axes[0]
    for method in METHOD_ORDER:
        d = beta_summary[beta_summary["method"].eq(method)].sort_values("beta")
        ax.plot(
            d["beta"], d["J1"], label=METHOD_LABELS[method],
            color=COLORS[method], linestyle=LINESTYLES[method],
            marker=MARKERS[method], markersize=3.5, linewidth=1.5,
        )
    ax.axvspan(1.5, 5.0, color="#E5E5E5", alpha=0.45, zorder=0)
    ax.axvline(1.5, color="#777777", linewidth=0.7)
    ax.axvline(5.0, color="#777777", linewidth=0.7)
    ax.set_xlabel(r"形状参数 $\beta$")
    ax.set_ylabel(r"联合相对误差 $J_1$")
    ax.set_title("A  点风险随测试位置变化", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=1)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.65)

    ax = axes[1]
    beta_ci = contrasts[contrasts["scope"].eq("beta")].copy()
    for comparator in ("Adaptive-MDM", "MDM-0.1"):
        label = f"相对{METHOD_LABELS[comparator]}"
        d = beta_ci[beta_ci["contrast"].eq(f"Direct-P minus {comparator}")].copy()
        d["scope_value"] = pd.to_numeric(d["scope_value"])
        d = d.sort_values("scope_value")
        color = COLORS[comparator]
        ax.plot(
            d["scope_value"], d["delta_J1"], label=label,
            color=color, linewidth=1.5,
            linestyle=LINESTYLES[comparator], marker=MARKERS[comparator],
            markersize=3.5,
        )
        ax.fill_between(
            d["scope_value"].to_numpy(float),
            d["ci95_low"].to_numpy(float),
            d["ci95_high"].to_numpy(float),
            color=color, alpha=0.15, linewidth=0,
        )
    ax.axhline(0, color="#222222", linewidth=0.9)
    ax.axvspan(1.5, 5.0, color="#E5E5E5", alpha=0.45, zorder=0)
    ax.axvline(1.5, color="#777777", linewidth=0.7)
    ax.axvline(5.0, color="#777777", linewidth=0.7)
    ax.set_xlabel(r"形状参数 $\beta$")
    ax.set_ylabel(r"配对风险差 $\Delta J_1$")
    ax.set_title("B  直接估计相对结构路线的风险差", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.65)
    fig.text(
        0.5, -0.035,
        "灰色区域为训练覆盖范围；阴影为分层配对 bootstrap 95% CI。风险差小于 0 表示直接估计更优。",
        ha="center", fontsize=8,
    )
    save_figure(fig, "fig_r04_domain_risk")
    plt.close(fig)


def plot_parameter_rmse(beta_summary: pd.DataFrame) -> None:
    configure_style()
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.25), constrained_layout=True)
    panels = [("beta_rmse", r"$\beta$ 相对 RMSE"),
              ("eta_rmse", r"$\eta$ 相对 RMSE"),
              ("gamma_rmse", r"$\gamma$ 误差 / $\eta$")]
    for index, (ax, (column, label)) in enumerate(zip(axes, panels)):
        for method in METHOD_ORDER:
            d = beta_summary[beta_summary["method"].eq(method)].sort_values("beta")
            ax.plot(
                d["beta"], d[column], label=METHOD_LABELS[method],
                color=COLORS[method], linestyle=LINESTYLES[method],
                marker=MARKERS[method], markersize=3.2, linewidth=1.4,
            )
        ax.axvspan(1.5, 5.0, color="#E5E5E5", alpha=0.45, zorder=0)
        ax.axvline(1.5, color="#777777", linewidth=0.7)
        ax.axvline(5.0, color="#777777", linewidth=0.7)
        ax.set_xlabel(r"形状参数 $\beta$")
        ax.set_ylabel(label)
        ax.set_title(f"{chr(65 + index)}  {label}", loc="left", fontweight="bold")
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.65)
    axes[0].legend(frameon=False)
    fig.text(
        0.5, -0.035,
        "RMSE 按真参数尺度标准化；仅在合法估计上计算，失败率另表报告。灰色区域为训练覆盖范围。",
        ha="center", fontsize=8,
    )
    save_figure(fig, "fig_r04_parameter_rmse")
    plt.close(fig)


def improvement_table(domain_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    indexed = domain_summary.set_index(["beta_group", "method"])
    for group in GROUP_ORDER:
        direct = indexed.loc[(group, "Direct-P")]
        for comparator in ("Adaptive-MDM", "MDM-0.1"):
            base = indexed.loc[(group, comparator)]
            row = {
                "beta_group": group,
                "comparator": comparator,
                "J1_direct": direct["J1"],
                "J1_comparator": base["J1"],
                "J1_change_percent": 100.0 * (direct["J1"] - base["J1"]) / base["J1"],
                "beta_rmse_change_percent": 100.0 * (direct["beta_rmse"] - base["beta_rmse"]) / base["beta_rmse"],
                "eta_rmse_change_percent": 100.0 * (direct["eta_rmse"] - base["eta_rmse"]) / base["eta_rmse"],
                "gamma_rmse_change_percent": 100.0 * (direct["gamma_rmse"] - base["gamma_rmse"]) / base["gamma_rmse"],
                "x0.95_rmse_change_percent": 100.0 * (direct["x0.95_rmse"] - base["x0.95_rmse"]) / base["x0.95_rmse"],
                "direct_failure_rate": direct["failure_rate"],
                "comparator_failure_rate": base["failure_rate"],
            }
            rows.append(row)
    return pd.DataFrame(rows)


def sample_geometry_summary(manifest: dict) -> pd.DataFrame:
    design = manifest["test_design"]
    rows = []
    for beta in design["beta"]:
        for ratio in design["gamma_over_eta"]:
            gamma = float(ratio) * float(design["eta"])
            for n_value in design["n"]:
                for repeat_id in range(int(design["repeats"])):
                    sample = generate_sample(
                        float(beta), float(design["eta"]), gamma,
                        int(n_value), repeat_id, seed=design["seed_namespace"],
                    )
                    mean = float(np.mean(sample))
                    rows.append(
                        {
                            "beta": float(beta),
                            "sample_cv": float(np.std(sample, ddof=1) / mean),
                            "max_over_mean": float(np.max(sample) / mean),
                            "range_over_mean": float((np.max(sample) - np.min(sample)) / mean),
                        }
                    )
    raw = pd.DataFrame(rows)
    output = raw.groupby("beta", sort=True).agg(
        n_samples=("sample_cv", "size"),
        sample_cv_q25=("sample_cv", lambda x: float(np.quantile(x, 0.25))),
        sample_cv_median=("sample_cv", "median"),
        sample_cv_q75=("sample_cv", lambda x: float(np.quantile(x, 0.75))),
        max_over_mean_q25=("max_over_mean", lambda x: float(np.quantile(x, 0.25))),
        max_over_mean_median=("max_over_mean", "median"),
        max_over_mean_q75=("max_over_mean", lambda x: float(np.quantile(x, 0.75))),
        range_over_mean_median=("range_over_mean", "median"),
    ).reset_index()
    return output


def plot_input_geometry(geometry: pd.DataFrame) -> None:
    configure_style()
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.25), constrained_layout=True)
    panels = [
        ("sample_cv", "样本变异系数"),
        ("max_over_mean", r"最大值 / 样本均值"),
    ]
    for index, (ax, (prefix, y_label)) in enumerate(zip(axes, panels)):
        x = geometry["beta"].to_numpy(float)
        median = geometry[f"{prefix}_median"].to_numpy(float)
        q25 = geometry[f"{prefix}_q25"].to_numpy(float)
        q75 = geometry[f"{prefix}_q75"].to_numpy(float)
        ax.fill_between(x, q25, q75, color="#56B4E9", alpha=0.25, linewidth=0)
        ax.plot(x, median, color="#0072B2", marker="o", markersize=3.5, linewidth=1.6)
        ax.axvspan(1.5, 5.0, color="#E5E5E5", alpha=0.45, zorder=0)
        ax.axvline(1.5, color="#777777", linewidth=0.7)
        ax.axvline(5.0, color="#777777", linewidth=0.7)
        ax.set_xlabel(r"形状参数 $\beta$")
        ax.set_ylabel(y_label)
        ax.set_title(f"{chr(65 + index)}  {y_label}", loc="left", fontweight="bold")
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.65)
    fig.text(
        0.5, -0.035,
        "曲线为每个 β 下 6,000 个共享测试样本的中位数，阴影为四分位区间；灰色区域为训练覆盖范围。",
        ha="center", fontsize=8,
    )
    save_figure(fig, "fig_r04_input_geometry")
    plt.close(fig)


def mdm_identifiability_sensitivity(manifest: dict) -> pd.DataFrame:
    """Analytic beta-direction sensitivity implied by the MDM pseudo-scale.

    For log(eta_i) = log(t_i-gamma) - log(q_i)/beta, the derivative with
    respect to beta is log(q_i)/beta**2.  Its spread across ranks is therefore
    a scale-free diagnostic of how strongly the MDM dispersion criterion can
    distinguish neighboring beta values.
    """
    rows = []
    for n_value in manifest["test_design"]["n"]:
        ranks = np.arange(1, int(n_value) + 1, dtype=float)
        f_hat = (ranks - 0.3) / (float(n_value) + 0.4)
        q = -np.log1p(-f_hat)
        log_q_sd = float(np.std(np.log(q), ddof=1))
        for beta in manifest["test_design"]["beta"]:
            sensitivity = log_q_sd / float(beta) ** 2
            rows.append(
                {
                    "n": int(n_value),
                    "beta": float(beta),
                    "sd_log_q": log_q_sd,
                    "beta_direction_sensitivity": sensitivity,
                }
            )
    output = pd.DataFrame(rows)
    reference = output[output["beta"].eq(1.5)].set_index("n")[
        "beta_direction_sensitivity"
    ]
    output["relative_to_beta_1.5"] = output.apply(
        lambda row: row["beta_direction_sensitivity"] / reference.loc[row["n"]],
        axis=1,
    )
    return output


def large_beta_error_correlations(frame: pd.DataFrame) -> pd.DataFrame:
    subset = frame[frame["beta"].ge(4.5)].copy()
    pairs = [
        ("beta_rel_error", "eta_rel_error"),
        ("beta_rel_error", "gamma_rel_error"),
        ("eta_rel_error", "gamma_rel_error"),
    ]
    rows = []
    for method, group in subset.groupby("method", sort=False):
        for left, right in pairs:
            valid = group[[left, right]].dropna()
            rows.append(
                {
                    "method": method,
                    "beta_region": "beta>=4.5",
                    "error_x": left,
                    "error_y": right,
                    "n_pairs": int(len(valid)),
                    "pearson_correlation": float(valid[left].corr(valid[right])),
                }
            )
    return pd.DataFrame(rows)


def selected_delta_summary(frame: pd.DataFrame) -> pd.DataFrame:
    adaptive = frame[frame["method"].eq("Adaptive-MDM")].copy()
    return adaptive.groupby(["beta", "n"], sort=True)["selected_delta"].agg(
        n_samples="size",
        mean="mean",
        q25=lambda x: float(np.quantile(x, 0.25)),
        median="median",
        q75=lambda x: float(np.quantile(x, 0.75)),
    ).reset_index()


def plot_sample_size(n_summary: pd.DataFrame, contrasts: pd.DataFrame) -> None:
    configure_style()
    seen = n_summary[n_summary["beta_group"].eq("seen_grid")]
    fig, axes = plt.subplots(1, 3, figsize=(10.6, 3.25), constrained_layout=True)
    for index, (column, y_label) in enumerate(
        [("J1", r"联合相对误差 $J_1$"), ("x0.95_rmse", r"$x_{0.95}$ 相对 RMSE")]
    ):
        ax = axes[index]
        for method in METHOD_ORDER:
            d = seen[seen["method"].eq(method)].sort_values("n")
            ax.plot(
                d["n"], d[column], label=METHOD_LABELS[method],
                color=COLORS[method], linestyle=LINESTYLES[method],
                marker=MARKERS[method], markersize=4.2, linewidth=1.5,
            )
        ax.set_xticks(sorted(seen["n"].unique()))
        ax.set_xlabel("样本量 n")
        ax.set_ylabel(y_label)
        ax.set_title(f"{chr(65 + index)}  {y_label}", loc="left", fontweight="bold")
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.65)
    axes[0].legend(frameon=False)

    ax = axes[2]
    d = contrasts[
        contrasts["scope"].eq("seen_grid_n")
        & contrasts["contrast"].eq("Direct-P minus Adaptive-MDM")
    ].copy()
    d["scope_value"] = pd.to_numeric(d["scope_value"])
    d = d.sort_values("scope_value")
    ax.errorbar(
        d["scope_value"], d["delta_J1"],
        yerr=np.vstack(
            [d["delta_J1"] - d["ci95_low"], d["ci95_high"] - d["delta_J1"]]
        ),
        color="#7A3E9D", marker="o", markersize=4.2, linewidth=1.4,
        capsize=3,
    )
    ax.axhline(0, color="#222222", linewidth=0.9)
    ax.set_xticks(d["scope_value"])
    ax.set_xlabel("样本量 n")
    ax.set_ylabel(r"Direct − Adaptive $Delta J_1$")
    ax.set_title("C  直接估计的配对优势", loc="left", fontweight="bold")
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.65)
    fig.text(
        0.5, -0.035,
        "已见网格结果；C 图误差线为 3000 次分层配对 bootstrap 95% CI，风险差小于 0 表示直接估计更优。",
        ha="center", fontsize=8,
    )
    save_figure(fig, "fig_r04_sample_size")
    plt.close(fig)


def plot_n_by_beta(n_beta_summary: pd.DataFrame) -> None:
    configure_style()
    n_values = sorted(n_beta_summary["n"].unique())
    fig, axes = plt.subplots(2, 2, figsize=(8.9, 6.15), constrained_layout=True)
    for index, (ax, n_value) in enumerate(zip(axes.flat, n_values)):
        subset = n_beta_summary[n_beta_summary["n"].eq(n_value)]
        for method in METHOD_ORDER:
            d = subset[subset["method"].eq(method)].sort_values("beta")
            ax.plot(
                d["beta"], d["J1"], label=METHOD_LABELS[method],
                color=COLORS[method], linestyle=LINESTYLES[method],
                marker=MARKERS[method], markersize=3.0, linewidth=1.35,
            )
        ax.axvspan(1.5, 5.0, color="#E5E5E5", alpha=0.45, zorder=0)
        ax.axvline(1.5, color="#777777", linewidth=0.7)
        ax.axvline(5.0, color="#777777", linewidth=0.7)
        ax.set_xlabel(r"形状参数 $\beta$")
        ax.set_ylabel(r"联合相对误差 $J_1$")
        ax.set_title(f"{chr(65 + index)}  n = {int(n_value)}", loc="left", fontweight="bold")
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.65)
    axes.flat[0].legend(frameon=False)
    fig.text(
        0.5, -0.02,
        "每个面板只改变样本量；灰色区域为训练覆盖的 beta 范围。",
        ha="center", fontsize=8,
    )
    save_figure(fig, "fig_r04_n_by_beta")
    plt.close(fig)


def plot_large_beta_mechanism(
    beta_summary: pd.DataFrame, sensitivity: pd.DataFrame
) -> None:
    configure_style()
    fig, axes = plt.subplots(1, 3, figsize=(10.7, 3.35), constrained_layout=True)

    ax = axes[0]
    adaptive = beta_summary[beta_summary["method"].eq("Adaptive-MDM")].sort_values("beta")
    parameter_lines = [
        ("beta_bias", r"$\beta$", "#0072B2", "o"),
        ("eta_bias", r"$\eta$", "#D55E00", "s"),
        ("gamma_bias", r"$\gamma/\eta$", "#009E73", "^"),
    ]
    for column, label, color, marker in parameter_lines:
        ax.plot(
            adaptive["beta"], adaptive[column], label=label,
            color=color, marker=marker, markersize=3.4, linewidth=1.45,
        )
    ax.axhline(0, color="#222222", linewidth=0.8)
    ax.axvspan(4.5, 5.75, color="#F0E442", alpha=0.18, zorder=0)
    ax.set_xlabel(r"真实形状参数 $\beta$")
    ax.set_ylabel("平均标准化偏差")
    ax.set_title("A  MDM 参数偏差的补偿方向", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=3)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.65)

    ax = axes[1]
    ax.plot(
        adaptive["beta"], adaptive["J1"], color="#D55E00", marker="s",
        markersize=3.4, linewidth=1.45, label=r"参数联合误差 $J_1$",
    )
    ax.plot(
        adaptive["beta"], adaptive["x0.95_rmse"], color="#0072B2", marker="o",
        markersize=3.4, linewidth=1.45, label=r"$x_{0.95}$ 相对 RMSE",
    )
    ax.axvspan(4.5, 5.75, color="#F0E442", alpha=0.18, zorder=0)
    ax.set_xlabel(r"真实形状参数 $\beta$")
    ax.set_ylabel("误差")
    ax.set_title("B  参数偏移与分位点误差分离", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.65)

    ax = axes[2]
    d = sensitivity[sensitivity["n"].eq(sensitivity["n"].min())].sort_values("beta")
    ax.plot(
        d["beta"], d["relative_to_beta_1.5"], color="#7A3E9D",
        marker="o", markersize=3.0, linewidth=1.4,
    )
    ax.axvspan(4.5, 5.75, color="#F0E442", alpha=0.18, zorder=0)
    ax.set_xlabel(r"形状参数 $\beta$")
    ax.set_ylabel(r"相对 $\beta$ 方向敏感度")
    ax.set_title(r"C  $1/\beta^2$ 导致形状方向变平", loc="left", fontweight="bold")
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.65)
    fig.text(
        0.5, -0.04,
        "A、B 为自适应 MDM 的实验结果；C 为由伪尺度公式推出的解析诊断，以同一 n 下 beta=1.5 的敏感度为 1。黄色区域为大 beta 诊断区。",
        ha="center", fontsize=8,
    )
    save_figure(fig, "fig_r04_large_beta_mechanism")
    plt.close(fig)


def write_report(domain: pd.DataFrame, contrast: pd.DataFrame,
                 improvements: pd.DataFrame, geometry: pd.DataFrame,
                 n_summary: pd.DataFrame, correlations: pd.DataFrame,
                 sensitivity: pd.DataFrame, manifest: dict, reps: int) -> None:
    direct_vs_adaptive = improvements[improvements["comparator"].eq("Adaptive-MDM")]
    by_group = direct_vs_adaptive.set_index("beta_group")
    ci = contrast[
        contrast["scope"].eq("beta_group")
        & contrast["contrast"].eq("Direct-P minus Adaptive-MDM")
    ].set_index("scope_value")
    geometry_by_beta = geometry.set_index("beta")
    seen_n = n_summary[n_summary["beta_group"].eq("seen_grid")].set_index(
        ["method", "n"]
    )
    corr_lookup = correlations.set_index(["method", "error_x", "error_y"])
    mdm_n7 = seen_n.loc[("Adaptive-MDM", 7), "J1"]
    mdm_n20 = seen_n.loc[("Adaptive-MDM", 20), "J1"]
    direct_n7 = seen_n.loc[("Direct-P", 7), "J1"]
    direct_n20 = seen_n.loc[("Direct-P", 20), "J1"]
    eta_gamma_corr = corr_lookup.loc[
        ("Adaptive-MDM", "eta_rel_error", "gamma_rel_error"),
        "pearson_correlation",
    ]
    sensitivity_at_5 = sensitivity[
        sensitivity["beta"].eq(5.0) & sensitivity["n"].eq(7)
    ]["relative_to_beta_1.5"].iloc[0]
    lines = [
        "# Study01 对齐的直接估计泛化实验结果",
        "",
        "## 核心结论",
        "",
        (
            "在训练覆盖范围内，Direct-P 的联合相对误差明显低于自适应 MDM；"
            "未见过的域内 β 点没有削弱这一优势。域外结果具有方向不对称性："
            "低 β 侧发生反转，高 β 侧在本轮测试上限 5.75 处仍保持优势。"
        ),
        "",
        "| 测试区域 | Direct-P $J_1$ | 自适应 MDM $J_1$ | Direct 相对变化 | 配对 $\\Delta J_1$（95% CI） |",
        "|---|---:|---:|---:|---:|",
    ]
    for group in GROUP_ORDER:
        row = by_group.loc[group]
        c = ci.loc[group]
        lines.append(
            f"| {GROUP_LABELS[group]} | {row['J1_direct']:.4f} | "
            f"{row['J1_comparator']:.4f} | {row['J1_change_percent']:+.1f}% | "
            f"{c['delta_J1']:+.4f} [{c['ci95_low']:+.4f}, {c['ci95_high']:+.4f}] |"
        )
    lines += [
        "",
        "负百分数和负风险差表示 Direct-P 更好。置信区间由每个设计单元内的共享样本"
        f"进行 {reps} 次分层配对 bootstrap 得到。远域外汇总同时包含低 β 与高 β 两侧，"
        "应结合逐 β 曲线解释。",
        "",
        "## 机制解释",
        "",
        "- 域内未见点与已见网格表现接近，说明网络学到的不只是八个 β 点的查表；在固定训练域内，它能够插值。",
        "- 低 β 侧从 β=1.25 起 Direct-P 已不再优于自适应 MDM；β=0.75 时差距进一步扩大。β 的 RMSE 是最先明显恶化的部分。",
        "- 高 β 侧没有出现同样反转；到 β=5.75，Direct-P 相对自适应 MDM 的 $J_1$ 仍低约 40%。因此外推风险不仅取决于离训练域多远，也取决于外推方向。",
        "- 低 β 远域外时 Direct-P 的 γ 仍较准，但 β 与 η 的误差上升，联合风险因此反转。网络可以输出合法数值，却没有训练域外的统计校准保证。",
        (
            "- 同一批测试样本的输入形态诊断显示，样本变异系数中位数从 β=1.50 的 "
            f"{geometry_by_beta.loc[1.5, 'sample_cv_median']:.3f} 上升到 β=0.75 的 "
            f"{geometry_by_beta.loc[0.75, 'sample_cv_median']:.3f}；最大值/均值中位数从 "
            f"{geometry_by_beta.loc[1.5, 'max_over_mean_median']:.3f} 上升到 "
            f"{geometry_by_beta.loc[0.75, 'max_over_mean_median']:.3f}。这直接确认了低 β 侧进入训练未覆盖的高离散输入形态。"
        ),
        "- 自适应 MDM 保留逐样本求解结构，域内点风险较高，但远域外退化更缓；这就是结构约束在分布偏移下的价值。",
        "",
        "## 样本量异质性",
        "",
        (
            f"- 在已见网格上，n 从 7 增加到 20 时，Direct-P 的 $J_1$ 从 "
            f"{direct_n7:.4f} 降到 {direct_n20:.4f}，改善 "
            f"{100 * (direct_n7 - direct_n20) / direct_n7:.1f}%；自适应 MDM 从 "
            f"{mdm_n7:.4f} 降到 {mdm_n20:.4f}，改善 "
            f"{100 * (mdm_n7 - mdm_n20) / mdm_n7:.1f}%。"
        ),
        "- 两类路线都从更大样本量获益，但 MDM 改善更快：秩概率近似和伪尺度离散度都会随样本量增加而稳定。",
        "- Direct-P 的优势随 n 增大而收窄，但到 n=20 仍然存在；这符合“训练域先验在极小样本时帮助更大”的解释。",
        "",
        r"## 大 $\beta$ 区域的 MDM 偏差机制",
        "",
        (
            r"MDM 使用伪尺度 $\eta_i=(t_{(i)}-\gamma)/q_i^{1/\beta}$，"
            r"$q_i=-\log(1-\hat F_i)$。取对数后有 "
            r"$\partial\log\eta_i/\partial\beta=\log(q_i)/\beta^2$。因此随 $\beta$ 增大，"
            r"伪尺度离散度对形状参数的区分能力按 $1/\beta^2$ 速度减弱。"
        ),
        (
            rf"- 按秩点对导数的离散度计算，$\beta=5$ 时的相对敏感度只有 "
            rf"$\beta=1.5$ 时的 {sensitivity_at_5:.3f}。这使得小样本扰动更容易沿平缓方向移动解。"
        ),
        (
            rf"- 在 $\beta\geq4.5$ 的共享测试样本中，自适应 MDM 的 $\eta$ 与 "
            rf"$\gamma$ 标准化误差相关系数为 {eta_gamma_corr:.3f}。实验中表现为 "
            r"$\beta$ 和 $\eta$ 负偏、$\gamma$ 正偏，三者在相近分布形状上相互补偿。"
        ),
        r"- 所以大 $\beta$ 时“参数偏差变大”与“某个分位点仍然较准”可以同时成立；后者不能反证三个参数已被准确识别。",
        "",
        "## 证据边界",
        "",
        f"- 训练样本 {manifest['training_design']['samples']:,}，独立共享测试样本 {manifest['validation']['n_samples']:,}。",
        "- β、γ/η、n 与 Study01 对齐；模型种子固定为 42。本实验回答该冻结协议下的点估计与外推问题，不代表多种子训练稳定性。",
        "- Bias、SD 和 RMSE 仅在合法估计上计算；表中同时保留原始尺度与标准化尺度。γ 的标准化误差除以 η，而不是除以可能很小的 γ。失败样本通过训练期冻结惩罚进入 $J_1$，失败率单独报告。",
        "- 区间覆盖率尚未进入本轮实验，因此不能由点估计结果推出不确定性估计也更好。",
        "",
        "## 产物",
        "",
        "- `domain_summary.csv`：四个测试区域的 Bias、SD、RMSE、尾部和失败率。",
        "- `beta_summary.csv`：每个 β 位置的同类指标。",
        "- `paired_bootstrap_contrasts.csv`：区域级和 β 级配对风险差及 95% CI。",
        "- `improvement_table.csv`：Direct-P 相对两条结构路线的百分比变化。",
        "- `sample_geometry_summary.csv`：共享测试样本的归一化输入形态诊断。",
        "- `n_domain_summary.csv` 与 `n_beta_summary.csv`：按样本量分层的区域级与连续 beta 结果。",
        "- `large_beta_summary.csv`、`large_beta_error_correlations.csv`：大 beta 区域的偏差、波动与误差补偿证据。",
        "- `mdm_identifiability_sensitivity.csv`：由 MDM 伪尺度公式推出的 beta 方向解析敏感度。",
        "- `../figures/fig_r04_domain_risk.*`：总体风险与交界图。",
        "- `../figures/fig_r04_parameter_rmse.*`：三个参数的 RMSE 退化图。",
        "- `../figures/fig_r04_input_geometry.*`：低 β 输入分布偏移诊断。",
        "- `../figures/fig_r04_sample_size.*` 与 `fig_r04_n_by_beta.*`：样本量异质性。",
        "- `../figures/fig_r04_large_beta_mechanism.*`：大 beta MDM 偏差、分位点补偿和解析敏感度。",
    ]
    (ANALYSIS_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_checksums(paths: list[Path]) -> None:
    lines = [f"{sha256_file(path)}  {path.relative_to(RUN_ROOT).as_posix()}" for path in paths]
    (RUN_ROOT / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-reps", type=int, default=BOOTSTRAP_REPS)
    args = parser.parse_args()
    reps = max(200, int(args.bootstrap_reps))

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    frame = pd.read_csv(RESULTS_PATH, low_memory=False)
    validate_inputs(frame, manifest)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    domain = summarize(frame, ["method", "beta_group"])
    beta = summarize(frame, ["method", "beta_group", "beta"])
    n_domain = summarize(frame, ["method", "beta_group", "n"])
    n_beta = summarize(frame, ["method", "beta_group", "beta", "n"])
    large_beta = summarize(
        frame[frame["beta"].ge(4.5)], ["method", "beta", "n"]
    )
    contrasts = bootstrap_contrasts(frame, reps)
    improvements = improvement_table(domain)
    geometry = sample_geometry_summary(manifest)
    sensitivity = mdm_identifiability_sensitivity(manifest)
    correlations = large_beta_error_correlations(frame)
    delta_summary = selected_delta_summary(frame)

    domain.to_csv(ANALYSIS_DIR / "domain_summary.csv", index=False)
    beta.to_csv(ANALYSIS_DIR / "beta_summary.csv", index=False)
    contrasts.to_csv(ANALYSIS_DIR / "paired_bootstrap_contrasts.csv", index=False)
    improvements.to_csv(ANALYSIS_DIR / "improvement_table.csv", index=False)
    geometry.to_csv(ANALYSIS_DIR / "sample_geometry_summary.csv", index=False)
    n_domain.to_csv(ANALYSIS_DIR / "n_domain_summary.csv", index=False)
    n_beta.to_csv(ANALYSIS_DIR / "n_beta_summary.csv", index=False)
    large_beta.to_csv(ANALYSIS_DIR / "large_beta_summary.csv", index=False)
    correlations.to_csv(
        ANALYSIS_DIR / "large_beta_error_correlations.csv", index=False
    )
    sensitivity.to_csv(
        ANALYSIS_DIR / "mdm_identifiability_sensitivity.csv", index=False
    )
    delta_summary.to_csv(ANALYSIS_DIR / "adaptive_delta_by_beta_n.csv", index=False)
    plot_domain_risk(beta, contrasts)
    plot_parameter_rmse(beta)
    plot_input_geometry(geometry)
    plot_sample_size(n_domain, contrasts)
    plot_n_by_beta(n_beta)
    plot_large_beta_mechanism(beta, sensitivity)
    write_report(
        domain, contrasts, improvements, geometry, n_domain, correlations,
        sensitivity, manifest, reps,
    )

    paths = [
        MANIFEST_PATH,
        RUN_ROOT / "method_summary.csv",
        RUN_ROOT / "cell_summary.csv",
        RUN_ROOT / "paired_method_differences.csv",
        RESULTS_PATH,
        ANALYSIS_DIR / "domain_summary.csv",
        ANALYSIS_DIR / "beta_summary.csv",
        ANALYSIS_DIR / "paired_bootstrap_contrasts.csv",
        ANALYSIS_DIR / "improvement_table.csv",
        ANALYSIS_DIR / "sample_geometry_summary.csv",
        ANALYSIS_DIR / "n_domain_summary.csv",
        ANALYSIS_DIR / "n_beta_summary.csv",
        ANALYSIS_DIR / "large_beta_summary.csv",
        ANALYSIS_DIR / "large_beta_error_correlations.csv",
        ANALYSIS_DIR / "mdm_identifiability_sensitivity.csv",
        ANALYSIS_DIR / "adaptive_delta_by_beta_n.csv",
        ANALYSIS_DIR / "report.md",
        FIGURE_DIR / "fig_r04_domain_risk.png",
        FIGURE_DIR / "fig_r04_domain_risk.pdf",
        FIGURE_DIR / "fig_r04_parameter_rmse.png",
        FIGURE_DIR / "fig_r04_parameter_rmse.pdf",
        FIGURE_DIR / "fig_r04_input_geometry.png",
        FIGURE_DIR / "fig_r04_input_geometry.pdf",
        FIGURE_DIR / "fig_r04_sample_size.png",
        FIGURE_DIR / "fig_r04_sample_size.pdf",
        FIGURE_DIR / "fig_r04_n_by_beta.png",
        FIGURE_DIR / "fig_r04_n_by_beta.pdf",
        FIGURE_DIR / "fig_r04_large_beta_mechanism.png",
        FIGURE_DIR / "fig_r04_large_beta_mechanism.pdf",
    ]
    write_checksums(paths)
    print(f"ANALYSIS_COMPLETE rows={len(frame)} bootstrap_reps={reps}")


if __name__ == "__main__":
    main()
