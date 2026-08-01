"""C3/C4 runner: alternative explanations + conditional validity.

Usage:
    python run_c3_c4.py [--output-dir DIR]

Reuses B4 results.csv + B5-v3 stress CSVs. No training, no new data.
Produces summary.json + manifest.json + at most 1 figure.

Provenance: a final manifest is only emitted when the study02c code subtree
is clean and its committed tip equals HEAD (fail closed). Use --output-dir to
rebuild/overwrite a current authoritative artifact directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_STUDY_CODE = Path(__file__).resolve().parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))
_REPO_ROOT = Path(__file__).resolve().parents[4]

import c3_c4_analyze
import data as c2data
import provenance

N_VALUES = [5, 7, 10, 15, 20]


def _git_tip():
    return provenance.git_tip()


def _fig_availability(c3_1, out_dir: Path):
    """Availability (D) vs D route-valid RMSE across domain x n — helps the
    availability-error tradeoff."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"  [fig] matplotlib unavailable: {e}")
        return None
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharey=True)
    for ax, dom in zip(axes, c3_1.keys()):
        ns = [int(k[1:]) for k in c3_1[dom].keys()]
        d_avail = [c3_1[dom][f"n{n}"]["availability"]["D"] for n in ns]
        d_rmse = [c3_1[dom][f"n{n}"]["common_valid"]["rmse_D"] for n in ns]
        ax.plot(ns, d_avail, "o-", label="D availability")
        ax2 = ax.twinx()
        ax2.plot(ns, d_rmse, "s--", color="tab:orange", label="D common-valid RMSE")
        ax.set_title(f"stress-{dom}")
        ax.set_xlabel("n")
        ax.set_xticks(ns)
        ax.set_ylabel("D availability", color="tab:blue")
        ax2.set_ylabel("D common-valid RMSE", color="tab:orange")
    fig.suptitle("C3-1: D availability vs common-valid error (stress)")
    fig.tight_layout()
    path = out_dir / "c3_1_availability_vs_error.png"
    fig.savefig(path, dpi=140)
    import matplotlib.pyplot as _plt
    _plt.close(fig)
    return path


def run_c3_c4(output_dir: Path | None = None):
    code_tip = _git_tip()
    if output_dir is None:
        run_id = f"C3C4-alternatives-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        output_dir = Path("Study/02-study-NN参数估计与分位点目标研究/artifacts/c") / run_id
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"=== C3/C4 analysis ===")
    print(f"Code tip: {code_tip}")
    print(f"Output: {out}")

    inputs = {
        "b4_results.csv": {"path": str(c3_c4_analyze.B4_RESULTS),
                           "sha256": c2data.sha256_file(c3_c4_analyze.B4_RESULTS)},
        "b5_v3_stress_low.csv": {"path": str(c3_c4_analyze.B5_V3_DIR / "stress_low.csv"),
                                 "sha256": c2data.sha256_file(c3_c4_analyze.B5_V3_DIR / "stress_low.csv")},
        "b5_v3_stress_high.csv": {"path": str(c3_c4_analyze.B5_V3_DIR / "stress_high.csv"),
                                  "sha256": c2data.sha256_file(c3_c4_analyze.B5_V3_DIR / "stress_high.csv")},
        "b5_v3_stress_loc.csv": {"path": str(c3_c4_analyze.B5_V3_DIR / "stress_loc.csv"),
                                 "sha256": c2data.sha256_file(c3_c4_analyze.B5_V3_DIR / "stress_loc.csv")},
        "b5_v6_manifest.json": {"path": str(c3_c4_analyze.B5_V6_MANIFEST),
                                "sha256": c2data.sha256_file(c3_c4_analyze.B5_V6_MANIFEST)},
    }

    print("\n[1/3] C3-1 availability vs error ...")
    c3_1 = c3_c4_analyze.c3_1_availability_vs_error()
    print("\n[2/3] C3-2 MLE survivor bias ...")
    c3_2 = c3_c4_analyze.c3_2_mle_survivor_bias()
    print("\n[3/3] C3-3 gate close + C4 conditional table ...")
    c3_3 = c3_c4_analyze.c3_3_close_training_gate()
    c4 = c3_c4_analyze.c4_conditional_selection(c3_1, c3_2)

    fig_paths = []
    f = _fig_availability(c3_1, out)
    if f:
        fig_paths.append(f)

    summary = {
        "task": "C3/C4 alternative explanations + conditional validity (existing B data only)",
        "code_tip": code_tip,
        "c3_1_availability_vs_error": c3_1,
        "c3_2_mle_survivor_bias": c3_2,
        "c3_3_training_gate": c3_3,
        "c4_conditional_selection": c4,
    }
    summary_path = out / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Provenance gate: fail closed unless the code subtree is clean at HEAD.
    if not provenance.require_code_clean(code_tip):
        raise SystemExit("Refusing to emit final manifest: code provenance not clean.")

    manifest = {
        "version": "1.1",
        "run_id": out.name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "complete",
        "code_tip": code_tip,
        "code_tree_clean": True,
        "task": "C3/C4 analysis on existing B data; 0 fits, 0 new data",
        "inputs": inputs,
        "outputs": {
            "summary.json": {"path": str(summary_path), "sha256": c2data.sha256_file(summary_path)},
        },
        "figures": [{"path": str(p), "sha256": c2data.sha256_file(p)} for p in fig_paths],
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  manifest: {manifest_path}  sha256={hashlib.sha256(manifest_path.read_bytes()).hexdigest()[:16]}")

    # concise stdout
    print("\n--- C3-1 availability & BH decision (main table) ---")
    for dom in c3_1:
        for n in N_VALUES:
            c = c3_1[dom][f"n{n}"]
            bhd = c["bh_decision"]
            print(f"  {dom} n{n:2d} P avail={c['availability']['P']:.3f} D avail={c['availability']['D']:.3f} "
                  f"commonRMSE P/D={c['common_valid']['rmse_P']:.3f}/{c['common_valid']['rmse_D']:.3f} "
                  f"BH={bhd['support']}|{bhd['direction']} -> {c['decision_category']}")

    print("\n--- C3-1 route-valid RMSE (supplementary; different denominators) ---")
    for dom in c3_1:
        for n in N_VALUES:
            c = c3_1[dom][f"n{n}"]
            rv = c["route_valid_rmse_supplementary"]
            print(f"  {dom} n{n:2d} P={rv['P']:.3f} D={rv['D']:.3f}")

    print("\n--- C3-2 MLE failure by n ---")
    for n in N_VALUES:
        c = c3_2[str(n)]
        print(f"  n{n:2d} MLE fail={c['mle_failure_rate']:.3f} "
              f"D rmse MLE-valid={c['subset_comparison']['D_rmse_on_MLE_valid']:.3f} "
              f"D rmse MLE-invalid={c['subset_comparison']['D_rmse_on_MLE_invalid']:.3f} "
              f"beta valid/invalid={c['mle_failure_beta']['valid_mean']:.2f}/{c['mle_failure_beta']['invalid_mean']:.2f}")

    print("\n--- C3-3 gate ---")
    print(f"  {c3_3['gate']}: {c3_3['reason']}")

    print(f"\n=== C3/C4 complete: {out} ===")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    provenance.add_output_dir_arg(parser)
    args = parser.parse_args()
    run_c3_c4(args.output_dir)
