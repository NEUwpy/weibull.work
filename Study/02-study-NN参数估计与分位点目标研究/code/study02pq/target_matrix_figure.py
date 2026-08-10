"""从已封存的矩阵 pilot 分析表重绘可独立阅读的结果图。"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import target_matrix_pilot as PILOT


def main() -> None:
    analysis = PILOT.ART_ROOT / "analysis"
    cells = pd.read_csv(analysis / "cell_metrics.csv")
    sensitivity = pd.read_csv(analysis / "sensitivity_matrices.csv")

    plt.rcParams.update({"font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.45))
    routes = ("P", "M95", "Q")
    colors = ("#4477AA", "#228833", "#EE7733")
    values = [np.sqrt(cells[f"mse_{route}"].mean()) for route in routes]
    axes[0].bar(routes, values, color=colors, width=0.62)
    for index, route in enumerate(routes):
        seed_values = [np.sqrt(part[f"mse_{route}"].mean())
                       for _, part in cells.groupby("seed", sort=True)]
        axes[0].scatter(np.full(len(seed_values), index), seed_values,
                        color="black", s=20, zorder=3)
    axes[0].set_ylabel("B5 held-out rRMSE")
    axes[0].set_title("(a) Held-out B5 rRMSE by training loss")

    for (_, label), part in sensitivity.groupby(["R", "target"], sort=False):
        by_beta = part.groupby("beta", as_index=False).first()
        axes[1].plot(by_beta.beta, by_beta.s_beta / by_beta.s_gamma,
                     marker="o", label=f"{label}: beta/gamma")
        axes[1].plot(by_beta.beta, by_beta.s_eta / by_beta.s_gamma,
                     marker="s", linestyle="--", label=f"{label}: eta/gamma")
    axes[1].axhline(1.0, color="0.7", linewidth=0.8)
    axes[1].set_xlabel("Weibull shape beta")
    axes[1].set_ylabel("dimensionless sensitivity ratio")
    axes[1].set_title("(b) B1/B5/B10 imply different parameter geometry")
    axes[1].legend(fontsize=7, ncol=2)
    fig.suptitle("Study02 target-sensitivity matrix pilot", fontweight="bold")
    fig.text(0.5, 0.008,
             "Descriptive pilot: 3 seeds x 2 folds x 4 n = 24 cells; "
             "bars = equal-cell rRMSE; dots = seed-level rRMSE; no confidence intervals.",
             ha="center", fontsize=8, color="0.3")
    fig.tight_layout(rect=(0, 0.045, 1, 0.96))
    fig.savefig(analysis / "target_matrix_pilot.png", dpi=220, bbox_inches="tight")
    fig.savefig(analysis / "target_matrix_pilot.pdf", bbox_inches="tight")
    plt.close(fig)

    manifest_path = PILOT.ART_ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["figure_code_sha256"] = PILOT._sha(Path(__file__))
    manifest["figure_contract"] = (
        "descriptive 3-seed x 2-fold x 4-n pilot; bars equal-cell rRMSE; "
        "dots seed-level rRMSE; no confidence intervals")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    PILOT._write_sha256sums()


if __name__ == "__main__":
    main()
