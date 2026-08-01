"""B6: three tracked figures from accepted B4/B5 manifests.

Analysis-only; reads only approved run manifests. Generates exactly three
figures that materially support B1-B7:
  1. core_error_vs_n  - pooled core relative RMSE of D vs P by n (B2)
  2. core_effect_by_n - per-n improvement I with 95% CI + pooled (B1/B2)
  3. stress_tradeoff  - stress D availability and paired-loss effect vs core
                        coverage, i.e. boundary/calibration tradeoff (B6/B7)
Input manifests and output figure SHA256 are recorded in SHA256SUMS.
"""

from __future__ import annotations

import hashlib, json, sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_STUDY = Path(__file__).resolve().parents[2]
_ART = _STUDY / "artifacts" / "b6"
_EXTERNAL = Path("C:/weibull-runs/study02/formal-b")
_B4_ANALYZE = _EXTERNAL / "B4-analyze-20260801-053046" / "manifest.json"
_B4_CORE = _EXTERNAL / "B4-core-20260801-051119" / "manifest.json"
_B5_V6 = _EXTERNAL / "B5-v6-20260801-073535" / "manifest.json"

def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _load(p):
    return json.loads(p.read_text(encoding="utf-8"))

def main():
    _ART.mkdir(parents=True, exist_ok=True)
    b4a = _load(_B4_ANALYZE)
    b4c = _load(_B4_CORE)
    b5  = _load(_B5_V6)

    ns = ["5", "7", "10", "15", "20"]
    fig1, ax1 = plt.subplots(figsize=(6, 4))
    d_rmse = [b4a["per_n"][n]["d_rmse"] for n in ns]
    p_rmse = [b4a["per_n"][n]["p_rmse"] for n in ns]
    ax1.plot(ns, p_rmse, "o-", label="P (parameter route)")
    ax1.plot(ns, d_rmse, "s-", label="D (direct route)")
    ax1.set_xlabel("n"); ax1.set_ylabel("pooled core relative RMSE (x0.95)")
    ax1.set_title("Core relative RMSE by n (B4-analyze)")
    ax1.legend(); ax1.grid(alpha=0.3)
    fig1.tight_layout()
    p1 = _ART / "core_error_vs_n.png"
    fig1.savefig(p1, dpi=150); plt.close(fig1)

    fig2, ax2 = plt.subplots(figsize=(6, 4))
    I  = [b4a["per_n"][n]["I"] for n in ns]
    lo = [b4a["per_n"][n]["ci_95_lower"] for n in ns]
    hi = [b4a["per_n"][n]["ci_95_upper"] for n in ns]
    ax2.errorbar(ns, I, yerr=[np.array(I)-np.array(lo), np.array(hi)-np.array(I)],
                 fmt="o-", capsize=4, label="per-n I (95% CI)")
    ax2.axhline(0, color="gray", ls="--", lw=1)
    ax2.axhline(0.05, color="red", ls=":", lw=1, label="materiality 5%")
    ax2.set_xlabel("n"); ax2.set_ylabel("I = (RMSE_P - RMSE_D)/RMSE_P")
    ax2.set_title("Core D-vs-P improvement by n (B4-analyze)")
    ax2.legend(); ax2.grid(alpha=0.3)
    fig2.tight_layout()
    p2 = _ART / "core_effect_by_n.png"
    fig2.savefig(p2, dpi=150); plt.close(fig2)

    # Stress: D availability by domain x n, plus core D coverage for reference
    fig3, ax3 = plt.subplots(figsize=(6, 4))
    domains = ["low", "high", "loc"]
    styles = {"low": "o-", "high": "s-", "loc": "^-"}
    for d in domains:
        avail = [b5["conformal"]["stress_degradation"][f"{d}_D_n{n}"]["availability"]
                 for n in ns]
        ax3.plot(ns, avail, styles[d], label=f"stress-{d} D availability")
    core_cov = [b5["conformal"]["core_coverage"][f"D_n{n}"]["cov95"] for n in ns]
    ax3.plot(ns, core_cov, "x--", color="black", label="core D cov95 (reference)")
    ax3.set_xlabel("n"); ax3.set_ylabel("D valid availability / core cov95")
    ax3.set_ylim(0, 1.05)
    ax3.set_title("Boundary availability vs core coverage (B5-v6)")
    ax3.legend(); ax3.grid(alpha=0.3)
    fig3.tight_layout()
    p3 = _ART / "stress_tradeoff.png"
    fig3.savefig(p3, dpi=150); plt.close(fig3)

    # Bind input/output hashes
    inputs = {
        "B4-analyze-20260801-053046/manifest.json": _sha(_B4_ANALYZE),
        "B4-core-20260801-051119/manifest.json": _sha(_B4_CORE),
        "B5-v6-20260801-073535/manifest.json": _sha(_B5_V6),
    }
    outputs = {p.name: _sha(p) for p in [p1, p2, p3]}
    sums = {"inputs": inputs, "outputs": outputs}
    sums_path = _ART / "SHA256SUMS"
    sums_path.write_text(json.dumps(sums, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for p in [p1, p2, p3]:
        print(p, "->", _sha(p))
    print("SHA256SUMS ->", _sha(sums_path))
    print("figures complete")

if __name__ == "__main__":
    main()
