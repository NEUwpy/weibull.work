"""Describe how much QCP resolves Q's target and parameter-compensation issues.

This module performs no training. It consumes the frozen common-budget P/Q
evidence and the frozen QCP confirmation evidence under protocol 22.
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


ROOT = Path(CFG.STUDY02_ROOT)
OUT = ROOT / "artifacts" / "qcp_resolution_distribution"
ANALYSIS = OUT / "analysis"
FIGURE_OUT = ROOT / "figures" / "qcp-main"
QCP_ROOT = ROOT / "artifacts" / "qcp_constrained_confirm"
MAIN_ROOT = ROOT / "artifacts" / "qcp_main_analysis"
BIAS_ROOT = ROOT / "artifacts" / "qcp_bias_variance"
PROTOCOL = ROOT / "protocols" / "22-QCP问题解决程度与估计分布展示合同.md"
SOURCE_CANDIDATES = (
    ROOT / "artifacts" / "equal_budget_sensitivity",
    ROOT / "历史实验" / "四路线同预算敏感性" / "artifacts" /
    "equal_budget_sensitivity",
)
ROUTES = ("P", "Q", "QCP")
COLORS = {"P": "#8C8C8C", "Q": "#56B4E9", "QCP": "#009E73"}
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


def _metrics(values: np.ndarray) -> dict[str, float]:
    absolute = np.abs(values)
    return {
        "rmsre": float(np.sqrt(np.mean(values ** 2))),
        "signed_relative_bias": float(np.mean(values)),
        "relative_error_sd": float(np.std(values)),
        "mae": float(np.mean(absolute)),
        "mdape": float(np.median(absolute)),
        "p95_absolute_error": float(np.quantile(absolute, 0.95)),
        "within_10pct": float(np.mean(absolute <= 0.10)),
        "within_20pct": float(np.mean(absolute <= 0.20)),
        "q025_signed_error": float(np.quantile(values, 0.025)),
        "q975_signed_error": float(np.quantile(values, 0.975)),
    }


def _relative_reduction(q: float, qcp: float) -> float:
    return float((q - qcp) / q)


def _plot(summary: dict, cell_rows: list[dict], representative: dict,
          representative_values: dict[str, np.ndarray]) -> None:
    fig = plt.figure(figsize=(7.2, 6.0), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, height_ratios=(1.0, 1.15))
    ax_effect = fig.add_subplot(grid[0, 0])
    ax_distribution = fig.add_subplot(grid[0, 1])
    ax_table = fig.add_subplot(grid[1, :])

    effects = np.asarray([
        100.0 * float(row["qcp_vs_q_relative_rmsre_improvement"])
        for row in cell_rows
    ])
    rng = np.random.default_rng(20260829)
    jitter = rng.uniform(-0.12, 0.12, size=effects.size)
    ax_effect.scatter(
        effects, jitter, s=16, alpha=0.55, color=COLORS["QCP"],
        edgecolors="none",
    )
    ax_effect.axvline(0.0, color="#555555", linewidth=1.0, linestyle="--")
    ax_effect.axvline(
        100.0 * summary["pooled_qcp_vs_q_relative_rmsre_improvement"],
        color="#222222", linewidth=1.0, linestyle=":",
        label="Pooled effect",
    )
    rep_effect = 100.0 * representative["qcp_vs_q_relative_rmsre_improvement"]
    ax_effect.scatter(
        [rep_effect], [0.0], marker="D", s=62, color="#E69F00",
        edgecolor="black", linewidth=0.7, zorder=4, label="Representative cell",
    )
    ax_effect.set_yticks([])
    ax_effect.set_ylim(-0.18, 0.18)
    ax_effect.set_xlabel("QCP vs Q relative RMSRE improvement (%)")
    ax_effect.set_title("A  Heterogeneity across 160 truth cells", loc="left",
                        fontweight="bold", fontsize=10)
    ax_effect.text(
        0.02, 0.95,
        f"{summary['favorable_truth_cells']}/160 cells favor QCP\n"
        f"median = {100.0 * summary['truth_cell_effect_quantiles']['q50']:.2f}%",
        transform=ax_effect.transAxes, va="top", fontsize=7.5,
    )
    ax_effect.legend(frameon=False, fontsize=6.8, loc="lower right")

    positions = np.arange(1, 4)
    values_percent = [100.0 * representative_values[route] for route in ROUTES]
    violin = ax_distribution.violinplot(
        values_percent, positions=positions, widths=0.74,
        showmeans=False, showmedians=False, showextrema=False,
        quantiles=[[0.025, 0.975]] * 3,
    )
    for body, route in zip(violin["bodies"], ROUTES):
        body.set_facecolor(COLORS[route])
        body.set_edgecolor("black")
        body.set_alpha(0.38)
        body.set_linewidth(0.6)
    if "cquantiles" in violin:
        violin["cquantiles"].set_color("#333333")
        violin["cquantiles"].set_linewidth(0.8)
    box = ax_distribution.boxplot(
        values_percent, positions=positions, widths=0.20, patch_artist=True,
        showfliers=False, medianprops={"color": "black", "linewidth": 1.1},
        whiskerprops={"linewidth": 0.7}, capprops={"linewidth": 0.7},
        boxprops={"linewidth": 0.7},
    )
    for patch, route in zip(box["boxes"], ROUTES):
        patch.set_facecolor(COLORS[route])
        patch.set_alpha(0.75)
    for idx, (route, values) in enumerate(zip(ROUTES, values_percent), start=1):
        chosen = rng.choice(values.size, size=min(240, values.size), replace=False)
        x = idx + rng.uniform(-0.22, 0.22, size=chosen.size)
        ax_distribution.scatter(
            x, values[chosen], s=4, alpha=0.12, color=COLORS[route],
            edgecolors="none",
        )
    ax_distribution.axhline(0.0, color="#555555", linewidth=1.0, linestyle="--")
    ax_distribution.set_xticks(positions, ROUTES)
    ax_distribution.set_ylabel("Signed relative error of $x_{0.95}$ (%)")
    ax_distribution.set_title(
        "B  Representative fixed-truth cell", loc="left",
        fontweight="bold", fontsize=10,
    )
    cell = summary["representative_truth_cell"]
    ax_distribution.text(
        0.02, 0.96,
        rf"$n={cell['n']}$, $\beta={cell['beta']:.1f}$, "
        rf"$\gamma/\eta={cell['gamma_over_eta']:.2f}$; 3,000 predictions/route",
        transform=ax_distribution.transAxes, va="top", fontsize=7.2,
    )
    y_min = min(float(np.quantile(values, 0.002)) for values in values_percent)
    y_max = max(float(np.quantile(values, 0.998)) for values in values_percent)
    ax_distribution.set_ylim(y_min, y_max)

    ax_table.axis("off")
    rows = summary["q_to_qcp_changes"]
    table_data = [
        ["RMSRE (%)", f"{100*rows['rmsre']['q']:.2f}",
         f"{100*rows['rmsre']['qcp']:.2f}", rows["rmsre"]["display_change"]],
        ["MAE (%)", f"{100*rows['mae']['q']:.2f}",
         f"{100*rows['mae']['qcp']:.2f}", rows["mae"]["display_change"]],
        ["MdAPE (%)", f"{100*rows['mdape']['q']:.2f}",
         f"{100*rows['mdape']['qcp']:.2f}", rows["mdape"]["display_change"]],
        [r"$P_{95}(|e|)$ (%)", f"{100*rows['p95_absolute_error']['q']:.2f}",
         f"{100*rows['p95_absolute_error']['qcp']:.2f}",
         rows["p95_absolute_error"]["display_change"]],
        [r"$\Pr(|e|\leq10\%)$ (%)", f"{100*rows['within_10pct']['q']:.2f}",
         f"{100*rows['within_10pct']['qcp']:.2f}",
         rows["within_10pct"]["display_change"]],
        ["Signed bias (%)", f"{100*rows['signed_relative_bias']['q']:.2f}",
         f"{100*rows['signed_relative_bias']['qcp']:.2f}",
         rows["signed_relative_bias"]["display_change"]],
        ["Within-cell SD (%)", f"{100*rows['within_cell_sd']['q']:.2f}",
         f"{100*rows['within_cell_sd']['qcp']:.2f}",
         rows["within_cell_sd"]["display_change"]],
        ["Parameter compensation index", f"{rows['compensation_index']['q']:.3f}",
         f"{rows['compensation_index']['qcp']:.3f}",
         rows["compensation_index"]["display_change"]],
    ]
    table = ax_table.table(
        cellText=table_data,
        colLabels=["Measure", "Q", "QCP", "QCP - Q"],
        cellLoc="center", colLoc="center", loc="center",
        colWidths=[0.34, 0.14, 0.14, 0.31],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.4)
    table.scale(1.0, 1.25)
    for (row, col), cell_obj in table.get_celld().items():
        cell_obj.set_edgecolor("#B0B0B0")
        cell_obj.set_linewidth(0.5)
        if row == 0:
            cell_obj.set_facecolor("#EAEAEA")
            cell_obj.set_text_props(fontweight="bold")
        elif col == 0:
            cell_obj.set_text_props(ha="left")
    ax_table.set_title(
        "C  What QCP changes relative to Q", loc="left",
        fontweight="bold", fontsize=10, pad=5,
    )

    for ax in (ax_effect, ax_distribution):
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=7.5)
        ax.grid(axis="x" if ax is ax_effect else "y", alpha=0.22)

    FIGURE_OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf", "svg"):
        path = FIGURE_OUT / f"fig_qcp_resolution_distribution.{suffix}"
        kwargs = {"dpi": 400} if suffix == "png" else {}
        fig.savefig(path, bbox_inches="tight", **kwargs)
    plt.close(fig)


def main() -> None:
    source = _source_root()
    main_summary_path = MAIN_ROOT / "analysis" / "summary.json"
    bias_summary_path = BIAS_ROOT / "analysis" / "summary.json"
    model_cells_path = MAIN_ROOT / "analysis" / "model_cells.csv"
    main_summary = json.loads(main_summary_path.read_text(encoding="utf-8"))
    bias_summary = json.loads(bias_summary_path.read_text(encoding="utf-8"))
    with model_cells_path.open("r", encoding="utf-8", newline="") as handle:
        model_rows = list(csv.DictReader(handle))
    if len(model_rows) != 200:
        raise RuntimeError(f"expected 200 model cells, got {len(model_rows)}")

    chunks: dict[str, dict[tuple[int, float, float], list[np.ndarray]]] = {
        route: defaultdict(list) for route in ROUTES
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
            if any(
                not np.array_equal(loaded["P"][field], loaded[route][field])
                for route in ("Q", "QCP")
            ):
                raise RuntimeError(
                    f"held-out key mismatch: n={n}, fold={fold}, seed={seed}, field={field}"
                )
        beta = loaded["P"]["keys_beta"].astype(np.float64)
        gamma = loaded["P"]["keys_gamma_over_eta"].astype(np.float64)
        for beta_value in np.unique(beta):
            for gamma_value in np.unique(gamma):
                mask = (beta == beta_value) & (gamma == gamma_value)
                key = (n, float(beta_value), float(gamma_value))
                for route in ROUTES:
                    values = loaded[route]["rel_err"].astype(np.float64)[mask]
                    if not np.isfinite(values).all():
                        raise RuntimeError(f"nonfinite relative error: route={route}, key={key}")
                    chunks[route][key].append(values)

    pooled_values = {
        route: np.concatenate([
            np.concatenate(chunks[route][key]) for key in sorted(chunks[route])
        ])
        for route in ROUTES
    }
    if any(values.size != 480_000 for values in pooled_values.values()):
        raise RuntimeError("expected 480,000 predictions per route")
    pooled_metrics = {route: _metrics(values) for route, values in pooled_values.items()}
    for route in ROUTES:
        expected = float(main_summary["pooled_rrmse"][route])
        if not np.isclose(pooled_metrics[route]["rmsre"], expected, atol=1e-12):
            raise RuntimeError(f"RMSRE mismatch for {route}")

    cell_rows: list[dict] = []
    representative_values_by_key: dict[tuple[int, float, float], dict[str, np.ndarray]] = {}
    for key in sorted(chunks["P"]):
        values = {route: np.concatenate(chunks[route][key]) for route in ROUTES}
        if any(route_values.size != 3_000 for route_values in values.values()):
            raise RuntimeError(f"expected 3,000 predictions per route for truth cell {key}")
        metrics = {route: _metrics(route_values) for route, route_values in values.items()}
        effect = _relative_reduction(metrics["Q"]["rmsre"], metrics["QCP"]["rmsre"])
        row = {
            "n": key[0],
            "beta": key[1],
            "gamma_over_eta": key[2],
            "qcp_vs_q_relative_rmsre_improvement": effect,
        }
        for route in ROUTES:
            for name, value in metrics[route].items():
                row[f"{route.lower()}_{name}"] = value
        cell_rows.append(row)
        representative_values_by_key[key] = values
    if len(cell_rows) != 160:
        raise RuntimeError(f"expected 160 truth cells, got {len(cell_rows)}")

    pooled_effect = float(
        main_summary["contrasts"]["QCP_minus_Q"]["relative_rrmse_improvement"]
    )
    representative = min(
        cell_rows,
        key=lambda row: (
            abs(row["qcp_vs_q_relative_rmsre_improvement"] - pooled_effect),
            row["n"], row["beta"], row["gamma_over_eta"],
        ),
    )
    representative_key = (
        int(representative["n"]), float(representative["beta"]),
        float(representative["gamma_over_eta"]),
    )
    effects = np.asarray([
        row["qcp_vs_q_relative_rmsre_improvement"] for row in cell_rows
    ])

    diagnostics = main_summary["diagnostics"]
    bias_routes = bias_summary["routes"]
    compensation_resolution = (
        diagnostics["Q"]["mean_exact_cancellation_index"]
        - diagnostics["QCP"]["mean_exact_cancellation_index"]
    ) / (
        diagnostics["Q"]["mean_exact_cancellation_index"]
        - diagnostics["P"]["mean_exact_cancellation_index"]
    )
    changes = {
        "rmsre": {
            "q": pooled_metrics["Q"]["rmsre"],
            "qcp": pooled_metrics["QCP"]["rmsre"],
            "relative_change": _relative_reduction(
                pooled_metrics["Q"]["rmsre"], pooled_metrics["QCP"]["rmsre"]
            ),
            "display_change": "-0.252 pp (-1.56%)",
        },
        "mae": {
            "q": pooled_metrics["Q"]["mae"],
            "qcp": pooled_metrics["QCP"]["mae"],
            "relative_change": _relative_reduction(
                pooled_metrics["Q"]["mae"], pooled_metrics["QCP"]["mae"]
            ),
            "display_change": "-0.247 pp (-2.21%)",
        },
        "mdape": {
            "q": pooled_metrics["Q"]["mdape"],
            "qcp": pooled_metrics["QCP"]["mdape"],
            "relative_change": _relative_reduction(
                pooled_metrics["Q"]["mdape"], pooled_metrics["QCP"]["mdape"]
            ),
            "display_change": "-0.278 pp (-3.41%)",
        },
        "p95_absolute_error": {
            "q": pooled_metrics["Q"]["p95_absolute_error"],
            "qcp": pooled_metrics["QCP"]["p95_absolute_error"],
            "relative_change": _relative_reduction(
                pooled_metrics["Q"]["p95_absolute_error"],
                pooled_metrics["QCP"]["p95_absolute_error"],
            ),
            "display_change": "-0.489 pp (-1.59%)",
        },
        "within_10pct": {
            "q": pooled_metrics["Q"]["within_10pct"],
            "qcp": pooled_metrics["QCP"]["within_10pct"],
            "absolute_change": (
                pooled_metrics["QCP"]["within_10pct"]
                - pooled_metrics["Q"]["within_10pct"]
            ),
            "display_change": "+1.30 pp",
        },
        "signed_relative_bias": {
            "q": pooled_metrics["Q"]["signed_relative_bias"],
            "qcp": pooled_metrics["QCP"]["signed_relative_bias"],
            "absolute_bias_reduction": 1.0 - abs(
                pooled_metrics["QCP"]["signed_relative_bias"]
            ) / abs(pooled_metrics["Q"]["signed_relative_bias"]),
            "display_change": "|bias| -8.50%",
        },
        "within_cell_sd": {
            "q": float(bias_routes["Q"]["within_truth_cell_sd_component"]),
            "qcp": float(bias_routes["QCP"]["within_truth_cell_sd_component"]),
            "relative_change": _relative_reduction(
                float(bias_routes["Q"]["within_truth_cell_sd_component"]),
                float(bias_routes["QCP"]["within_truth_cell_sd_component"]),
            ),
            "display_change": "-0.283 pp (-1.95%)",
        },
        "compensation_index": {
            "p": float(diagnostics["P"]["mean_exact_cancellation_index"]),
            "q": float(diagnostics["Q"]["mean_exact_cancellation_index"]),
            "qcp": float(diagnostics["QCP"]["mean_exact_cancellation_index"]),
            "excess_over_p_removed": float(compensation_resolution),
            "display_change": f"{100.0 * compensation_resolution:.1f}% excess removed",
        },
    }

    quantiles = np.quantile(effects, [0.0, 0.10, 0.25, 0.50, 0.75, 0.90, 1.0])
    summary = {
        "protocol_id": "study02-qcp-resolution-distribution-v1",
        "status": "COMPLETE",
        "evidence_level": "post-test descriptive analysis of frozen evidence",
        "predictions_per_route": 480_000,
        "truth_cells": 160,
        "predictions_per_truth_cell_per_route": 3_000,
        "pooled_metrics": pooled_metrics,
        "pooled_qcp_vs_q_relative_rmsre_improvement": pooled_effect,
        "favorable_truth_cells": int(np.sum(effects > 0.0)),
        "truth_cell_effect_quantiles": {
            name: float(value) for name, value in zip(
                ("min", "q10", "q25", "q50", "q75", "q90", "max"), quantiles
            )
        },
        "representative_selection_rule": (
            "truth cell whose QCP-vs-Q relative RMSRE improvement is closest "
            "to the pooled QCP-vs-Q effect; lexicographic tie-break"
        ),
        "representative_truth_cell": {
            "n": representative_key[0],
            "beta": representative_key[1],
            "gamma_over_eta": representative_key[2],
            "qcp_vs_q_relative_rmsre_improvement": float(
                representative["qcp_vs_q_relative_rmsre_improvement"]
            ),
            "metrics": {
                route: {
                    name: float(representative[f"{route.lower()}_{name}"])
                    for name in pooled_metrics[route]
                }
                for route in ROUTES
            },
        },
        "q_to_qcp_changes": changes,
        "interpretation": {
            "primary": (
                "QCP nearly removes Q's excess parameter compensation relative to P, "
                "while its additional target-error gain is modest."
            ),
            "boundary": (
                "The constraint solves parameter plausibility more completely than it "
                "solves target error; QCP does not dominate Q in every truth cell."
            ),
        },
    }

    ANALYSIS.mkdir(parents=True, exist_ok=True)
    _write_json(ANALYSIS / "summary.json", summary)
    with (ANALYSIS / "truth_cell_metrics.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cell_rows[0]))
        writer.writeheader()
        writer.writerows(cell_rows)
    representative_values = representative_values_by_key[representative_key]
    with (ANALYSIS / "representative_predictions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["route", "relative_error"])
        writer.writeheader()
        for route in ROUTES:
            writer.writerows(
                {"route": route, "relative_error": float(value)}
                for value in representative_values[route]
            )

    _plot(summary, cell_rows, representative, representative_values)

    manifest = {
        "protocol_id": summary["protocol_id"],
        "status": "COMPLETE",
        "new_training_fits": 0,
        "protocol_sha256": _sha(PROTOCOL),
        "main_summary_sha256": _sha(main_summary_path),
        "bias_summary_sha256": _sha(bias_summary_path),
        "model_cells_sha256": _sha(model_cells_path),
        "evidence_file_count": len(evidence_paths),
        "evidence_hashes_sha256": hashlib.sha256(
            "\n".join(sorted(_sha(path) for path in evidence_paths)).encode("ascii")
        ).hexdigest(),
        "analysis_code_sha256": _sha(Path(__file__)),
    }
    _write_json(OUT / "manifest.json", manifest)
    files = sorted(
        path for path in OUT.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (OUT / "SHA256SUMS").write_text(
        "\n".join(f"{_sha(path)}  {path.relative_to(OUT).as_posix()}" for path in files)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
