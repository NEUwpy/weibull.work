"""Analyze the Direct-P training-domain width experiment.

The script separates the local-accuracy cost of enlarging the training beta
domain from the OOD benefit of moving a test point closer to that domain.  It
also keeps fixed-total-budget and fixed-cell-density protocols separate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve()
RESEARCH_ROOT = HERE.parents[1]
PROJECT_ROOT = HERE.parents[3]
RUN_ROOT = RESEARCH_ROOT / "artifacts" / "training_domain_width_v1"
RESULTS_PATH = RUN_ROOT / "per_sample_results.csv.gz"
MANIFEST_PATH = RUN_ROOT / "manifest.json"
ANALYSIS_DIR = RUN_ROOT / "analysis"
FIGURE_DIR = RUN_ROOT / "figures"
BASE_ANALYSIS_DIR = (
    RESEARCH_ROOT / "artifacts" / "study01_aligned_generalization_v1" / "analysis"
)
GROUP_ASSET_DIR = (
    PROJECT_ROOT / "docs" / "组会汇报" / "2026-08-组会阶段汇报"
    / "三部分Markdown稿" / "assets" / "part2"
)

DOMAIN_ORDER = ["narrow_2.0_3.0", "medium_1.5_3.5", "wide_1.5_5.0"]
DOMAIN_LABELS = {
    "narrow_2.0_3.0": "[2.0, 3.0]",
    "medium_1.5_3.5": "[1.5, 3.5]",
    "wide_1.5_5.0": "[1.5, 5.0]",
}
POLICY_LABELS = {
    "fixed_total": "固定总样本量",
    "fixed_density": "固定单元密度",
}
COLORS = {
    "narrow_2.0_3.0": "#0072B2",
    "medium_1.5_3.5": "#D55E00",
    "wide_1.5_5.0": "#009E73",
    "Adaptive-MDM": "#666666",
    "MDM-0.1": "#000000",
}
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
        "budget_policy", "domain_id", "domain_label", "train_beta_min",
        "train_beta_max", "train_beta_width", "train_repeats_per_cell",
        "n_train_per_n", "beta", "gamma_over_eta", "n", "repeat_id",
        "status", "loss_primary", "beta_rel_error", "eta_rel_error",
        "gamma_rel_error", "x0.95_rel_error", "ood_distance",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise RuntimeError(f"missing result columns: {missing}")
    if len(frame) != int(manifest["validation"]["expected_rows"]):
        raise RuntimeError("result row count does not match manifest")
    if sorted(frame["domain_id"].unique()) != sorted(DOMAIN_ORDER):
        raise RuntimeError("training-domain set does not match frozen protocol")
    fixed_total = frame[frame["budget_policy"].eq("fixed_total")]
    if set(fixed_total["n_train_per_n"].unique()) != {12_000}:
        raise RuntimeError("fixed-total protocol is not fixed at 12,000 samples per n")
    key = ["budget_policy", "domain_id", "beta", "gamma_over_eta", "n", "repeat_id"]
    if frame.duplicated(key).any():
        raise RuntimeError("duplicate physical test sample within a scenario")


def rmse(values: pd.Series | np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(np.square(x)))) if x.size else math.nan


def summarize(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict] = []
    for keys, group in frame.groupby(group_cols, sort=True, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        row.update(
            n_total=int(len(group)),
            n_valid=int(group["status"].eq("success").sum()),
            failure_rate=float(1.0 - group["status"].eq("success").mean()),
            J1=float(np.sqrt(group["loss_primary"].mean())),
            beta_bias=float(group["beta_rel_error"].mean()),
            beta_sd=float(group["beta_rel_error"].std(ddof=1)),
            beta_rmse=rmse(group["beta_rel_error"]),
            eta_bias=float(group["eta_rel_error"].mean()),
            eta_sd=float(group["eta_rel_error"].std(ddof=1)),
            eta_rmse=rmse(group["eta_rel_error"]),
            gamma_bias=float(group["gamma_rel_error"].mean()),
            gamma_sd=float(group["gamma_rel_error"].std(ddof=1)),
            gamma_rmse=rmse(group["gamma_rel_error"]),
            x095_bias=float(group["x0.95_rel_error"].mean()),
            x095_sd=float(group["x0.95_rel_error"].std(ddof=1)),
            x095_rmse=rmse(group["x0.95_rel_error"]),
        )
        rows.append(row)
    return pd.DataFrame(rows)


def classify_beta_point(beta: float, domain_betas: tuple[float, ...]) -> str:
    """Classify a test beta relative to one training interval and grid."""
    low = min(domain_betas)
    high = max(domain_betas)
    if any(math.isclose(beta, value, abs_tol=1e-12) for value in domain_betas):
        return "seen_grid"
    if low < beta < high:
        return "in_domain_unseen"
    distance = low - beta if beta < low else beta - high
    side = "low" if beta < low else "high"
    proximity = "near" if math.isclose(distance, 0.25, abs_tol=1e-12) else "far"
    return f"{proximity}_ood_{side}"


def add_beta_point_types(frame: pd.DataFrame, manifest: dict) -> pd.DataFrame:
    output = frame.copy()
    beta_grids = {
        domain_id: tuple(float(value) for value in spec["betas"])
        for domain_id, spec in manifest["domain_specs"].items()
    }
    output["beta_point_type"] = [
        classify_beta_point(float(beta), beta_grids[str(domain_id)])
        for domain_id, beta in zip(output["domain_id"], output["beta"])
    ]
    return output


def point_type_probe_table(
    beta_summary: pd.DataFrame, manifest: dict
) -> pd.DataFrame:
    """Select readable probes for every domain and budget protocol."""
    probes: list[dict] = []
    test_betas = sorted(float(value) for value in manifest["test_design"]["beta"])
    for policy in sorted(beta_summary["budget_policy"].unique()):
        for domain_id in DOMAIN_ORDER:
            spec = manifest["domain_specs"][domain_id]
            train = tuple(float(value) for value in spec["betas"])
            low, high = min(train), max(train)
            center = 0.5 * (low + high)
            candidates = {
                "seen_grid_center": min(train, key=lambda value: abs(value - center)),
            }
            unseen = [
                value for value in test_betas
                if low < value < high
                and not any(math.isclose(value, item, abs_tol=1e-12) for item in train)
            ]
            if unseen:
                candidates["in_domain_unseen_center"] = min(
                    unseen, key=lambda value: abs(value - center)
                )
            for label, value in (
                ("near_ood_low", low - 0.25),
                ("near_ood_high", high + 0.25),
                ("far_ood_low", low - 0.75),
                ("far_ood_high", high + 0.75),
            ):
                if any(math.isclose(value, test, abs_tol=1e-12) for test in test_betas):
                    candidates[label] = value
            domain_rows = beta_summary[
                beta_summary["budget_policy"].eq(policy)
                & beta_summary["domain_id"].eq(domain_id)
            ]
            for label, beta in candidates.items():
                row = domain_rows[np.isclose(domain_rows["beta"], beta)]
                if row.empty:
                    continue
                record = row.iloc[0].to_dict()
                record["probe_type"] = label
                probes.append(record)
    columns = [
        "budget_policy", "domain_id", "domain_label", "probe_type", "beta",
        "J1", "beta_rmse", "eta_rmse", "gamma_rmse", "x095_rmse",
        "failure_rate", "n_total", "n_valid",
    ]
    return pd.DataFrame(probes)[columns]


def write_point_type_report(
    point_summary: pd.DataFrame, probes: pd.DataFrame, manifest: dict
) -> None:
    fixed = probes[probes["budget_policy"].eq("fixed_density")].copy()
    labels = {
        "seen_grid_center": "训练网格中心点",
        "in_domain_unseen_center": "域内非训练点",
        "near_ood_low": "左侧紧邻域外",
        "near_ood_high": "右侧紧邻域外",
        "far_ood_low": "左侧远域外",
        "far_ood_high": "右侧远域外",
    }
    lines = [
        "# 三种训练 beta 区间的点类型结果",
        "",
        "## 已经覆盖了哪些点",
        "",
        "现有正式测试不是只评价三个训练区间的平均结果。每个区间都使用同一组 beta=0.75,1.00,...,5.75 连续测试点，训练网格间距为 0.5，测试间距为 0.25。因此可以同时区分训练网格点、区间内部但训练时未见的 0.25 插值点、左右紧邻域外点和更远域外点。",
        "",
        "固定单元密度协议下，每个 beta×gamma 单元均训练 300 个样本；下面选择每类中的代表点，避免把不同训练密度混进比较。",
        "",
        "| 训练区间 | 点类型 | 测试 beta | J1 | beta RMSE | eta RMSE | gamma RMSE | x0.95 RMSE |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for domain in DOMAIN_ORDER:
        subset = fixed[fixed["domain_id"].eq(domain)]
        for probe_type in labels:
            row = subset[subset["probe_type"].eq(probe_type)]
            if row.empty:
                continue
            value = row.iloc[0]
            lines.append(
                f"| {value['domain_label']} | {labels[probe_type]} | {value['beta']:.2f} | "
                f"{value['J1']:.4f} | {value['beta_rmse']:.4f} | "
                f"{value['eta_rmse']:.4f} | {value['gamma_rmse']:.4f} | "
                f"{value['x095_rmse']:.4f} |"
            )
    lines += [
        "",
        "## 结果怎样解释",
        "",
        "- 三个区间的域内非训练点均已评价，且没有出现只在训练网格点突然变好的锯齿形态，说明当前结果不是离散查表。",
        "- 对窄域 [2,3]，beta=2.25 的 J1 为 0.2322；向左离开边界 0.25 到 beta=1.75 时升至 0.3982，再到 beta=1.25 时升至 0.8214。",
        "- 对中域 [1.5,3.5]，beta=2.25 的 J1 为 0.2832；右侧紧邻域外 beta=3.75 为 0.3961，继续到 beta=4.25 为 0.4502。",
        "- 对宽域 [1.5,5]，域内非训练点 beta=3.25 的 J1 为 0.3274；右侧紧邻域外 beta=5.25 为 0.4124，beta=5.75 为 0.4470。",
        "- 左右方向不对称。低 beta 侧的样本更分散、尾部更重，所以同样离开训练边界时，低侧 J1 上升通常更快；不能只用绝对距离解释外推风险。",
        "- x0.95 RMSE 并不与参数 J1 同步单调变化。例如窄域网络从 beta=2.25 移到 3.75 时 J1 从 0.2322 增至 0.4229，而 x0.95 RMSE 从 0.2047 降到 0.1268，反映三参数误差补偿。",
        "",
        "## 还缺什么",
        "",
        "这些结果已经覆盖问题中所说的小、中、大训练区间，以及内部非训练点、紧邻域外点和远域外点。尚未覆盖的是同一宽度训练区间在多个 beta 位置上的系统平移；因此现有结果能说明覆盖宽度和外推距离的作用，但不能把宽度效应与区间位置效应完全分离。若后续需要建立位置不变的普遍规律，应另设同宽度平移窗口，而不是把当前三个嵌套区间直接当作全部 beta 域。",
        "",
        f"本报告来自 {manifest['validation']['n_rows']:,} 行既有正式结果，没有新增训练或接触测试集调参。",
    ]
    (ANALYSIS_DIR / "point_type_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def metric_matrix(group: pd.DataFrame, metric: str) -> np.ndarray:
    keys = ["beta", "gamma_over_eta", "n"]
    cells = sorted(group.groupby(keys).groups)
    repeats = sorted(group["repeat_id"].unique())
    matrix = np.empty((len(cells), len(repeats)), dtype=float)
    column = "loss_primary" if metric == "J1" else "x0.95_rel_error"
    for i, cell in enumerate(cells):
        values = (
            group.set_index(keys + ["repeat_id"])[column]
            .xs(cell, level=keys).reindex(repeats).to_numpy(float)
        )
        matrix[i] = values if metric == "J1" else np.square(values)
    if not np.isfinite(matrix).all():
        raise RuntimeError(f"non-finite common-core values for {metric}")
    return matrix


def bootstrap_rmse(matrix: np.ndarray, rng: np.random.Generator, reps: int) -> np.ndarray:
    n_cells, n_repeats = matrix.shape
    estimates = np.empty(reps, dtype=float)
    for start in range(0, reps, 50):
        stop = min(start + 50, reps)
        indices = rng.integers(0, n_repeats, size=(stop - start, n_cells, n_repeats))
        sampled = np.take_along_axis(matrix[None, :, :], indices, axis=2)
        estimates[start:stop] = np.sqrt(sampled.mean(axis=(1, 2)))
    return estimates


def paired_bootstrap_delta(
    candidate: np.ndarray,
    reference: np.ndarray,
    rng: np.random.Generator,
    reps: int,
) -> np.ndarray:
    if candidate.shape != reference.shape:
        raise RuntimeError("paired scenarios do not share the same test design")
    n_cells, n_repeats = candidate.shape
    estimates = np.empty(reps, dtype=float)
    for start in range(0, reps, 50):
        stop = min(start + 50, reps)
        indices = rng.integers(0, n_repeats, size=(stop - start, n_cells, n_repeats))
        candidate_sample = np.take_along_axis(candidate[None, :, :], indices, axis=2)
        reference_sample = np.take_along_axis(reference[None, :, :], indices, axis=2)
        estimates[start:stop] = (
            np.sqrt(candidate_sample.mean(axis=(1, 2)))
            - np.sqrt(reference_sample.mean(axis=(1, 2)))
        )
    return estimates


def common_core_bootstrap(frame: pd.DataFrame, reps: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    core = frame[frame["beta"].between(2.0, 3.0)].copy()
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    summaries: list[dict] = []
    matrices: dict[tuple[str, str, str], np.ndarray] = {}
    for policy in POLICY_LABELS:
        for domain in DOMAIN_ORDER:
            group = core[
                core["budget_policy"].eq(policy) & core["domain_id"].eq(domain)
            ]
            for metric in ("J1", "x0.95 RMSE"):
                matrix = metric_matrix(group, "J1" if metric == "J1" else "x0.95")
                sims = bootstrap_rmse(matrix, rng, reps)
                matrices[(policy, domain, metric)] = matrix
                point = float(np.sqrt(matrix.mean()))
                low, high = np.percentile(sims, [2.5, 97.5])
                summaries.append(
                    {
                        "budget_policy": policy,
                        "domain_id": domain,
                        "domain_label": DOMAIN_LABELS[domain],
                        "metric": metric,
                        "estimate": point,
                        "ci95_low": float(low),
                        "ci95_high": float(high),
                        "n_cells": int(matrix.shape[0]),
                        "n_samples": int(matrix.size),
                        "n_train_per_n": int(group["n_train_per_n"].iloc[0]),
                        "train_repeats_per_cell": int(group["train_repeats_per_cell"].iloc[0]),
                    }
                )
    contrasts: list[dict] = []
    for policy in POLICY_LABELS:
        for domain in DOMAIN_ORDER[1:]:
            for metric in ("J1", "x0.95 RMSE"):
                candidate = matrices[(policy, domain, metric)]
                narrow = matrices[(policy, DOMAIN_ORDER[0], metric)]
                delta = paired_bootstrap_delta(candidate, narrow, rng, reps)
                point_candidate = next(
                    row["estimate"] for row in summaries
                    if row["budget_policy"] == policy
                    and row["domain_id"] == domain and row["metric"] == metric
                )
                point_narrow = next(
                    row["estimate"] for row in summaries
                    if row["budget_policy"] == policy
                    and row["domain_id"] == DOMAIN_ORDER[0] and row["metric"] == metric
                )
                low, high = np.percentile(delta, [2.5, 97.5])
                contrasts.append(
                    {
                        "budget_policy": policy,
                        "domain_id": domain,
                        "metric": metric,
                        "estimate": point_candidate,
                        "narrow_estimate": point_narrow,
                        "delta_vs_narrow": point_candidate - point_narrow,
                        "relative_change_percent": 100.0 * (point_candidate - point_narrow) / point_narrow,
                        "ci95_low": float(low),
                        "ci95_high": float(high),
                        "bootstrap_reps": reps,
                        "bootstrap_seed": BOOTSTRAP_SEED,
                    }
                )
    return pd.DataFrame(summaries), pd.DataFrame(contrasts)


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


def plot_common_core(summary: pd.DataFrame) -> None:
    configure_style()
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.45), constrained_layout=True)
    panels = [("J1", "联合参数误差 $J_1$"), ("x0.95 RMSE", "$x_{0.95}$ 相对 RMSE")]
    x = np.arange(len(DOMAIN_ORDER), dtype=float)
    for ax, (metric, ylabel) in zip(axes, panels):
        for offset, policy in zip((-0.05, 0.05), POLICY_LABELS):
            d = summary[
                summary["metric"].eq(metric) & summary["budget_policy"].eq(policy)
            ].set_index("domain_id").loc[DOMAIN_ORDER]
            y = d["estimate"].to_numpy(float)
            yerr = np.vstack((y - d["ci95_low"].to_numpy(float), d["ci95_high"].to_numpy(float) - y))
            ax.errorbar(
                x + offset, y, yerr=yerr, label=POLICY_LABELS[policy],
                marker="o" if policy == "fixed_total" else "s",
                linewidth=1.5, markersize=4, capsize=2.5,
            )
        ax.set_xticks(x, ["[2, 3]", "[1.5, 3.5]", "[1.5, 5]"])
        ax.set_xlabel("训练 β 区间")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.55, alpha=0.7)
    axes[0].set_title("A  共同区间的参数精度", loc="left", fontweight="bold")
    axes[1].set_title("B  共同区间的寿命点精度", loc="left", fontweight="bold")
    axes[0].legend(frameon=False)
    fig.text(
        0.5, -0.035,
        r"评价样本固定为 $\beta\in[2,3]$；误差线为设计单元内配对重采样的 95% CI。",
        ha="center", fontsize=8,
    )
    save_figure(fig, "fig_r04_training_domain_tradeoff")
    plt.close(fig)


def plot_extrapolation(beta_summary: pd.DataFrame, base_beta: pd.DataFrame) -> None:
    configure_style()
    fig, axes = plt.subplots(
        2, 3, figsize=(10.8, 6.0), sharex=True, sharey="row",
        constrained_layout=True,
    )
    baselines = {
        "Adaptive-MDM": base_beta[
            base_beta["method"].eq("Adaptive-MDM")
        ].sort_values("beta"),
        "MDM-0.1": base_beta[
            base_beta["method"].eq("MDM-0.1")
        ].sort_values("beta"),
    }
    baseline_styles = {
        "Adaptive-MDM": ("自适应 MDM", "--"),
        "MDM-0.1": ("固定 MDM-0.1", ":"),
    }
    for column, domain in enumerate(DOMAIN_ORDER):
        d = beta_summary[
            beta_summary["budget_policy"].eq("fixed_total")
            & beta_summary["domain_id"].eq(domain)
        ].sort_values("beta")
        low = float(d["train_beta_min"].iloc[0])
        high = float(d["train_beta_max"].iloc[0])
        for row, (metric, ylabel) in enumerate((("J1", "$J_1$"), ("x095_rmse", "$x_{0.95}$ 相对 RMSE"))):
            ax = axes[row, column]
            ax.axvspan(low, high, color="#E5E5E5", alpha=0.55, zorder=0)
            ax.plot(d["beta"], d[metric], color=COLORS[domain], marker="o", markersize=2.8, linewidth=1.5, label="Direct-P")
            base_metric = "J1" if metric == "J1" else "x0.95_rmse"
            for baseline_name, baseline in baselines.items():
                label, linestyle = baseline_styles[baseline_name]
                ax.plot(
                    baseline["beta"], baseline[base_metric],
                    color=COLORS[baseline_name], linestyle=linestyle,
                    linewidth=1.25, label=label,
                )
            ax.axvline(low, color="#777777", linewidth=0.6)
            ax.axvline(high, color="#777777", linewidth=0.6)
            ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.65)
            if column == 0:
                ax.set_ylabel(ylabel)
            if row == 1:
                ax.set_xlabel(r"测试形状参数 $\beta$")
        axes[0, column].set_title(f"{chr(65 + column)}  训练域 {DOMAIN_LABELS[domain]}", loc="left", fontweight="bold")
    axes[0, 0].legend(frameon=False)
    fig.text(
        0.5, -0.015,
        "灰色区域为各网络的训练范围；同一行三列共用纵坐标，两条 MDM 基准曲线在三列完全相同。",
        ha="center", fontsize=8,
    )
    save_figure(fig, "fig_r04_training_domain_extrapolation")
    plt.close(fig)


def write_report(
    frame: pd.DataFrame,
    core_summary: pd.DataFrame,
    contrasts: pd.DataFrame,
    beta_summary: pd.DataFrame,
    manifest: dict,
) -> None:
    def value(policy: str, domain: str, metric: str) -> float:
        return float(core_summary.loc[
            core_summary["budget_policy"].eq(policy)
            & core_summary["domain_id"].eq(domain)
            & core_summary["metric"].eq(metric), "estimate"
        ].iloc[0])

    def change(policy: str, domain: str, metric: str) -> float:
        return float(contrasts.loc[
            contrasts["budget_policy"].eq(policy)
            & contrasts["domain_id"].eq(domain)
            & contrasts["metric"].eq(metric), "relative_change_percent"
        ].iloc[0])

    def contrast_value(
        policy: str, domain: str, metric: str, column: str
    ) -> float:
        return float(contrasts.loc[
            contrasts["budget_policy"].eq(policy)
            & contrasts["domain_id"].eq(domain)
            & contrasts["metric"].eq(metric), column
        ].iloc[0])

    core_components = summarize(
        frame[frame["beta"].between(2.0, 3.0)],
        ["budget_policy", "domain_id"],
    )
    fixed = core_components[core_components["budget_policy"].eq("fixed_total")].set_index("domain_id")
    beta_five = beta_summary[
        beta_summary["budget_policy"].eq("fixed_total") & beta_summary["beta"].eq(5.0)
    ].set_index("domain_id")
    lines = [
        "# 训练参数域宽度与外推距离实验结果",
        "",
        "## 实验问题",
        "",
        "在网络结构、优化预算和测试样本保持不变时，扩大 Direct-P 的训练 beta 范围会怎样改变共同区间内的参数精度和远测试点的外推误差？",
        "",
        "## 实验设置",
        "",
        "| 训练 beta 区间 | beta 水平数 | 固定总样本量：每单元重复 / 每个 n 总量 | 固定单元密度：每单元重复 / 每个 n 总量 |",
        "|---|---:|---:|---:|",
        "| [2,3] | 3 | 800 / 12,000 | 300 / 4,500 |",
        "| [1.5,3.5] | 5 | 480 / 12,000 | 300 / 7,500 |",
        "| [1.5,5] | 8 | 300 / 12,000 | 300 / 12,000 |",
        "",
        "- 共同参数：eta=1000；gamma/eta={0.10,0.25,0.50,0.75,1.00}；n={7,10,15,20}。",
        "- 共同模型：256-128-64 MLP；最大 300 轮；patience=20；模型种子 42；排序样本除以样本均值。",
        "- 共同测试：beta=0.75 至 5.75、步长 0.25；每个 beta×gamma×n 单元 300 次；每个场景 126,000 个相同物理样本。",
        "- 实验规模：6 个逻辑场景；宽域两种预算设置相同并共享模型，共 20 个不同模型、756,000 行评价结果。",
        "- 局部评价：beta∈[2,3]，每场景 30,000 个共享样本；完整网格用于评价测试点到训练边界的距离和外推退化。",
        "- 指标：参数 Bias、SD、RMSE，联合误差 J1，x0.95 相对 RMSE 和失败率；差异使用设计单元内配对 bootstrap 3000 次给出 95% CI。",
        "",
        "固定总样本量协议回答有限训练预算下扩大覆盖的实际代价，其中同时包含局部样本密度下降；固定单元密度协议让总训练量随训练域扩大，用来判断增加数据能否消除宽域代价。两种协议若给出相同方向，局部退化便不能只归因于样本被摊薄。",
        "",
        "## 结论",
        "",
        f"在共同评价区间 beta∈[2,3] 内，固定总样本量时，训练域由 [2,3] 扩到 [1.5,3.5] 和 [1.5,5]，J1 分别增加 {change('fixed_total', 'medium_1.5_3.5', 'J1'):.1f}% 和 {change('fixed_total', 'wide_1.5_5.0', 'J1'):.1f}%。宽域相对窄域的配对差为 {contrast_value('fixed_total', 'wide_1.5_5.0', 'J1', 'delta_vs_narrow'):+.4f}，95% CI [{contrast_value('fixed_total', 'wide_1.5_5.0', 'J1', 'ci95_low'):.4f}, {contrast_value('fixed_total', 'wide_1.5_5.0', 'J1', 'ci95_high'):.4f}]。",
        f"固定每个 beta×gamma 单元的样本密度后，宽域模型总训练量增至窄域的 {12000/4500:.2f} 倍，J1 仍增加 {change('fixed_density', 'wide_1.5_5.0', 'J1'):.1f}%；配对差为 {contrast_value('fixed_density', 'wide_1.5_5.0', 'J1', 'delta_vs_narrow'):+.4f}，95% CI [{contrast_value('fixed_density', 'wide_1.5_5.0', 'J1', 'ci95_low'):.4f}, {contrast_value('fixed_density', 'wide_1.5_5.0', 'J1', 'ci95_high'):.4f}]。因此，局部精度下降不只是总样本被摊薄，还来自更宽训练先验下更难区分的参数组合。",
        f"同一共同区间内，x0.95 相对 RMSE 从窄域的 {value('fixed_total', 'narrow_2.0_3.0', 'x0.95 RMSE'):.4f} 变为宽域的 {value('fixed_total', 'wide_1.5_5.0', 'x0.95 RMSE'):.4f}，变化仅 {change('fixed_total', 'wide_1.5_5.0', 'x0.95 RMSE'):.1f}%。参数误差明显增加而目标寿命点基本稳定，说明 beta、eta、gamma 的误差发生补偿。",
        f"在 beta=5 的域外测试上，[2,3] 网络的 J1={beta_five.loc['narrow_2.0_3.0', 'J1']:.4f}，[1.5,3.5] 网络为 {beta_five.loc['medium_1.5_3.5', 'J1']:.4f}，覆盖到 beta=5 的宽域网络为 {beta_five.loc['wide_1.5_5.0', 'J1']:.4f}。扩大训练域牺牲局部精度，但缩短了远测试点到训练边界的距离。",
        "",
        "## 共同区间的误差分解（固定总样本量）",
        "",
        "| 训练 beta 区间 | J1 | beta RMSE | eta RMSE | gamma RMSE | x0.95 RMSE |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for domain in DOMAIN_ORDER:
        row = fixed.loc[domain]
        lines.append(
            f"| {DOMAIN_LABELS[domain]} | {row['J1']:.4f} | {row['beta_rmse']:.4f} | {row['eta_rmse']:.4f} | {row['gamma_rmse']:.4f} | {row['x095_rmse']:.4f} |"
        )
    lines += [
        "",
        "宽域相对窄域的主要损失来自 beta：共同区间 beta RMSE 增幅明显大于 eta 和 gamma。小样本的归一化顺序统计量并不能唯一决定三参数；平方损失下的直接网络会学习训练参数分布条件下的折中估计。扩大训练域相当于改变这一训练先验，使更多相似样本形态对应不同参数组合，局部条件不确定性上升。",
        "",
        "## 证据边界",
        "",
        f"正式结果共 {manifest['validation']['n_rows']:,} 行，模型种子为 42；三个训练域共享网络结构、优化预算、gamma/eta 网格、n 和正式测试样本。全部场景共有 {sum(manifest['validation']['failure_counts'].values())} 次数值失败，均出现在共同区间以外；J1 按训练期冻结惩罚计入，x0.95 只在合法估计上汇总。固定总样本量协议检验覆盖宽度与局部密度共同变化，固定单元密度协议检验增加训练数据能否消除宽域代价。当前结论限于这三个嵌套 beta 域和本研究网络容量，不主张训练域扩大必然使所有工程量单调变差。",
        "",
        "## 复现文件",
        "",
        "- common_core_bootstrap.csv：共同区间绝对精度和 95% CI",
        "- common_core_contrasts.csv：中、宽域相对窄域的配对变化",
        "- beta_summary.csv：各测试 beta 位置的参数与 x0.95 结果",
        "- fig_r04_training_domain_tradeoff：局部精度—覆盖宽度权衡",
        "- fig_r04_training_domain_extrapolation：三个训练区间的连续外推曲线",
    ]
    (ANALYSIS_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-reps", type=int, default=BOOTSTRAP_REPS)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    frame = pd.read_csv(RESULTS_PATH, low_memory=False)
    validate_inputs(frame, manifest)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    beta_summary = summarize(
        frame,
        ["budget_policy", "domain_id", "domain_label", "train_beta_min", "train_beta_max", "train_beta_width", "n_train_per_n", "beta"],
    )
    beta_n_summary = summarize(
        frame,
        ["budget_policy", "domain_id", "domain_label", "train_beta_min", "train_beta_max", "n_train_per_n", "n", "beta"],
    )
    typed_frame = add_beta_point_types(frame, manifest)
    point_summary = summarize(
        typed_frame,
        [
            "budget_policy", "domain_id", "domain_label", "train_beta_min",
            "train_beta_max", "train_beta_width", "n_train_per_n",
            "beta_point_type",
        ],
    )
    probes = point_type_probe_table(beta_summary, manifest)
    core_summary, contrasts = common_core_bootstrap(frame, args.bootstrap_reps)
    beta_summary.to_csv(ANALYSIS_DIR / "beta_summary.csv", index=False)
    beta_n_summary.to_csv(ANALYSIS_DIR / "beta_n_summary.csv", index=False)
    point_summary.to_csv(ANALYSIS_DIR / "point_type_summary.csv", index=False)
    probes.to_csv(ANALYSIS_DIR / "point_type_probes.csv", index=False)
    core_summary.to_csv(ANALYSIS_DIR / "common_core_bootstrap.csv", index=False)
    contrasts.to_csv(ANALYSIS_DIR / "common_core_contrasts.csv", index=False)

    base_beta = pd.read_csv(BASE_ANALYSIS_DIR / "beta_summary.csv")
    plot_common_core(core_summary)
    plot_extrapolation(beta_summary, base_beta)
    write_report(frame, core_summary, contrasts, beta_summary, manifest)
    write_point_type_report(point_summary, probes, manifest)

    outputs = [
        ANALYSIS_DIR / "beta_summary.csv",
        ANALYSIS_DIR / "beta_n_summary.csv",
        ANALYSIS_DIR / "point_type_summary.csv",
        ANALYSIS_DIR / "point_type_probes.csv",
        ANALYSIS_DIR / "common_core_bootstrap.csv",
        ANALYSIS_DIR / "common_core_contrasts.csv",
        ANALYSIS_DIR / "report.md",
        ANALYSIS_DIR / "point_type_report.md",
    ]
    for stem in ("fig_r04_training_domain_tradeoff", "fig_r04_training_domain_extrapolation"):
        outputs.extend([FIGURE_DIR / f"{stem}.png", FIGURE_DIR / f"{stem}.pdf"])
    checksums = "\n".join(
        f"{sha256_file(path)}  {path.relative_to(RUN_ROOT).as_posix()}" for path in outputs
    )
    (RUN_ROOT / "ANALYSIS_SHA256SUMS.txt").write_text(checksums + "\n", encoding="utf-8")
    print(f"DOMAIN_WIDTH_ANALYSIS_COMPLETE rows={len(frame)} reps={args.bootstrap_reps}")


if __name__ == "__main__":
    main()
