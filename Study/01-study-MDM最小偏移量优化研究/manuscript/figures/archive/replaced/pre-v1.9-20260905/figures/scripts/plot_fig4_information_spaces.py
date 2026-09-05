"""Render Figure 4: the five L1--L5 parameter-space partitions."""

from __future__ import annotations

import csv
from itertools import product
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


SCRIPT_DIR = Path(__file__).resolve().parent
FIGURE_DIR = SCRIPT_DIR.parent
OUTPUT_STEM = FIGURE_DIR / "main" / "fig4_information_spaces"
SOURCE_PATH = FIGURE_DIR / "data" / "derived" / "fig4_information_space_cells.csv"

BETA_GRID = np.arange(1.5, 5.01, 0.5)
RATIO_GRID = np.array([0.10, 0.25, 0.50, 0.75, 1.00])
N_GRID = np.array([7, 10, 15, 20])


def write_source_data() -> None:
    """Write the 160-cell design and its group identity under L1--L5."""
    SOURCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = SOURCE_PATH.with_name(f"{SOURCE_PATH.stem}.new.csv")
    fields = [
        "beta", "gamma_over_eta", "n",
        "L1_group", "L2_group", "L3_group", "L4_group", "L5_group",
    ]
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for beta, ratio, n_value in product(BETA_GRID, RATIO_GRID, N_GRID):
            writer.writerow({
                "beta": f"{beta:.1f}",
                "gamma_over_eta": f"{ratio:.2f}",
                "n": int(n_value),
                "L1_group": "all",
                "L2_group": f"n={int(n_value)}",
                "L3_group": f"beta={beta:.1f}",
                "L4_group": f"beta={beta:.1f}|n={int(n_value)}",
                "L5_group": (
                    f"beta={beta:.1f}|gamma_over_eta={ratio:.2f}|n={int(n_value)}"
                ),
            })
    temporary.replace(SOURCE_PATH)


def add_partition_plane(ax, vertices, facecolor, edgecolor, alpha=0.17) -> None:
    ax.add_collection3d(
        Poly3DCollection(
            [vertices], facecolor=facecolor, edgecolor=edgecolor,
            linewidth=0.72, alpha=alpha,
        )
    )


def add_space_box(ax, facecolor="#487C8F", edgecolor="#376476") -> None:
    """Represent L1 as one complete parameter space."""
    b0, b1 = BETA_GRID.min(), BETA_GRID.max()
    r0, r1 = RATIO_GRID.min(), RATIO_GRID.max()
    n0, n1 = N_GRID.min(), N_GRID.max()
    faces = [
        [(b0, r0, n0), (b1, r0, n0), (b1, r1, n0), (b0, r1, n0)],
        [(b0, r0, n1), (b1, r0, n1), (b1, r1, n1), (b0, r1, n1)],
        [(b0, r0, n0), (b1, r0, n0), (b1, r0, n1), (b0, r0, n1)],
        [(b0, r1, n0), (b1, r1, n0), (b1, r1, n1), (b0, r1, n1)],
        [(b0, r0, n0), (b0, r1, n0), (b0, r1, n1), (b0, r0, n1)],
        [(b1, r0, n0), (b1, r1, n0), (b1, r1, n1), (b1, r0, n1)],
    ]
    ax.add_collection3d(
        Poly3DCollection(
            faces,
            facecolor=mpl.colors.to_rgba(facecolor, 0.14),
            edgecolor=edgecolor,
            linewidth=0.95,
        )
    )


def add_information_space(ax, layer: str) -> None:
    """Draw the actual 8 x 5 x 4 grid and one information partition."""
    ax.set_proj_type("ortho")
    ax.view_init(elev=21, azim=-56)
    ax.set_xlim(1.38, 5.12)
    ax.set_ylim(0.04, 1.06)
    ax.set_zlim(5.8, 21.2)
    ax.set_box_aspect((1.22, 0.96, 0.90), zoom=1.17)

    beta, ratio, n_values = np.meshgrid(
        BETA_GRID, RATIO_GRID, N_GRID, indexing="ij"
    )
    if layer == "L1":
        add_space_box(ax)
    elif layer == "L2":
        colors = mpl.colormaps["Oranges"](np.linspace(0.42, 0.82, len(N_GRID)))
        for n_value, color in zip(N_GRID, colors):
            add_partition_plane(
                ax,
                [
                    (BETA_GRID.min(), RATIO_GRID.min(), n_value),
                    (BETA_GRID.max(), RATIO_GRID.min(), n_value),
                    (BETA_GRID.max(), RATIO_GRID.max(), n_value),
                    (BETA_GRID.min(), RATIO_GRID.max(), n_value),
                ],
                color, color,
            )
            mask = n_values == n_value
            ax.scatter(
                beta[mask], ratio[mask], n_values[mask], s=7.0,
                color=color, depthshade=False, edgecolor="white", linewidth=0.22,
            )
    elif layer == "L3":
        colors = mpl.colormaps["Blues"](np.linspace(0.36, 0.84, len(BETA_GRID)))
        for beta_value, color in zip(BETA_GRID, colors):
            add_partition_plane(
                ax,
                [
                    (beta_value, RATIO_GRID.min(), N_GRID.min()),
                    (beta_value, RATIO_GRID.max(), N_GRID.min()),
                    (beta_value, RATIO_GRID.max(), N_GRID.max()),
                    (beta_value, RATIO_GRID.min(), N_GRID.max()),
                ],
                color, color,
            )
            mask = np.isclose(beta, beta_value)
            ax.scatter(
                beta[mask], ratio[mask], n_values[mask], s=6.8,
                color=color, depthshade=False, edgecolor="white", linewidth=0.20,
            )
    elif layer == "L4":
        colors = mpl.colormaps["Blues"](np.linspace(0.42, 0.86, len(BETA_GRID)))
        for beta_value, color in zip(BETA_GRID, colors):
            for n_value in N_GRID:
                ax.plot(
                    np.full_like(RATIO_GRID, beta_value), RATIO_GRID,
                    np.full_like(RATIO_GRID, n_value), color=color,
                    lw=0.95, alpha=0.90,
                )
                ax.scatter(
                    np.full_like(RATIO_GRID, beta_value), RATIO_GRID,
                    np.full_like(RATIO_GRID, n_value), s=7.0, color=color,
                    depthshade=False, edgecolor="white", linewidth=0.20,
                )
    elif layer == "L5":
        ax.scatter(
            beta.ravel(), ratio.ravel(), n_values.ravel(), s=8.0,
            color="#4C956C", alpha=0.90, depthshade=False,
            edgecolor="white", linewidth=0.18,
        )
    else:
        raise ValueError(f"Unknown information layer: {layer}")

    labels = {
        "L1": ("全局统一", "1 组"),
        "L2": (r"按 $n$", "4 组"),
        "L3": (r"按 $\beta$", "8 组"),
        "L4": (r"按 $(\beta,n)$", "32 组"),
        "L5": (r"按 $(\beta,\gamma/\eta,n)$", "160 组"),
    }
    title, subtitle = labels[layer]
    ax.set_title(f"{layer}  {title}\n{subtitle}", fontsize=9.0, pad=0.0)
    ax.set_xticks(BETA_GRID)
    ax.set_yticks(RATIO_GRID)
    ax.set_zticks(N_GRID)
    ax.set_xlabel(r"$\beta$", labelpad=1, fontsize=8.0)
    ax.set_ylabel(r"$\gamma/\eta$", labelpad=3, fontsize=8.0)
    ax.set_zlabel("")
    ax.text2D(
        0.955, 0.50, r"$n$", transform=ax.transAxes,
        ha="center", va="center", fontsize=8.0,
    )
    ax.tick_params(labelsize=6.2, pad=0.4, length=2.2, width=0.60)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor((1, 1, 1, 0))
        axis.pane.set_edgecolor("#D8E0E5")
        axis._axinfo["grid"]["color"] = mpl.colors.to_rgba("#D8E0E5", 0.50)
        axis._axinfo["grid"]["linewidth"] = 0.45


def export_figure(fig: plt.Figure) -> None:
    from make_submission_figures import export_figure as shared_export
    shared_export(fig, OUTPUT_STEM.name, OUTPUT_STEM.parent)


def main() -> None:
    mpl.rcParams.update({"font.family":"sans-serif",
        "font.sans-serif":["Microsoft YaHei","Arial","DejaVu Sans"],
        "font.size":8,"axes.unicode_minus":False,"svg.fonttype":"none","pdf.fonttype":42})
    write_source_data()
    fig,ax=plt.subplots(figsize=(183/25.4,70/25.4));ax.axis("off")
    rows=[
        ["L1","全局统一","1","全部 160 个组合"],
        ["L2",r"$n$","4",r"同一 $n$ 下的 40 个组合"],
        ["L3",r"$\beta$","8",r"同一 $\beta$ 下的 20 个组合"],
        ["L4",r"$(\beta,n)$","32",r"同一 $(\beta,n)$ 下的 5 个位置尺度比"],
        ["L5",r"$(\beta,\gamma/\eta,n)$","160","同一完整参数组合内的重复样本"],
    ]
    table=ax.table(cellText=rows,colLabels=["规则","分组信息","组数","组内样本来源"],
        colWidths=[.10,.25,.10,.55],cellLoc="center",loc="center")
    table.auto_set_font_size(False);table.set_fontsize(8.6);table.scale(1,1.6)
    for (row,col),cell in table.get_celld().items():
        cell.set_edgecolor("#D7DEE4");cell.set_linewidth(.5)
        cell.set_facecolor("#EAF1F6" if row==0 else ("#F8FAFC" if row%2 else "white"))
    ax.set_title("各组均由训练样本的平均损失曲线确定一个偏移量",fontsize=8,pad=12)
    export_figure(fig)
    print(OUTPUT_STEM.with_suffix(".png"))


if __name__ == "__main__":
    main()
