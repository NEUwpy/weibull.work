"""MDM gamma=0 derivative step-size sensitivity using workbook samples."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize_scalar


WORK_DIR = Path(__file__).resolve().parent
INPUT_PATH = WORK_DIR / "step_sensitivity_samples.json"
SOURCE_DATA_PATH = WORK_DIR / "mdm_gamma0_step_sensitivity.csv"
DELIVERY_DIR = (
    Path(r"D:\weibull\docs")
    / "临时任务-W2-1000-3000-MDM偏移量估计-20260825"
    / "260826位置参数500"
)
OUTPUT_PATH = DELIVERY_DIR / "MDM位置参数零边界_梯度步长敏感性检验.png"

OFFSET = 0.1
ORIGINAL_RELATIVE_STEP = 1e-5
RELATIVE_STEPS = np.logspace(-2, -8, 25)
POLY_WINDOWS = np.array([1e-2, 3e-3, 1e-3, 3e-4, 1e-4, 3e-5, 1e-5])


def bernard_ranks(n: int) -> np.ndarray:
    i = np.arange(1, n + 1, dtype=float)
    return (i - 0.3) / (n + 0.4)


class ProfileSigma:
    def __init__(self, sample: np.ndarray):
        self.sample = np.asarray(sample, dtype=float)
        ranks = bernard_ranks(len(self.sample))
        self.x = -np.log1p(-ranks)
        self.cache: dict[float, tuple[float, float]] = {}

    def eta_std(self, beta: float, gamma: float) -> float:
        denom = np.power(self.x, 1.0 / beta)
        eta_i = (self.sample - gamma) / denom
        return float(np.std(eta_i, ddof=1))

    def evaluate(self, gamma: float) -> tuple[float, float]:
        key = float(gamma)
        if key not in self.cache:
            result = minimize_scalar(
                lambda beta: self.eta_std(beta, key),
                bounds=(0.1, 15.0),
                method="bounded",
                options={"xatol": 1e-12, "maxiter": 1000},
            )
            if not result.success:
                raise RuntimeError(f"beta profiling failed at gamma={gamma}")
            self.cache[key] = (float(result.x), float(result.fun))
        return self.cache[key]

    def analytic_envelope_gradient_at_zero(self) -> tuple[float, float, float]:
        beta0, sigma0 = self.evaluate(0.0)
        q = np.power(self.x, -1.0 / beta0)
        eta_i = self.sample * q
        centered = eta_i - eta_i.mean()
        gradient = float(
            np.sum(centered * (-q)) / ((len(self.sample) - 1) * sigma0)
        )
        return beta0, sigma0, gradient


def local_quadratic_slope(profile: ProfileSigma, window: float) -> float:
    gamma = np.linspace(0.0, window, 11)
    sigma = np.array([profile.evaluate(float(g))[1] for g in gamma])
    scaled = gamma / window
    coefficients = np.polyfit(scaled, sigma, deg=2)
    return float(coefficients[-2] / window)


def analyze_case(sample_id: int, sample: np.ndarray) -> tuple[dict, list[dict]]:
    profile = ProfileSigma(sample)
    t_min = float(sample.min())
    beta0, sigma0, analytic = profile.analytic_envelope_gradient_at_zero()
    rows: list[dict] = []

    forward = []
    richardson = []
    for relative_h in RELATIVE_STEPS:
        h = t_min * relative_h
        f_h = profile.evaluate(h)[1]
        f_half = profile.evaluate(h / 2.0)[1]
        d_h = (f_h - sigma0) / h
        d_half = (f_half - sigma0) / (h / 2.0)
        d_rich = 2.0 * d_half - d_h
        forward.append(d_h)
        richardson.append(d_rich)
        rows.append(
            {
                "sample_id": sample_id,
                "estimator": "forward_difference",
                "relative_step_or_window": relative_h,
                "gradient": d_h,
            }
        )
        rows.append(
            {
                "sample_id": sample_id,
                "estimator": "richardson",
                "relative_step_or_window": relative_h,
                "gradient": d_rich,
            }
        )

    poly = []
    for relative_window in POLY_WINDOWS:
        slope = local_quadratic_slope(profile, t_min * relative_window)
        poly.append(slope)
        rows.append(
            {
                "sample_id": sample_id,
                "estimator": "local_quadratic",
                "relative_step_or_window": relative_window,
                "gradient": slope,
            }
        )

    rows.append(
        {
            "sample_id": sample_id,
            "estimator": "analytic_envelope",
            "relative_step_or_window": math.nan,
            "gradient": analytic,
        }
    )
    idx_original = int(np.argmin(np.abs(np.log10(RELATIVE_STEPS) + 5.0)))
    summary = {
        "sample_id": sample_id,
        "t_min": t_min,
        "beta_at_zero": beta0,
        "sigma_at_zero": sigma0,
        "analytic_gradient": analytic,
        "original_step_gradient": float(forward[idx_original]),
        "original_relative_step": float(RELATIVE_STEPS[idx_original]),
        "forward": np.asarray(forward),
        "richardson": np.asarray(richardson),
        "poly": np.asarray(poly),
    }
    return summary, rows


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 8,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "legend.frameon": False,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def draw(summaries: list[dict]) -> None:
    configure_style()
    fig, axes = plt.subplots(1, 2, figsize=(180 / 25.4, 92 / 25.4), sharey=True)
    colors = {"forward": "#4C78A8", "richardson": "#F28E2B", "poly": "#59A14F"}

    for ax, summary, panel in zip(axes, summaries, ["a", "b"]):
        ax.plot(
            RELATIVE_STEPS,
            summary["forward"],
            color=colors["forward"],
            marker="o",
            markersize=2.6,
            linewidth=1.1,
            label="单侧有限差分",
        )
        ax.plot(
            RELATIVE_STEPS,
            summary["richardson"],
            color=colors["richardson"],
            marker="s",
            markersize=2.4,
            linewidth=1.0,
            label="Richardson 外推",
        )
        ax.scatter(
            POLY_WINDOWS,
            summary["poly"],
            color=colors["poly"],
            marker="^",
            s=16,
            zorder=4,
            label="局部二次拟合",
        )
        ax.axhline(OFFSET, color="#B2182B", linestyle="-.", linewidth=1.0, label="判据 δ=0.1")
        ax.axhline(
            summary["analytic_gradient"],
            color="#222222",
            linestyle="--",
            linewidth=1.0,
            label="解析包络导数",
        )
        ax.axvline(
            ORIGINAL_RELATIVE_STEP,
            color="#777777",
            linestyle=":",
            linewidth=0.9,
            label=r"程序步长 $10^{-5}$",
        )
        ax.set_xscale("log")
        ax.invert_xaxis()
        ax.set_xlim(2e-2, 5e-9)
        ax.set_ylim(0.094, 0.116)
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.7)
        ax.set_xlabel(r"相对步长或拟合窗口 $h/t_{(1)}$")
        ax.set_title(f"{panel}  n=7，第{summary['sample_id']}组", loc="left", fontweight="bold", fontsize=9)
        ax.text(
            0.03,
            0.96,
            "解析导数 = " + f"{summary['analytic_gradient']:.6f}\n"
            + "程序步长结果 = " + f"{summary['original_step_gradient']:.6f}",
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=7.2,
        )

    axes[0].set_ylabel("γ=0 处的廓线梯度 g(0)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.015), fontsize=7)
    fig.suptitle("MDM 位置参数零边界的梯度步长敏感性检验", y=0.995, fontsize=10, fontweight="bold")
    fig.subplots_adjust(left=0.115, right=0.985, top=0.88, bottom=0.28, wspace=0.15)
    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=600, facecolor="white")
    plt.close(fig)


def main() -> None:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    summaries = []
    source_rows = []
    for case in payload["cases"]:
        summary, rows = analyze_case(
            int(case["sample_id"]), np.asarray(case["values"], dtype=float)
        )
        summaries.append(summary)
        source_rows.extend(rows)

    with SOURCE_DATA_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(source_rows[0]))
        writer.writeheader()
        writer.writerows(source_rows)

    draw(summaries)
    qa = []
    for s in summaries:
        stable_mask = (RELATIVE_STEPS <= 1e-4) & (RELATIVE_STEPS >= 1e-6)
        stable_values = s["forward"][stable_mask]
        qa.append(
            {
                "sample_id": s["sample_id"],
                "analytic_gradient": s["analytic_gradient"],
                "original_step_gradient": s["original_step_gradient"],
                "stable_forward_min": float(stable_values.min()),
                "stable_forward_max": float(stable_values.max()),
                "original_minus_analytic": float(
                    s["original_step_gradient"] - s["analytic_gradient"]
                ),
                "all_checks_above_offset": bool(
                    min(
                        s["analytic_gradient"],
                        float(stable_values.min()),
                        float(s["poly"].min()),
                    )
                    > OFFSET
                ),
            }
        )
    print(json.dumps({"figure": str(OUTPUT_PATH), "qa": qa}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
