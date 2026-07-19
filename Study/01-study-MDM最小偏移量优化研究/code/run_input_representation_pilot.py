"""Study01 pilot: summary features vs sorted raw-sample input.

This is a group-meeting sensitivity check, not a formal E3/E4 experiment.
It reuses the sealed E3b sample/risk-curve caches and evaluates one existing-grid
combo-holdout fold with one seed. Formal artifacts are never modified.
"""

import argparse
import json
import math
import os
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import run_E3b_vector_mlp as e3b


STUDY_ROOT = e3b.STUDY_ROOT
PILOT_DIR = os.path.join(STUDY_ROOT, "artifacts", "pilot", "input_representation")
FEATURE_CACHE = os.path.join(e3b.E3B_OUTPUT_DIR, "sample_features.csv")
RISK_CACHE = os.path.join(e3b.E3B_OUTPUT_DIR, "risk_curves.csv")
KEYS = ["beta", "gamma_over_eta", "n", "repeat_id"]
RAW_MAX_N = max(e3b.N_GRID)
RAW_INPUT_FIELDS = (
    [f"x_sorted_{i + 1}_z" for i in range(RAW_MAX_N)]
    + [f"mask_{i + 1}" for i in range(RAW_MAX_N)]
    + ["n"]
)
FEATURE_FIELDS_WITHOUT_N = [
    field for field in e3b.SAMPLE_FEATURE_COLS if field != "n"
]


def load_cached_samples():
    """Load and align the E3b feature and 26-point risk-curve caches."""
    df_features = pd.read_csv(FEATURE_CACHE)
    df_risk = pd.read_csv(RISK_CACHE)
    target_cols = [f"loss_d{delta}" for delta in e3b.DELTA_GRID]

    missing_targets = [col for col in target_cols if col not in df_risk.columns]
    if missing_targets:
        raise ValueError(f"Missing risk-curve columns: {missing_targets}")
    if df_features.duplicated(KEYS).any() or df_risk.duplicated(KEYS).any():
        raise ValueError("Duplicate sample keys in E3b caches")

    df = df_features.merge(df_risk[KEYS + target_cols], on=KEYS, how="inner", validate="one_to_one")
    if len(df) != len(df_features) or len(df) != len(df_risk):
        raise ValueError(
            f"Cache key mismatch: features={len(df_features)}, risk={len(df_risk)}, merged={len(df)}"
        )
    if not np.isfinite(df[target_cols].to_numpy(dtype=float)).all():
        raise ValueError("Risk-curve cache contains non-finite values")
    return df.sort_values(KEYS).reset_index(drop=True), target_cols


def combo_mask(df, combos):
    combo_set = {(float(beta), float(gamma_ratio), int(n)) for beta, gamma_ratio, n in combos}
    return np.fromiter(
        (
            (float(row.beta), float(row.gamma_over_eta), int(row.n)) in combo_set
            for row in df.itertuples(index=False)
        ),
        dtype=bool,
        count=len(df),
    )


def split_fold(df, fold_number):
    folds = e3b.get_combo_split()
    if fold_number < 1 or fold_number > len(folds):
        raise ValueError(f"fold_number must be 1..{len(folds)}")
    fold = folds[fold_number - 1]
    train_mask = combo_mask(df, fold["train_combos"])
    test_mask = combo_mask(df, fold["test_combos"])
    if np.any(train_mask & test_mask) or np.any(~(train_mask | test_mask)):
        raise ValueError("Fold membership is not a complete disjoint partition")
    return train_mask, test_mask, fold


def build_feature_inputs(df_train, df_test, include_n=True):
    means = df_train[e3b.FEATURE_COLS_ZSCORE].mean(axis=0)
    stds = df_train[e3b.FEATURE_COLS_ZSCORE].std(axis=0, ddof=0).replace(0, 1.0)

    def transform(df):
        z = (df[e3b.FEATURE_COLS_ZSCORE] - means) / stds
        raw_cols = list(e3b.FEATURE_COLS_RAW)
        if not include_n:
            raw_cols.remove("n")
        raw = df[raw_cols].astype(float)
        return np.hstack([z.to_numpy(dtype=np.float32), raw.to_numpy(dtype=np.float32)])

    return transform(df_train), transform(df_test), {
        "zscore_means": {key: float(value) for key, value in means.items()},
        "zscore_stds": {key: float(value) for key, value in stds.items()},
    }


def reconstruct_sorted_samples(df):
    samples = []
    for row in df.itertuples(index=False):
        eta = float(row.eta)
        gamma = float(row.gamma_over_eta) * eta
        sample = e3b.generate_sample(
            float(row.beta), eta, gamma, int(row.n), int(row.repeat_id), seed=e3b.SEED_NAMESPACE
        )
        sample = np.sort(np.asarray(sample, dtype=np.float64))
        if len(sample) != int(row.n) or len(sample) > RAW_MAX_N:
            raise ValueError(f"Unexpected reconstructed sample length: {len(sample)}")
        samples.append(sample)
    return samples


def fit_raw_scaler(train_samples):
    all_values = np.concatenate(train_samples)
    mean = float(all_values.mean())
    std = float(all_values.std(ddof=0))
    if std < 1e-12:
        std = 1.0
    return mean, std


def encode_sorted_samples(samples, mean, std):
    """Encode variable-length sorted samples as values + mask + n."""
    X = np.zeros((len(samples), RAW_MAX_N * 2 + 1), dtype=np.float32)
    for row_idx, sample in enumerate(samples):
        n = len(sample)
        X[row_idx, :n] = ((sample - mean) / std).astype(np.float32)
        X[row_idx, RAW_MAX_N:RAW_MAX_N + n] = 1.0
        X[row_idx, -1] = float(n)
    return X


def evaluate_predictions(df_test, Y_test, Y_pred):
    selected_idx = np.argmin(Y_pred, axis=1)
    selected_loss = Y_test[np.arange(len(Y_test)), selected_idx]
    result = {
        "pooled_J1": float(math.sqrt(float(np.mean(selected_loss)))),
        "mean_selected_loss": float(np.mean(selected_loss)),
    }
    per_n = {}
    n_values = df_test["n"].to_numpy(dtype=int)
    for n in sorted(np.unique(n_values)):
        mask = n_values == n
        per_n[str(int(n))] = {
            "J1": float(math.sqrt(float(np.mean(selected_loss[mask])))),
            "n_samples": int(mask.sum()),
        }
    result["per_n"] = per_n
    return result, selected_idx, selected_loss


def train_and_evaluate(name, X_train, Y_train, X_test, df_test, Y_test, seed, max_iter):
    started = time.perf_counter()
    Y_pred, n_iter = e3b.train_vector_mlp(
        X_train,
        Y_train,
        X_test,
        seed=seed,
        max_iter=max_iter,
        hidden_layers=e3b.MLP_HIDDEN_LAYERS,
        batch_size=e3b.MLP_BATCH_SIZE,
    )
    runtime = time.perf_counter() - started
    metrics, selected_idx, selected_loss = evaluate_predictions(df_test, Y_test, Y_pred)
    metrics.update({
        "model": name,
        "runtime_seconds": float(runtime),
        "training_iterations": int(n_iter),
        "input_dimension": int(X_train.shape[1]),
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
    })
    return metrics, selected_idx, selected_loss


def train_routed_n_specialists(df_train, df_test, target_cols, seed, max_iter):
    """Train one feature model per known sample size and route test rows by n."""
    routed_idx = np.empty(len(df_test), dtype=int)
    routed_loss = np.empty(len(df_test), dtype=np.float32)
    components = {}

    for n in sorted(df_train["n"].unique()):
        train_mask = df_train["n"].to_numpy(dtype=int) == int(n)
        test_mask = df_test["n"].to_numpy(dtype=int) == int(n)
        if not train_mask.any() or not test_mask.any():
            raise ValueError(f"Missing train or test rows for specialist n={n}")

        specialist_train = df_train.loc[train_mask].reset_index(drop=True)
        specialist_test = df_test.loc[test_mask].reset_index(drop=True)
        X_train, X_test, scaler = build_feature_inputs(
            specialist_train, specialist_test, include_n=False
        )
        Y_train = specialist_train[target_cols].to_numpy(dtype=np.float32)
        Y_test = specialist_test[target_cols].to_numpy(dtype=np.float32)
        metrics, selected_idx, selected_loss = train_and_evaluate(
            f"summary_features_specialist_n{int(n)}",
            X_train,
            Y_train,
            X_test,
            specialist_test,
            Y_test,
            seed,
            max_iter,
        )
        components[str(int(n))] = {"metrics": metrics, "scaler": scaler}
        routed_idx[test_mask] = selected_idx
        routed_loss[test_mask] = selected_loss

    per_n = {
        n: components[n]["metrics"]["per_n"][n]
        for n in sorted(components, key=int)
    }
    aggregate = {
        "pooled_J1": float(math.sqrt(float(np.mean(routed_loss)))),
        "mean_selected_loss": float(np.mean(routed_loss)),
        "per_n": per_n,
        "model": "routed_known_n_specialists_12",
        "runtime_seconds": float(sum(item["metrics"]["runtime_seconds"] for item in components.values())),
        "training_iterations": int(sum(item["metrics"]["training_iterations"] for item in components.values())),
        "component_iterations": {
            n: item["metrics"]["training_iterations"] for n, item in components.items()
        },
        "input_dimension": len(FEATURE_FIELDS_WITHOUT_N),
        "train_samples": int(len(df_train)),
        "test_samples": int(len(df_test)),
        "model_count": len(components),
    }
    return aggregate, routed_idx, routed_loss, components


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fold", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-iter", type=int, default=e3b.MLP_MAX_ITER)
    args = parser.parse_args()

    os.makedirs(PILOT_DIR, exist_ok=True)
    df, target_cols = load_cached_samples()
    train_mask, test_mask, fold = split_fold(df, args.fold)
    df_train = df.loc[train_mask].reset_index(drop=True)
    df_test = df.loc[test_mask].reset_index(drop=True)
    Y_train = df_train[target_cols].to_numpy(dtype=np.float32)
    Y_test = df_test[target_cols].to_numpy(dtype=np.float32)

    X_feature_train, X_feature_test, feature_scaler = build_feature_inputs(df_train, df_test)
    X_feature_no_n_train, X_feature_no_n_test, _ = build_feature_inputs(
        df_train, df_test, include_n=False
    )
    train_raw_samples = reconstruct_sorted_samples(df_train)
    test_raw_samples = reconstruct_sorted_samples(df_test)
    raw_mean, raw_std = fit_raw_scaler(train_raw_samples)
    X_raw_train = encode_sorted_samples(train_raw_samples, raw_mean, raw_std)
    X_raw_test = encode_sorted_samples(test_raw_samples, raw_mean, raw_std)

    feature_metrics, feature_idx, feature_loss = train_and_evaluate(
        "summary_features_13",
        X_feature_train,
        Y_train,
        X_feature_test,
        df_test,
        Y_test,
        args.seed,
        args.max_iter,
    )
    feature_no_n_metrics, feature_no_n_idx, feature_no_n_loss = train_and_evaluate(
        "summary_features_12_without_n",
        X_feature_no_n_train,
        Y_train,
        X_feature_no_n_test,
        df_test,
        Y_test,
        args.seed,
        args.max_iter,
    )
    specialist_metrics, specialist_idx, specialist_loss, specialist_components = (
        train_routed_n_specialists(
            df_train, df_test, target_cols, args.seed, args.max_iter
        )
    )
    raw_metrics, raw_idx, raw_loss = train_and_evaluate(
        "sorted_raw_masked",
        X_raw_train,
        Y_train,
        X_raw_test,
        df_test,
        Y_test,
        args.seed,
        args.max_iter,
    )

    feature_j1 = feature_metrics["pooled_J1"]
    feature_no_n_j1 = feature_no_n_metrics["pooled_J1"]
    raw_j1 = raw_metrics["pooled_J1"]
    specialist_j1 = specialist_metrics["pooled_J1"]
    relative_change = (raw_j1 - feature_j1) / feature_j1
    no_n_relative_change = (feature_no_n_j1 - feature_j1) / feature_j1
    specialist_vs_unified_no_n = (specialist_j1 - feature_no_n_j1) / feature_no_n_j1
    specialist_vs_full = (specialist_j1 - feature_j1) / feature_j1
    comparison = pd.DataFrame(
        [feature_metrics, feature_no_n_metrics, specialist_metrics, raw_metrics]
    )
    comparison.to_csv(os.path.join(PILOT_DIR, "comparison.csv"), index=False)

    predictions = df_test[KEYS].copy()
    predictions["feature_delta"] = [e3b.DELTA_GRID[idx] for idx in feature_idx]
    predictions["feature_true_loss"] = feature_loss
    predictions["feature_without_n_delta"] = [e3b.DELTA_GRID[idx] for idx in feature_no_n_idx]
    predictions["feature_without_n_true_loss"] = feature_no_n_loss
    predictions["specialist_delta"] = [e3b.DELTA_GRID[idx] for idx in specialist_idx]
    predictions["specialist_true_loss"] = specialist_loss
    predictions["raw_delta"] = [e3b.DELTA_GRID[idx] for idx in raw_idx]
    predictions["raw_true_loss"] = raw_loss
    predictions.to_csv(os.path.join(PILOT_DIR, "selected_predictions.csv"), index=False)

    summary = {
        "status": "PILOT_ONLY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fold": fold["fold_name"],
        "seed": args.seed,
        "max_iter": args.max_iter,
        "models": [feature_metrics, feature_no_n_metrics, specialist_metrics, raw_metrics],
        "specialist_components": specialist_components,
        "raw_minus_feature_relative_J1": float(relative_change),
        "raw_minus_feature_absolute_J1": float(raw_j1 - feature_j1),
        "without_n_minus_full_feature_relative_J1": float(no_n_relative_change),
        "without_n_minus_full_feature_absolute_J1": float(feature_no_n_j1 - feature_j1),
        "specialist_minus_unified_without_n_relative_J1": float(specialist_vs_unified_no_n),
        "specialist_minus_unified_without_n_absolute_J1": float(specialist_j1 - feature_no_n_j1),
        "specialist_minus_full_feature_relative_J1": float(specialist_vs_full),
        "specialist_minus_full_feature_absolute_J1": float(specialist_j1 - feature_j1),
        "interpretation_boundary": (
            "One fold and one seed only; this is an input-representation sensitivity check, "
            "not formal multi-fold/multi-seed evidence or a general superiority claim."
        ),
        "feature_input_fields": e3b.SAMPLE_FEATURE_COLS,
        "feature_input_fields_without_n": FEATURE_FIELDS_WITHOUT_N,
        "raw_input_fields": RAW_INPUT_FIELDS,
        "raw_representation": {
            "description": "sorted raw observations, train-only scalar z-score, right padding to n=20, explicit mask, n",
            "train_value_mean": raw_mean,
            "train_value_std": raw_std,
        },
        "feature_scaler": feature_scaler,
        "test_combos": [list(combo) for combo in fold["test_combos"]],
        "source_caches": [FEATURE_CACHE, RISK_CACHE],
    }
    with open(os.path.join(PILOT_DIR, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    print(json.dumps({
        "feature_pooled_J1": feature_j1,
        "feature_without_n_pooled_J1": feature_no_n_j1,
        "specialist_pooled_J1": specialist_j1,
        "raw_pooled_J1": raw_j1,
        "raw_minus_feature_relative_J1": relative_change,
        "without_n_minus_full_feature_relative_J1": no_n_relative_change,
        "specialist_minus_unified_without_n_relative_J1": specialist_vs_unified_no_n,
        "output_dir": PILOT_DIR,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
