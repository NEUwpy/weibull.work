"""Test whether QCP restores Q errors away from the trained x_0.95 target.

No model is trained. The analysis consumes frozen common-budget P/Q and QCP
parameter predictions under protocol 23.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from . import config as CFG
from . import constrained_confirm as CONFIRM


ROOT = Path(CFG.STUDY02_ROOT)
OUT = ROOT / "artifacts" / "qcp_cross_quantile_recovery"
ANALYSIS = OUT / "analysis"
FIGURE_OUT = ROOT / "figures" / "qcp-main"
QCP_ROOT = ROOT / "artifacts" / "qcp_constrained_confirm"
MAIN_ROOT = ROOT / "artifacts" / "qcp_main_analysis"
PROTOCOL = ROOT / "protocols" / "23-QCP跨寿命点恢复机制合同.md"
COMPARISON_PROTOCOL = ROOT / "protocols" / "24-三路线跨寿命点总比较合同.md"
SOURCE_CANDIDATES = (
    ROOT / "artifacts" / "equal_budget_sensitivity",
    ROOT / "归档" / "旧实验" / "四路线同预算敏感性" / "artifacts" /
    "equal_budget_sensitivity",
)
ROUTES = ("P", "Q", "QCP")
PRIMARY_R = (0.90, 0.95, 0.99)
CURVE_R = np.unique(np.concatenate((np.linspace(0.50, 0.99, 50), PRIMARY_R)))
COLORS = {"P": "#7A7A7A", "Q": "#0072B2", "QCP": "#009E73"}
LINESTYLES = {"P": "--", "Q": "-.", "QCP": "-"}
MARKERS = {"P": "s", "Q": "o", "QCP": "D"}
KEY_FIELDS = ("keys_beta", "keys_gamma_over_eta", "keys_n", "keys_repeat_id")


def _source_root() -> Path:
    for candidate in SOURCE_CANDIDATES:
        if (candidate / "evidence").exists():
            return candidate
    raise FileNotFoundError("frozen common-budget P/Q evidence was not found")


def _sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as data:
        return {name: np.asarray(data[name]) for name in data.files}


def _evidence_path(source: Path, n: int, fold: int, seed: int, route: str) -> Path:
    root = QCP_ROOT if route == "QCP" else source
    return root / "evidence" / f"n{n}_f{fold}_s{seed}_r{route}.npz"


def _quantile(beta: np.ndarray, eta: np.ndarray, gamma: np.ndarray,
              reliability: float) -> np.ndarray:
    return gamma + eta * (-np.log(reliability)) ** (1.0 / beta)


def _metrics(error: np.ndarray) -> dict[str, float]:
    absolute = np.abs(error)
    return {
        "rmsre": float(np.sqrt(np.mean(error ** 2))),
        "mae": float(np.mean(absolute)),
        "signed_relative_bias": float(np.mean(error)),
        "relative_error_sd": float(np.std(error)),
        "within_10pct": float(np.mean(absolute <= 0.10)),
    }


def _paired_contrast(
    target: str, comparator: str, reliability: float,
    pooled: dict, model_mse: dict, truth_cell_errors: dict,
    *, seed: int,
) -> dict[str, object]:
    boot = CONFIRM.crossed_bootstrap_contrast(
        model_mse[reliability][target], model_mse[reliability][comparator],
        replicates=200_000, seed=seed,
    )
    target_rmsre = pooled[reliability][target]["rmsre"]
    comparator_rmsre = pooled[reliability][comparator]["rmsre"]
    effects = []
    for key in sorted(truth_cell_errors[reliability][target]):
        target_values = np.concatenate(
            truth_cell_errors[reliability][target][key]
        )
        comparator_values = np.concatenate(
            truth_cell_errors[reliability][comparator][key]
        )
        target_cell = float(np.sqrt(np.mean(target_values ** 2)))
        comparator_cell = float(np.sqrt(np.mean(comparator_values ** 2)))
        effects.append((comparator_cell - target_cell) / comparator_cell)
    return {
        "target": target,
        "comparator": comparator,
        "relative_rmsre_improvement": float(
            (comparator_rmsre - target_rmsre) / comparator_rmsre
        ),
        "relative_rmsre_improvement_95ci":
            boot["relative_rrmse_improvement_95ci"],
        "favorable_truth_cells": int(np.sum(np.asarray(effects) > 0.0)),
        "total_truth_cells": len(effects),
    }


def _plot(summary: dict, curve_rows: list[dict], primary_rows: list[dict]) -> None:
    fig, (ax_curve, ax_effect, ax_param) = plt.subplots(
        1, 3, figsize=(7.2, 2.65), constrained_layout=True
    )

    for route in ROUTES:
        rows = [row for row in curve_rows if row["route"] == route]
        ax_curve.plot(
            [row["reliability"] for row in rows],
            [100.0 * row["rmsre"] for row in rows],
            color=COLORS[route], linestyle=LINESTYLES[route], linewidth=1.5,
            label=route,
        )
    for reliability in PRIMARY_R:
        ax_curve.axvline(reliability, color="#B0B0B0", linewidth=0.65,
                        linestyle=":", zorder=0)
    ax_curve.set_xlabel("Reliability level, $R$")
    ax_curve.set_ylabel("RMSRE of $x_R$ (%)")
    ax_curve.set_title("A  Life-point accuracy", loc="left",
                       fontweight="bold", fontsize=8.8)
    ax_curve.legend(frameon=False, fontsize=7, ncol=3)

    x = np.arange(len(PRIMARY_R))
    for offset, (name, color, marker) in enumerate((
        ("QCP vs Q", COLORS["QCP"], "D"),
        ("QCP vs P", "#D55E00", "o"),
    )):
        contrast = [
            summary["pairwise_comparisons"][f"x_{r:.2f}"][name.replace(" ", "_")]
            for r in PRIMARY_R
        ]
        effect = np.asarray([
            100.0 * row["relative_rmsre_improvement"] for row in contrast
        ])
        low = np.asarray([
            100.0 * row["relative_rmsre_improvement_95ci"][0]
            for row in contrast
        ])
        high = np.asarray([
            100.0 * row["relative_rmsre_improvement_95ci"][1]
            for row in contrast
        ])
        x_offset = x + (-0.08 if offset == 0 else 0.08)
        ax_effect.errorbar(
            x_offset, effect, yerr=np.vstack((effect - low, high - effect)),
            fmt=marker, color=color, markerfacecolor=color,
            markeredgecolor="black", markeredgewidth=0.55, capsize=3,
            linewidth=1.1, markersize=4.8, label=name,
        )
    ax_effect.axhline(0.0, color="#555555", linewidth=0.9, linestyle="--")
    ax_effect.set_xticks(x, [f"$x_{{{r:.2f}}}$" for r in PRIMARY_R])
    ax_effect.set_ylabel("Relative RMSRE gain (%)")
    ax_effect.set_title("B  QCP contrasts", loc="left",
                        fontweight="bold", fontsize=8.8)
    ax_effect.legend(frameon=False, fontsize=6.8, loc="upper center")

    components = ("beta", "eta", "gamma")
    width = 0.24
    positions = np.arange(len(components))
    for index, route in enumerate(ROUTES):
        values = [100.0 * summary["parameter_normalized_rmse"][route][component]
                  for component in components]
        ax_param.bar(
            positions + (index - 1) * width, values, width=width,
            color=COLORS[route], alpha=0.86, label=route,
            edgecolor="black", linewidth=0.35,
        )
    ax_param.set_yscale("log")
    ax_param.set_xticks(positions, [r"$u_\beta$", r"$u_\eta$", r"$u_\gamma$"])
    ax_param.set_ylabel("Normalized RMSE (%)")
    ax_param.set_title("C  Parameter recovery", loc="left",
                       fontweight="bold", fontsize=8.8)
    ax_param.legend(frameon=False, fontsize=7, ncol=3)

    for ax in (ax_curve, ax_effect, ax_param):
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=7.5)
        ax.grid(axis="y", alpha=0.20)

    FIGURE_OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf", "svg"):
        kwargs = {"dpi": 400} if suffix == "png" else {}
        fig.savefig(FIGURE_OUT / f"fig_qcp_cross_quantile_recovery.{suffix}",
                    bbox_inches="tight", **kwargs)
    plt.close(fig)


def main() -> None:
    source = _source_root()
    model_cells_path = MAIN_ROOT / "analysis" / "model_cells.csv"
    with model_cells_path.open("r", encoding="utf-8", newline="") as handle:
        model_rows = list(csv.DictReader(handle))
    if len(model_rows) != 200:
        raise RuntimeError(f"expected 200 model cells, got {len(model_rows)}")

    ns = sorted({int(row["n"]) for row in model_rows})
    folds = sorted({int(row["fold"]) for row in model_rows})
    seeds = sorted({int(row["seed"]) for row in model_rows})
    indices = (
        {value: index for index, value in enumerate(ns)},
        {value: index for index, value in enumerate(folds)},
        {value: index for index, value in enumerate(seeds)},
    )
    model_mse = {
        reliability: {
            route: np.empty((len(ns), len(folds), len(seeds)), dtype=np.float64)
            for route in ROUTES
        }
        for reliability in PRIMARY_R
    }
    errors = {
        reliability: {route: [] for route in ROUTES}
        for reliability in CURVE_R
    }
    parameter_errors = {
        route: {component: [] for component in ("beta", "eta", "gamma")}
        for route in ROUTES
    }
    truth_cell_errors = {
        reliability: {route: defaultdict(list) for route in ROUTES}
        for reliability in PRIMARY_R
    }
    evidence_paths: set[Path] = set()

    for row in model_rows:
        n, fold, seed = int(row["n"]), int(row["fold"]), int(row["seed"])
        loaded = {}
        for route in ROUTES:
            path = _evidence_path(source, n, fold, seed, route)
            loaded[route] = _load(path)
            evidence_paths.add(path)
        for field in KEY_FIELDS:
            if any(not np.array_equal(loaded["P"][field], loaded[route][field])
                   for route in ("Q", "QCP")):
                raise RuntimeError(
                    f"held-out key mismatch: n={n}, fold={fold}, seed={seed}, field={field}"
                )

        beta = loaded["P"]["keys_beta"].astype(np.float64)
        eta = np.full(beta.shape, 1000.0)
        gamma_ratio = loaded["P"]["keys_gamma_over_eta"].astype(np.float64)
        gamma = 1000.0 * gamma_ratio
        idx = (indices[0][n], indices[1][fold], indices[2][seed])

        route_predictions = {}
        for route in ROUTES:
            beta_hat = loaded[route]["beta_hat"].astype(np.float64)
            eta_hat = loaded[route]["eta_hat"].astype(np.float64)
            gamma_hat = loaded[route]["gamma_hat"].astype(np.float64)
            if not (np.isfinite(beta_hat).all() and np.isfinite(eta_hat).all()
                    and np.isfinite(gamma_hat).all()):
                raise RuntimeError(f"nonfinite parameter prediction: {n=}, {fold=}, {seed=}, {route=}")
            route_predictions[route] = (beta_hat, eta_hat, gamma_hat)
            parameter_errors[route]["beta"].append((beta_hat - beta) / beta)
            parameter_errors[route]["eta"].append((eta_hat - eta) / eta)
            parameter_errors[route]["gamma"].append((gamma_hat - gamma) / eta)

        for reliability in CURVE_R:
            true = _quantile(beta, eta, gamma, float(reliability))
            for route in ROUTES:
                prediction = _quantile(*route_predictions[route], float(reliability))
                error = (prediction - true) / true
                if not np.isfinite(error).all():
                    raise RuntimeError(f"nonfinite life-point error: {reliability=}, {route=}")
                errors[reliability][route].append(error)
                if reliability in PRIMARY_R:
                    model_mse[reliability][route][idx] = float(np.mean(error ** 2))
                    for beta_value in np.unique(beta):
                        for gamma_value in np.unique(gamma_ratio):
                            mask = (beta == beta_value) & (gamma_ratio == gamma_value)
                            key = (n, float(beta_value), float(gamma_value))
                            truth_cell_errors[reliability][route][key].append(error[mask])

    curve_rows: list[dict] = []
    pooled: dict[float, dict[str, dict[str, float]]] = {}
    for reliability in CURVE_R:
        pooled[float(reliability)] = {}
        for route in ROUTES:
            values = np.concatenate(errors[reliability][route])
            if values.size != 480_000:
                raise RuntimeError("expected 480,000 predictions per route and reliability")
            metric = _metrics(values)
            pooled[float(reliability)][route] = metric
            curve_rows.append({"reliability": float(reliability), "route": route,
                               **metric})

    primary_rows: list[dict] = []
    decisions = {}
    comparisons = {}
    for offset, reliability in enumerate(PRIMARY_R):
        key = f"x_{reliability:.2f}"
        if np.isclose(reliability, 0.95):
            contrast_seeds = (2026082811, 2026082812, 2026082813)
        elif np.isclose(reliability, 0.90):
            contrast_seeds = (2026082911, 2026082912, 2026082913)
        else:
            contrast_seeds = (2026082921, 2026082922, 2026082923)
        current = {
            "Q_vs_P": _paired_contrast(
                "Q", "P", reliability, pooled, model_mse, truth_cell_errors,
                seed=contrast_seeds[0],
            ),
            "QCP_vs_Q": _paired_contrast(
                "QCP", "Q", reliability, pooled, model_mse, truth_cell_errors,
                seed=contrast_seeds[1],
            ),
            "QCP_vs_P": _paired_contrast(
                "QCP", "P", reliability, pooled, model_mse, truth_cell_errors,
                seed=contrast_seeds[2],
            ),
        }
        comparisons[key] = current
        qcp_vs_q = current["QCP_vs_Q"]
        relative = float(qcp_vs_q["relative_rmsre_improvement"])
        ci = qcp_vs_q["relative_rmsre_improvement_95ci"]
        decisions[f"x_{reliability:.2f}"] = {
            "qcp_vs_q_relative_rmsre_improvement": relative,
            "relative_rmsre_improvement_95ci": ci,
            "favorable_truth_cells": int(qcp_vs_q["favorable_truth_cells"]),
        }
        for route in ROUTES:
            row = {"reliability": reliability, "route": route,
                   **pooled[reliability][route]}
            if route == "QCP":
                row.update({
                    "qcp_vs_q_relative_rmsre_improvement": relative,
                    "qcp_vs_q_ci_low": float(ci[0]),
                    "qcp_vs_q_ci_high": float(ci[1]),
                    "favorable_truth_cells": int(qcp_vs_q["favorable_truth_cells"]),
                })
            else:
                row.update({
                    "qcp_vs_q_relative_rmsre_improvement": "",
                    "qcp_vs_q_ci_low": "", "qcp_vs_q_ci_high": "",
                    "favorable_truth_cells": "",
                })
            primary_rows.append(row)

    parameter_rmse = {
        route: {
            component: float(np.sqrt(np.mean(np.concatenate(values) ** 2)))
            for component, values in route_values.items()
        }
        for route, route_values in parameter_errors.items()
    }
    off_target_supported = all(
        decisions[f"x_{reliability:.2f}"]["qcp_vs_q_relative_rmsre_improvement"] > 0
        and decisions[f"x_{reliability:.2f}"]["relative_rmsre_improvement_95ci"][0] > 0
        for reliability in (0.90, 0.99)
    )
    if off_target_supported:
        verdict = "CROSS_QUANTILE_RECOVERY_SUPPORTED"
    else:
        count = sum(
            decisions[f"x_{reliability:.2f}"]["qcp_vs_q_relative_rmsre_improvement"] > 0
            and decisions[f"x_{reliability:.2f}"]["relative_rmsre_improvement_95ci"][0] > 0
            for reliability in (0.90, 0.99)
        )
        verdict = "PARTIAL_SUPPORT" if count == 1 else "NOT_SUPPORTED"

    summary = {
        "protocol_id": "study02-qcp-cross-quantile-recovery-v1",
        "status": "COMPLETE",
        "manuscript_admission": "ADMITTED_BY_USER_2026-08-29",
        "evidence_level": "post-test mechanism analysis of frozen predictions",
        "new_training_fits": 0,
        "model_cells_per_route": 200,
        "predictions_per_route": 480_000,
        "primary_reliability_levels": list(PRIMARY_R),
        "pooled_metrics": {f"{r:.2f}": pooled[r] for r in PRIMARY_R},
        "qcp_vs_q": decisions,
        "pairwise_comparisons": comparisons,
        "parameter_normalized_rmse": parameter_rmse,
        "verdict": verdict,
        "interpretation_boundary": (
            "Cross-quantile gains, if present, show downstream recovery at the "
            "prespecified life points; they do not establish universal full-distribution dominance."
        ),
    }

    ANALYSIS.mkdir(parents=True, exist_ok=True)
    _write_json(ANALYSIS / "summary.json", summary)
    with (ANALYSIS / "reliability_curve.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(curve_rows[0]))
        writer.writeheader()
        writer.writerows(curve_rows)
    with (ANALYSIS / "primary_life_point_metrics.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(primary_rows[0]))
        writer.writeheader()
        writer.writerows(primary_rows)
    comparison_rows = []
    for reliability in PRIMARY_R:
        key = f"x_{reliability:.2f}"
        row = {
            "reliability": reliability,
            "p_rmsre": pooled[reliability]["P"]["rmsre"],
            "q_rmsre": pooled[reliability]["Q"]["rmsre"],
            "qcp_rmsre": pooled[reliability]["QCP"]["rmsre"],
        }
        for name, contrast in comparisons[key].items():
            prefix = name.lower()
            row[f"{prefix}_relative_rmsre_improvement"] = \
                contrast["relative_rmsre_improvement"]
            row[f"{prefix}_ci_low"] = contrast["relative_rmsre_improvement_95ci"][0]
            row[f"{prefix}_ci_high"] = contrast["relative_rmsre_improvement_95ci"][1]
            row[f"{prefix}_favorable_truth_cells"] = contrast["favorable_truth_cells"]
        comparison_rows.append(row)
    with (ANALYSIS / "three_route_comparison.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison_rows[0]))
        writer.writeheader()
        writer.writerows(comparison_rows)
    cell_rows = []
    for reliability in PRIMARY_R:
        for key in sorted(truth_cell_errors[reliability]["Q"]):
            route_rmsre = {}
            for route in ROUTES:
                values = np.concatenate(truth_cell_errors[reliability][route][key])
                route_rmsre[route] = float(np.sqrt(np.mean(values ** 2)))
            cell_rows.append({
                "reliability": reliability, "n": key[0], "beta": key[1],
                "gamma_over_eta": key[2],
                "p_rmsre": route_rmsre["P"], "q_rmsre": route_rmsre["Q"],
                "qcp_rmsre": route_rmsre["QCP"],
                "qcp_vs_q_relative_rmsre_improvement":
                    (route_rmsre["Q"] - route_rmsre["QCP"]) / route_rmsre["Q"],
            })
    with (ANALYSIS / "truth_cell_effects.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cell_rows[0]))
        writer.writeheader()
        writer.writerows(cell_rows)

    _plot(summary, curve_rows, primary_rows)

    manifest = {
        "protocol_id": summary["protocol_id"],
        "status": "COMPLETE",
        "new_training_fits": 0,
        "protocol_sha256": _sha(PROTOCOL),
        "comparison_protocol_sha256": _sha(COMPARISON_PROTOCOL),
        "model_cells_sha256": _sha(model_cells_path),
        "evidence_file_count": len(evidence_paths),
        "evidence_hashes_sha256": hashlib.sha256(
            "\n".join(sorted(_sha(path) for path in evidence_paths)).encode("ascii")
        ).hexdigest(),
        "analysis_code_sha256": _sha(Path(__file__)),
    }
    _write_json(OUT / "manifest.json", manifest)
    files = sorted(path for path in OUT.rglob("*")
                   if path.is_file() and path.name != "SHA256SUMS")
    (OUT / "SHA256SUMS").write_text(
        "\n".join(f"{_sha(path)}  {path.relative_to(OUT).as_posix()}" for path in files)
        + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
