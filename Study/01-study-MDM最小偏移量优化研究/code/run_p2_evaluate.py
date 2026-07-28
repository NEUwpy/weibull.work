"""Shared P2 evaluation helpers and fixed-delta baselines."""

from __future__ import annotations

import argparse
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
    if not np.isfinite(failure_penalty) or failure_penalty < 0:
        raise P2EvaluationError("failure_penalty must be finite and non-negative")
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
    failed = (
        rows["loss"].isna()
        | rows["status"].ne("success")
        | rows["failure_reason"].fillna("").astype(str).str.len().gt(0)
    )
    rows["failed"] = failed
    rows["failure_reason"] = rows["failure_reason"].fillna("")
    rows.loc[rows["loss"].isna(), "failure_reason"] = rows.loc[
        rows["loss"].isna(), "failure_reason"
    ].replace("", "missing_or_non_finite_loss")
    rows["true_loss_complete_case"] = rows["loss"]
    rows["true_loss"] = rows["loss"].where(~failed, failure_penalty)
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
    for (track, model), group in rows.groupby(["track", "model"], sort=True):
        complete = group.loc[~group["failed"], "true_loss_complete_case"].dropna()
        records.append(
            {
                "track": track,
                "model": model,
                "n_samples": int(len(group)),
                "n_failed": int(group["failed"].sum()),
                "failure_rate": float(group["failed"].mean()),
                "pooled_J1": math.sqrt(float(group["true_loss"].mean())),
                "complete_case_J1": (
                    math.sqrt(float(complete.mean())) if len(complete) else None
                ),
            }
        )
    return {"rows": records}


def evaluate_baselines(
    risk_data: pd.DataFrame, failure_penalty: float = 1.0
) -> tuple[pd.DataFrame, dict]:
    rows = pd.concat(
        [
            evaluate_fixed_delta(
                risk_data, DEFAULT_DELTA, "Default", failure_penalty
            ),
            evaluate_fixed_delta(risk_data, L1_DELTA, "L1", failure_penalty),
        ],
        ignore_index=True,
    )
    return rows, summarize_rows(rows)


def _write_json_atomic(path: Path, value: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failure-penalty", type=float, default=1.0)
    args = parser.parse_args()
    data = load_p2_risk_data()
    rows, summary = evaluate_baselines(data, args.failure_penalty)
    rows.to_csv(P2_DIR / "p2_baseline_per_sample.csv", index=False)
    _write_json_atomic(P2_DIR / "p2_baseline_summary.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
