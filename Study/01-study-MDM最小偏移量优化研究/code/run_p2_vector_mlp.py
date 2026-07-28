"""P2 Vector-MLP adapter over the frozen E4d production implementation."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))

import run_E4_formal_validation as e4  # noqa: E402
from config import STUDY_ROOT  # noqa: E402
from p2_config import (  # noqa: E402
    OUTPUT_DIR_NAME,
    P2_APPROVED_PARENT_COMMIT,
    P2_FORMAL_AUTHORIZED,
    P2_TOTAL_COMBOS,
    REPEATS,
    SEED_NAMESPACE,
    build_p2_combos,
)
from run_p2_evaluate import (  # noqa: E402
    apply_failure_contract,
    evaluate_baselines,
    load_p2_risk_data,
    write_csv_atomic,
    write_json_atomic,
)
from run_p2_generate import (  # noqa: E402
    _git,
    _input_hashes,
    _sha256_file,
    _write_text_atomic,
    run_smoke as generate_smoke,
)

P2_DIR = Path(STUDY_ROOT) / "artifacts" / "formal" / OUTPUT_DIR_NAME


class P2VectorError(RuntimeError):
    """Fail-closed Vector-MLP error."""


def _read_and_verify_sha256sums(root: Path) -> set[str]:
    sums_path = root / "SHA256SUMS"
    if not sums_path.is_file():
        raise P2VectorError(f"missing SHA256SUMS: {root}")
    entries: dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if (
            len(parts) != 2
            or len(parts[0]) != 64
            or any(ch not in "0123456789abcdef" for ch in parts[0].lower())
        ):
            raise P2VectorError(f"malformed SHA256SUMS line: {line[:80]}")
        digest, relative = parts
        relative = relative.strip()
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise P2VectorError(f"unsafe SHA256SUMS path: {relative}")
        if relative in entries:
            raise P2VectorError(f"duplicate SHA256SUMS entry: {relative}")
        entries[relative] = digest
    for relative, expected in entries.items():
        path = root / relative
        if not path.is_file() or _sha256_file(path) != expected:
            raise P2VectorError(f"SHA256 mismatch or missing file: {relative}")
    return set(entries)


def validate_evaluation_preflight(
    p2_dir: Path,
    *,
    formal: bool,
) -> dict:
    """Bind evaluation to the generation context, clean HEAD, and sealed inputs."""
    p2_dir = p2_dir.resolve()
    if formal:
        if p2_dir != P2_DIR.resolve():
            raise P2VectorError("formal evaluation must use the frozen P2 directory")
        if not P2_FORMAL_AUTHORIZED:
            raise P2VectorError("P2 formal evaluation is sealed")
        if not P2_APPROVED_PARENT_COMMIT:
            raise P2VectorError("approved parent commit is not bound")
        if _git("rev-parse", "HEAD^") != P2_APPROVED_PARENT_COMMIT:
            raise P2VectorError(
                "evaluation HEAD is not the direct child of the approved parent"
            )
    context_path = p2_dir / "run_context.json"
    manifest_path = p2_dir / "manifest.json"
    if not context_path.is_file() or not manifest_path.is_file():
        raise P2VectorError("generation context or manifest missing")
    context = json.loads(context_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    head = _git("rev-parse", "HEAD")
    if _git("status", "--porcelain"):
        raise P2VectorError("worktree must be fully clean before evaluation")
    if context.get("generation_commit") != head:
        raise P2VectorError("evaluation HEAD differs from generation commit")
    if context.get("input_hashes") != _input_hashes():
        raise P2VectorError("evaluation input code/config hashes changed")
    if manifest.get("generation_commit") != head:
        raise P2VectorError("manifest generation commit mismatch")
    if context.get("approved_parent_commit", "") != P2_APPROVED_PARENT_COMMIT:
        raise P2VectorError("generation approved-parent binding mismatch")
    expected_combos = P2_TOTAL_COMBOS if formal else int(
        manifest.get("combo_counts", {}).get("total", -1)
    )
    if int(manifest.get("combo_counts", {}).get("total", -1)) != expected_combos:
        raise P2VectorError("generation combo count mismatch")
    chunk_paths = {
        f"chunks/{item['path']}" for item in manifest.get("chunks", [])
    }
    expected_generation = {
        "run_context.json",
        "progress.json",
        "manifest.json",
        *chunk_paths,
    }
    sealed = _read_and_verify_sha256sums(p2_dir)
    if sealed != expected_generation:
        raise P2VectorError("generation SHA256SUMS exact file set mismatch")
    actual = {
        path.relative_to(p2_dir).as_posix()
        for path in p2_dir.rglob("*")
        if path.is_file()
    }
    if actual != expected_generation | {"SHA256SUMS"}:
        raise P2VectorError("unknown, stale, or partial file in generation directory")
    return {"context": context, "manifest": manifest, "sealed": sorted(sealed)}


def _seal_complete_outputs(root: Path, expected_relative: set[str]) -> None:
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.resolve() != (root / "SHA256SUMS").resolve()
    }
    if actual != expected_relative:
        missing = sorted(expected_relative - actual)
        extra = sorted(actual - expected_relative)
        raise P2VectorError(
            f"final output set mismatch; missing={missing}, extra={extra}"
        )
    lines = [
        f"{_sha256_file(root / relative)}  {relative}"
        for relative in sorted(expected_relative)
    ]
    _write_text_atomic(root / "SHA256SUMS", "\n".join(lines) + "\n")
    if _read_and_verify_sha256sums(root) != expected_relative:
        raise P2VectorError("final SHA256 seal verification failed")


def write_complete_evaluation(
    output_dir: Path,
    rows: pd.DataFrame,
    model_summary: pd.DataFrame,
    baseline_rows: pd.DataFrame,
    summary: dict,
    *,
    generation_root: Path | None = None,
) -> None:
    """Atomically write all evaluation products, then seal their exact file set."""
    output_dir = output_dir.resolve()
    generation_root = (
        output_dir if generation_root is None else generation_root.resolve()
    )
    generation_files = {
        path.relative_to(output_dir).as_posix()
        for path in generation_root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if generation_root != output_dir:
        generation_files.add(
            (generation_root / "SHA256SUMS").relative_to(output_dir).as_posix()
        )
    names = {
        "p2_vector_per_sample.csv",
        "p2_vector_model_summary.csv",
        "p2_baseline_per_sample.csv",
        "p2_evaluation_summary.json",
    }
    existing = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
        and path.resolve() != (output_dir / "SHA256SUMS").resolve()
    }
    if existing != generation_files:
        raise P2VectorError("pre-write output set mismatch")
    for name in names:
        if (output_dir / name).exists():
            raise P2VectorError(f"refusing to overwrite evaluation output: {name}")
    write_csv_atomic(output_dir / "p2_vector_per_sample.csv", rows)
    write_csv_atomic(output_dir / "p2_vector_model_summary.csv", model_summary)
    write_csv_atomic(output_dir / "p2_baseline_per_sample.csv", baseline_rows)
    summary = dict(summary)
    summary["final_seal"] = {
        "generation_commit": _git("rev-parse", "HEAD"),
        "approved_parent_commit": P2_APPROVED_PARENT_COMMIT,
        "files_excluding_SHA256SUMS": len(generation_files | names),
    }
    write_json_atomic(output_dir / "p2_evaluation_summary.json", summary)
    _seal_complete_outputs(output_dir, generation_files | names)


def production_contract() -> dict:
    """Expose values from the production module; do not duplicate constants."""
    return {
        "feature_columns": list(e4.SAMPLE_FEATURE_COLS),
        "zscore_columns": list(e4.FEATURE_COLS_ZSCORE),
        "raw_columns": list(e4.FEATURE_COLS_RAW),
        "hidden_layers": tuple(e4.MLP_HIDDEN_LAYERS),
        "max_iter": int(e4.MLP_MAX_ITER),
        "batch_size": int(e4.MLP_BATCH_SIZE),
        "alpha": float(e4.MLP_ALPHA),
        "learning_rate": float(e4.MLP_LR),
        "validation_fraction": float(e4.MLP_VALIDATION_FRACTION),
        "n_iter_no_change": int(e4.MLP_N_ITER_NO_CHANGE),
        "seeds": list(e4.STABILITY_SEEDS),
        "folds": [
            {
                "fold_name": fold["fold_name"],
                "train_combos": [list(item) for item in fold["train_combos"]],
                "test_combos": [list(item) for item in fold["test_combos"]],
            }
            for fold in e4.get_combo_split()
        ],
    }


def verify_production_contract() -> dict:
    contract = production_contract()
    if len(contract["feature_columns"]) != 13:
        raise P2VectorError("production feature count is not 13")
    if len(contract["folds"]) != 5 or contract["seeds"] != [42, 2026, 3407]:
        raise P2VectorError("production fold/seed contract changed")
    split_path = (
        Path(STUDY_ROOT)
        / "artifacts"
        / "formal"
        / "E4_robustness"
        / "split_report.csv"
    )
    if not split_path.is_file():
        raise P2VectorError("E4 split_report.csv missing")
    reference = pd.read_csv(split_path)
    for fold in e4.get_combo_split():
        name = fold["fold_name"]
        actual = set(
            tuple(item)
            for item in reference.loc[
                reference["fold"] == name,
                ["test_beta", "test_gamma_over_eta", "test_n"],
            ].itertuples(index=False, name=None)
        )
        expected = set(tuple(item) for item in fold["test_combos"])
        if actual != expected:
            raise P2VectorError(f"fold mismatch versus split_report: {name}")
    return contract


def load_main_grid() -> pd.DataFrame:
    data, _ = e4.load_authoritative_main_chunks()
    return data


def prepare_main_training(df_mc: pd.DataFrame) -> pd.DataFrame:
    features = e4.build_feature_table_from_mc(df_mc)
    merged = df_mc.merge(
        features,
        on=e4.SAMPLE_KEYS,
        how="left",
        suffixes=("", "_feature"),
        validate="many_to_one",
    )
    merged = merged.drop(
        columns=[c for c in merged.columns if c.endswith("_feature")]
    )
    merged = e4.compute_loss(merged)
    if merged[e4.SAMPLE_FEATURE_COLS].isna().any().any():
        raise P2VectorError("main-grid production features contain missing values")
    return merged


def prepare_p2_features(
    p2_risk: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    combos = [
        (f"{track}_{beta:.2f}_{ge:.2f}_{n}", beta, ge, n)
        for track, beta, ge, n in build_p2_combos()
        if (
            (p2_risk["track"] == track)
            & np.isclose(p2_risk["beta"], beta)
            & np.isclose(p2_risk["gamma_over_eta"], ge)
            & (p2_risk["n"] == n)
        ).any()
    ]
    if not combos:
        raise P2VectorError("P2 risk data does not match frozen combos")
    risk = p2_risk.copy()
    risk["combo_id"] = risk.apply(
        lambda row: (
            f"{row['track']}_{float(row['beta']):.2f}_"
            f"{float(row['gamma_over_eta']):.2f}_{int(row['n'])}"
        ),
        axis=1,
    )
    features = e4.build_feature_table_for_combos(
        combos, risk, seed_ns=SEED_NAMESPACE
    )
    hash_table = (
        risk[
            [
                "combo_id",
                "repeat_id",
                "sample_sha256",
            ]
        ]
        .drop_duplicates()
        .copy()
    )
    features = features.merge(
        hash_table,
        on=["combo_id", "repeat_id"],
        how="left",
        validate="one_to_one",
    )
    if features["sample_sha256"].isna().any():
        raise P2VectorError("P2 features missing sample SHA256")
    return features, risk


def _training_fold(
    main_training: pd.DataFrame, fold: dict
) -> tuple[pd.DataFrame, dict, dict, float, np.ndarray, np.ndarray]:
    train_combos = set(tuple(item) for item in fold["train_combos"])
    combo_keys = list(
        zip(
            main_training["beta"],
            main_training["gamma_over_eta"],
            main_training["n"],
        )
    )
    mask = np.fromiter(
        (tuple(item) in train_combos for item in combo_keys),
        dtype=bool,
        count=len(combo_keys),
    )
    train = main_training.loc[mask].copy()
    means, stds = e4._fit_zscore_params(train)
    valid = train["loss"].dropna()
    if valid.empty:
        raise P2VectorError(f"{fold['fold_name']}: no valid training losses")
    penalty = float(np.nanpercentile(valid, 99))
    train["loss_filled"] = train["loss"].fillna(penalty)
    samples, targets = e4._pivot_risk_vectors(
        train, "loss_filled", penalty
    )
    if len(samples) != 36_000 or targets.shape != (36_000, len(e4.DELTA_GRID)):
        raise P2VectorError(
            f"{fold['fold_name']}: unexpected production training shape "
            f"{len(samples)} / {targets.shape}"
        )
    inputs = e4._build_X_from_samples(samples, means, stds)
    return train, means, stds, penalty, inputs, targets


def _track_rows(
    model,
    target_scaler,
    p2_features: pd.DataFrame,
    p2_loss: pd.DataFrame,
    means: dict,
    stds: dict,
    penalty: float,
    fold_name: str,
    seed: int,
) -> list[dict]:
    rows: list[dict] = []
    for track in sorted(p2_loss["track"].unique()):
        loss_track = p2_loss[p2_loss["track"] == track]
        lookup_columns = [
            "beta", "gamma_over_eta", "n", "repeat_id", "delta",
        ]
        if loss_track.duplicated(lookup_columns).any():
            raise P2VectorError(f"{track}: duplicate realized-loss keys")
        realized_lookup = {
            (
                float(row.beta),
                float(row.gamma_over_eta),
                int(row.n),
                int(row.repeat_id),
                float(row.delta),
            ): row
            for row in loss_track.itertuples(index=False)
        }
        combo_ids = set(loss_track["combo_id"].unique())
        feat_track = p2_features[p2_features["combo_id"].isin(combo_ids)]
        evaluated = e4._evaluate_single_model_indexed(
            model,
            target_scaler,
            feat_track,
            loss_track,
            means,
            stds,
            penalty,
            fold_name,
            seed,
        )
        hash_lookup = feat_track.set_index(
            ["beta", "gamma_over_eta", "n", "repeat_id"]
        )["sample_sha256"]
        for row in evaluated:
            key = (
                row["beta"],
                row["gamma_over_eta"],
                row["n"],
                row["repeat_id"],
            )
            row["sample_sha256"] = hash_lookup.loc[key]
            row["track"] = track
            row["model"] = "Vector-MLP-L6"
            row["failure_penalty"] = penalty
            realized = realized_lookup.get(
                (
                    float(row["beta"]),
                    float(row["gamma_over_eta"]),
                    int(row["n"]),
                    int(row["repeat_id"]),
                    float(row["selected_delta"]),
                )
            )
            if realized is None:
                resolved = apply_failure_contract(
                    None, "failed", "missing_selected_delta", penalty
                )
            else:
                resolved = apply_failure_contract(
                    getattr(realized, "loss", np.nan),
                    getattr(realized, "status", ""),
                    getattr(realized, "failure_reason", ""),
                    penalty,
                )
            row.update(resolved)
        rows.extend(evaluated)
    return rows


def _model_summaries(rows: pd.DataFrame) -> pd.DataFrame:
    records = []
    for (track, fold, seed), group in rows.groupby(
        ["track", "fold", "seed"], sort=True
    ):
        records.append(
            {
                "track": track,
                "fold": fold,
                "seed": int(seed),
                "model": "Vector-MLP-L6",
                "n_samples": int(len(group)),
                "n_failed": int(group["failed"].sum()),
                "failure_rate": float(group["failed"].mean()),
                "pooled_J1": math.sqrt(float(group["true_loss"].mean())),
                "endpoint_rate": float(
                    group["selected_delta"].isin([0.00, 0.02, 0.48, 0.50]).mean()
                ),
                "mean_regret": float(group["regret"].mean()),
            }
        )
    return pd.DataFrame(records)


def _cross_model_summary(model_summary: pd.DataFrame) -> dict:
    output = {}
    for track, group in model_summary.groupby("track", sort=True):
        values = group["pooled_J1"].to_numpy(dtype=float)
        output[track] = {
            "n_models": int(len(values)),
            "min": float(np.min(values)),
            "Q1": float(np.quantile(values, 0.25)),
            "median": float(np.median(values)),
            "Q3": float(np.quantile(values, 0.75)),
            "max": float(np.max(values)),
            "mean": float(np.mean(values)),
            "SD": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
        }
    return output


def run_vector_evaluation(
    p2_risk: pd.DataFrame,
    folds: list[dict] | None = None,
    seeds: list[int] | None = None,
    run_reproduction_gate: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    verify_production_contract()
    main_grid = load_main_grid()
    if run_reproduction_gate:
        gate = e4._e3b_reproduction_gate_check(main_grid)
        if not gate.get("overall_pass"):
            raise P2VectorError("live E3b reproduction gate failed")
    main_training = prepare_main_training(main_grid)
    p2_features, p2_loss = prepare_p2_features(p2_risk)
    folds = list(e4.get_combo_split() if folds is None else folds)
    seeds = list(e4.STABILITY_SEEDS if seeds is None else seeds)
    all_rows = []
    training_receipts = []
    for fold in folds:
        _, means, stds, penalty, inputs, targets = _training_fold(
            main_training, fold
        )
        for seed in seeds:
            started = time.time()
            model, target_scaler = e4._train_mlp(inputs, targets, seed)
            rows = _track_rows(
                model,
                target_scaler,
                p2_features,
                p2_loss,
                means,
                stds,
                penalty,
                fold["fold_name"],
                seed,
            )
            all_rows.extend(rows)
            training_receipts.append(
                {
                    "fold": fold["fold_name"],
                    "seed": seed,
                    "failure_penalty": penalty,
                    "n_train_samples": int(len(inputs)),
                    "n_iter": int(model.n_iter_),
                    "elapsed_s": time.time() - started,
                }
            )
    per_sample = pd.DataFrame(all_rows)
    expected = (
        p2_features[["combo_id", "repeat_id"]].drop_duplicates().shape[0]
        * len(folds)
        * len(seeds)
    )
    if len(per_sample) != expected:
        raise P2VectorError(
            f"Vector rows={len(per_sample)}, expected={expected}"
        )
    key_columns = ["track", "fold", "seed", "beta", "gamma_over_eta", "n", "repeat_id"]
    if per_sample.duplicated(key_columns).any():
        raise P2VectorError("duplicate Vector-MLP per-sample keys")
    model_summary = _model_summaries(per_sample)
    summary = {
        "production_contract": production_contract(),
        "training_receipts": training_receipts,
        "cross_model_distribution": _cross_model_summary(model_summary),
    }
    return per_sample, model_summary, summary


def run_smoke(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=False)
    generation_dir = output_dir / "generation"
    generate_smoke(generation_dir)
    validate_evaluation_preflight(generation_dir, formal=False)
    risk = load_p2_risk_data(
        p2_dir=generation_dir,
        combos=build_p2_combos()[:1],
        repeats=2,
    )
    rows, model_summary, summary = run_vector_evaluation(
        risk,
        folds=e4.get_combo_split()[:1],
        seeds=e4.STABILITY_SEEDS[:1],
        run_reproduction_gate=False,
    )
    baselines, baseline_summary = evaluate_baselines(
        risk, summary["training_receipts"]
    )
    summary["baseline_summary"] = baseline_summary
    write_complete_evaluation(
        output_dir,
        rows,
        model_summary,
        baselines,
        summary,
        generation_root=generation_dir,
    )
    return {
        "vector_rows": len(rows),
        "model_rows": len(model_summary),
        "baseline_rows": len(baselines),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", type=Path)
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    if args.smoke is not None:
        receipt = run_smoke(args.smoke.resolve())
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0
    if not args.full:
        parser.error("choose --smoke PATH or --full")
    if not P2_FORMAL_AUTHORIZED:
        raise P2VectorError(
            "P2 formal evaluation is sealed; request exact-commit authorization"
        )
    validate_evaluation_preflight(P2_DIR, formal=True)
    risk = load_p2_risk_data()
    rows, model_summary, summary = run_vector_evaluation(
        risk, run_reproduction_gate=True
    )
    baseline_rows, baseline_summary = evaluate_baselines(
        risk, summary["training_receipts"]
    )
    summary["baseline_summary"] = baseline_summary
    write_complete_evaluation(
        P2_DIR,
        rows,
        model_summary,
        baseline_rows,
        summary,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
