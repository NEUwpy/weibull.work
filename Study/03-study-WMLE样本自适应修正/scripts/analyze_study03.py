"""Analyze historical replay and controlled simulations separately."""
from pathlib import Path
import json
import sys
import hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
sys.path[:0] = [str(ROOT / "python"), str(STUDY / "scripts")]
from studies.common.sample import generate_sample
from run_wmle_diagnostic_grid import sample_features

OUT = STUDY / "results/analysis_v1"
KEYS = ["cohort", "beta", "eta", "gamma", "sample_size"]


def supplement(path):
    d = pd.read_csv(path)
    m = json.loads(path.with_name("manifest.json").read_text(encoding="utf-8"))
    d = d.rename(columns={"n": "sample_size"})
    d["seed_namespace"] = m["seed_namespace"]
    info = d["extra"].map(lambda x: json.loads(x).get("solution_info", {}))
    d["solution_status"] = info.map(lambda x: x.get("status", "unknown"))
    d["objective"] = info.map(lambda x: x.get("objective", np.nan))
    d["origin"] = str(path.relative_to(STUDY))
    feats = []
    sample_rows = []
    for r in d.itertuples():
        sample = generate_sample(r.beta, r.eta, r.gamma, r.sample_size,
                                 r.repeat_id, seed=m["seed_namespace"])
        feats.append(sample_features(sample))
        for i, value in enumerate(sample, 1):
            sample_rows.append(dict(beta=r.beta, eta=r.eta, gamma=r.gamma,
                                    sample_size=r.sample_size, repeat_id=r.repeat_id,
                                    seed_namespace=m["seed_namespace"],
                                    observation_index=i, value=value,
                                    origin=str(path.relative_to(STUDY))))
    return pd.concat([d.reset_index(drop=True), pd.DataFrame(feats)], axis=1), sample_rows


def wilson(k, n):
    if not n:
        return (np.nan, np.nan)
    z = 1.959963984540054
    p = k / n
    c = (p + z*z / (2*n)) / (1 + z*z/n)
    h = z * np.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return c-h, c+h


def summarize(d):
    records = []
    for key, g in d.groupby(KEYS):
        v = g[g.valid]
        r = dict(zip(KEYS, key))
        r.update(total=len(g), valid=len(v), failed=len(g)-len(v),
                 failure_rate=1-len(v)/len(g))
        for threshold, label in [(0.5, "50"), (1.0, "100")]:
            k = int((v.E >= threshold).sum())
            lo, hi = wilson(k, len(v))
            r.update({f"extreme{label}_count": k,
                      f"extreme{label}_rate_valid": k/len(v) if len(v) else np.nan,
                      f"extreme{label}_ci_low": lo, f"extreme{label}_ci_high": hi})
        r["failure_or_extreme50_rate_all"] = (len(g)-len(v)+r["extreme50_count"])/len(g)
        for name in ["e_beta", "e_eta", "e_gamma", "E"]:
            a = v[name]
            r.update({f"{name}_mean": a.mean(), f"{name}_sd": a.std(),
                      f"{name}_rmse": np.sqrt((a*a).mean()),
                      f"{name}_median_abs": a.abs().median(),
                      f"{name}_p95_abs": a.abs().quantile(.95),
                      f"{name}_max_abs": a.abs().max()})
        for name in ["beta_hat", "eta_hat", "gamma_hat"]:
            r.update({f"{name}_mean": v[name].mean(), f"{name}_sd": v[name].std(),
                      f"{name}_p05": v[name].quantile(.05),
                      f"{name}_p50": v[name].median(), f"{name}_p95": v[name].quantile(.95)})
        records.append(r)
    return pd.DataFrame(records)


def table(d, columns):
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|"*len(columns)]
    for row in d[columns].itertuples(index=False, name=None):
        lines.append("| " + " | ".join(f"{x:.4g}" if isinstance(x, float) else str(x) for x in row) + " |")
    return "\n".join(lines)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    old_path = STUDY / "results/existing_cases_v1/wmle_existing_cases_long.csv"
    grid_path = STUDY / "results/diagnostic_grid_v1/wmle_estimates_long.csv"
    old = pd.read_csv(old_path)
    inventory = pd.read_csv(STUDY / "results/existing_cases_v1/source_inventory.csv")
    verified_seeds = inventory.set_index("case_id").seed_namespace
    old["seed_namespace"] = old.case_id.map(verified_seeds)
    old["cohort"] = "historical_complete"
    old["repeat_id"] = old["sample_id"] - 1
    old["origin"] = str(old_path.relative_to(STUDY))
    grid = pd.read_csv(grid_path)
    grid["cohort"] = "controlled_20260922"
    grid["seed_namespace"] = 20260922
    grid["origin"] = str(grid_path.relative_to(STUDY))
    frames = [old, grid]
    sample_rows = []
    inputs = [old_path, grid_path]
    for path in sorted((STUDY / "results/supplement_v1").glob("*/results.csv")):
        d, samples = supplement(path)
        d["cohort"] = "controlled_20260922" if path.parent.name == "controlled_missing" else "historical_complete"
        frames.append(d)
        sample_rows.extend(samples)
        inputs.append(path)
    data = pd.concat(frames, ignore_index=True, sort=False)
    data["valid"] = data.converged.eq(True) & data.solution_status.eq("ok")
    data["valid"] &= np.isfinite(data[["beta_hat", "eta_hat", "gamma_hat"]]).all(axis=1)
    for name, scale in [("beta", "beta"), ("eta", "eta"), ("gamma", "eta")]:
        data["e_"+name] = ((data[name+"_hat"]-data[name])/data[scale]).where(data.valid)
    data["E"] = data[["e_beta", "e_eta", "e_gamma"]].abs().max(axis=1, skipna=False)
    assert not data.duplicated(KEYS + ["repeat_id"]).any()
    assert len(data) == 4500
    summary = summarize(data)
    assert len(summary) == 57
    for cohort, expected in [("historical_complete", 50), ("controlled_20260922", 100)]:
        assert summary.loc[summary.cohort.eq(cohort), "total"].eq(expected).all()
    data.to_csv(OUT / "all_case_rows.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(sample_rows).to_csv(OUT / "supplement_samples_long.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUT / "cell_summary_all.csv", index=False, encoding="utf-8-sig")
    summary[summary.cohort.eq("historical_complete")].to_csv(OUT / "historical_complete_summary.csv", index=False, encoding="utf-8-sig")
    ctrl = summary[summary.cohort.eq("controlled_20260922")]
    ctrl.to_csv(OUT / "controlled_summary.csv", index=False, encoding="utf-8-sig")
    data.groupby(KEYS + ["solution_status"], dropna=False).size().rename("count").reset_index().to_csv(
        OUT / "solver_status_counts.csv", index=False, encoding="utf-8-sig")
    data[data.valid].sort_values("E", ascending=False).head(100).to_csv(
        OUT / "worst_cases_top100.csv", index=False, encoding="utf-8-sig")
    # Correlations within a fixed true-parameter/sample-size cell, never pooled.
    correlations = []
    for key, group in data[data.valid].groupby(KEYS):
        for feat in ["sample_min", "sample_range", "sample_cv", "gap_1", "gap_2", "largest_gap_rel_range"]:
            pair = group[[feat, "E"]].dropna()
            correlations.append({**dict(zip(KEYS, key)), "feature": feat,
                                 "n_pairs": len(pair), "spearman": pair[feat].corr(pair.E, method="spearman")})
    pd.DataFrame(correlations).to_csv(OUT / "feature_correlations_by_cell.csv", index=False, encoding="utf-8-sig")
    hist = pd.read_csv(STUDY / "results/existing_cases_v1/historical_display_estimates.csv")
    compare = hist.merge(old, on=["case_id", "sample_size", "sample_id"], suffixes=("_display", "_replay"), validate="one_to_one")
    for name in ["beta_hat", "eta_hat", "gamma_hat"]:
        compare[name+"_delta"] = compare[name+"_replay"] - compare[name+"_display"]
    compare.to_csv(OUT / "historical_display_comparison.csv", index=False, encoding="utf-8-sig")
    # Three independent one-factor comparisons share the same reference cell.
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    colors = ["#0072B2", "#D55E00", "#009E73"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.7), sharey=True)
    axes_spec = [("beta", ctrl.eta.eq(1000) & ctrl.gamma.eq(1000)),
                 ("eta", ctrl.beta.eq(2) & ctrl.gamma.eq(1000)),
                 ("gamma", ctrl.beta.eq(2) & ctrl.eta.eq(1000))]
    for ax, (axis, mask) in zip(axes, axes_spec):
        for color, (level, part) in zip(colors, ctrl[mask].groupby(axis)):
            part = part.sort_values("sample_size")
            y = part.extreme50_rate_valid
            ax.errorbar(part.sample_size, y,
                        yerr=[y-part.extreme50_ci_low, part.extreme50_ci_high-y],
                        marker="o", capsize=2, color=color, label=f"{axis}={level:g}")
        ax.set(title=f"Vary {axis} only", xlabel="Sample size n", xticks=[7,15,30], ylim=(0,1))
        ax.legend(frameon=False, fontsize=8)
        ax.grid(alpha=.18)
    axes[0].set_ylabel("P(E >= 0.5 | valid fit)")
    fig.suptitle("WMLE controlled baseline: 100 draws per cell; Wilson 95% intervals")
    fig.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(OUT / f"controlled_three_axes.{ext}", dpi=220)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharey=True)
    for ax, n in zip(axes, [7,15,30]):
        part = data[data.cohort.eq("controlled_20260922") & data.eta.eq(1000) &
                    data.gamma.eq(1000) & data.sample_size.eq(n) & data.valid]
        for color, (beta, group) in zip(colors, part.groupby("beta")):
            y = np.sort(group.E)
            ax.step(y, np.arange(1,len(y)+1)/len(y), where="post", color=color, label=f"beta={beta:g}")
        ax.axvline(.5, color="gray", linestyle="--", linewidth=.8)
        ax.set(xlabel="Maximum normalized parameter error E", title=f"n={n}", xlim=(0,3))
        ax.legend(frameon=False, fontsize=8)
        ax.grid(alpha=.18)
    axes[0].set_ylabel("Empirical cumulative proportion (valid fits)")
    fig.suptitle("Within-cell error distributions; eta=1000, gamma=1000")
    fig.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(OUT / f"within_cell_error_ecdf.{ext}", dpi=220)
    plt.close(fig)
    text = ["# Study03 原 WMLE 基线统计（自动生成）", "",
            "历史复核及补齐组与统一模拟组分开汇总，禁止跨组混合解释。", "",
            "误差 eβ=(β̂−β)/β，eη=(η̂−η)/η，eγ=(γ̂−γ)/η；E=max(|eβ|,|eη|,|eγ|)。",
            "下表大误差率的分母为有效估计数；失败率分母为总抽样数。50% 是探索性阈值。",
            "CSV 同时提供 100% 阈值、失败或大误差联合比例、Wilson 区间及各分量偏差/标准差/RMSE。", ""]
    cols = ["beta", "eta", "gamma", "sample_size", "total", "valid", "failure_rate", "extreme50_rate_valid", "E_median_abs", "E_p95_abs"]
    for cohort, label in [("historical_complete", "历史 8 组复核与 n=30 补齐"), ("controlled_20260922", "统一 seed 新模拟：11 个组合")]:
        text += [f"## {label}", "", table(summary[summary.cohort.eq(cohort)], cols), ""]
    text += ["## 图", "", "![三条控制变量轴](controlled_three_axes.png)", "",
             "![同一真参数下误差分布](within_cell_error_ecdf.png)", ""]
    (OUT / "统计报告.md").write_text("\n".join(text), encoding="utf-8")
    manifest = dict(rows=len(data), cells=len(summary), historical_rows=1200, controlled_rows=3300,
                    error_definition="E=max(abs((bhat-b)/b),abs((ehat-e)/e),abs((ghat-g)/e))",
                    inputs=[dict(path=str(p.relative_to(STUDY)), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in inputs])
    (OUT / "analysis_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"rows":len(data), "cells":len(summary), "valid":int(data.valid.sum())}))


if __name__ == "__main__":
    main()
