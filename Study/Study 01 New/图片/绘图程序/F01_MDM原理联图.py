"""F01: MDM estimation steps and repeated-sample location variability.
Recomputed from saved observations; a method illustration, not a performance trial.
Run from any directory. Dependencies: numpy, scipy, matplotlib.
"""
from __future__ import annotations
import csv
import hashlib
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import scipy
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
sys.path.insert(0, str(REPO / "python"))
from methods.mdm import MDM

STEM = "F01_MDM原理联图"
SOURCE = REPO / "public/case-studies/mdm/verification-182-046/data.csv"
SAMPLE_ID = "Sample-1-3"
ORDER = np.arange(1, 8)
RANKS = (ORDER - 0.3) / 7.4
LOG_RANKS = -np.log1p(-RANKS)
TRACE_STEPS = 1800
ENSEMBLE_STEPS = 600
GAMMA_VIEW = (700., 1250.)
BLUE, GRAY, PALE, INK = "#0072B2", "#777777", "#B6B6B6", "#333333"
COLORS = {"0": GRAY, "0.1": BLUE, "trial": PALE}
MARKERS = {"0": "o", "0.1": "s", "trial": "^"}

def pseudo(sample, beta, gamma):
    return (sample - gamma) / LOG_RANKS ** (1.0 / beta)

def sigma(sample, beta, gamma):
    return float(np.std(pseudo(sample, beta, gamma), ddof=1))

def calculate():
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        source_rows = {r["id"]: r for r in csv.DictReader(stream)}
    sample = np.sort([float(source_rows[SAMPLE_ID][f"v{i}"]) for i in ORDER])
    roots, points, rows = {}, {}, []

    def record(panel, kind, x, y, beta="", gamma="", delta=""):
        rows.append((panel, SAMPLE_ID, kind, x, y, beta, gamma, delta))

    for i, value in zip(ORDER, sample):
        record("input", "sorted_observation", int(i), value)
    for delta in ("0", "0.1"):
        model = MDM(sample.tolist())
        result = model.run(offset=float(delta), trace=True,
                           gamma_steps=TRACE_STEPS if delta == "0" else 60)
        assert result[-1]
        root = dict(zip(("beta", "eta", "gamma"), map(float, result[:3])))
        roots[delta] = root
        for p in model.trace_data["grad_gamma_curve"]:
            if not p.get("virtual", False) and (delta == "0" or p["source"] == "solver_root"):
                points[p["gamma"]] = p
        p = points[root["gamma"]]
        assert abs(p["gradient"] - float(delta)) < 1e-6
        values = pseudo(sample, root["beta"], root["gamma"])
        np.testing.assert_allclose(values.mean(), root["eta"], atol=1e-8)
        for i, value in zip(ORDER, values):
            record("a", "pseudo_scale", int(i), value, root["beta"], root["gamma"], delta)
        record("a", "mean", 4., values.mean(), root["beta"], root["gamma"], delta)
        record("c", "intersection", root["gamma"], p["gradient"],
               root["beta"], root["gamma"], delta)
    # Explicit conditional slices include BOTH positions selected in panel c.
    betas = np.linspace(1.5, 4, 701)
    slices = {}
    for key in ("trial", "0", "0.1"):
        gamma = 800. if key == "trial" else roots[key]["gamma"]
        fit = minimize_scalar(lambda b: sigma(sample, b, gamma),
                              bounds=(0.1, 15), method="bounded")
        yy = np.array([sigma(sample, b, gamma) for b in betas])
        slices[key] = {"gamma": gamma, "beta": float(fit.x),
                       "sigma": float(fit.fun), "curve": yy}
        if key != "trial":
            np.testing.assert_allclose(fit.x, roots[key]["beta"], atol=1e-8)
        for b, value in zip(betas, yy):
            record("b", "conditional_curve", b, value, b, gamma, "" if key == "trial" else key)
        record("b", "minimum", fit.x, fit.fun, fit.x, gamma, "" if key == "trial" else key)
        record("support", "slice_minimum", gamma, fit.fun, fit.x, gamma, "" if key == "trial" else key)
    points = sorted(points.values(), key=lambda p: p["gamma"])
    for p in points:
        assert 0 <= p["gamma"] < sample.min()
        assert np.isfinite(p["gradient"])
        np.testing.assert_allclose(sigma(sample, p["best_beta"], p["gamma"]),
                                   p["sigma_min"], atol=1e-8)
        record("support", "profile", p["gamma"], p["sigma_min"], p["best_beta"], p["gamma"])
        record("c", "gradient", p["gamma"], p["gradient"], p["best_beta"], p["gamma"])
    curves = {field: np.array([p[field] for p in points])
              for field in ("gamma", "sigma_min", "gradient")}
    ensemble = {}
    for sample_id, source in source_rows.items():
        obs = np.sort([float(source[f"v{i}"]) for i in ORDER])
        item = {"sample": obs.tolist(), "estimates": {}}
        trace_points = {}
        for delta in ("0", "0.1"):
            model = MDM(obs.tolist())
            result = model.run(offset=float(delta), trace=True,
                               gamma_steps=ENSEMBLE_STEPS if delta == "0" else 60)
            assert result[-1]
            info = model.last_solution_info
            assert info["root_solver"] != "right_edge_fit", (sample_id, delta)
            item["estimates"][delta] = dict(zip(("beta", "eta", "gamma"), map(float, result[:3])))
            item["estimates"][delta]["boundary"] = info["solution_strategy"] == "truncated_at_zero"
            for p in model.trace_data["grad_gamma_curve"]:
                if not p.get("virtual", False) and (delta == "0" or p["source"] == "solver_root"):
                    trace_points[p["gamma"]] = p
            if not item["estimates"][delta]["boundary"]:
                assert abs(trace_points[result[2]]["gradient"] - float(delta)) < 1e-6
            rows.append(("d" if delta == "0" else "e", sample_id, "ensemble_estimate", result[2], float(delta),
                         result[0], result[2], delta))
        ordered = sorted(trace_points.values(), key=lambda p: p["gamma"])
        item["gamma"] = np.array([p["gamma"] for p in ordered])
        item["gradient"] = np.array([p["gradient"] for p in ordered])
        assert np.isfinite(item["gradient"]).all()
        for p in ordered:
            rows.append(("de", sample_id, "ensemble_gradient", p["gamma"], p["gradient"],
                         p["best_beta"], p["gamma"], ""))
        for i, value in zip(ORDER, obs):
            rows.append(("input_ensemble", sample_id, "sorted_observation", int(i), value, "", "", ""))
        ensemble[sample_id] = item
    summary = {}
    for delta in ("0", "0.1"):
        estimates = np.array([v["estimates"][delta]["gamma"] for v in ensemble.values()])
        summary[delta] = {"count": len(estimates), "mean": float(estimates.mean()),
                          "sd": float(estimates.std(ddof=1)), "min": float(estimates.min()),
                          "max": float(estimates.max()), "rmse": float(np.sqrt(np.mean((estimates-1000)**2))),
                          "boundary_count": sum(v["estimates"][delta]["boundary"] for v in ensemble.values())}
    # Map source records to the four displayed panels; retain intermediates as support.
    remapped = []
    for panel, series, kind, x, y, beta, gamma, delta in rows:
        if panel == "a":
            panel = "support"
        elif panel == "b":
            panel = "a" if delta == "0" else "support"
        elif panel == "c":
            panel = "b" if kind == "gradient" or delta == "0" else "support"
        elif panel in ("d", "e", "de"):
            panel = {"d": "c", "e": "d", "de": "cd"}[panel]
        panel = {"a": "b", "b": "a"}.get(panel, panel)
        remapped.append((panel, series, kind, x, y, beta, gamma, delta))
    return sample, betas, slices, curves, roots, ensemble, summary, remapped

def style():
    available = {f.name for f in font_manager.fontManager.ttflist}
    font = next((n for n in ("Microsoft YaHei", "Noto Sans CJK SC", "SimHei") if n in available), None)
    if font is None:
        raise RuntimeError("A Chinese font is required.")
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": [font, "DejaVu Sans"],
        "font.size": 8, "axes.labelsize": 8.3, "xtick.labelsize": 7.3, "ytick.labelsize": 7.3,
        "legend.fontsize": 7, "legend.frameon": False,
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.7,
        "xtick.major.width": 0.65, "ytick.major.width": 0.65, "lines.linewidth": 1.4,
        "mathtext.fontset": "dejavusans", "svg.fonttype": "none", "pdf.fonttype": 42,
        "axes.unicode_minus": False, "savefig.facecolor": "white",
    })
    return font

def draw(values):
    """Export independent scientific panels; draw.io owns the composition."""
    _, betas, slices, curves, roots, ensemble, summary, _ = values
    out = REPO / "tmp" / "f01-data-check"
    out.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 11, "axes.labelsize": 11, "xtick.labelsize": 10,
                         "ytick.labelsize": 10, "svg.fonttype": "path"})
    def save(fig, name):
        for suffix in ("png", "svg", "pdf"):
            fig.savefig(out / f"{name}.{suffix}", dpi=400, facecolor="white")
        plt.close(fig)
    r, s = roots["0"], slices["0"]
    fig = plt.figure(figsize=(4.3, 3.4))
    ax = fig.add_axes([.19, .25, .77, .70])
    view = (curves["gamma"] >= GAMMA_VIEW[0]) & (curves["gamma"] <= GAMMA_VIEW[1])
    ymin = float(curves["gradient"][view].min() - .07)
    ymax = float(curves["gradient"][view].max() + .045)
    ax.plot(curves["gamma"], curves["gradient"], color=INK)
    ax.set(xlabel=r"位置参数 $\gamma_j$", ylabel=r"梯度 $\nabla(\gamma_j)$",
           xlim=GAMMA_VIEW, ylim=(ymin, ymax), xticks=[800, 1000, 1200])
    ax.axhline(0, color=GRAY, ls="--", lw=1)
    ax.scatter(r["gamma"], 0, s=45, facecolor="white", edgecolor=INK, zorder=5)
    ax.vlines(r["gamma"], ymin, 0, color=INK, ls=":", lw=1)
    ax.annotate(rf'$\hat{{\gamma}}={r["gamma"]:.1f}$',
                xy=(r["gamma"], 0), xytext=(735, ymax*.48),
                fontsize=12, arrowprops=dict(arrowstyle="->", color=INK, lw=.9))
    save(fig, "F01a_位置求解")

    fig = plt.figure(figsize=(4.3, 3.4))
    ax = fig.add_axes([.19, .25, .77, .70])
    ax.plot(betas, s["curve"], color=INK)
    ax.scatter(s["beta"], s["sigma"], s=45, facecolor="white", edgecolor=INK, zorder=5)
    ax.vlines(s["beta"], 0, s["sigma"], color=INK, ls=":", lw=1)
    ymax = float(s["curve"].max()) * 1.13
    ax.set(xlabel=r"形状参数 $\beta_k$", ylabel=r"标准差 $\sigma_\eta(\hat{\gamma},\beta_k)$",
           xlim=(1.5, 4), ylim=(0, ymax), xticks=[1.5, 2.5, 3.5])
    ax.text(.96, .94, rf'$\gamma_j=\hat{{\gamma}}={r["gamma"]:.1f}$',
            transform=ax.transAxes, fontsize=10, ha="right", va="top")
    ax.annotate(rf'$\hat{{\beta}}={s["beta"]:.3f}$', xy=(s["beta"], s["sigma"]),
                xytext=(2.7, ymax*.44), fontsize=12,
                arrowprops=dict(arrowstyle="->", color=INK, lw=.9))
    save(fig, "F01b_形状回代")

    for delta, name in (("0", "F01c_零偏移多样本"), ("0.1", "F01d_正偏移多样本")):
        fig = plt.figure(figsize=(5.8, 4.5))
        ax = fig.add_axes([.14, .36, .82, .59])
        strip = fig.add_axes([.14, .15, .82, .11], sharex=ax)
        ax.set(ylabel=r"梯度 $\nabla(\gamma_j)$", xlim=(-45, 1800), ylim=(-.035, .34),
               yticks=[0, .1, .2, .3])
        ax.tick_params(axis="x", labelbottom=False)
        for item in ensemble.values():
            ax.plot(item["gamma"], item["gradient"], color="#888888", lw=.75, alpha=.65)
            e = item["estimates"][delta]
            if not e["boundary"]:
                ax.scatter(e["gamma"], float(delta), s=20, marker=MARKERS[delta],
                           facecolor="white" if delta == "0" else BLUE,
                           edgecolor=COLORS[delta], lw=.7, zorder=4)
        ax.axhline(float(delta), color=COLORS[delta], ls="--", lw=1.3, zorder=3)
        ax.text(35, float(delta)+.012, rf"$\delta={delta}$", color=COLORS[delta],
                bbox=dict(facecolor="white", edgecolor="none", pad=.2))
        if summary[delta]["boundary_count"]:
            ax.text(.035, .90, "10组位置估计落在下界0", transform=ax.transAxes,
                    fontsize=10, va="top")
        placed = []
        levels = [0.] + [sign*level*.07 for level in range(1,16) for sign in (1,-1)]
        for sample_id in sorted(ensemble, key=lambda k: ensemble[k]["estimates"][delta]["gamma"]):
            e = ensemble[sample_id]["estimates"][delta]
            y = next(level for level in levels
                     if all(abs(e["gamma"]-x0)>=32 or abs(level-y0)>=.065 for x0,y0 in placed))
            placed.append((e["gamma"],y))
            strip.scatter(e["gamma"],y,s=21,marker=MARKERS[delta],
                          facecolor="white" if delta=="0" else BLUE,edgecolor=COLORS[delta],lw=.8)
        strip.axvline(1000,color="#999999",ls=":",lw=.9)
        strip.set(xlim=(-45,1800),ylim=(-.43,.43),yticks=[],xticks=[0,500,1000,1500],
                  xlabel=r"位置参数估计 $\hat{\gamma}_\delta$")
        strip.spines["left"].set_visible(False)
        fig.text(.14,.295,f'30个位置估计；样本标准差 = {summary[delta]["sd"]:.1f}',
                 fontsize=11,color=COLORS[delta])
        save(fig,name)

def main():
    font = style()
    values = calculate()
    data = ROOT / "数据"
    data.mkdir(exist_ok=True)
    csv_path = data / f"{STEM}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["panel", "series", "kind", "x", "y", "beta", "gamma", "delta"])
        writer.writerows(values[-1])
    draw(values)
    metadata = {
        "figure": "F01", "revision": 12,
        "sources_doi": ["10.1142/S0219455423500852", "10.12068/j.issn.1005-3026.2025.20240194"],
        "source_relation": "Recomputed from MDM principles and 2025 Figures 1/3/4/5. Panels a-b: one saved example using delta=0 only; c/d: the same full set of 30 saved random samples, no selection by outcome and no ideal samples.",
        "sample_source": SOURCE.relative_to(REPO).as_posix(), "sample_id": SAMPLE_ID,
        "selection": "Retains previous random sample A. A complete estimation example, not performance evidence or an exact reproduction of the original paper observations.",
        "true_parameters": {"beta": 2, "eta": 1000, "gamma": 1000}, "n": 7,
        "samples_sorted": values[0].tolist(),
        "rank_formula": "(i-0.3)/(n+0.4), manuscript Eq. (3); not 2025 exact median ranks",
        "ranks": RANKS.tolist(), "std_ddof": 1,
        "solver": "python/methods/mdm.py:MDM.run", "rank_method": "bernard", "trace_steps": TRACE_STEPS,
        "beta_search_bounds": [0.1, 15], "beta_plot_range": [1.5, 4], "gamma_plot_range": list(GAMMA_VIEW),
        "gradient": "Unmodified production finite differences. Full traces in CSV; displayed neighborhood includes both selected roots and the gamma=800 conditional slice.",
        "estimates": values[4], "composition_source": "F01_MDM原理联图.drawio", "font": font,
        "ensemble": {"sample_ids": list(values[5]), "trace_steps": ENSEMBLE_STEPS,
                     "selection": "All rows of source CSV, in original order; no new simulation.",
                     "estimates": {k: v["estimates"] for k, v in values[5].items()},
                     "location_summary": values[6], "std_ddof": 1,
                     "gamma_plot_range": [-45, 1800], "gradient_plot_range": [-.035, .34],
                     "display": "Peaks outside gradient view clipped; full traces in CSV. All estimates shown below each rule panel on identical axes, including boundary estimates. Boundary estimates are not plotted as intersections. Deterministic vertical stacking separates nearby dots without changing x coordinates."},
        "diagram": {"type": "integrated process diagram", "flow": ["ordered sample and ranks", "conditional beta minimization at each trial gamma and profile gradient", "a: gamma solution with embedded gradient curve", "b: beta solution with embedded conditional curve", "mean pseudo-scale eta", "parameter tuple"], "layout": "Curves are inside consecutive process nodes; solid arrows connect nodes. No external curve callouts.", "expansion": "Same truth, different samples, repeat estimator; c/d compare delta=0/0.1."},
        "panel_linkage": "Panel a selects gamma, passed directly to panel b for beta minimization, followed by eta and output nodes. c/d compare 30 paired estimates.",
        "versions": {"numpy": np.__version__, "scipy": scipy.__version__, "matplotlib": matplotlib.__version__},
        "checks": {"profile_matches_equation": True, "root_residual_below_1e_6": True,
                   "conditional_beta_matches_estimate": True, "pseudo_scale_mean_matches_eta": True,
                   "all_gradients_finite": True, "standalone_panels": 4},
        "sha256": {"sample_source": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                   "script": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "solver": hashlib.sha256((REPO / "python/methods/mdm.py").read_bytes()).hexdigest(),
                   "data": hashlib.sha256(csv_path.read_bytes()).hexdigest()},
    }
    (data / f"{STEM}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"figure": STEM, "rows": len(values[-1]), "location_summary": values[6]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
