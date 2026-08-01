"""C2 runner: deterministic mechanism analysis on existing B evidence.

Usage:
    python run_c2.py [--output-dir DIR]

Produces under DIR (default artifacts/c/<run-id>):
    - summary.json     (machine-readable C2-1/C2-2/C2-3 summaries)
    - manifest.json    (inputs, hashes, code tip, provenance, environment)
    - at most 2 figures (only when they aid n-heterogeneity / propagation)

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

from data import (B3_MANIFEST, B4_NPZ, B4_RESULTS, B5_V6_MANIFEST,
                  N_VALUES, generate_test_data, infer_p_params,
                  load_b3_manifest, load_b4_npz, load_b4_results,
                  load_p_models, sha256_file, verify_p_inference)
import c2_analyze
import provenance


def _git_tip():
    return provenance.git_tip()


def _fig1(per_n, out_dir: Path):
    """Per-n RMSE (P/D) — helps n heterogeneity."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"  [fig] matplotlib unavailable: {e}")
        return None
    ns = [int(n) for n in per_n.keys()]
    p = [per_n[str(n)]["P"]["rmse"] for n in ns]
    d = [per_n[str(n)]["D"]["rmse"] for n in ns]
    fig, ax = plt.subplots(figsize=(6, 4))
    x = np.arange(len(ns))
    w = 0.38
    ax.bar(x - w/2, p, w, label="P (parameter route)")
    ax.bar(x + w/2, d, w, label="D (direct route)")
    ax.set_xticks(x); ax.set_xticklabels(ns)
    ax.set_xlabel("sample size n")
    ax.set_ylabel("x0.95 relative RMSE")
    ax.set_title("C2-1: per-n RMSE (core, 6,400 paired rows)")
    ax.legend()
    fig.tight_layout()
    path = out_dir / "c2_1_per_n_rmse.png"
    fig.savefig(path, dpi=140)
    import matplotlib.pyplot as _plt
    _plt.close(fig)
    return path


def _fig2(propagation, out_dir: Path):
    """Per-n mean |parameter contribution| to x0.95 error (P) — propagation."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"  [fig] matplotlib unavailable: {e}")
        return None
    ns = [int(n) for n in N_VALUES]
    beta = [propagation["per_n"][str(n)]["relative_mean_abs"]["beta"] for n in ns]
    eta = [propagation["per_n"][str(n)]["relative_mean_abs"]["eta"] for n in ns]
    gamma = [propagation["per_n"][str(n)]["relative_mean_abs"]["gamma"] for n in ns]
    combined = [propagation["per_n"][str(n)]["relative_mean_abs"]["combined"] for n in ns]
    fig, ax = plt.subplots(figsize=(6, 4))
    x = np.arange(len(ns)); w = 0.2
    ax.bar(x - 1.5*w, beta, w, label="beta only")
    ax.bar(x - 0.5*w, eta, w, label="eta only")
    ax.bar(x + 0.5*w, gamma, w, label="gamma only")
    ax.bar(x + 1.5*w, combined, w, label="combined (all three)")
    ax.set_xticks(x); ax.set_xticklabels(ns)
    ax.set_xlabel("sample size n")
    ax.set_ylabel("mean |relative contribution| (x0.95 / true)")
    ax.set_title("C2-2: P parameter-error contributions to x0.95 (relative, ensembled)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = out_dir / "c2_2_param_propagation.png"
    fig.savefig(path, dpi=140)
    import matplotlib.pyplot as _plt
    _plt.close(fig)
    return path


def run_c2(output_dir: Path | None = None):
    code_tip = _git_tip()
    if output_dir is None:
        run_id = f"C2-mechanism-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        output_dir = Path("Study/02-study-NN参数估计与分位点目标研究/artifacts/c") / run_id
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"=== C2 mechanism analysis ===")
    print(f"Code tip: {code_tip}")
    print(f"Output: {out}")

    # Inputs + hashes
    inputs = {
        "b3_manifest": {"path": str(B3_MANIFEST), "sha256": sha256_file(B3_MANIFEST)},
        "b4_results.csv": {"path": str(B4_RESULTS), "sha256": sha256_file(B4_RESULTS)},
        "b4_per_seed_predictions.npz": {"path": str(B4_NPZ), "sha256": sha256_file(B4_NPZ)},
        "b5_v6_manifest": {"path": str(B5_V6_MANIFEST), "sha256": sha256_file(B5_V6_MANIFEST)},
    }

    print("\n[1/4] Loading B data ...")
    b3 = load_b3_manifest()
    rows = load_b4_results()
    npz = load_b4_npz()
    print(f"  results rows: {len(rows)}")

    print("\n[2/4] Loading frozen P models + regenerating B4 test data ...")
    models = load_p_models(b3)
    datasets = generate_test_data()
    print(f"  datasets: {len(datasets)}")

    print("\n[3/4] Inferring P per-seed parameter predictions (no refit) ...")
    p_params = infer_p_params(models, datasets)
    check = verify_p_inference(p_params, npz)
    print(f"  {check}")
    assert check["max_abs_rel_diff"] < 1e-4, "P inference diverges from B4 NPZ"

    print("\n[4/4] Running C2 analyses ...")
    c2_1 = c2_analyze.c2_1_n_heterogeneity(rows, npz)
    c2_2 = c2_analyze.c2_2_propagation(p_params, datasets)
    c2_2_alignment = c2_analyze.c2_2_b4_alignment(p_params, datasets, rows)
    c2_3 = c2_analyze.c2_3_target_alignment(rows, npz)
    c2_2["b4_alignment"] = c2_2_alignment

    # Figures (at most 2)
    fig_paths = []
    f1 = _fig1(c2_1["per_n"], out)
    if f1: fig_paths.append(f1)
    f2 = _fig2(c2_2, out)
    if f2: fig_paths.append(f2)

    summary = {
        "task": "C2 mechanism analysis (existing B evidence, no new fit)",
        "code_tip": code_tip,
        "c2_1_n_heterogeneity": c2_1,
        "c2_2_parameter_to_x095_propagation": c2_2,
        "c2_3_target_alignment_attribution": c2_3,
    }
    summary_path = out / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Provenance gate: only emit a final manifest when the code subtree is
    # clean and its committed tip equals HEAD (fail closed).
    if not provenance.require_code_clean(code_tip):
        raise SystemExit("Refusing to emit final manifest: code provenance not clean.")

    manifest = {
        "version": "1.2",
        "run_id": out.name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "complete",
        "code_tip": code_tip,
        "code_tree_clean": True,
        "task": "C2 mechanism analysis on existing B evidence; inference only, no refit",
        "inputs": inputs,
        "outputs": {
            "summary.json": {"path": str(summary_path), "sha256": sha256_file(summary_path)},
        },
        "figures": [{"path": str(p), "sha256": sha256_file(p)} for p in fig_paths],
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  manifest: {manifest_path}  sha256={hashlib.sha256(manifest_path.read_bytes()).hexdigest()[:16]}")

    # ---- concise stdout for the C2 report ----
    print("\n--- C2-1 per-n summary ---")
    for n in N_VALUES:
        p = c2_1["per_n"][str(n)]
        print(f"  n={n:2d} P rmse={p['P']['rmse']:.4f} D rmse={p['D']['rmse']:.4f} "
              f"paired D-better={p['paired_D_better_proportion']:.3f} "
              f"clusters RMSE D-better={p['clusters']['n_clusters_rmse_D_better']}/64 "
              f"(cluster I med={p['clusters']['cluster_I_median']:.3f})")
    pooled = c2_1["pooled"]
    print(f"  row-pooled I={pooled['I_row_pooled']:.4f}  equal-per-n I={pooled['I_equal_per_n']:.4f}")

    print("\n--- C2-1 seed spread (normalized SD/true_x095) ---")
    for n in N_VALUES:
        p = c2_1["per_n"][str(n)]["seed_spread"]
        print(f"  n={n:2d} P norm spread mean={p['P_normalized_spread_mean']:.4f} "
              f"D norm spread mean={p['D_normalized_spread_mean']:.4f} "
              f"P spearman={p['P_spread_vs_err_spearman']:.3f} D spearman={p['D_spread_vs_err_spearman']:.3f}")

    print("\n--- C2-2 per-n relative counterfactual (mean abs /true) ---")
    for n in N_VALUES:
        p = c2_2["per_n"][str(n)]
        print(f"  n={n:2d} beta={p['relative_mean_abs']['beta']:.4f} eta={p['relative_mean_abs']['eta']:.4f} "
              f"gamma={p['relative_mean_abs']['gamma']:.4f} combined={p['relative_mean_abs']['combined']:.4f} "
              f"nonadd_abs={p['nonadditivity_relative']['mean_abs']:.4f} "
              f"jac_resid={p['jacobian_reference_relative']['mean_jac_resid_abs']:.4f}")
    print(f"  B4 alignment (vs P_rel_err): max_abs_diff={c2_2['b4_alignment']['max_abs_diff']:.3e} "
          f"mean_abs_diff={c2_2['b4_alignment']['mean_abs_diff']:.3e}")

    print("\n--- C2-3 attribution ---")
    dc = c2_3["direction_reversal_check"]
    print(f"  P ensemble RMSE={dc['P_ensemble_rmse_rowpooled']:.4f} "
          f"Dctrl ensemble RMSE={dc['Dctrl_ensemble_rmse_rowpooled']:.4f}")
    print(f"  P seed RMSE range [{dc['P_seed_rmse_min']:.4f}, {dc['P_seed_rmse_max']:.4f}]")
    print(f"  Dctrl seed RMSE range [{dc['Dctrl_seed_rmse_min']:.4f}, {dc['Dctrl_seed_rmse_max']:.4f}]")
    print(f"  worst Dctrl seed below best P seed: {dc['worst_Dctrl_seed_below_best_P_seed']}")
    print(f"  gap P-Dctrl = {dc['gap_P_ensemble_minus_Dctrl_ensemble']:.4f}")

    print(f"\n=== C2 complete: {out} ===")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    provenance.add_output_dir_arg(parser)
    args = parser.parse_args()
    run_c2(args.output_dir)
