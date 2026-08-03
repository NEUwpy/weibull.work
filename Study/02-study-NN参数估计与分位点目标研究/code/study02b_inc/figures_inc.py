"""Publication figures for the incremental B run.

Reads the analysis_summary.json produced by analyze_inc and renders the three
frozen-main figures:
  1. inc_1_I_by_n.png      — D-vs-P improvement I(n) across the dense n grid
                             with 95% CI and BH support markers.
  2. inc_2_I_by_beta.png   — I as a function of beta (marginal over rho) for a
                             subset of n, from the parameter grid.
  3. inc_3_region_mixing.png — I(beta, rho) surface for n=7 and n=10 (the
                             near-zero aggregate n) showing opposing regional
                             effects.

Usage:
    python -m study02b_inc.figures_inc --run-dir <dir> [--out <dir>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from study02b_inc import config as C


def _fig(out: Path, name: str):
    fig = plt.figure(figsize=(7, 4.5), dpi=160)
    ax = fig.add_subplot(111)
    return fig, ax


def fig_I_by_n(ax, summary) -> None:
    per_n = summary["core"]["per_n"]
    ns = [int(n) for n in C.N_VALUES]
    xs = np.arange(len(ns))
    i = np.array([per_n[str(n)]["I"] for n in ns])
    lo = np.array([per_n[str(n)]["ci_lo"] for n in ns])
    hi = np.array([per_n[str(n)]["ci_hi"] for n in ns])
    bh = [per_n[str(n)]["bh"] for n in ns]

    ax.errorbar(xs, i, yerr=[i - lo, hi - i], fmt="o-", color="#1f77b4",
                capsize=3, markersize=4, linewidth=1.2, zorder=3)
    ax.axhline(0, color="#888", linewidth=0.8, linestyle="--")
    base = float(np.nanmax(np.concatenate([i, hi])))
    ymax = base + 0.09
    for x, n, s in zip(xs, ns, bh):
        if s == "supported":
            ax.scatter([x], [ymax - 0.02], marker="*", color="#d62728", s=90, zorder=4)
    ax.set_xticks(xs)
    ax.set_xticklabels([str(n) for n in ns], rotation=45, fontsize=7)
    ax.set_xlabel("n")
    ax.set_ylabel("I = (RMSE_P - RMSE_D) / RMSE_P")
    ax.set_title("D-vs-P relative RMSE improvement vs sample size n\n"
                 "(error bars: 95% hierarchical paired-seed bootstrap)")
    ax.grid(alpha=0.3)
    ax.set_ylim(min(float(np.nanmin(np.concatenate([lo, [0.0]]))) - 0.05, 0) - 0.05, ymax)
    ax.annotate("★ = BH-supported", xy=(0.98, 0.97), xycoords="axes fraction",
                ha="right", va="top", fontsize=8)


def fig_I_by_beta(ax, summary) -> None:
    marg = summary["grid"]["n_marginal_beta"]
    for n in ["5", "7", "10", "15"]:
        m = marg.get(n, {})
        if not m:
            continue
        xs = sorted(float(k) for k in m)
        ys = [m[str(k)] if str(k) in m else np.nan for k in xs]
        ax.plot(xs, ys, marker="o", markersize=3, linewidth=1.2,
                label=f"n={n}")
    ax.axhline(0, color="#888", linewidth=0.8, linestyle="--")
    ax.axvspan(C.P_BETA_RANGE[0], C.P_BETA_RANGE[1], color="#2ca02c", alpha=0.08,
               label="training support")
    ax.set_xlabel(r"$\beta$")
    ax.set_ylabel("I (marginal over ρ)")
    ax.set_title("D-vs-P improvement vs β by sample size n\n"
                 "(green band = training support [1.2, 4])")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)


def fig_region_mixing(ax, summary, n_val: int) -> None:
    per_cell = summary["grid"]["per_cell"]
    cells = [v for v in per_cell.values() if int(v["n"]) == n_val and abs(v["eta"] - C.PG_ETA) < 1e-9]
    betas = sorted({v["beta"] for v in cells})
    rhos = sorted({v["rho"] for v in cells})
    Z = np.full((len(betas), len(rhos)), np.nan)
    for v in cells:
        bi = betas.index(v["beta"]); ri = rhos.index(v["rho"])
        Z[bi, ri] = v["I"]
    mesh = ax.pcolormesh(betas, rhos, Z.T, cmap="RdBu_r", vmin=-0.6, vmax=0.6,
                         shading="auto")
    ax.set_xlabel(r"$\beta$"); ax.set_ylabel(r"$\rho=\gamma/\eta$")
    ax.set_title(f"I(β, ρ) at n={n_val}  (opposing regional effects)")
    fig = ax.figure
    cb = fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("I")
    ax.set_xticks(betas[::2]); ax.tick_params(labelsize=7)


def run_figures(run_dir: Path, out: Path | None = None) -> list[Path]:
    run_dir = Path(run_dir)
    out = out or (run_dir / "figures")
    out.mkdir(parents=True, exist_ok=True)
    summary = json.loads((run_dir / "analysis" / "analysis_summary.json").read_text(encoding="utf-8"))

    written = []
    fig, ax = _fig(out, "inc_1")
    fig_I_by_n(ax, summary)
    fig.tight_layout(); p = out / "inc_1_I_by_n.png"; fig.savefig(p); plt.close(fig)
    written.append(p)

    fig, ax = _fig(out, "inc_2")
    fig_I_by_beta(ax, summary)
    fig.tight_layout(); p = out / "inc_2_I_by_beta.png"; fig.savefig(p); plt.close(fig)
    written.append(p)

    for n_val in (7, 10):
        fig, ax = _fig(out, f"inc_3")
        fig_region_mixing(ax, summary, n_val)
        fig.tight_layout(); p = out / f"inc_3_region_mixing_n{n_val}.png"; fig.savefig(p)
        plt.close(fig); written.append(p)

    print("Figures written:", [str(p) for p in written])
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    run_figures(Path(args.run_dir), Path(args.out) if args.out else None)


if __name__ == "__main__":
    main()
