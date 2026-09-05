"""Figure 2: merge full-grid and zoom panels; use unchanged source CSVs.

Contract: panel a shows all 26 candidate risks with the minimum/default marked;
panel b retains the within-cell sampling SD distributions for 160 cells.
Python/matplotlib, 183 x 85 mm. No inset, no data recomputation.
"""
from make_submission_figures import *

def figure_1_offset_baseline(paths):
    curve = pd.read_csv(DERIVED_DIR / "fig1_delta_risk.csv")
    d_min = float(curve.loc[curve["J1"].idxmin(), "delta"])
    j_min = float(curve["J1"].min())
    j_default = float(curve.loc[np.isclose(curve["delta"], 0.10), "J1"].iloc[0])
    stability = pd.read_csv(DERIVED_DIR / "fig1_fixed_offset_stability.csv")

    fig, (ax, distribution) = plt.subplots(
        1, 2, figsize=(183 * MM, 85 * MM),
        gridspec_kw={"width_ratios": [1.15, 1.00], "wspace": 0.44},
    )
    for target in (ax,):
        target.plot(curve["delta"], curve["J1"], color=COLORS["ink"],
                    lw=1.45, marker="o", ms=2.8, mfc="white", mew=0.8)
        style_axis(target)
        target.set_xlabel(r"Offset, $\delta$")
        target.set_ylabel(r"Pooled $J_1$")

    ax.scatter([d_min], [j_min], s=28, color=COLORS["raw"], zorder=5,
               label=f"Minimum ({d_min:.2f})")
    ax.scatter([0.10], [j_default], s=30, color=COLORS["accent"], marker="s",
               zorder=5, label="Default (0.10)")
    ax.set_xlim(-0.01, 0.51)
    ax.set_ylim(0.60, max(curve["J1"].max() + 0.015, 0.96))
    ax.legend(loc="upper right", handletextpad=0.5)
    ax.set_title("Full candidate grid", pad=4)
    panel_label(ax, "a")

    ax.annotate(f"最低点\n$J_1={j_min:.4f}$", (d_min, j_min),
                xytext=(0.075, 0.78), ha="left", va="top", fontsize=8.6,
                arrowprops={"arrowstyle": "-", "lw": 0.7, "color": COLORS["muted"]})
    ax.annotate(f"固定规则\n$J_1={j_default:.4f}$", (0.10, j_default),
                xytext=(0.24, 0.618), ha="left", va="bottom", fontsize=8.6,
                arrowprops={"arrowstyle": "-", "lw": 0.7, "color": COLORS["muted"]})
    ax.set_xticks(np.arange(0, 0.51, 0.1))

    parameters = ["beta", "eta", "gamma"]
    method_specs = [
        ("No offset", -0.18, COLORS["accent"]),
        ("Default", 0.18, COLORS["raw"]),
    ]
    for xi, parameter in enumerate(parameters):
        medians = {}
        for method, shift, color in method_specs:
            values = stability.loc[
                (stability["parameter"] == parameter) &
                (stability["method"] == method),
                "within_cell_normalized_sd",
            ].to_numpy(dtype=float)
            medians[method] = float(np.median(values))
            violin = distribution.violinplot(
                [values], positions=[xi + shift], widths=0.30,
                showmeans=False, showmedians=False, showextrema=False,
            )
            for body in violin["bodies"]:
                body.set_facecolor(color)
                body.set_edgecolor(color)
                body.set_alpha(0.25)
                body.set_linewidth(0.7)
            distribution.boxplot(
                [values], positions=[xi + shift], widths=0.09,
                showfliers=False, patch_artist=True,
                medianprops={"color": color, "linewidth": 1.15},
                boxprops={"facecolor": "white", "edgecolor": color, "linewidth": 0.8},
                whiskerprops={"color": color, "linewidth": 0.7},
                capprops={"color": color, "linewidth": 0.7},
            )
        reduction = 100 * (1 - medians["Default"] / medians["No offset"])
        y_top = stability.loc[
            stability["parameter"] == parameter,
            "within_cell_normalized_sd",
        ].max()
        distribution.text(
            xi, y_top + 0.045, f"median −{reduction:.0f}%",
            ha="center", va="bottom", fontsize=5.7, color=COLORS["ink"],
        )
    distribution.set_xticks(range(3), [r"$\beta$", r"$\eta$", r"$\gamma$"])
    distribution.set_xlim(-0.55, 2.55)
    distribution.set_ylim(0.05, 1.25)
    distribution.set_ylabel("Within-cell normalized SD")
    distribution.set_title("Within-cell sampling dispersion", pad=4)
    legend_handles = [
        mpl.lines.Line2D([], [], color=color, marker="s", linestyle="none",
                         markersize=5, label=(r"$\delta=0$" if method == "No offset"
                                               else r"$\delta=0.10$"))
        for method, _, color in method_specs
    ]
    distribution.legend(handles=legend_handles, loc="upper right",
                        handletextpad=0.3, borderaxespad=0.2)
    style_axis(distribution, ygrid=True)
    panel_label(distribution, "b")
    fig.align_ylabels()
    export_figure(fig, "fig2_offset_baseline_combined", MAIN_DIR)


if __name__ == "__main__":
    figure_1_offset_baseline(None)
