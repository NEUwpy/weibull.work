"""Extend the original MDM Fig. 5 using current samples and held-out AMDM choices.

Run with --refresh-data to regenerate traces; otherwise plot the saved CSVs.
The first 30 repetitions are selected by ID, never by prediction performance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

FIGURES = Path(__file__).resolve().parents[1]
STUDY = FIGURES.parents[1]
REPO = STUDY.parents[1]
DATA = FIGURES / "data" / "derived"
STEM = "F03_fixed_vs_adaptive_v01"
SOURCE = STUDY / "artifacts/formal/E5_normalized_raw"
PREDICTIONS = SOURCE / "specialist/raw_specialist_results.csv"
META = SOURCE / "shared_data/chunks/chunk_0036_meta.json"
SCAN = META.with_name("chunk_0036_mdm.csv")
CURVES = DATA / f"{STEM}_curves.csv"
POINTS = DATA / f"{STEM}_points.csv"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract():
    sys.path.insert(0, str(REPO / "python"))
    from methods.mdm import MDM
    from studies.common.sample import generate_sample

    meta = json.loads(META.read_text(encoding="utf-8"))
    assert meta["unit"] == dict(beta=2., eta=1000., gamma=1000., gamma_over_eta=1., n=7)
    raw = pd.read_csv(PREDICTIONS)
    selected = raw[(raw.beta == 2) & (raw.eta == 1000) & (raw.gamma == 1000)
                   & (raw.n == 7) & (raw.seed == 42) & (raw.repeat_id < 30)]
    assert len(selected) == 30 and set(selected.repeat_id) == set(range(30))
    assert selected.is_valid.all()
    scan = pd.read_csv(SCAN)
    curves, points, sample_rows = [], [], []
    for row in selected.sort_values("repeat_id").itertuples():
        rid = int(row.repeat_id)
        sample = generate_sample(2., 1000., 1000., 7, rid, seed=meta["seed_namespace"])
        sample_rows.extend(dict(repeat_id=rid, order=i, lifetime=float(v))
                           for i, v in enumerate(sample, 1))
        for method, delta in (("fixed", .1), ("adaptive", float(row.selected_delta))):
            model = MDM(sample)
            beta, eta, gamma, _, ok = model.run(trace=True, offset=delta, gamma_steps=160)
            assert ok
            trace = model.trace_data
            frozen = scan[(scan.repeat_id == rid) & np.isclose(scan.delta, delta)]
            assert len(frozen) == 1
            saved = frozen.iloc[0]
            np.testing.assert_allclose([beta, eta, gamma],
                                       saved[["beta_hat", "eta_hat", "gamma_hat"]].to_numpy(float),
                                       rtol=1e-5, atol=1e-3)
            loss = ((beta - 2) / 2) ** 2 + ((eta - 1000) / 1000) ** 2 + ((gamma - 1000) / 1000) ** 2
            if method == "adaptive":
                np.testing.assert_allclose(loss, row.true_loss, rtol=1e-5, atol=1e-6)
            root = next(p for p in trace["grad_gamma_curve"] if p["source"] == "solver_root")
            # A fitted virtual endpoint must not be displayed as an observed curve point.
            assert not root.get("virtual", False), "An extrapolated root needs separate plotting treatment"
            boundary = trace["solution_strategy"] == "truncated_at_zero"
            if not boundary:
                np.testing.assert_allclose(root["gradient"], delta, atol=1e-5)
            points.append(dict(repeat_id=rid, method=method, delta=delta,
                               gamma_hat=gamma, gradient=root["gradient"], boundary=boundary,
                               beta_hat=beta, eta_hat=eta, loss=loss,
                               fold=int(row.fold), model_seed=int(row.seed), model=row.model))
            for p in trace["grad_gamma_curve"]:
                if not p.get("virtual", False) and np.isfinite([p["gamma"], p["gradient"]]).all():
                    curves.append(dict(repeat_id=rid, gamma=p["gamma"], gradient=p["gradient"]))
        print(f"sample {rid + 1}/30 verified", flush=True)
    DATA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(curves).drop_duplicates(["repeat_id", "gamma"]).sort_values(
        ["repeat_id", "gamma"]).to_csv(CURVES, index=False)
    pd.DataFrame(points).to_csv(POINTS, index=False)
    samples_path = DATA / f"{STEM}_samples.csv"
    pd.DataFrame(sample_rows).to_csv(samples_path, index=False)
    provenance = {
        "purpose": "Illustrate fixed versus sample-adaptive selection, not prove per-sample optimality",
        "conceptual_source": "Xie et al. 2025, doi:10.12068/j.issn.1005-3026.2025.20240194, Fig. 5",
        "design": meta["unit"], "repeat_ids": list(range(30)),
        "selection_rule": "First 30 repeat IDs, independent of outcomes; not the original paper's exact samples",
        "seed_namespace": meta["seed_namespace"], "model_seed": 42,
        "prediction_identity": "E5 Normalized-RAW / Mean-Normalized-MLP, held-out predictions",
        "boundary_rule": "Triangle at actual gradient(0); never force a boundary solution onto delta",
        "checks": "60 reproduced estimates match frozen scan; 30 adaptive losses match saved predictions",
        "inputs": [{"path": str(p.relative_to(REPO)).replace("\\", "/"), "sha256": digest(p)}
                   for p in (PREDICTIONS, META, SCAN, REPO / "python/methods/mdm.py",
                             REPO / "python/studies/common/sample.py")],
        "derived": [{"file": p.name, "sha256": digest(p)} for p in (CURVES, POINTS, samples_path)],
    }
    (DATA / f"{STEM}_provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plot():
    curves, points = pd.read_csv(CURVES), pd.read_csv(POINTS)
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Microsoft YaHei", "DejaVu Sans"],
                         "font.size": 8, "axes.labelsize": 9, "axes.titlesize": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.unicode_minus": False, "svg.fonttype": "none", "pdf.fonttype": 42,
                         "axes.linewidth": .7, "xtick.major.width": .7, "ytick.major.width": .7})
    red, blue = "#BC493F", "#2266A6"
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.55), sharex=True, sharey=True)
    fig.subplots_adjust(left=.10, right=.98, top=.76, bottom=.23, wspace=.14)
    xmax = np.ceil(points.gamma_hat.max() / 200) * 200 + 100
    for ax, method, color, letter, title in zip(
            axes, ("fixed", "adaptive"), (red, blue), ("a", "b"),
            ("固定偏移 MDM", "样本自适应 AMDM")):
        for _, curve in curves.groupby("repeat_id"):
            ax.plot(curve.gamma, curve.gradient, color="#565C63", alpha=.40, lw=.65, zorder=1)
        sub = points[points.method == method]
        if method == "fixed":
            ax.axhline(.1, color=color, lw=1.25, ls=(0, (5, 2)), zorder=2)
            ax.text(.045, .88, r"$\delta_0=0.10$", transform=ax.transAxes, color=color, fontsize=10)
        else:
            # Short horizontal ticks expose the chosen height without 30 full-width guide lines.
            for p in sub.itertuples():
                ax.hlines(p.delta, max(0, p.gamma_hat - 75), p.gamma_hat + 75,
                          color=color, alpha=.65, lw=.85, zorder=2)
            ax.text(.045, .88, r"$\hat\delta(X_i)$", transform=ax.transAxes, color=color, fontsize=10)
        interior = sub[~sub.boundary]
        ax.scatter(interior.gamma_hat, interior.gradient, s=20, marker="s" if method == "fixed" else "o",
                   facecolor="white" if method == "fixed" else color, edgecolor=color, lw=.9, zorder=4)
        boundary = sub[sub.boundary]
        if len(boundary):
            ax.scatter(boundary.gamma_hat, boundary.gradient, s=30, marker="^",
                       facecolor=color, edgecolor="white", lw=.5, zorder=5, clip_on=False)
        ax.set_xlim(-40, xmax)
        ax.set_ylim(-.045, .60)
        ax.set_xticks(np.arange(0, xmax, 500))
        ax.set_yticks(np.arange(0, .61, .1))
        ax.set_xlabel(r"位置参数 $\gamma$")
        ax.text(0, 1.10, letter, transform=ax.transAxes, fontsize=13, fontweight="bold")
        ax.text(.08, 1.10, title, transform=ax.transAxes, fontsize=10)
        marker = Line2D([], [], color=color, marker="s" if method == "fixed" else "o", ls="none",
                        markerfacecolor="white" if method == "fixed" else color, markersize=4)
        ax.legend([marker], ["固定规则选点" if method == "fixed" else "折外预测选点"],
                  loc="upper left", bbox_to_anchor=(.015, .84), frameon=False, handletextpad=.4)
    axes[0].set_ylabel(r"廓线梯度 $V_X(\gamma)$")
    fig.text(.5, .97, "同一参数条件、相同的 30 个随机样本", ha="center", va="top", fontsize=11)
    fig.text(.5, .89, r"$\beta=2,\ \eta=1000,\ \gamma=1000,\ n=7$", ha="center", fontsize=9)
    fig.text(.10, .075, "a  所有曲线采用同一偏移水平", fontsize=8, color=red)
    fig.text(.565, .075, "b  按当前样本选择偏移水平", fontsize=8, color=blue)
    if points.boundary.any():
        fig.text(.5, .005, "三角形：约束边界解（γ = 0），此时不一定存在与偏移水平线的交点。",
                 ha="center", fontsize=7, color="#555555")
    output = FIGURES / "main"
    output.mkdir(exist_ok=True)
    for extension in ("png", "svg", "pdf"):
        fig.savefig(output / f"{STEM}.{extension}", dpi=400, facecolor="white")
    plt.close(fig)
    print(points.groupby("method").agg(samples=("repeat_id", "count"),
                                       boundaries=("boundary", "sum"),
                                       delta_min=("delta", "min"), delta_max=("delta", "max")).to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-data", action="store_true")
    args = parser.parse_args()
    if args.refresh_data or not CURVES.exists() or not POINTS.exists():
        extract()
    plot()
