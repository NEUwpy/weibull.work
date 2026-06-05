"""make_figures.py — produce all publication figures into ../figures/."""
import glob, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm
from mdm_core import (sample_weibull3, estimate_mdm, _moving_average)

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "axes.titlesize": 12, "axes.labelsize": 11,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 140, "savefig.bbox": "tight", "savefig.dpi": 150,
    "legend.fontsize": 9, "legend.frameon": False,
})
ETA = 100.0
DELTAS = np.array([0, 0.01, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.50, 0.70, 1.00])
FIG = "../figures/"

df = pd.read_csv("../data/agg_master.csv")
betas = sorted(df.beta.unique())
ns = sorted(df.n.unique())
grs = sorted(df.gamma_over_eta.unique())
BLUE, ORNG, GRN, RED, PURP = "#1f4e79", "#c55a11", "#2e7d32", "#c00000", "#7030a0"


# ------------------------------------------------------------------ Fig 1: geometry
def fig_geometry():
    cases = [dict(beta=5.0, gr=0.1, n=20, seed=14, tag="(a) β=5, n=20"),
             dict(beta=2.0, gr=0.1, n=20, seed=13, tag="(b) β=2, n=20"),
             dict(beta=1.2, gr=0.1, n=30, seed=3, tag="(c) β=1.2, n=30")]
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.2), sharex="col")
    cols = cm.viridis(np.linspace(0.05, 0.92, len(DELTAS)))
    show = [0, 0.05, 0.10, 0.20, 0.50]
    for j, c in enumerate(cases):
        rng = np.random.default_rng(c["seed"])
        g_true = c["gr"] * ETA
        t = sample_weibull3(c["beta"], ETA, g_true, c["n"], rng)
        res = estimate_mdm(t, DELTAS)
        g = res["gamma_grid"]; s = res["sigma_min"]; grad = res["grad"]
        s_sm = _moving_average(s, 7)
        ax = axes[0, j]
        ax.plot(g, s_sm, color=BLUE, lw=1.6)
        ax.axvline(g_true, color=GRN, ls="--", lw=1.3, label="true γ")
        ax.axvline(t[0], color=RED, ls=":", lw=1.3, label="$t_{min}$")
        ax.plot(res["gamma0"], np.interp(res["gamma0"], g, s_sm), "o",
                color="k", ms=5, label="bowl bottom (δ=0)")
        for d in show:
            gh = res[float(d)]["gamma_hat"]
            ax.axvline(gh, color=cm.viridis(d / 0.5 * 0.9), lw=1.0, alpha=0.9)
        lo = min(g_true, res["gamma0"]) - 0.4 * (t[0] - min(g_true, res["gamma0"]) + 1)
        ax.set_xlim(max(g.min(), lo), t[0] + 0.10 * (t[0] - lo + 1))
        ax.set_title(c["tag"])
        if j == 0:
            ax.set_ylabel(r"$\sigma_{min}(\gamma)$")
            ax.legend(loc="upper left", fontsize=8)
        ax2 = axes[1, j]
        ax2.plot(g, grad, color=ORNG, lw=1.4)
        ax2.axhline(0, color="k", lw=0.6)
        for d in show:
            if d == 0:
                continue
            ax2.axhline(d, color="gray", ls=":", lw=0.6)
            gh = res[float(d)]["gamma_hat"]
            ax2.plot(gh, np.interp(gh, g, grad), "o", ms=4,
                     color=cm.viridis(d / 0.5 * 0.9))
        ax2.set_xlim(axes[0, j].get_xlim())
        yv = grad[(g >= ax2.get_xlim()[0]) & (g <= ax2.get_xlim()[1])]
        if yv.size:
            ax2.set_ylim(min(-0.15, np.percentile(yv, 1)), max(0.65, np.percentile(yv, 96)))
        ax2.set_xlabel(r"$\gamma$")
        if j == 0:
            ax2.set_ylabel(r"slope $d\sigma_{min}/d\gamma$")
    fig.suptitle("Geometry of the MDM criterion: the σ_min bowl and the gradient-offset stops "
                 "(colored = δ = 0, .05, .10, .20, .50)", y=1.01, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG + "fig1_geometry.png"); plt.close(fig)


# ------------------------------------------------------------------ Fig 2: NE vs delta by beta
def fig_ne_vs_delta_beta():
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    piv = df.groupby(["beta", "delta"])["NE_mean_capped"].mean().unstack("delta")
    cmap = cm.plasma(np.linspace(0.05, 0.85, len(betas)))
    for col, b in zip(cmap, betas):
        y = piv.loc[b].values
        ax.plot(DELTAS, y, "-o", color=col, ms=4, lw=1.6, label=f"β={b:g}")
        bi = int(np.argmin(y))
        ax.plot(DELTAS[bi], y[bi], "*", color=col, ms=14,
                markeredgecolor="k", markeredgewidth=0.5, zorder=5)
    ax.axvline(0.10, color="gray", ls="--", lw=1)
    ax.text(0.105, ax.get_ylim()[1]*0.96, "δ=0.1\n(common)", fontsize=8, color="gray", va="top")
    ax.set_xlabel("gradient offset δ"); ax.set_ylabel("mean normalized error (capped)")
    ax.set_title("Accuracy vs δ for each shape β  (★ = optimum)")
    ax.legend(title="shape", ncol=1)
    fig.tight_layout(); fig.savefig(FIG + "fig2_ne_vs_delta_beta.png"); plt.close(fig)


# ------------------------------------------------------------------ Fig 3: best-delta trends
def fig_best_trends():
    bestp = pd.read_csv("../data/best_per_scenario.csv")
    # marginal optima (argmin of scenario-averaged NE) — the decision-relevant line
    def marg(col):
        g = df.groupby([col, "delta"])["NE_mean_capped"].mean().reset_index()
        gi = g.groupby(col)["NE_mean_capped"].idxmin()
        return g.loc[gi].set_index(col)["delta"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, (col, lab) in zip(axes, [("beta", "shape β"),
                                     ("n", "sample size n"),
                                     ("gamma_over_eta", "location ratio γ/η")]):
        q1 = bestp.groupby(col)["best_delta"].quantile(0.25)
        q3 = bestp.groupby(col)["best_delta"].quantile(0.75)
        opt = marg(col)
        xs = opt.index.values
        ax.fill_between(xs, q1.reindex(xs).values, q3.reindex(xs).values,
                        color=BLUE, alpha=0.15, label="per-scenario IQR")
        ax.plot(xs, opt.values, "-o", color=BLUE, lw=1.8, ms=6,
                label="optimal δ (min avg NE)")
        ax.axhline(0.10, color=RED, ls="--", lw=1, label="δ=0.1")
        ax.set_xlabel(lab); ax.set_ylabel("optimal δ")
        if col in ("beta", "n"):
            ax.set_xscale("log"); ax.set_xticks(xs)
            ax.set_xticklabels([f"{v:g}" for v in xs])
        ax.set_title(f"optimal δ vs {lab.split('(')[0]}")
    axes[0].legend(loc="upper right", fontsize=8)
    fig.suptitle("How the optimal offset depends on the (unknown) parameters", y=1.03)
    fig.tight_layout(); fig.savefig(FIG + "fig3_best_delta_trends.png"); plt.close(fig)


# ------------------------------------------------------------------ Fig 4: heatmap best delta over (beta,n)
def fig_heatmap():
    bestp = pd.read_csv("../data/best_per_scenario.csv")
    M = bestp.groupby(["beta", "n"])["best_delta"].median().unstack("n")
    M = M.reindex(index=betas, columns=ns)
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    im = ax.imshow(M.values, cmap="viridis", aspect="auto", origin="lower")
    ax.set_xticks(range(len(ns))); ax.set_xticklabels(ns)
    ax.set_yticks(range(len(betas))); ax.set_yticklabels([f"{b:g}" for b in betas])
    ax.set_xlabel("sample size n"); ax.set_ylabel("shape β")
    for i in range(len(betas)):
        for j in range(len(ns)):
            v = M.values[i, j]
            ax.text(j, i, f"{v:g}", ha="center", va="center",
                    color="white" if v < 0.4 else "black", fontsize=9)
    cb = fig.colorbar(im, ax=ax); cb.set_label("median optimal δ")
    ax.set_title("Optimal δ across (β, n)  — driven mainly by β, decreasing in n")
    fig.tight_layout(); fig.savefig(FIG + "fig4_heatmap_best_delta.png"); plt.close(fig)


# ------------------------------------------------------------------ Fig 5: ladder
def fig_ladder():
    lad = pd.read_csv("../data/ladder.csv")
    fig, ax = plt.subplots(figsize=(9, 4.4))
    names = ["δ=0\n(classical ∇=0)", "δ=0.1\n(baseline)", "global best\nfixed δ",
             "by n\n(know n)", "by β\n(know β)", "by (β,γ/η)", "per scenario\n(n,β,γ/η)",
             "per-sample\noracle"]
    vals = lad["impr_pct"].values
    colors = [RED] + ["#9aa0a6"] + ["#5b9bd5"] + [GRN]*4 + [PURP]
    bars = ax.bar(range(len(vals)), vals, color=colors)
    ax.axhline(0, color="k", lw=0.8)
    for i, v in enumerate(vals):
        ax.text(i, v + (1.2 if v >= 0 else -1.2), f"{v:+.0f}%",
                ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
    ax.set_xticks(range(len(names))); ax.set_xticklabels(names, fontsize=8.5)
    ax.set_ylabel("NE improvement vs fixed δ=0.1 (%)")
    ax.set_title("Ladder of knowledge levels: how much each buys over the δ=0.1 default")
    ax.set_ylim(min(vals) - 12, max(vals) + 10)
    fig.tight_layout(); fig.savefig(FIG + "fig5_ladder.png"); plt.close(fig)


# ------------------------------------------------------------------ Fig 6: delta=0 vs 0.1 vs best + anomaly
def fig_offset_essential():
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11.5, 4.3))
    piv = df.groupby(["beta", "delta"])["NE_mean_capped"].mean().unstack("delta")
    ne0 = piv[0.0].values; ne01 = piv[0.10].values
    nebest = piv.min(axis=1).values
    xb = np.arange(len(betas)); w = 0.26
    axL.bar(xb - w, ne0, w, label="δ=0 (∇=0)", color=RED)
    axL.bar(xb, ne01, w, label="δ=0.1", color="#5b9bd5")
    axL.bar(xb + w, nebest, w, label="best δ", color=GRN)
    axL.set_xticks(xb); axL.set_xticklabels([f"{b:g}" for b in betas])
    axL.set_xlabel("shape β"); axL.set_ylabel("mean normalized error (capped)")
    axL.set_title("Using an offset is essential\n(δ=0 vs δ=0.1 vs best)")
    axL.legend()
    an = df.groupby(["n", "delta"])["anom_rate"].mean().unstack("delta")
    axR.plot(ns, 100*an[0.0].values, "-o", color=RED, label="δ=0 (∇=0)")
    axR.plot(ns, 100*an[0.10].values, "-s", color="#5b9bd5", label="δ=0.1")
    axR.set_xscale("log"); axR.set_xticks(ns); axR.set_xticklabels(ns)
    axR.set_xlabel("sample size n"); axR.set_ylabel("anomalous-estimate rate (%)")
    axR.set_title("The offset removes catastrophic failures")
    axR.legend()
    fig.tight_layout(); fig.savefig(FIG + "fig6_offset_essential.png"); plt.close(fig)


# ------------------------------------------------------------------ Fig 7: gamma boxplots delta=0/0.1/best
def fig_gamma_box():
    # representative scenario: beta=3, gr=0.1, n=30
    z = np.load("../data/raw_n30.npz")
    bi = list(z["betas"]).index(3.0); gi = list(z["grs"]).index(0.1)
    g_true = 0.1 * ETA
    didx = {round(float(d),3): k for k, d in enumerate(DELTAS)}
    bestp = pd.read_csv("../data/best_per_scenario.csv")
    bd = bestp[(bestp.n==30)&(bestp.beta==3.0)&(bestp.gamma_over_eta==0.1)]["best_delta"].iloc[0]
    sel = [(0.0, "δ=0"), (0.10, "δ=0.1"), (float(bd), f"best δ={bd:g}")]
    data = []
    for d, _ in sel:
        gh = z["ghat"][bi, gi, didx[round(d,3)], :]
        data.append(gh[np.isfinite(gh)])
    fig, ax = plt.subplots(figsize=(7, 4.3))
    bp = ax.boxplot(data, labels=[s[1] for s in sel], showfliers=False,
                    patch_artist=True, widths=0.55)
    for patch, c in zip(bp["boxes"], [RED, "#5b9bd5", GRN]):
        patch.set_facecolor(c); patch.set_alpha(0.6)
    ax.axhline(g_true, color=GRN, ls="--", lw=1.4, label=f"true γ={g_true:g}")
    tmin_med = np.median(z["tmin"][bi, gi])
    ax.axhline(tmin_med, color="k", ls=":", lw=1, label=f"median $t_{{min}}$≈{tmin_med:.0f}")
    ax.set_ylabel(r"$\hat\gamma$"); ax.legend()
    ax.set_title("Estimated γ̂ (β=3, γ/η=0.1, n=30): the offset removes the\nwild spread of the ∇=0 solution")
    lo = np.percentile(np.concatenate(data), 1); hi = max(tmin_med, g_true) + 20
    ax.set_ylim(min(lo, -60), hi)
    fig.tight_layout(); fig.savefig(FIG + "fig7_gamma_box.png"); plt.close(fig)


# ------------------------------------------------------------------ Fig 8: scale invariance
def fig_scale():
    fig, ax = plt.subplots(figsize=(7, 4.3))
    for eta, mk, c in [(50, "o", BLUE), (100, "s", ORNG), (200, "^", GRN)]:
        rng = np.random.default_rng(42)
        t = sample_weibull3(2.0, eta, 0.1 * eta, 30, rng)
        res = estimate_mdm(t, DELTAS)
        gh = np.array([res[float(d)]["gamma_hat"] for d in DELTAS]) / eta
        ax.plot(DELTAS, gh, mk + "-", color=c, ms=6, lw=1.4, label=f"η={eta}", alpha=0.85)
    ax.axhline(0.1, color="k", ls="--", lw=1, label="true γ/η = 0.1")
    ax.set_xlabel("gradient offset δ"); ax.set_ylabel(r"$\hat\gamma/\eta$")
    ax.set_title("Scale invariance: δ is dimensionless, so γ̂/η is identical across η\n"
                 "(curves coincide exactly for a matched random stream)")
    ax.legend()
    fig.tight_layout(); fig.savefig(FIG + "fig8_scale_invariance.png"); plt.close(fig)


# ------------------------------------------------------------------ Fig 9: strict root + flank
def fig_roots():
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11.5, 4.2))
    sr = df.groupby("delta")["strict_rate"].mean()
    axL.plot(sr.index, 100*sr.values, "-o", color=BLUE)
    axL.set_xlabel("gradient offset δ"); axL.set_ylabel("strict interior root exists (%)")
    axL.set_ylim(0, 105)
    axL.set_title("A strict ∇=δ root exists in most cases;\nelse a constrained solution is used")
    hf = df.groupby("beta")["has_flank_rate"].mean()
    axR.bar([f"{b:g}" for b in hf.index], 100*hf.values, color=ORNG)
    axR.set_xlabel("shape β"); axR.set_ylabel("samples with a rising right flank (%)")
    axR.set_ylim(0, 105)
    axR.set_title("For β<1 the bowl often sits at the boundary\n(no flank → constrained solution)")
    fig.tight_layout(); fig.savefig(FIG + "fig9_roots.png"); plt.close(fig)


# ------------------------------------------------------------------ Fig 10: bias/rmse vs delta (trade-off)
def fig_tradeoff():
    # beta=2, gr=0.1, n=30
    sub = df[(df.beta==2.0)&(df.gamma_over_eta==0.1)&(df.n==30)].sort_values("delta")
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.7), sharex=True)
    specs = [("gamma", "γ", 10.0), ("beta", "β", 2.0), ("eta", "η", 100.0)]
    for ax, (p, lab, tv) in zip(axes, specs):
        ax.plot(sub.delta, sub[f"{p}_bias"], "-o", color=BLUE, ms=4, label="bias")
        ax.plot(sub.delta, sub[f"{p}_rmse"], "-s", color=ORNG, ms=4, label="RMSE")
        ax.axhline(0, color="k", lw=0.6)
        ax.set_xlabel("δ"); ax.set_title(f"{lab}  (true={tv:g})")
        if p == "gamma":
            ax.set_ylabel("error"); ax.legend()
    fig.suptitle("Bias/RMSE trade-off vs δ  (β=2, γ/η=0.1, n=30): "
                 "small δ under-shoots γ, large δ over-shoots toward $t_{min}$", y=1.04)
    fig.tight_layout(); fig.savefig(FIG + "fig10_tradeoff.png"); plt.close(fig)


for fn in [fig_geometry, fig_ne_vs_delta_beta, fig_best_trends, fig_heatmap,
           fig_ladder, fig_offset_essential, fig_gamma_box, fig_scale,
           fig_roots, fig_tradeoff]:
    fn(); print("done", fn.__name__, flush=True)
print("ALL FIGURES DONE")
