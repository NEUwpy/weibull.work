"""Plot one-factor comparisons from the completed opportunity statistics."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

STUDY = Path(__file__).resolve().parents[1]
OUT = STUDY / "results/j3_scan_v1"


def main():
    d = pd.read_csv(OUT / "policy_by_cell.csv")
    d = d[d.cohort.eq("controlled_20260922")]
    specs = [
        ("beta", d.eta.eq(1000) & d.gamma.eq(1000)),
        ("eta", d.beta.eq(2) & d.gamma.eq(1000)),
        ("gamma", d.beta.eq(2) & d.eta.eq(1000)),
    ]
    policies = [
        ("original", "Original", "#0072B2", "-"),
        ("fixed_global", "Global fixed (same data)", "#D55E00", "--"),
        ("fixed_cell", "True-cell fixed (oracle)", "#CC79A7", ":"),
        ("oracle", "Sample oracle", "#009E73", "-"),
    ]
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(3, 3, figsize=(11, 9), sharey=True)
    for col, (axis, mask) in enumerate(specs):
        part = d[mask]
        for row, n in enumerate([7, 15, 30]):
            ax = axes[row, col]
            for policy, label, color, ls in policies:
                points = part[part.sample_size.eq(n) & part.policy.eq(policy)].sort_values(axis)
                ax.plot(points[axis], points.bad_rate, marker="o", markersize=4,
                        color=color, linestyle=ls, label=label)
            ax.set(title=f"n={n}: vary {axis}", xlabel=axis, ylim=(0, 1),
                   xticks=sorted(part[axis].unique()))
            ax.grid(alpha=.18)
            if col == 0:
                ax.set_ylabel("Failure or E >= 0.5 / all draws")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=4, loc="lower center", frameon=False, fontsize=9)
    fig.suptitle("J3 opportunity: change one true parameter at a time", fontsize=13)
    fig.tight_layout(rect=(0, .055, 1, .97))
    for ext in ["png", "pdf"]:
        fig.savefig(OUT / f"controlled_three_axes.{ext}", dpi=220)
    plt.close(fig)
    print("Three controlled axes exported.")


if __name__ == "__main__":
    main()
