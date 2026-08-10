"""同参数组合、独立 repeats 的最小 P/Q pilot。"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

from . import config as CFG
from . import data as DATA
from . import training as TR


OUT_DIR = os.path.join(CFG.STUDY02_ROOT, "artifacts", "pq_iid_pilot")


def run_pilot(fold_idx: int = 0) -> dict:
    master = DATA.build_master()
    DATA.verify_integrity(master)
    rows = []
    packed = {k: [] for k in ("keys", "n", "seed", "p_rel_err_sq", "q_rel_err_sq")}
    q_params = {k: [] for k in ("beta_hat", "eta_hat", "gamma_hat", "min_x")}

    for n in CFG.N_GRID:
        for seed in CFG.SEEDS:
            p = TR.train_one_fit(
                n, fold_idx, seed, "P", master,
                split_strategy="repeat_stratified",
            )
            q = TR.train_one_fit(
                n, fold_idx, seed, "Q", master,
                split_strategy="repeat_stratified",
            )
            mp, mq = p["meta"], q["meta"]
            pp, qp = p["predictions"], q["predictions"]
            assert mp["init_param_sha"] == mq["init_param_sha"]
            assert mp["batch_order_sha"] == mq["batch_order_sha"]
            assert mp["train_rows_sha"] == mq["train_rows_sha"]
            assert mp["val_rows_sha"] == mq["val_rows_sha"]
            assert mp["test_rows_sha"] == mq["test_rows_sha"]
            assert mp["scaler_sha"] == mq["scaler_sha"]
            assert np.array_equal(pp["keys"], qp["keys"])

            rows.append({
                "n": n,
                "fold": fold_idx + 1,
                "seed": seed,
                "p_rrmse": mp["rrmse_x95"],
                "q_rrmse": mq["rrmse_x95"],
                "q_minus_p_mse": float(np.mean(qp["rel_err_sq"] - pp["rel_err_sq"])),
                "p_best_epoch": mp["best_epoch"],
                "q_best_epoch": mq["best_epoch"],
            })
            packed["keys"].append(pp["keys"])
            packed["n"].append(np.full(len(pp["rel_err_sq"]), n, dtype=np.int16))
            packed["seed"].append(np.full(len(pp["rel_err_sq"]), seed, dtype=np.int32))
            packed["p_rel_err_sq"].append(pp["rel_err_sq"])
            packed["q_rel_err_sq"].append(qp["rel_err_sq"])
            for key in q_params:
                q_params[key].append(qp[key])
            print(f"n={n} seed={seed}: P={mp['rrmse_x95']:.5f} Q={mq['rrmse_x95']:.5f}")

    frame = pd.DataFrame(rows)
    evidence = {k: np.concatenate(v) for k, v in packed.items()}
    diag = {k: np.concatenate(v) for k, v in q_params.items()}
    pooled_p = float(np.sqrt(np.mean(evidence["p_rel_err_sq"])))
    pooled_q = float(np.sqrt(np.mean(evidence["q_rel_err_sq"])))
    by_n = {}
    for n in CFG.N_GRID:
        mask = evidence["n"] == n
        by_n[str(n)] = {
            "p_rrmse": float(np.sqrt(np.mean(evidence["p_rel_err_sq"][mask]))),
            "q_rrmse": float(np.sqrt(np.mean(evidence["q_rel_err_sq"][mask]))),
        }
    summary = {
        "status": "descriptive_pilot_not_formal_inference",
        "design": {
            "split": "repeat_stratified_same_parameter_support",
            "fold": fold_idx + 1,
            "train_validation_test_repeats_per_combo": [180, 60, 60],
            "n_grid": CFG.N_GRID,
            "seeds": CFG.SEEDS,
            "n_paired_units": len(frame),
        },
        "pooled": {
            "p_rrmse": pooled_p,
            "q_rrmse": pooled_q,
            "q_relative_change_vs_p": (pooled_q - pooled_p) / pooled_p,
            "q_minus_p_mse": float(np.mean(
                evidence["q_rel_err_sq"] - evidence["p_rel_err_sq"]
            )),
        },
        "unit_directions": {
            "q_better": int((frame.q_rrmse < frame.p_rrmse).sum()),
            "p_better": int((frame.p_rrmse < frame.q_rrmse).sum()),
            "n_units": len(frame),
        },
        "by_n": by_n,
        "q_parameter_diagnostic": {
            "beta_hat_median": float(np.median(diag["beta_hat"])),
            "eta_hat_median": float(np.median(diag["eta_hat"])),
            "gamma_hat_median": float(np.median(diag["gamma_hat"])),
            "corr_gamma_hat_min_x": float(np.corrcoef(diag["gamma_hat"], diag["min_x"])[0, 1]),
        },
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    frame.to_csv(os.path.join(OUT_DIR, "per_unit.csv"), index=False)
    np.savez_compressed(os.path.join(OUT_DIR, "evidence.npz"), **evidence)
    with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fold", type=int, default=1, choices=range(1, CFG.N_FOLDS + 1))
    args = parser.parse_args()
    print(json.dumps(run_pilot(args.fold - 1), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
