"""Render the submission-grade three-panel E13 parameter-domain figure."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from scipy.interpolate import RegularGridInterpolator


SCRIPT_DIR = Path(__file__).resolve().parent
FIGURE_DIR = SCRIPT_DIR.parent
STUDY_ROOT = FIGURE_DIR.parents[1]
SOURCE_DIR = STUDY_ROOT / "artifacts" / "formal" / "E13_beta_domain_sensitivity"
OUTPUT_DIR = FIGURE_DIR / "main"
OUTPUT_STEM = "fig3_beta_domain_sensitivity"

BETA_GRID = np.round(np.arange(1.50, 5.00 + 0.001, 0.25), 2)
RATIO_GRID = np.array([0.10, 0.25, 0.50, 0.75, 1.00])
N_GRID = np.array([7, 10, 15, 20])
SLAB_1 = (2.50, 3.50)
SLAB_2 = (2.75, 3.75)


def load_surface_data():
    curves = pd.read_csv(SOURCE_DIR / "window_risk_curves.csv")
    summary = pd.read_csv(SOURCE_DIR / "window_summary.csv").sort_values("beta_center")
    curves = curves.sort_values(["beta_center", "delta"]).copy()
    centers = summary["beta_center"].to_numpy(dtype=float)
    deltas = np.sort(curves["delta"].unique()).astype(float)
    j1 = np.vstack(
        [
            curves[np.isclose(curves["beta_center"], center)]
            .sort_values("delta")["J1"]
            .to_numpy(dtype=float)
            for center in centers
        ]
    )
    center_fine = np.linspace(centers.min(), centers.max(), 151)
    delta_fine = np.linspace(deltas.min(), deltas.max(), 201)
    delta_mesh, center_mesh = np.meshgrid(delta_fine, center_fine)
    j1_interpolation = RegularGridInterpolator(
        (centers, deltas), j1, method="linear", bounds_error=True
    )
    j1_fine = j1_interpolation(
        np.column_stack([center_mesh.ravel(), delta_mesh.ravel()])
    ).reshape(center_mesh.shape)
    return (
        curves, summary, centers, deltas, j1,
        center_mesh, delta_mesh, j1_fine,
    )


def draw_parameter_box(ax, lower, upper, color, alpha, linewidth):
    """Draw one beta-window parameter space as a translucent cuboid."""
    y0, y1 = RATIO_GRID.min(), RATIO_GRID.max()
    z0, z1 = N_GRID.min(), N_GRID.max()
    vertices = {
        "000": (lower, y0, z0), "001": (lower, y0, z1),
        "010": (lower, y1, z0), "011": (lower, y1, z1),
        "100": (upper, y0, z0), "101": (upper, y0, z1),
        "110": (upper, y1, z0), "111": (upper, y1, z1),
    }
    faces = [
        [vertices[k] for k in ("000", "001", "011", "010")],
        [vertices[k] for k in ("100", "101", "111", "110")],
        [vertices[k] for k in ("000", "001", "101", "100")],
        [vertices[k] for k in ("010", "011", "111", "110")],
        [vertices[k] for k in ("000", "010", "110", "100")],
        [vertices[k] for k in ("001", "011", "111", "101")],
    ]
    ax.add_collection3d(
        Poly3DCollection(
            faces, facecolors=color, edgecolors=color,
            linewidths=linewidth, alpha=alpha,
        )
    )


def panel_a(ax):
    beta, ratio, n_values = np.meshgrid(BETA_GRID, RATIO_GRID, N_GRID, indexing="ij")
    ax.scatter(beta.ravel(), ratio.ravel(), n_values.ravel(), s=3.4,
               color="#AAB4BC", alpha=0.38, depthshade=False, linewidth=0)
    selected_1 = (beta >= SLAB_1[0] - 1e-12) & (beta <= SLAB_1[1] + 1e-12)
    selected_2 = (beta >= SLAB_2[0] - 1e-12) & (beta <= SLAB_2[1] + 1e-12)
    ax.scatter(beta[selected_1], ratio[selected_1], n_values[selected_1], s=7.0,
               color="#2D7FA3", alpha=0.78, depthshade=False,
               edgecolor="white", linewidth=0.18)
    ax.scatter(beta[selected_2], ratio[selected_2], n_values[selected_2], s=7.0,
               color="#D17A3A", alpha=0.58, depthshade=False,
               edgecolor="white", linewidth=0.18)

    draw_parameter_box(ax, *SLAB_1, color="#2D7FA3", alpha=0.095, linewidth=0.95)
    draw_parameter_box(ax, *SLAB_2, color="#D17A3A", alpha=0.075, linewidth=0.95)

    # One short grid-step shift, explicitly parallel to the beta axis.
    ax.plot([3.00, 3.25], [1.035, 1.035], [21.1, 21.1],
            color="#C8483C", lw=1.9, marker=">", markevery=[1],
            markersize=5.0, solid_capstyle="round")
    ax.text(2.42, 1.035, 21.15, r"$B_1=[2.50,3.50]$",
            color="#1F6483", fontsize=6.2, fontweight="bold")
    ax.text(3.30, 1.035, 21.15, r"$B_2=[2.75,3.75]$",
            color="#A85B29", fontsize=6.2, fontweight="bold")

    ax.set_xlim(1.42, 5.08)
    ax.set_ylim(0.04, 1.07)
    ax.set_zlim(5.5, 21.5)
    ax.set_xticks(np.arange(1.5, 5.01, 0.5))
    ax.set_yticks(RATIO_GRID)
    ax.set_zticks(N_GRID)
    ax.set_xlabel(r"$\beta$", labelpad=1)
    ax.set_ylabel(r"$\gamma/\eta$", labelpad=3)
    ax.set_zlabel(r"$n$", labelpad=0)
    ax.set_title("a   相邻参数空间", loc="left", fontweight="bold", pad=0)
    ax.view_init(elev=21, azim=-56)
    # A and C occupy equal GridSpec cells; a small 3D zoom compensates for the
    # extra internal padding that makes 3D axes look smaller than a 2D axes.
    ax.set_box_aspect((1.22, 0.96, 0.90), zoom=1.18)
    style_3d(ax)


def panel_b(ax, summary, centers, center_mesh, delta_mesh, j1_fine, cmap, norm, levels):
    ax.contourf(delta_mesh, center_mesh, j1_fine, levels=levels,
                cmap=cmap, norm=norm, extend="max", antialiased=False)
    for row in summary.itertuples(index=False):
        ax.plot([row.near_optimal_1pct_lower, row.near_optimal_1pct_upper],
                [row.beta_center, row.beta_center], color="black", lw=1.7,
                solid_capstyle="butt", zorder=5)
    ax.plot(summary["best_delta"], centers, color="#C8483C", lw=1.2,
            marker="o", markersize=4.0, markerfacecolor="#C8483C",
            markeredgecolor="white", markeredgewidth=0.5, zorder=6)
    ax.axvline(0.10, color="#596771", lw=1.0, linestyle="--", zorder=4)
    ax.set_xlim(0, 0.50)
    ax.set_ylim(centers.min(), centers.max())
    ax.set_xticks(np.arange(0, 0.51, 0.10))
    ax.set_yticks(centers)
    ax.set_yticklabels(
        [f"[{row.beta_lower:.2f}, {row.beta_upper:.2f}]" for row in summary.itertuples(index=False)],
        fontsize=5.8,
    )
    ax.set_xlabel(r"偏移量 $\delta$")
    ax.set_ylabel(r"形状参数域 $B(c)$")
    # Lift the title to the same visual band as the two 3D-panel titles.
    ax.set_title(r"c   $J_1$ 风险俯视图", loc="left", fontweight="bold", y=1.14)
    ax.set_box_aspect(1.0)
    ax.spines[["top", "right"]].set_visible(False)


def panel_c(ax, curves, summary, centers, deltas, j1, center_mesh, delta_mesh,
            j1_fine, cmap, norm):
    ax.plot_surface(delta_mesh, center_mesh, j1_fine,
                    facecolors=cmap(norm(j1_fine)), linewidth=0,
                    antialiased=False, shade=False, alpha=0.76,
                    zorder=1,
                    rcount=151, ccount=201)
    # Explicitly overlay every observed row: 11 beta windows x 26 delta points.
    # The very small vertical lift prevents z-fighting without altering the
    # scientific shape; computed_zorder=False keeps the observed rows visible.
    line_lift = 0.0025
    for center, row_values in zip(centers, j1):
        y_values = np.full_like(deltas, center)
        z_values = row_values + line_lift
        ax.plot(deltas, y_values, z_values,
                color="white", lw=2.65, alpha=0.98, zorder=6)
        ax.plot(deltas, y_values, z_values,
                color="#24343D", lw=1.05, alpha=1.0, zorder=7)
        ax.scatter(deltas, y_values, z_values + 0.0008,
                   color="#24343D", s=7.0, alpha=1.0, depthshade=False,
                   edgecolor="white", linewidth=0.35, zorder=8)

    best_j1 = j1.min(axis=1)
    best_line, = ax.plot(
        summary["best_delta"], centers, best_j1 + 0.008,
        color="#C8483C", lw=1.65, marker="o", markersize=3.8,
        markerfacecolor="#C8483C", markeredgecolor="white",
        markeredgewidth=0.5, zorder=9
    )
    best_line.set_path_effects(
        [path_effects.Stroke(linewidth=2.6, foreground="white", alpha=0.90),
         path_effects.Normal()]
    )
    default_j1 = np.array(
        [
            curves[np.isclose(curves["beta_center"], center)
                   & np.isclose(curves["delta"], 0.10)]["J1"].iloc[0]
            for center in centers
        ]
    )
    default_line, = ax.plot(
        np.full_like(centers, 0.10), centers, default_j1 + 0.006,
        color="#596771", lw=1.1, linestyle="--", marker="s",
        markersize=2.8, markerfacecolor="white", markeredgewidth=0.5, zorder=8
    )
    default_line.set_path_effects(
        [path_effects.Stroke(linewidth=2.0, foreground="white", alpha=0.85),
         path_effects.Normal()]
    )

    ax.set_xlim(0, 0.50)
    ax.set_ylim(centers.min(), centers.max())
    ax.set_zlim(0.49, 1.01)
    ax.set_xticks(np.arange(0, 0.51, 0.10))
    ax.set_yticks(centers)
    ax.set_yticklabels(
        [f"[{row.beta_lower:.2f}, {row.beta_upper:.2f}]"
         for row in summary.itertuples(index=False)],
        fontsize=4.9,
    )
    ax.tick_params(axis="y", pad=-1)
    for label in ax.get_yticklabels():
        label.set_horizontalalignment("left")
        label.set_verticalalignment("center")
    ax.set_zticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_xlabel(r"$\delta$", labelpad=2)
    ax.set_ylabel(r"$\beta$ 区间", labelpad=4)
    ax.set_zlabel("")
    ax.text2D(0.985, 0.69, r"$J_1$", transform=ax.transAxes,
              rotation=90, ha="center", va="center", fontsize=7.2)
    ax.set_title(r"b   $J_1$ 风险地形", loc="left", fontweight="bold", pad=0)
    # Oblique side view exposes the depth and width of the diagonal low-risk valley.
    ax.view_init(elev=24, azim=-75)
    ax.set_box_aspect((1.20, 1.00, 0.88), zoom=1.14)
    style_3d(ax)


def style_3d(ax):
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor((1, 1, 1, 0))
        axis.pane.set_edgecolor("#D7DEE5")
        axis._axinfo["grid"]["color"] = mpl.colors.to_rgba("#D7DEE5", 0.52)
        axis._axinfo["grid"]["linewidth"] = 0.4


def export_figure(fig):
    """Atomically export Figure 3 in the four manuscript formats."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    svg_target = OUTPUT_DIR / f"{OUTPUT_STEM}.svg"
    svg_temporary = OUTPUT_DIR / f"{OUTPUT_STEM}.new.svg"
    fig.savefig(svg_temporary, bbox_inches="tight", facecolor="white")
    svg_text = svg_temporary.read_text(encoding="utf-8")
    svg_temporary.write_text(
        "\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    svg_temporary.replace(svg_target)
    for extension, kwargs in (
        ("pdf", {}),
        ("png", {"dpi": 300}),
    ):
        target = OUTPUT_DIR / f"{OUTPUT_STEM}.{extension}"
        temporary = OUTPUT_DIR / f"{OUTPUT_STEM}.new.{extension}"
        fig.savefig(temporary, bbox_inches="tight", facecolor="white", **kwargs)
        temporary.replace(target)
    tiff_target = OUTPUT_DIR / f"{OUTPUT_STEM}.tiff"
    tiff_temporary = OUTPUT_DIR / f"{OUTPUT_STEM}.new.tiff"
    fig.savefig(
        tiff_temporary,
        dpi=600,
        bbox_inches="tight",
        facecolor="white",
        pil_kwargs={"compression": "tiff_lzw"},
    )
    tiff_temporary.replace(tiff_target)
    plt.close(fig)


def main():
    (
        curves, summary, centers, deltas, j1,
        center_mesh, delta_mesh, j1_fine,
    ) = load_surface_data()
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "Arial", "DejaVu Sans", "sans-serif"],
            "axes.unicode_minus": False,
            "font.size": 7.2,
            "axes.linewidth": 0.75,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )
    # Absolute J1 throughout; denser low-end boundaries improve discrimination
    # inside the scientifically important low-risk region without normalizing
    # each beta window separately.
    levels = np.array([
        0.50, 0.51, 0.52, 0.53, 0.54, 0.55, 0.56, 0.57,
        0.58, 0.59, 0.60, 0.615, 0.63, 0.645, 0.66, 0.68,
        0.70, 0.73, 0.76, 0.80, 0.85, 0.90, 0.95, 1.00,
    ])
    cmap = mpl.colormaps["YlGnBu"]
    norm = BoundaryNorm(levels, cmap.N, clip=True)

    fig = plt.figure(figsize=(15.2, 5.25))
    gs = fig.add_gridspec(1, 4, width_ratios=[1.18, 1.18, 0.12, 0.78],
                          left=0.035, right=0.925, bottom=0.15, top=0.91,
                          wspace=0.08)
    ax_a = fig.add_subplot(gs[0, 0], projection="3d")
    ax_b = fig.add_subplot(gs[0, 1], projection="3d", computed_zorder=False)
    ax_c = fig.add_subplot(gs[0, 3])
    ax_c.set_anchor("C")
    panel_a(ax_a)
    panel_c(ax_b, curves, summary, centers, deltas, j1, center_mesh,
            delta_mesh, j1_fine, cmap, norm)
    panel_b(ax_c, summary, centers, center_mesh, delta_mesh, j1_fine,
            cmap, norm, levels)

    legend = [
        Line2D([0], [0], color="#C8483C", marker="o", markeredgecolor="white",
               lw=1.4, markersize=4.5, label="离散最低点"),
        Line2D([0], [0], color="black", lw=1.7, label="最低点以上 1% 内"),
        Line2D([0], [0], color="#596771", linestyle="--", lw=1.0,
               label=r"$\delta=0.10$"),
        Line2D([0], [0], color="#2F3D46", marker=".", lw=0.75,
               markersize=3, label="实际 26 点风险曲线"),
    ]
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.61, 0.015),
               ncol=4, frameon=False, fontsize=6.7, handlelength=2.2,
               columnspacing=1.4)

    # Match the colorbar's vertical extent exactly to panel c's heatmap area.
    fig.canvas.draw()
    panel_c_bbox = ax_c.get_position()
    scalar = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
    scalar.set_array([])
    cax = fig.add_axes([0.943, panel_c_bbox.y0, 0.012, panel_c_bbox.height])
    cbar = fig.colorbar(scalar, cax=cax)
    cbar.set_ticks([0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 0.90, 1.00])
    cbar.set_ticklabels(["0.50", "0.55", "0.60", "0.65", "0.70", "0.80", "0.90", "1.00"])
    cbar.ax.set_title(r"$J_1$", fontsize=7, pad=4)
    cbar.outline.set_linewidth(0.55)

    export_figure(fig)
    print(OUTPUT_DIR / f"{OUTPUT_STEM}.png")


if __name__ == "__main__":
    main()
