"""verify_estimator.py — overlay anchor and gamma_hat(delta) on the curve."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mdm_core import (sample_weibull3, estimate_mdm, make_gamma_grid,
                      sigma_min_curve, weibull_x, _moving_average)

ETA = 100.0
deltas = [0.0, 0.03, 0.05, 0.1, 0.2, 0.5]
cases = [
    dict(beta=0.8, gr=0.1, n=20, seed=11),
    dict(beta=1.2, gr=0.1, n=20, seed=12),
    dict(beta=2.0, gr=0.1, n=20, seed=0),
    dict(beta=2.0, gr=0.1, n=20, seed=13),
    dict(beta=3.0, gr=0.1, n=20, seed=14),
    dict(beta=2.0, gr=0.5, n=30, seed=15),
]

fig, axes = plt.subplots(len(cases), 2, figsize=(12, 3.0 * len(cases)))
for r, c in enumerate(cases):
    beta, gr, n, seed = c["beta"], c["gr"], c["n"], c["seed"]
    g_true = gr * ETA
    rng = np.random.default_rng(seed)
    t = sample_weibull3(beta, ETA, g_true, n, rng)
    res = estimate_mdm(t, deltas)
    g = res["gamma_grid"]; s = res["sigma_min"]; grad = res["grad"]
    s_sm = _moving_average(s, 7)

    ax = axes[r, 0]
    ax.plot(g, s, lw=1, alpha=0.5, label="σ_min")
    ax.plot(g, s_sm, lw=1.3, color="C0", label="σ_min (smooth)")
    ax.axvline(t[0], color="r", ls=":", lw=1, label=f"t_min={t[0]:.1f}")
    ax.axvline(g_true, color="g", ls="--", lw=1, label=f"true γ={g_true:g}")
    ax.axvline(res["gamma0"], color="k", lw=1, label=f"anchor δ=0")
    cols = plt.cm.viridis(np.linspace(0, 0.9, len(deltas)))
    for d, col in zip(deltas, cols):
        gh = res[d]["gamma_hat"]
        ax.axvline(gh, color=col, lw=0.9, ls="-")
    # zoom to region of interest
    lo = min(g_true, res["gamma0"]) - 1.5 * (t[0] - min(g_true, res["gamma0"]) + 1)
    ax.set_xlim(max(g.min(), lo), t[0] + 0.15 * (t[0] - lo + 1))
    ax.set_title(f"β={beta} γ/η={gr} n={n} seed={seed}")
    ax.legend(fontsize=6, loc="upper left")

    ax = axes[r, 1]
    ax.plot(g, grad, lw=1.2, color="darkorange", label="slope")
    ax.axhline(0, color="k", lw=0.6)
    for d in deltas:
        ax.axhline(d, color="gray", ls=":", lw=0.6)
        gh = res[d]["gamma_hat"]
        ax.plot(gh, np.interp(gh, g, grad), "o", ms=4)
    ax.axvline(res["gamma0"], color="k", lw=1)
    ax.set_xlim(axes[r, 0].get_xlim())
    yv = grad[(g >= axes[r, 0].get_xlim()[0]) & (g <= axes[r, 0].get_xlim()[1])]
    if yv.size:
        ax.set_ylim(min(-0.2, yv.min()), max(0.6, np.percentile(yv, 97)))
    ax.set_title("slope; markers = γ̂(δ)")

    print(f"β={beta} gr={gr} n={n} seed={seed} t_min={t[0]:.2f} true={g_true:g} "
          f"anchor={res['gamma0']:.2f}")
    for d in deltas:
        rr = res[d]
        print(f"   δ={d:4.2f} γ̂={rr['gamma_hat']:9.2f} β̂={rr['beta_hat']:6.2f} "
              f"η̂={rr['eta_hat']:7.1f} strict={rr['strict_root']}")

plt.tight_layout()
plt.savefig("../figures/_verify_estimator.png", dpi=110)
print("saved ../figures/_verify_estimator.png")
