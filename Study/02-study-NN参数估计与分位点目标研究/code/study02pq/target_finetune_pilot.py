"""最小目标切换 pilot：共同 P checkpoint 后比较 P 续训与 Q 微调。

这不是正式推断。固定 fold 1，在四个 n 和三个 seed 上检查目标分位点微调是否
产生稳定改善信号；结果写入一个紧凑的 pilot 目录。
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

from . import config as CFG
from . import data as DATA
from . import training as TR


PILOT_DIR = os.path.join(CFG.STUDY02_ROOT, "artifacts", "pq_target_finetune_pilot")


def _rrmse(parts: list[np.ndarray]) -> float:
    return float(np.sqrt(np.mean(np.concatenate(parts))))


def run_pilot(fold_idx: int = 0, continuation_epochs: int = 100,
              continuation_lr: float = 1e-4) -> dict:
    master = DATA.build_master()
    DATA.verify_integrity(master)

    rows = []
    evidence = {name: [] for name in (
        "keys", "n", "seed", "p_base", "p_continue", "q_finetune"
    )}
    parameter_diagnostics = {name: [] for name in (
        "q_beta_hat", "q_eta_hat", "q_gamma_hat", "q_min_x"
    )}

    for n in CFG.N_GRID:
        for seed in CFG.SEEDS:
            base = TR.train_one_fit(
                n, fold_idx, seed, "P", master, return_state=True
            )
            state = base["model_state"]
            p_continue = TR.train_one_fit(
                n, fold_idx, seed, "P", master,
                max_epochs=continuation_epochs,
                initial_state=state, include_initial=True,
                learning_rate=continuation_lr,
            )
            q_finetune = TR.train_one_fit(
                n, fold_idx, seed, "Q", master,
                max_epochs=continuation_epochs,
                initial_state=state, include_initial=True,
                learning_rate=continuation_lr,
            )

            bp = base["predictions"]
            pp = p_continue["predictions"]
            qp = q_finetune["predictions"]
            assert np.array_equal(bp["keys"], pp["keys"])
            assert np.array_equal(bp["keys"], qp["keys"])

            r_base = base["meta"]["rrmse_x95"]
            r_pcont = p_continue["meta"]["rrmse_x95"]
            r_qft = q_finetune["meta"]["rrmse_x95"]
            rows.append({
                "n": n,
                "fold": fold_idx + 1,
                "seed": seed,
                "p_base_rrmse": r_base,
                "p_continue_rrmse": r_pcont,
                "q_finetune_rrmse": r_qft,
                "q_minus_p_base_mse": float(np.mean(qp["rel_err_sq"] - bp["rel_err_sq"])),
                "q_minus_p_continue_mse": float(np.mean(qp["rel_err_sq"] - pp["rel_err_sq"])),
                "p_continue_best_epoch": p_continue["meta"]["best_epoch"],
                "q_finetune_best_epoch": q_finetune["meta"]["best_epoch"],
            })
            evidence["keys"].append(bp["keys"])
            evidence["n"].append(np.full(len(bp["rel_err_sq"]), n, dtype=np.int16))
            evidence["seed"].append(np.full(len(bp["rel_err_sq"]), seed, dtype=np.int32))
            evidence["p_base"].append(bp["rel_err_sq"])
            evidence["p_continue"].append(pp["rel_err_sq"])
            evidence["q_finetune"].append(qp["rel_err_sq"])
            parameter_diagnostics["q_beta_hat"].append(qp["beta_hat"])
            parameter_diagnostics["q_eta_hat"].append(qp["eta_hat"])
            parameter_diagnostics["q_gamma_hat"].append(qp["gamma_hat"])
            parameter_diagnostics["q_min_x"].append(qp["min_x"])
            print(
                f"n={n} seed={seed}: P-base={r_base:.5f} "
                f"P-cont={r_pcont:.5f} Q-ft={r_qft:.5f}"
            )

    frame = pd.DataFrame(rows)
    packed = {k: np.concatenate(v) for k, v in evidence.items()}
    diag = {k: np.concatenate(v) for k, v in parameter_diagnostics.items()}
    pooled = {
        "p_base_rrmse": _rrmse(evidence["p_base"]),
        "p_continue_rrmse": _rrmse(evidence["p_continue"]),
        "q_finetune_rrmse": _rrmse(evidence["q_finetune"]),
        "q_minus_p_base_mse": float(np.mean(packed["q_finetune"] - packed["p_base"])),
        "q_minus_p_continue_mse": float(np.mean(packed["q_finetune"] - packed["p_continue"])),
    }
    summary = {
        "status": "descriptive_pilot_not_formal_inference",
        "design": {
            "fold": fold_idx + 1,
            "n_grid": CFG.N_GRID,
            "seeds": CFG.SEEDS,
            "common_start": "best P checkpoint",
            "continuation_epochs": continuation_epochs,
            "continuation_learning_rate": continuation_lr,
            "epoch_zero_is_candidate": True,
        },
        "pooled": pooled,
        "unit_directions": {
            "q_better_than_p_base": int((frame.q_finetune_rrmse < frame.p_base_rrmse).sum()),
            "q_better_than_p_continue": int((frame.q_finetune_rrmse < frame.p_continue_rrmse).sum()),
            "q_selected_after_epoch_zero": int((frame.q_finetune_best_epoch > 0).sum()),
            "n_units": int(len(frame)),
        },
        "q_parameter_diagnostic": {
            "beta_hat_median": float(np.median(diag["q_beta_hat"])),
            "eta_hat_median": float(np.median(diag["q_eta_hat"])),
            "gamma_hat_median": float(np.median(diag["q_gamma_hat"])),
            "corr_gamma_hat_min_x": float(np.corrcoef(
                diag["q_gamma_hat"], diag["q_min_x"]
            )[0, 1]),
        },
    }

    os.makedirs(PILOT_DIR, exist_ok=True)
    frame.to_csv(os.path.join(PILOT_DIR, "per_unit.csv"), index=False)
    np.savez_compressed(os.path.join(PILOT_DIR, "evidence.npz"), **packed)
    with open(os.path.join(PILOT_DIR, "summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fold", type=int, default=1, choices=range(1, CFG.N_FOLDS + 1))
    parser.add_argument("--continuation-epochs", type=int, default=100)
    parser.add_argument("--continuation-lr", type=float, default=1e-4)
    args = parser.parse_args()
    summary = run_pilot(args.fold - 1, args.continuation_epochs, args.continuation_lr)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
