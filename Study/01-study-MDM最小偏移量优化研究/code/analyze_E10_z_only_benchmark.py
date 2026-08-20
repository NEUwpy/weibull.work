"""Estimate an empirical Z-only conditional-risk benchmark for Study01.

This is a bounded mechanism experiment, not a replacement production method.
It reuses the frozen 160-cell, 300-repeat, 26-delta loss scan and never reruns
MDM.  The only predictor input is

    Z = sort(X) / mean(X)

for a fixed sample size n.  True parameters are used only to create the
Monte-Carlo loss labels and to score the held-out decisions.

The design separates model screening from confirmation:

* repeats 0..159: candidate fitting;
* repeats 160..199: candidate selection;
* repeats 200..299: untouched confirmation.

The selected flexible regressor is an empirical upper bound on the minimum
Z-only risk, not an exact Bayes-risk calculation.  L6 remains the grid-restricted
complete-information lower reference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import Ridge
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler


HERE = Path(__file__).resolve().parent
STUDY_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import dim_raw_config as CFG
import run_E6b_dimensional_raw_specialist as E6


CONTRACT = "E10_z_only_benchmark_v1"
OUTPUT_DIR = (
    STUDY_ROOT / "artifacts" / "candidate" / "E10_z_only_benchmark"
)
PAPER_PREDICTION_DIR = (
    STUDY_ROOT / "artifacts" / "formal" / "E5_normalized_raw" /
    "specialist" / "predictions"
)

FIT_REPEATS = frozenset(range(0, 160))
VALIDATION_REPEATS = frozenset(range(160, 200))
DEVELOPMENT_REPEATS = frozenset(range(0, 200))
CONFIRMATION_REPEATS = frozenset(range(200, 300))
SEED = 42
DEFAULT_INDEX = int(
    np.flatnonzero(np.isclose(np.asarray(CFG.DELTA_GRID), CFG.DEFAULT_DELTA))[0]
)
SAMPLE_KEYS = list(E6.SAMPLE_KEYS)
CANDIDATES = ("ridge", "knn", "extra_trees", "mlp_current", "mlp_wide")
LEARNING_REPEATS_PER_CELL = (40, 80, 120, 160, 200)


def sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def git_value(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=STUDY_ROOT, text=True
    ).strip()


def mean_normalize(sample: np.ndarray) -> np.ndarray:
    sample = np.asarray(sample, dtype=np.float64)
    mean = float(np.mean(sample))
    if not np.isfinite(mean) or mean <= 0:
        raise ValueError("sample mean must be positive and finite")
    return np.sort(sample) / mean


def repeat_partition(repeat_id: int) -> str:
    repeat_id = int(repeat_id)
    if repeat_id in FIT_REPEATS:
        return "fit"
    if repeat_id in VALIDATION_REPEATS:
        return "validation"
    if repeat_id in CONFIRMATION_REPEATS:
        return "confirmation"
    raise ValueError(f"repeat_id outside frozen range: {repeat_id}")


def prepare_data() -> tuple[pd.DataFrame, dict, dict]:
    print("[E10] loading frozen 160-cell scan", flush=True)
    scan = E6.load_mc_scan()
    manifest = json.loads(Path(CFG.MC_MANIFEST_PATH).read_text(encoding="utf-8"))
    integrity = E6.verify_data_integrity(scan, manifest)
    scan = E6.compute_per_sample_loss(scan)
    if scan["loss"].isna().any():
        # The frozen E5 data currently have no failures.  Keep a deterministic
        # fallback so the analysis remains well-defined if that changes.
        for n_value in CFG.N_GRID:
            mask = (scan["n"] == n_value) & scan["repeat_id"].isin(FIT_REPEATS)
            penalty = float(np.nanpercentile(scan.loc[mask, "loss"], 99))
            scan.loc[scan["n"] == n_value, "loss"] = (
                scan.loc[scan["n"] == n_value, "loss"].fillna(penalty)
            )
    scan["loss_filled"] = scan["loss"]
    scan["is_valid"] = scan["status"].eq("success") & scan["loss"].notna()

    raw_map, _ = E6.build_raw_sample_map(scan)
    z_map = {key: mean_normalize(value) for key, value in raw_map.items()}
    return scan, z_map, integrity


def matrices_for_n(
    scan: pd.DataFrame, z_map: dict, n_value: int
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    keys, x, y, _ = E6.pivot_raw_vector(scan, z_map, int(n_value))
    if len(keys) != 40 * CFG.REPEATS:
        raise RuntimeError(f"n={n_value}: unexpected sample count {len(keys)}")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise RuntimeError(f"n={n_value}: non-finite matrix")
    if not np.allclose(x.mean(axis=1), 1.0, rtol=0.0, atol=1e-12):
        raise RuntimeError(f"n={n_value}: input is not mean normalized")
    return keys, x, y


def _scaled_xy(
    x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, StandardScaler]:
    input_scaler = StandardScaler()
    target_scaler = StandardScaler()
    x_train_s = input_scaler.fit_transform(x_train)
    x_test_s = input_scaler.transform(x_test)
    y_train_s = target_scaler.fit_transform(y_train)
    return x_train_s, y_train_s, x_test_s, target_scaler


def safe_n_iter(model: object) -> int:
    """Return an integer iteration count for estimators that expose it."""
    value = getattr(model, "n_iter_", 0)
    if value is None:
        return 0
    array = np.asarray(value)
    return int(array.max()) if array.size else 0


def fit_predict(
    candidate: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
) -> tuple[np.ndarray, dict]:
    """Fit one predeclared conditional-risk learner and predict raw losses."""
    if candidate not in CANDIDATES:
        raise ValueError(candidate)
    x_train_s, y_train_s, x_test_s, target_scaler = _scaled_xy(
        x_train, y_train, x_test
    )
    started = time.time()
    if candidate == "ridge":
        model = Ridge(alpha=10.0)
    elif candidate == "knn":
        model = KNeighborsRegressor(
            n_neighbors=75, weights="distance", p=2, n_jobs=-1
        )
    elif candidate == "extra_trees":
        model = ExtraTreesRegressor(
            n_estimators=256,
            min_samples_leaf=2,
            max_features=1.0,
            random_state=SEED,
            n_jobs=-1,
        )
    else:
        hidden = (
            tuple(CFG.MLP_HIDDEN_LAYERS)
            if candidate == "mlp_current"
            else (512, 256, 128)
        )
        model = MLPRegressor(
            hidden_layer_sizes=hidden,
            activation="relu",
            solver="adam",
            alpha=CFG.MLP_ALPHA,
            learning_rate_init=CFG.MLP_LR,
            max_iter=CFG.MLP_MAX_ITER,
            early_stopping=True,
            validation_fraction=CFG.MLP_VALIDATION_FRACTION,
            n_iter_no_change=CFG.MLP_N_ITER_NO_CHANGE,
            random_state=SEED,
            batch_size=CFG.MLP_BATCH_SIZE,
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        model.fit(x_train_s, y_train_s)
    prediction_s = model.predict(x_test_s)
    prediction = target_scaler.inverse_transform(prediction_s)
    prediction = np.clip(prediction, 0.0, None)
    metadata = {
        "candidate": candidate,
        "fit_seconds": float(time.time() - started),
        "n_iter": safe_n_iter(model),
        "only_z_input": True,
    }
    return prediction, metadata


def selected_loss(prediction: np.ndarray, actual: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if prediction.shape != actual.shape:
        raise ValueError("prediction and actual loss curves must align")
    indices = np.argmin(prediction, axis=1)
    losses = actual[np.arange(len(actual)), indices]
    return indices.astype(int), losses.astype(float)


def j1(losses: np.ndarray) -> float:
    return float(math.sqrt(float(np.mean(np.asarray(losses, dtype=float)))))


def choose_candidates(
    scan: pd.DataFrame, z_map: dict
) -> tuple[dict[int, str], pd.DataFrame]:
    rows = []
    selected = {}
    for n_value in CFG.N_GRID:
        keys, x, y = matrices_for_n(scan, z_map, int(n_value))
        repeat_ids = keys["repeat_id"].to_numpy(dtype=int)
        fit_mask = np.isin(repeat_ids, list(FIT_REPEATS))
        validation_mask = np.isin(repeat_ids, list(VALIDATION_REPEATS))
        if fit_mask.sum() != 40 * 160 or validation_mask.sum() != 40 * 40:
            raise RuntimeError(f"n={n_value}: broken development split")
        for candidate in CANDIDATES:
            print(f"[E10 screen] n={n_value} candidate={candidate}", flush=True)
            prediction, metadata = fit_predict(
                candidate, x[fit_mask], y[fit_mask], x[validation_mask]
            )
            _, losses = selected_loss(prediction, y[validation_mask])
            rows.append({
                "n": int(n_value),
                "candidate": candidate,
                "validation_R": float(np.mean(losses)),
                "validation_J1": j1(losses),
                **metadata,
            })
        n_rows = [row for row in rows if row["n"] == int(n_value)]
        winner = min(n_rows, key=lambda row: (row["validation_R"], row["candidate"]))
        selected[int(n_value)] = str(winner["candidate"])
        print(
            f"[E10 screen] n={n_value} selected={winner['candidate']} "
            f"J1={winner['validation_J1']:.6f}", flush=True
        )
    return selected, pd.DataFrame(rows)


def load_paper_seed42() -> pd.DataFrame:
    frames = []
    for n_value in CFG.N_GRID:
        paths = sorted(PAPER_PREDICTION_DIR.glob(f"n{n_value}_fold*_seed42.csv"))
        if len(paths) != 5:
            raise FileNotFoundError(f"n={n_value}: expected 5 seed42 prediction files")
        frames.extend(pd.read_csv(path) for path in paths)
    result = pd.concat(frames, ignore_index=True)
    if result.duplicated(SAMPLE_KEYS).any() or len(result) != 48_000:
        raise RuntimeError("paper seed42 predictions do not form 48,000 unique samples")
    return result


def l5_choices_from_development(
    keys: pd.DataFrame, y: np.ndarray, development_mask: np.ndarray
) -> dict[tuple[float, float, int], int]:
    choices = {}
    work = keys.copy()
    for beta in CFG.BETA_GRID:
        for goe in CFG.GAMMA_OVER_ETA_GRID:
            cell = (
                development_mask
                & np.isclose(work["beta"].to_numpy(dtype=float), beta)
                & np.isclose(work["gamma_over_eta"].to_numpy(dtype=float), goe)
            )
            if int(cell.sum()) != len(DEVELOPMENT_REPEATS):
                raise RuntimeError(f"broken L5 development cell beta={beta}, goe={goe}")
            choices[(float(beta), float(goe), int(work["n"].iloc[0]))] = int(
                np.argmin(np.mean(y[cell], axis=0))
            )
    return choices


def confirmation_run(
    scan: pd.DataFrame,
    z_map: dict,
    selected_candidates: dict[int, str],
) -> pd.DataFrame:
    paper = load_paper_seed42()
    output_rows = []
    for n_value in CFG.N_GRID:
        keys, x, y = matrices_for_n(scan, z_map, int(n_value))
        repeat_ids = keys["repeat_id"].to_numpy(dtype=int)
        development_mask = np.isin(repeat_ids, list(DEVELOPMENT_REPEATS))
        confirmation_mask = np.isin(repeat_ids, list(CONFIRMATION_REPEATS))
        if development_mask.sum() != 40 * 200 or confirmation_mask.sum() != 40 * 100:
            raise RuntimeError(f"n={n_value}: broken confirmation split")

        candidate = selected_candidates[int(n_value)]
        print(f"[E10 confirm] n={n_value} candidate={candidate}", flush=True)
        prediction, _ = fit_predict(
            candidate, x[development_mask], y[development_mask], x[confirmation_mask]
        )
        z_indices, z_losses = selected_loss(prediction, y[confirmation_mask])
        if candidate == "mlp_current":
            in_domain_prediction = prediction
        else:
            print(f"[E10 confirm] n={n_value} current-architecture control", flush=True)
            in_domain_prediction, _ = fit_predict(
                "mlp_current",
                x[development_mask], y[development_mask], x[confirmation_mask],
            )
        in_domain_indices, in_domain_losses = selected_loss(
            in_domain_prediction, y[confirmation_mask]
        )
        confirm_keys = keys.loc[confirmation_mask].reset_index(drop=True)

        l5_choices = l5_choices_from_development(keys, y, development_mask)
        l5_indices = np.asarray([
            l5_choices[(float(row.beta), float(row.gamma_over_eta), int(n_value))]
            for row in confirm_keys.itertuples(index=False)
        ], dtype=int)
        y_confirm = y[confirmation_mask]
        l5_losses = y_confirm[np.arange(len(y_confirm)), l5_indices]
        l6_indices = np.argmin(y_confirm, axis=1)
        l6_losses = y_confirm[np.arange(len(y_confirm)), l6_indices]
        default_losses = y_confirm[:, DEFAULT_INDEX]

        paper_n = paper[
            (paper["n"] == int(n_value))
            & paper["repeat_id"].isin(CONFIRMATION_REPEATS)
        ].copy()
        paper_n = confirm_keys.merge(
            paper_n[SAMPLE_KEYS + ["selected_delta_idx", "true_loss"]],
            on=SAMPLE_KEYS,
            how="left",
            validate="one_to_one",
        )
        if paper_n[["selected_delta_idx", "true_loss"]].isna().any().any():
            raise RuntimeError(f"n={n_value}: missing paper predictions")
        paper_indices = paper_n["selected_delta_idx"].to_numpy(dtype=int)
        paper_losses = y_confirm[np.arange(len(y_confirm)), paper_indices]
        if not np.allclose(
            paper_losses, paper_n["true_loss"].to_numpy(dtype=float),
            rtol=0.0, atol=1e-12,
        ):
            raise RuntimeError(f"n={n_value}: paper true loss does not match scan")

        for i, row in confirm_keys.iterrows():
            output_rows.append({
                **{key: row[key] for key in SAMPLE_KEYS},
                "default_loss": float(default_losses[i]),
                "l5_loss": float(l5_losses[i]),
                "paper_mlp_loss": float(paper_losses[i]),
                "in_domain_current_mlp_loss": float(in_domain_losses[i]),
                "z_reference_loss": float(z_losses[i]),
                "l6_loss": float(l6_losses[i]),
                "l5_delta": float(CFG.DELTA_GRID[l5_indices[i]]),
                "paper_mlp_delta": float(CFG.DELTA_GRID[paper_indices[i]]),
                "in_domain_current_mlp_delta": float(
                    CFG.DELTA_GRID[in_domain_indices[i]]
                ),
                "z_reference_delta": float(CFG.DELTA_GRID[z_indices[i]]),
                "l6_delta": float(CFG.DELTA_GRID[l6_indices[i]]),
                "z_reference_candidate": candidate,
            })
    result = pd.DataFrame(output_rows)
    if len(result) != 16_000 or result.duplicated(SAMPLE_KEYS).any():
        raise RuntimeError("confirmation output must contain 16,000 unique samples")
    return result


def method_summary(sample_losses: pd.DataFrame) -> pd.DataFrame:
    methods = {
        "Default": "default_loss",
        "L5-parameter-conditional": "l5_loss",
        "Paper-MLP": "paper_mlp_loss",
        "In-domain-current-MLP": "in_domain_current_mlp_loss",
        "Z-only-empirical-reference": "z_reference_loss",
        "L6-complete-information": "l6_loss",
    }
    rows = []
    for method, column in methods.items():
        for n_value, group in [("pooled", sample_losses)] + list(
            sample_losses.groupby("n", sort=True)
        ):
            risk = float(group[column].mean())
            rows.append({
                "method": method,
                "n": n_value,
                "R_mean_loss": risk,
                "J1": math.sqrt(risk),
                "count": int(len(group)),
            })
    return pd.DataFrame(rows)


def gap_decomposition(sample_losses: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    risk = {
        name: float(sample_losses[column].mean())
        for name, column in {
            "default": "default_loss",
            "l5": "l5_loss",
            "paper_mlp": "paper_mlp_loss",
            "in_domain_current_mlp": "in_domain_current_mlp_loss",
            "z_reference": "z_reference_loss",
            "l6": "l6_loss",
        }.items()
    }
    rows = [
        {
            "component": "achieved_by_paper_mlp",
            "R_difference": risk["default"] - risk["paper_mlp"],
        },
        {
            "component": "paper_mlp_to_in_domain_current_architecture",
            "R_difference": (
                risk["paper_mlp"] - risk["in_domain_current_mlp"]
            ),
        },
        {
            "component": "current_architecture_to_flexible_reference",
            "R_difference": (
                risk["in_domain_current_mlp"] - risk["z_reference"]
            ),
        },
        {
            "component": "z_reference_to_l6_remaining",
            "R_difference": risk["z_reference"] - risk["l6"],
        },
        {
            "component": "l5_to_l6_realization_value",
            "R_difference": risk["l5"] - risk["l6"],
        },
    ]
    total = risk["default"] - risk["l6"]
    for row in rows:
        row["share_of_default_to_l6"] = row["R_difference"] / total
    identity_error = abs(
        total - sum(row["R_difference"] for row in rows[:4])
    )
    status = (
        "TIGHTER_ACHIEVED_Z_ONLY_REFERENCE"
        if risk["z_reference"] < risk["paper_mlp"]
        else "REFERENCE_DID_NOT_BEAT_PAPER_MLP"
    )
    return pd.DataFrame(rows), {
        "risk": risk,
        "default_to_l6_R_gap": total,
        "additive_identity_abs_error": identity_error,
        "z_reference_status": status,
        "interpretation": (
            "In population, the risk of any fixed Z-only rule cannot be lower "
            "than the Z-only Bayes risk. The confirmation value here is a sample "
            "estimate for one achieved rule, not an exact Bayes risk or a formal "
            "finite-sample confidence bound on it."
        ),
    }


def paired_repeat_bootstrap(
    sample_losses: pd.DataFrame, n_boot: int = 20_000
) -> pd.DataFrame:
    comparisons = {
        "z_reference_minus_paper_mlp": ("z_reference_loss", "paper_mlp_loss"),
        "in_domain_current_mlp_minus_paper_mlp": (
            "in_domain_current_mlp_loss", "paper_mlp_loss"
        ),
        "z_reference_minus_in_domain_current_mlp": (
            "z_reference_loss", "in_domain_current_mlp_loss"
        ),
        "paper_mlp_minus_default": ("paper_mlp_loss", "default_loss"),
        "l5_minus_l6": ("l5_loss", "l6_loss"),
        "z_reference_minus_l6": ("z_reference_loss", "l6_loss"),
    }
    by_repeat = sample_losses.groupby("repeat_id", sort=True)[
        sorted({column for pair in comparisons.values() for column in pair})
    ].mean()
    if list(by_repeat.index) != list(range(200, 300)):
        raise RuntimeError("confirmation repeat blocks are incomplete")
    rng = np.random.default_rng(20260820)
    draws = rng.integers(0, len(by_repeat), size=(n_boot, len(by_repeat)))
    rows = []
    for name, (left, right) in comparisons.items():
        diff = by_repeat[left].to_numpy() - by_repeat[right].to_numpy()
        bootstrap = diff[draws].mean(axis=1)
        rows.append({
            "comparison": name,
            "R_difference": float(diff.mean()),
            "ci95_low": float(np.quantile(bootstrap, 0.025)),
            "ci95_high": float(np.quantile(bootstrap, 0.975)),
            "n_repeat_blocks": int(len(diff)),
            "n_bootstrap": int(n_boot),
        })
    return pd.DataFrame(rows)


def _entropy(values: pd.Series) -> float:
    probabilities = values.value_counts(normalize=True).to_numpy(dtype=float)
    return float(-(probabilities * np.log(probabilities)).sum())


def mechanism_by_cell(sample_losses: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Quantify realization-level variation without treating argmin as a label."""
    rows = []
    for (beta, goe, n_value), group in sample_losses.groupby(
        ["beta", "gamma_over_eta", "n"], sort=True
    ):
        if len(group) != len(CONFIRMATION_REPEATS):
            raise RuntimeError("mechanism cell must contain 100 confirmation samples")
        rows.append({
            "beta": float(beta),
            "gamma_over_eta": float(goe),
            "n": int(n_value),
            "count": int(len(group)),
            "l5_R": float(group["l5_loss"].mean()),
            "l6_R": float(group["l6_loss"].mean()),
            "l5_to_l6_R_gap": float(
                (group["l5_loss"] - group["l6_loss"]).mean()
            ),
            "paper_to_z_reference_R_gain": float(
                (group["paper_mlp_loss"] - group["z_reference_loss"]).mean()
            ),
            "l5_l6_delta_match_rate": float(
                np.isclose(group["l5_delta"], group["l6_delta"]).mean()
            ),
            "paper_l6_delta_match_rate": float(
                np.isclose(group["paper_mlp_delta"], group["l6_delta"]).mean()
            ),
            "z_reference_l6_delta_match_rate": float(
                np.isclose(group["z_reference_delta"], group["l6_delta"]).mean()
            ),
            "l6_delta_entropy_nats": _entropy(group["l6_delta"]),
            "l6_effective_delta_count": float(
                math.exp(_entropy(group["l6_delta"]))
            ),
        })
    table = pd.DataFrame(rows)
    pooled = {
        "l5_l6_delta_match_rate": float(
            np.isclose(sample_losses["l5_delta"], sample_losses["l6_delta"]).mean()
        ),
        "paper_l6_delta_match_rate": float(
            np.isclose(
                sample_losses["paper_mlp_delta"], sample_losses["l6_delta"]
            ).mean()
        ),
        "z_reference_l6_delta_match_rate": float(
            np.isclose(
                sample_losses["z_reference_delta"], sample_losses["l6_delta"]
            ).mean()
        ),
        "median_cell_l6_effective_delta_count": float(
            table["l6_effective_delta_count"].median()
        ),
    }
    return table, pooled


def learning_curve(
    scan: pd.DataFrame,
    z_map: dict,
    selected_candidates: dict[int, str],
) -> tuple[pd.DataFrame, dict]:
    """Diagnose whether the selected Z-only reference is still data limited."""
    rows = []
    for n_value in CFG.N_GRID:
        keys, x, y = matrices_for_n(scan, z_map, int(n_value))
        repeat_ids = keys["repeat_id"].to_numpy(dtype=int)
        confirm = np.isin(repeat_ids, list(CONFIRMATION_REPEATS))
        candidate = selected_candidates[int(n_value)]
        for repeats_per_cell in LEARNING_REPEATS_PER_CELL:
            train = (repeat_ids >= 0) & (repeat_ids < repeats_per_cell)
            expected_train = 40 * repeats_per_cell
            if int(train.sum()) != expected_train or int(confirm.sum()) != 4_000:
                raise RuntimeError("broken learning-curve partition")
            print(
                f"[E10 learning] n={n_value} candidate={candidate} "
                f"repeats_per_cell={repeats_per_cell}", flush=True,
            )
            prediction, metadata = fit_predict(
                candidate, x[train], y[train], x[confirm]
            )
            _, losses = selected_loss(prediction, y[confirm])
            rows.append({
                "n": int(n_value),
                "candidate": candidate,
                "repeats_per_cell": int(repeats_per_cell),
                "training_samples": int(train.sum()),
                "confirmation_samples": int(confirm.sum()),
                "R_mean_loss": float(np.mean(losses)),
                "J1": j1(losses),
                "fit_seconds": metadata["fit_seconds"],
            })
    table = pd.DataFrame(rows)
    pooled_rows = []
    for repeats_per_cell, group in table.groupby("repeats_per_cell", sort=True):
        # Every n contributes the same 4,000 confirmation samples.
        risk = float(group["R_mean_loss"].mean())
        pooled_rows.append({
            "repeats_per_cell": int(repeats_per_cell),
            "R_mean_loss": risk,
            "J1": math.sqrt(risk),
        })
    pooled = pd.DataFrame(pooled_rows)
    r160 = float(pooled.loc[pooled["repeats_per_cell"] == 160, "R_mean_loss"].iloc[0])
    r200 = float(pooled.loc[pooled["repeats_per_cell"] == 200, "R_mean_loss"].iloc[0])
    summary = {
        "pooled": pooled.to_dict(orient="records"),
        "R_change_160_to_200": r200 - r160,
        "relative_R_change_160_to_200": (r200 - r160) / r160,
        "interpretation_boundary": (
            "Repeated evaluation on the fixed confirmation set is descriptive; "
            "the curve diagnoses data sensitivity but is not used for model selection."
        ),
    }
    return table, summary


def write_report(summary: dict, method_table: pd.DataFrame) -> None:
    pooled = method_table[method_table["n"].astype(str) == "pooled"].set_index("method")
    risk = summary["gap_decomposition"]["risk"]
    lines = [
        "# E10 Z-only 条件风险经验参照",
        "",
        f"状态：`{summary['status']}`。本结果为机制研究候选证据，不是精确 Bayes 风险。",
        "",
        "## 设计",
        "",
        "- 输入仅为按样本量分别处理的 $Z=\\operatorname{sort}(X)/\\bar X$。",
        "- 160 个参数组合等权；不输入真参数、组合编号、repeat id 或原始尺度。",
        "- repeats 0–159 拟合，160–199 选择候选，200–299 作 untouched confirmation。",
        "- 复用既有 26 点损失，不重跑 MDM。",
        "",
        "## Confirmation 结果",
        "",
        "| 方法 | R=mean(loss) | J1 |",
        "|---|---:|---:|",
    ]
    for method in (
        "Default", "L5-parameter-conditional", "Paper-MLP",
        "In-domain-current-MLP",
        "Z-only-empirical-reference", "L6-complete-information",
    ):
        row = pooled.loc[method]
        lines.append(f"| {method} | {row.R_mean_loss:.8f} | {row.J1:.6f} |")
    lines.extend([
        "",
        "## 解释边界",
        "",
        f"- Z-only 经验参照状态：`{summary['gap_decomposition']['z_reference_status']}`。",
        "- L5 与 Z-only 使用不同信息，不能排列成单向层级。",
        "- L6 使用真参数与当前样本，是 26 点网格内的完全信息事后参照。",
        "- Z-only 经验参照只是一个已实现规则。在总体风险意义下，它位于"
        "$R_Z^*$ 之上；这里报告的是该规则的确认集估计值，不是精确 Bayes 风险或"
        "严格的有限样本界。",
        "- L6 给出逐样本的完全信息下界；经验参照与 L6 之间的距离仍混合了"
        "进一步可学习空间和完全信息差，不能全部归因于其中任何一项。",
        "- 可加差距使用 $R=J_1^2$，不直接加减 $J_1$。",
        "",
        "## 风险值",
        "",
        f"- Default: {risk['default']:.8f}",
        f"- Paper MLP: {risk['paper_mlp']:.8f}",
        f"- In-domain current architecture: {risk['in_domain_current_mlp']:.8f}",
        f"- Z-only empirical reference: {risk['z_reference']:.8f}",
        f"- L6: {risk['l6']:.8f}",
        "",
        "论文是否据此修改，需要先由 Mentor 审查统计含义和证据边界。",
        "",
    ])
    (OUTPUT_DIR / "candidate_report.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )


def run() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()
    scan, z_map, integrity = prepare_data()
    selected_candidates, validation = choose_candidates(scan, z_map)
    sample_losses = confirmation_run(scan, z_map, selected_candidates)
    methods = method_summary(sample_losses)
    gaps, gap_summary = gap_decomposition(sample_losses)
    bootstrap = paired_repeat_bootstrap(sample_losses)
    mechanism_cells, mechanism_summary = mechanism_by_cell(sample_losses)
    learning, learning_summary = learning_curve(scan, z_map, selected_candidates)

    validation.to_csv(OUTPUT_DIR / "validation_candidates.csv", index=False, lineterminator="\n")
    methods.to_csv(OUTPUT_DIR / "confirmation_by_method.csv", index=False, lineterminator="\n")
    gaps.to_csv(OUTPUT_DIR / "gap_decomposition.csv", index=False, lineterminator="\n")
    bootstrap.to_csv(OUTPUT_DIR / "paired_repeat_bootstrap.csv", index=False, lineterminator="\n")
    mechanism_cells.to_csv(
        OUTPUT_DIR / "mechanism_by_cell.csv", index=False, lineterminator="\n"
    )
    learning.to_csv(OUTPUT_DIR / "learning_curve.csv", index=False, lineterminator="\n")
    # The row-level confirmation table is needed for independent recomputation
    # but is compact enough to remain a candidate artifact.
    sample_losses.to_csv(
        OUTPUT_DIR / "confirmation_sample_losses.csv", index=False, lineterminator="\n"
    )

    summary = {
        "status": "CANDIDATE_MECHANISM_EVIDENCE",
        "contract": CONTRACT,
        "definition": (
            "Current 160-cell equal-weight design; Z=sort(X)/mean(X); "
            "26-point conditional expected loss decision."
        ),
        "partitions": {
            "fit": [0, 159],
            "validation": [160, 199],
            "confirmation": [200, 299],
        },
        "selected_candidates_by_n": {
            str(key): value for key, value in selected_candidates.items()
        },
        "confirmation_samples": int(len(sample_losses)),
        "input_integrity": integrity,
        "gap_decomposition": gap_summary,
        "realization_mechanism": mechanism_summary,
        "learning_curve": learning_summary,
        "runtime_seconds": float(time.time() - started),
        "seed": SEED,
        "candidate_set": list(CANDIDATES),
        "source_commit": git_value("rev-parse", "HEAD"),
        "source_manifest_sha256_lf": sha256_lf(Path(CFG.MC_MANIFEST_PATH)),
        "script_sha256_lf": sha256_lf(Path(__file__)),
        "limitations": [
            "The empirical reference is not the exact Bayes risk.",
            "The parameter-cell prior is uniform over the current discrete design.",
            "The result does not establish continuous-parameter or new-n generalization.",
            "Raw X and absolute scale are intentionally excluded.",
        ],
    }
    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    write_report(summary, methods)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", action="store_true",
        help="execute the bounded candidate experiment",
    )
    args = parser.parse_args()
    if not args.run:
        parser.error("explicit --run is required")
    run()


if __name__ == "__main__":
    main()
