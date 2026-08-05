"""
explore_shape.py
Diagnostic plots of the profiled curve sigma_min(gamma), the profiled
beta*(gamma), and the slope d sigma_min/d gamma, for several (beta, gamma/eta)
settings and sample sizes. Used to understand the actual geometry before
finalising the delta estimator.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mdm_core import sample_weibull3, sigma_min_curve, make_gamma_grid, weibull_x

rng = np.random.default_rng(7)

ETA = 100.0
settings = [
    dict(beta=0.8, gr=0.1, n=20),
    dict(beta=1.2, gr=0.1, n=20),
    dict(beta=2.0, gr=0.1, n=20),
    dict(beta=3.0, gr=0.1, n=20),
    dict(beta=2.0, gr=0.0, n=20),
    dict(beta=2.0, gr=0.5, n=20),
    dict(beta=2.0, gr=0.1, n=10),
    dict(beta=2.0, gr=0.1, n=50),
]

beta_grid = np.exp(np.linspace(np.log(0.1), np.log(30.0), 80))

fig, axes = plt.subplots(len(settings), 3, figsize=(13, 3.0 * len(settings)))

for row, st in enumerate(settings):
    beta, gr, n = st["beta"], st["gr"], st["n"]
    gamma_true = gr * ETA
    t = sample_weibull3(beta, ETA, gamma_true, n, rng)
    t_min = t[0]

    gg = make_gamma_grid(t, n_points=300, span_mult=4.0)
    sig, bstar, ehat = sigma_min_curve(t, gg, beta_grid)
    ok = np.isfinite(sig)
    gg, sig, bstar = gg[ok], sig[ok], bstar[ok]
    grad = np.gradient(sig, gg)

    ax = axes[row, 0]
    ax.plot(gg, sig, lw=1.3)
    ax.axvline(gamma_true, color="g", ls="--", lw=1, label=f"true γ={gamma_true:g}")
    ax.axvline(t_min, color="r", ls=":", lw=1, label=f"t_min={t_min:.1f}")
    imin = np.argmin(sig)
    ax.plot(gg[imin], sig[imin], "ko", ms=4, label="argmin")
    ax.set_title(f"σ_min(γ)  β={beta} γ/η={gr} n={n}")
    ax.legend(fontsize=6)

    ax = axes[row, 1]
    ax.plot(gg, bstar, lw=1.3, color="purple")
    ax.axvline(gamma_true, color="g", ls="--", lw=1)
    ax.axvline(t_min, color="r", ls=":", lw=1)
    ax.axhline(beta, color="g", ls="-", lw=0.7, alpha=0.5)
    ax.set_title(f"β*(γ)  (true β={beta})")

    ax = axes[row, 2]
    ax.plot(gg, grad, lw=1.3, color="darkorange")
    ax.axhline(0, color="k", lw=0.6)
    for d in [0.05, 0.1, 0.2]:
        ax.axhline(-d, color="gray", ls=":", lw=0.7)
    ax.axvline(gamma_true, color="g", ls="--", lw=1)
    ax.axvline(t_min, color="r", ls=":", lw=1)
    ax.set_title("slope dσ_min/dγ")
    ax.set_ylim(np.percentile(grad, 2), np.percentile(grad, 98))

plt.tight_layout()
plt.savefig("../figures/_explore_shape.png", dpi=110)
print("saved ../figures/_explore_shape.png")

# Print numeric summary of slope near t_min and near true gamma
print("\nrow  beta  gr   n   t_min   gamma_true  argmin_g  slope@true  slope@(t_min-1%span)")
for row, st in enumerate(settings):
    beta, gr, n = st["beta"], st["gr"], st["n"]
    gamma_true = gr * ETA
    rng2 = np.random.default_rng(100 + row)
    t = sample_weibull3(beta, ETA, gamma_true, n, rng2)
    t_min = t[0]
    span = t[-1] - t[0]
    gg = make_gamma_grid(t, n_points=400, span_mult=4.0)
    sig, bstar, ehat = sigma_min_curve(t, gg, beta_grid)
    ok = np.isfinite(sig)
    gg, sig = gg[ok], sig[ok]
    grad = np.gradient(sig, gg)
    imin = np.argmin(sig)
    s_true = np.interp(gamma_true, gg, grad)
    s_near = np.interp(t_min - 0.01 * span, gg, grad)
    print(f"{row:3d}  {beta:4.1f}  {gr:3.2f}  {n:3d}  {t_min:6.1f}  {gamma_true:8.1f}  "
          f"{gg[imin]:8.1f}  {s_true:+9.4f}  {s_near:+9.4f}")
