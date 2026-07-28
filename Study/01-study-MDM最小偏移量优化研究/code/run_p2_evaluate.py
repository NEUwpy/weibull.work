"""Shared P2 evaluation helpers and fixed-delta baselines."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))

from p2_config import (  # noqa: E402
    DEFAULT_DELTA,
    L1_DELTA,
    OUTPUT_DIR_NAME,
    REPEATS,
    build_p2_combos,
)
from config import STUDY_ROOT  # noqa: E402
from run_p2_generate import _chunk_path, validate_chunk  # noqa: E402
import run_E4_formal_validation as e4  # noqa: E402

P2_DIR = Path(STUDY_ROOT) / "artifacts" / "formal" / OUTPUT_DIR_NAME


class P2EvaluationError(RuntimeError):
    """Fail-closed evaluation error."""


def apply_failure_contract(
    loss: float | None,
    status: str,
    failure_reason: str,
    failure_penalty: float,
) -> dict:
    """Apply the single P2 per-model failure contract used by every method."""
    if not np.isfinite(failure_penalty) or failure_penalty < 0:
        raise P2EvaluationError("failure_penalty must be finite and non-negative")
    numeric_loss = float(loss) if loss is not None else np.nan
    reason = (
        "" if failure_reason is None or pd.isna(failure_reason)
        else str(failure_reason)
    )
    status_value = "" if status is None or pd.isna(status) else str(status)
    failed = (
        status_value != "success"
        or not np.isfinite(numeric_loss)
        or bool(reason)
    )
    if failed and not reason:
        reason = "missing_or_non_finite_loss"
    return {
        "failed": bool(failed),
        "failure_reason": reason,
        "true_loss_complete_case": numeric_loss if not failed else np.nan,
        "true_loss": failure_penalty if failed else numeric_loss,
    }


def load_p2_risk_data(
    p2_dir: Path = P2_DIR,
    combos: list[tuple[str, float, float, int]] | None = None,
    repeats: int = REPEATS,
) -> pd.DataFrame:
    combos = list(build_p2_combos() if combos is None else combos)
    frames = []
    for combo in combos:
        path = _chunk_path(*combo, chunks_dir=p2_dir / "chunks")
        validate_chunk(path, combo, repeats=repeats)
        frames.append(pd.read_csv(path))
    if not frames:
        raise P2EvaluationError("no P2 risk data")
    data = pd.concat(frames, ignore_index=True, sort=False)
    expected = len(combos) * repeats * len(e4.DELTA_GRID)
    if len(data) != expected:
        raise P2EvaluationError(f"P2 rows={len(data)}, expected={expected}")
    return e4.compute_loss(data)


def evaluate_fixed_delta(
    risk_data: pd.DataFrame,
    delta: float,
    model: str,
    failure_penalty: float,
) -> pd.DataFrame:
    """Return one realized-loss row per P2 sample."""
    sample_keys = [
        "track",
        "combo_id",
        "beta",
        "eta",
        "gamma",
        "gamma_over_eta",
        "n",
        "repeat_id",
        "sample_sha256",
    ]
    samples = risk_data[sample_keys].drop_duplicates()
    selected = risk_data[np.isclose(risk_data["delta"], delta)].copy()
    if selected.duplicated(sample_keys).any():
        raise P2EvaluationError(f"{model}: duplicate selected-delta rows")
    rows = samples.merge(
        selected[sample_keys + ["loss", "status", "failure_reason"]],
        on=sample_keys,
        how="left",
        validate="one_to_one",
    )
    resolved = rows.apply(
        lambda row: apply_failure_contract(
            row.get("loss"),
            row.get("status", ""),
            row.get("failure_reason", ""),
            failure_penalty,
        ),
        axis=1,
        result_type="expand",
    )
    for column in resolved.columns:
        rows[column] = resolved[column]
    rows["selected_delta"] = float(delta)
    rows["model"] = model
    return rows


def summarize_rows(rows: pd.DataFrame) -> dict:
    if rows.empty:
        raise P2EvaluationError("cannot summarize empty evaluation rows")
    required = {"track", "model", "true_loss", "failed"}
    missing = sorted(required - set(rows.columns))
    if missing:
        raise P2EvaluationError(f"summary missing columns: {missing}")
    records = []
    grouping = ["track", "model"]
    if {"fold", "seed"}.issubset(rows.columns):
        grouping.extend(["fold", "seed"])
    for keys, group in rows.groupby(grouping, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        identity = dict(zip(grouping, keys))
        complete = group.loc[~group["failed"], "true_loss_complete_case"].dropna()
        record = {
            **identity,
            "n_samples": int(len(group)),
            "n_failed": int(group["failed"].sum()),
            "failure_rate": float(group["failed"].mean()),
            "pooled_J1": math.sqrt(float(group["true_loss"].mean())),
            "complete_case_J1": (
                math.sqrt(float(complete.mean())) if len(complete) else None
            ),
        }
        if "seed" in record:
            record["seed"] = int(record["seed"])
        records.append(record)
    return {"rows": records}


def evaluate_baselines(
    risk_data: pd.DataFrame,
    model_penalties: list[dict],
) -> tuple[pd.DataFrame, dict]:
    if not model_penalties:
        raise P2EvaluationError("model_penalties must contain fold/seed receipts")
    blocks = []
    seen = set()
    for receipt in model_penalties:
        fold = str(receipt["fold"])
        seed = int(receipt["seed"])
        penalty = float(receipt["failure_penalty"])
        identity = (fold, seed)
        if identity in seen:
            raise P2EvaluationError(f"duplicate model penalty: {identity}")
        seen.add(identity)
        for delta, model in ((DEFAULT_DELTA, "Default"), (L1_DELTA, "L1")):
            block = evaluate_fixed_delta(
                risk_data, delta, model, penalty
            )
            block["fold"] = fold
            block["seed"] = seed
            block["failure_penalty"] = penalty
            blocks.append(block)
    rows = pd.concat(blocks, ignore_index=True)
    return rows, summarize_rows(rows)


def write_json_atomic(path: Path, value: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    if temp.exists():
        raise P2EvaluationError(f"stale partial file exists: {temp}")
    try:
        temp.write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def write_csv_atomic(path: Path, frame: pd.DataFrame) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    if temp.exists():
        raise P2EvaluationError(f"stale partial file exists: {temp}")
    try:
        frame.to_csv(temp, index=False)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def main() -> int:
    raise P2EvaluationError(
        "standalone baseline evaluation is disabled; use "
        "run_p2_vector_mlp.py so all methods share per-model P99 penalties"
    )


if __name__ == "__main__":
    raise SystemExit(main())
