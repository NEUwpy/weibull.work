"""Platform-style MDM gradient plot with dense sampling near gamma=0."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize_scalar


WORK_DIR = Path(__file__).resolve().parent
INPUT_PATH = WORK_DIR / "step_sensitivity_samples.json"
DELIVERY_DIR = (
    Path(r"D:\weibull\docs")
    / "临时任务-W2-1000-3000-MDM偏移量估计-20260825"
    / "260826位置参数500"
)
OUTPUT_PATH = DELIVERY_DIR / "n7第4组_MDM位置参数梯度图_γ0附近加密.png"

sys.path.insert(0, str(Path(r"D:\weibull\python")))
from studies.common.runner import run_method  # noqa: E402


OFFSET = 0.10
NEAR_MAX = 20.0
NEAR_STEP = 0.1


class PlatformProfile:
    def __init__(self, sample: np.ndarray):
        self.sample = np.asarray(sample, dtype=float)
        n = len(self.sample)
        ranks = (np.arange(1, n + 1, dtype=float) - 0.3) / (n + 0.4)
        self.x = -np.log1p(-ranks)
        self.cache: dict[float, tuple[float, float]] = {}

    def evaluate(self, gamma: float) -> tuple[float, float]:
        key = float(gamma)
        if key not in self.cache:
            def objective(beta: float) -> float:
                denom = np.power(self.x, 1.0 / beta)
                eta_i = (self.sample - key) / denom
                return float(np.std(eta_i, ddof=1))

            result = minimize_scalar(
                objective,
                bounds=(0.1, 15.0),
                method="bounded",
            )
            if not result.success:
                raise RuntimeError(f"beta profiling failed at gamma={gamma}")
            self.cache[key] = (float(result.x), float(result.fun))
        return self.cache[key]

    def gradient(self, gamma: float) -> float:
        gamma = float(gamma)
        t_min = float(self.sample.min())
        scale = max(abs(t_min), 1.0)
        nominal_h = scale * 1e-5
        left_room = max(gamma, 0.0)
        right_room = max(t_min - gamma, 0.0)
        if right_room <= 0.0:
            return float("inf")
        if gamma <= 0.0 or left_room <= nominal_h:
            h = min(nominal_h, right_room * 0.25)
            h = max(h, np.finfo(float).eps * scale)
            return (self.evaluate(gamma + h)[1] - self.evaluate(gamma)[1]) / h
        if right_room <= nominal_h:
            h = min(nominal_h, left_room * 0.25, right_room * 0.5)
            h = max(h, np.finfo(float).eps * scale)
            return (self.evaluate(gamma)[1] - self.evaluate(gamma - h)[1]) / h
        h = min(nominal_h, left_room * 0.25, right_room * 0.25)
        h = max(h, np.finfo(float).eps * scale)
        return (self.evaluate(gamma + h)[1] - self.evaluate(gamma - h)[1]) / (2.0 * h)


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
        }
    )


def load_sample() -> np.ndarray:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    case = next(item for item in payload["cases"] if int(item["sample_id"]) == 4)
    return np.asarray(case["values"], dtype=float)


def dense_gamma_grid(t_min: float) -> np.ndarray:
    near = np.arange(0.0, NEAR_MAX + NEAR_STEP / 2.0, NEAR_STEP)
    middle = np.arange(22.0, 100.0 + 1e-12, 2.0)
    far = np.linspace(105.0, 0.90 * t_min, 46)
    right = t_min - np.geomspace(t_min * 1e-3, t_min * 0.10, 64)
    grid = np.unique(np.concatenate([near, middle, far, right]))
    return grid[(grid >= 0.0) & (grid < t_min)]


def main() -> None:
    configure_style()
    sample = load_sample()
    t_min = float(sample.min())
    profile = PlatformProfile(sample)
    gammas = dense_gamma_grid(t_min)
    gradients = np.array([profile.gradient(float(g)) for g in gammas])

    official = run_method(
        "mdm",
        sample,
        variant="mdm-delta-0.10",
        offset=OFFSET,
        gamma_steps=240,
        trace=True,
    )
    g0_official = float((official.get("extra") or {}).get("solution_info", {}).get("probe_gradient_at_zero"))
    g0_dense = float(gradients[np.argmin(np.abs(gammas))])
    if abs(g0_dense - g0_official) > 1e-8:
        raise RuntimeError(f"g(0) mismatch: dense={g0_dense}, platform={g0_official}")

    near_mask = gammas <= NEAR_MAX
    near_min_idx = np.flatnonzero(near_mask)[np.argmin(gradients[near_mask])]
    near_min_gamma = float(gammas[near_min_idx])
    near_min_gradient = float(gradients[near_min_idx])
    if near_min_gradient <= OFFSET:
        raise RuntimeError("Dense near-zero grid found a point at or below delta=0.1")

    fig, ax = plt.subplots(figsize=(165 / 25.4, 96 / 25.4))
    red = "#ef4444"
    green = "#10b981"
    orange = "#f59e0b"
    slate = "#64748b"
    grid_color = "#f1f5f9"

    ax.plot(gammas, gradients, color=red, linewidth=1.6, zorder=2)
    ax.scatter(
        gammas,
        gradients,
        s=10,
        facecolors="white",
        edgecolors=red,
        linewidths=0.8,
        zorder=3,
    )
    ax.axhline(OFFSET, color=green, linestyle=(0, (3, 3)), linewidth=1.2, zorder=1)
    ax.axvline(0.0, color=orange, linestyle=(0, (3, 3)), linewidth=1.3, zorder=1)
    ax.set_xlim(-5.0, t_min + 5.0)
    ax.set_ylim(0.0, 0.95)
    ax.set_xticks([0, 150, 300, 450, round(t_min)])
    ax.set_yticks([0.0, 0.25, 0.50, 0.75, 0.95])
    ax.grid(axis="y", color=grid_color, linewidth=0.8, linestyle=(0, (3, 3)))
    ax.set_xlabel("位置参数 γ", color=slate, labelpad=7)
    ax.set_ylabel("梯度 " + r"$\nabla(\gamma)$", color=slate, labelpad=7)
    ax.tick_params(labelsize=7)
    ax.text(t_min + 2.0, OFFSET, "δ=0.100", color=green, fontsize=7, ha="right", va="bottom")
    ax.text(3.0, 0.012, "最优γ=0", color=orange, fontsize=7, ha="left", va="bottom")

    ax.set_title("位置参数梯度判据", loc="left", fontsize=11, fontweight="bold", pad=24)
    ax.text(
        0.0,
        1.035,
        "n=7，第4组；红色空心点为真实计算点，γ=0附近已加密",
        transform=ax.transAxes,
        color=slate,
        fontsize=7.5,
        ha="left",
        va="bottom",
    )
    ax.text(
        1.0,
        1.035,
        f"估计 β={official['beta_hat']:.4f}   η={official['eta_hat']:.2f}   γ={official['gamma_hat']:.2f}   R²={official['r_squared']:.4f}",
        transform=ax.transAxes,
        color="#0f172a",
        fontsize=7.5,
        ha="right",
        va="bottom",
    )

    inset = ax.inset_axes([0.08, 0.49, 0.43, 0.39])
    inset.plot(gammas[near_mask], gradients[near_mask], color=red, linewidth=1.4)
    inset.scatter(
        gammas[near_mask],
        gradients[near_mask],
        s=9,
        facecolors="white",
        edgecolors=red,
        linewidths=0.7,
        zorder=3,
    )
    inset.axhline(OFFSET, color=green, linestyle=(0, (3, 3)), linewidth=1.0)
    inset.axvline(0.0, color=orange, linestyle=(0, (3, 3)), linewidth=1.0)
    inset.set_xlim(-0.5, NEAR_MAX)
    inset.set_ylim(0.099, max(0.112, float(gradients[near_mask].max()) + 0.0008))
    inset.set_xticks([0, 5, 10, 15, 20])
    inset.set_yticks([0.100, 0.104, 0.108, 0.112])
    inset.grid(axis="y", color=grid_color, linewidth=0.7, linestyle=(0, (3, 3)))
    inset.tick_params(labelsize=6, pad=1.5)
    inset.set_title("γ=0附近加密：0–20，间隔0.1", fontsize=7.2, loc="left", pad=3)
    inset.annotate(
        f"最低点 g({near_min_gamma:.1f})={near_min_gradient:.6f}\n仍高于0.1",
        xy=(near_min_gamma, near_min_gradient),
        xytext=(4.2, 0.1052),
        fontsize=6.5,
        color="#0f172a",
        arrowprops={"arrowstyle": "->", "color": slate, "linewidth": 0.7},
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "#cbd5e1", "linewidth": 0.7},
    )
    ax.indicate_inset_zoom(inset, edgecolor="#94a3b8", linewidth=0.8)

    fig.subplots_adjust(left=0.105, right=0.97, bottom=0.15, top=0.82)
    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=600, facecolor="white")
    plt.close(fig)

    print(
        json.dumps(
            {
                "figure": str(OUTPUT_PATH),
                "sample_id": 4,
                "sample_min": t_min,
                "dense_points_total": int(len(gammas)),
                "dense_points_near_zero": int(near_mask.sum()),
                "near_zero_range": [0.0, NEAR_MAX],
                "near_zero_step": NEAR_STEP,
                "g0": g0_dense,
                "near_zero_min_gamma": near_min_gamma,
                "near_zero_min_gradient": near_min_gradient,
                "all_near_zero_above_offset": bool(np.all(gradients[near_mask] > OFFSET)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
