"""Minimal diagnostic for when Direct-P should defer to a structural estimate.

This experiment reuses the current Research04 training design and Direct-P
implementation.  It does not search network architectures.  Observable risk
signals are calibrated on an independent in-domain validation panel, then
evaluated once on the frozen continuous-beta panel.  MDM-0.1 is the structural
fallback because it does not depend on another learned selector.
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import NearestNeighbors


HERE = Path(__file__).resolve()
RESEARCH_ROOT = HERE.parents[1]
PROJECT_ROOT = HERE.parents[3]
STUDY_CODE = PROJECT_ROOT / "Study" / "01-study-MDM最小偏移量优化研究" / "code"
PYTHON_ROOT = PROJECT_ROOT / "python"
for path in (HERE.parent, STUDY_CODE, PYTHON_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_p3_direct_mlp as DIRECT  # noqa: E402
import run_study01_aligned_generalization as BASE  # noqa: E402
from studies.common.runner import run_method  # noqa: E402
from studies.common.sample import generate_sample  # noqa: E402


VALIDATION_NAMESPACE = "research04_replacement_boundary_validation_v1"
TEST_NAMESPACE = BASE.TEST_SEED_NAMESPACE
OUT_DIR = RESEARCH_ROOT / "artifacts" / "replacement_boundary_v1"
TRAIN_NEIGHBORS = 25
DISTANCE_NEIGHBORS = 5


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_panel(
    betas: tuple[float, ...], n_value: int, repeats: int, namespace: str
) -> tuple[np.ndarray, pd.DataFrame]:
    samples: list[np.ndarray] = []
    rows: list[dict] = []
    for beta in betas:
        for ratio in BASE.GAMMA_RATIOS:
            gamma = ratio * BASE.ETA
            for repeat_id in range(repeats):
                sample = generate_sample(
                    beta, BASE.ETA, gamma, n_value, repeat_id, seed=namespace
                )
                samples.append(np.asarray(sample, dtype=np.float64))
                rows.append(
                    {
                        "beta": beta,
                        "gamma_over_eta": ratio,
                        "n": n_value,
                        "repeat_id": repeat_id,
                        "beta_group": BASE.beta_group(beta),
                    }
                )
    return np.vstack(samples), pd.DataFrame(rows)


def build_training_panel(n_value: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    raw, metadata = generate_panel(
        BASE.TRAIN_BETAS, n_value, BASE.TRAIN_REPEATS, BASE.TRAIN_SEED_NAMESPACE
    )
    means = raw.mean(axis=1)
    normalized = raw / means[:, None]
    params = np.column_stack(
        [
            metadata["beta"].to_numpy(dtype=float),
            np.full(len(metadata), BASE.ETA, dtype=float),
            metadata["gamma_over_eta"].to_numpy(dtype=float) * BASE.ETA,
        ]
    )
    return normalized, params, means


def estimate_mdm(sample: np.ndarray) -> dict:
    return run_method("mdm", sample, offset=BASE.DEFAULT_DELTA)


def empirical_percentile(values: np.ndarray, reference: np.ndarray) -> np.ndarray:
    clean = np.sort(reference[np.isfinite(reference)])
    if clean.size == 0:
        raise RuntimeError("risk-score calibration reference is empty")
    return np.searchsorted(clean, values, side="right") / clean.size


def evaluate_panel(
    samples: np.ndarray,
    metadata: pd.DataFrame,
    model,
    model_info: dict,
    train_x: np.ndarray,
    train_params: np.ndarray,
    workers: int,
) -> pd.DataFrame:
    means = samples.mean(axis=1)
    normalized = samples / means[:, None]
    direct = DIRECT.predict_direct_mlp(model, model_info, normalized, means)

    standardized_train = (train_x - model_info["x_mean"]) / model_info["x_std"]
    standardized_eval = (normalized - model_info["x_mean"]) / model_info["x_std"]
    neighbors = NearestNeighbors(n_neighbors=TRAIN_NEIGHBORS, n_jobs=-1)
    neighbors.fit(standardized_train)
    distances, indices = neighbors.kneighbors(standardized_eval)
    support_distance = distances[:, :DISTANCE_NEIGHBORS].mean(axis=1) / math.sqrt(
        train_x.shape[1]
    )

    neighbor_targets = np.column_stack(
        [np.log(train_params[:, 0]), train_params[:, 2] / train_params[:, 1]]
    )[indices]
    ambiguity = np.sqrt(np.var(neighbor_targets, axis=1, ddof=0).sum(axis=1))

    ddof = 1 if samples.shape[1] > 1 else 0
    sample_cv = samples.std(axis=1, ddof=ddof) / means
    max_over_mean = samples.max(axis=1) / means

    if workers == 1:
        mdm_results = [estimate_mdm(sample) for sample in samples]
    else:
        with mp.Pool(processes=workers) as pool:
            mdm_results = list(pool.imap(estimate_mdm, list(samples), chunksize=32))

    rows: list[dict] = []
    for i, item in metadata.reset_index(drop=True).iterrows():
        beta = float(item["beta"])
        ratio = float(item["gamma_over_eta"])
        gamma = ratio * BASE.ETA
        direct_row = BASE.result_row(
            "Direct-P", beta, ratio, int(item["n"]), int(item["repeat_id"]),
            samples[i], direct[i, 0], direct[i, 1], direct[i, 2], True, "", None,
            np.nan,
        )
        mdm = mdm_results[i]
        mdm_row = BASE.result_row(
            "MDM-0.1", beta, ratio, int(item["n"]), int(item["repeat_id"]),
            samples[i], mdm.get("beta_hat"), mdm.get("eta_hat"),
            mdm.get("gamma_hat"), bool(mdm.get("converged")),
            BASE._failure_reason(mdm), BASE.DEFAULT_DELTA, np.nan,
        )
        disagreement = np.nan
        if direct_row["status"] == "success" and mdm_row["status"] == "success":
            disagreement = math.sqrt(
                ((direct_row["beta_hat"] - mdm_row["beta_hat"]) / mdm_row["beta_hat"]) ** 2
                + ((direct_row["eta_hat"] - mdm_row["eta_hat"]) / mdm_row["eta_hat"]) ** 2
                + ((direct_row["gamma_hat"] - mdm_row["gamma_hat"]) / mdm_row["eta_hat"]) ** 2
            )
        rows.append(
            {
                **item.to_dict(),
                "direct_status": direct_row["status"],
                "mdm_status": mdm_row["status"],
                "direct_loss": direct_row["loss_natural"],
                "mdm_loss": mdm_row["loss_natural"],
                "support_distance": float(support_distance[i]),
                "neighbor_target_spread": float(ambiguity[i]),
                "sample_cv": float(sample_cv[i]),
                "max_over_mean": float(max_over_mean[i]),
                "direct_mdm_disagreement": float(disagreement),
                "true_gamma": gamma,
            }
        )
    return pd.DataFrame(rows)


def score_summary(validation: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    score_names = [
        "support_distance",
        "neighbor_target_spread",
        "sample_cv",
        "max_over_mean",
        "direct_mdm_disagreement",
    ]
    for frame in (validation, test):
        support_rank = empirical_percentile(
            frame["support_distance"].to_numpy(float),
            validation["support_distance"].to_numpy(float),
        )
        ambiguity_rank = empirical_percentile(
            frame["neighbor_target_spread"].to_numpy(float),
            validation["neighbor_target_spread"].to_numpy(float),
        )
        frame["combined_support_score"] = np.maximum(support_rank, ambiguity_rank)
    score_names.append("combined_support_score")

    valid_pair = test["direct_loss"].notna() & test["mdm_loss"].notna()
    event = test.loc[valid_pair, "direct_loss"] > test.loc[valid_pair, "mdm_loss"]
    summaries: list[dict] = []
    for score in score_names:
        values = test.loc[valid_pair, score]
        finite = values.notna()
        auc = np.nan
        if finite.any() and event.loc[finite].nunique() == 2:
            auc = roc_auc_score(event.loc[finite], values.loc[finite])
        summaries.append(
            {
                "score": score,
                "n_test_pairs": int(finite.sum()),
                "auc_direct_worse_than_mdm": float(auc),
                "spearman_with_direct_loss": float(
                    values.loc[finite].corr(test.loc[values.loc[finite].index, "direct_loss"], method="spearman")
                ),
            }
        )

    finite_losses = pd.concat(
        [validation["direct_loss"], validation["mdm_loss"]], ignore_index=True
    ).dropna()
    penalty = float(np.percentile(finite_losses, 99))
    direct_loss = test["direct_loss"].fillna(penalty).to_numpy(float)
    mdm_loss = test["mdm_loss"].fillna(penalty).to_numpy(float)
    policies: list[dict] = []
    for score in score_names:
        reference = validation[score].dropna().to_numpy(float)
        if reference.size == 0:
            continue
        test_score = test[score].to_numpy(float)
        for quantile in (0.80, 0.90, 0.95, 0.975, 0.99):
            threshold = float(np.quantile(reference, quantile))
            use_direct = np.isfinite(test_score) & (test_score <= threshold)
            use_direct |= test["mdm_loss"].isna().to_numpy() & test["direct_loss"].notna().to_numpy()
            selected = np.where(use_direct, direct_loss, mdm_loss)
            policies.append(
                {
                    "score": score,
                    "validation_quantile": quantile,
                    "threshold": threshold,
                    "direct_coverage": float(use_direct.mean()),
                    "selected_J1": float(np.sqrt(np.mean(selected))),
                    "always_direct_J1": float(np.sqrt(np.mean(direct_loss))),
                    "always_mdm_J1": float(np.sqrt(np.mean(mdm_loss))),
                    "direct_worse_rate_among_accepted": float(
                        np.mean(direct_loss[use_direct] > mdm_loss[use_direct])
                    ) if use_direct.any() else np.nan,
                }
            )
    return pd.DataFrame(summaries), pd.DataFrame(policies)


def run(repeats: int, workers: int, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"replacement-boundary diagnostic: repeats={repeats}, workers={workers}, "
        f"out={out_dir}",
        flush=True,
    )
    validation_parts: list[pd.DataFrame] = []
    test_parts: list[pd.DataFrame] = []
    training_meta: dict[str, dict] = {}
    for n_value in BASE.N_VALUES:
        print(f"n={n_value}: training Direct-P", flush=True)
        train_x, train_params, train_means = build_training_panel(n_value)
        model, info = DIRECT.train_direct_mlp(
            train_x, train_params, train_means, BASE.MODEL_SEED
        )
        training_meta[str(n_value)] = {
            "n_train": int(len(train_x)),
            "n_iter": int(info["n_iter"]),
            "best_val_loss": float(info["best_val_loss"]),
        }
        validation_x, validation_meta = generate_panel(
            BASE.TRAIN_BETAS, n_value, repeats, VALIDATION_NAMESPACE
        )
        test_x, test_meta = generate_panel(
            BASE.TEST_BETAS, n_value, repeats, TEST_NAMESPACE
        )
        print(f"n={n_value}: evaluating validation panel", flush=True)
        validation_parts.append(
            evaluate_panel(
                validation_x, validation_meta, model, info, train_x, train_params, workers
            )
        )
        print(f"n={n_value}: evaluating test panel", flush=True)
        test_parts.append(
            evaluate_panel(test_x, test_meta, model, info, train_x, train_params, workers)
        )

    validation = pd.concat(validation_parts, ignore_index=True)
    test = pd.concat(test_parts, ignore_index=True)
    score_table, policy_table = score_summary(validation, test)
    domain_table = (
        test.assign(
            direct_loss_finite=test["direct_loss"].notna(),
            mdm_loss_finite=test["mdm_loss"].notna(),
        )
        .groupby("beta_group", as_index=False)
        .agg(
            n=("beta", "size"),
            direct_mean_loss=("direct_loss", "mean"),
            mdm_mean_loss=("mdm_loss", "mean"),
            direct_success_rate=("direct_loss_finite", "mean"),
            mdm_success_rate=("mdm_loss_finite", "mean"),
            support_distance_median=("support_distance", "median"),
            target_spread_median=("neighbor_target_spread", "median"),
        )
    )
    domain_table["direct_J1"] = np.sqrt(domain_table["direct_mean_loss"])
    domain_table["mdm_J1"] = np.sqrt(domain_table["mdm_mean_loss"])

    validation.to_csv(out_dir / "validation_rows.csv.gz", index=False, compression="gzip")
    test.to_csv(out_dir / "test_rows.csv.gz", index=False, compression="gzip")
    score_table.to_csv(out_dir / "risk_score_summary.csv", index=False)
    policy_table.to_csv(out_dir / "selective_policy_summary.csv", index=False)
    domain_table.to_csv(out_dir / "domain_summary.csv", index=False)
    manifest = {
        "run_id": "replacement_boundary_v1",
        "generated_at": utc_now(),
        "status": "candidate",
        "purpose": "minimal observable-risk diagnostic for Direct-P fallback",
        "model_seed": BASE.MODEL_SEED,
        "training_seed_namespace": BASE.TRAIN_SEED_NAMESPACE,
        "validation_seed_namespace": VALIDATION_NAMESPACE,
        "test_seed_namespace": TEST_NAMESPACE,
        "validation_betas": list(BASE.TRAIN_BETAS),
        "test_betas": list(BASE.TEST_BETAS),
        "gamma_over_eta": list(BASE.GAMMA_RATIOS),
        "n": list(BASE.N_VALUES),
        "repeats_per_cell": repeats,
        "fallback": "MDM-0.1",
        "risk_scores": [
            "support_distance",
            "neighbor_target_spread",
            "sample_cv",
            "max_over_mean",
            "direct_mdm_disagreement",
            "combined_support_score",
        ],
        "training": training_meta,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("replacement-boundary diagnostic complete", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--workers", type=int, default=max(1, (mp.cpu_count() or 2) - 1))
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.repeats < 2:
        raise SystemExit("--repeats must be at least 2")
    run(args.repeats, args.workers, args.out_dir)
