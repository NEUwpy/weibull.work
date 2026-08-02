"""A-E1-faithful P-route data generation and input scaler.

The approved A-E1 V checkpoints were trained on **scaled** sorted-z inputs:
per-position (mean, sd) fit from the 100k training rows, `(x-mean)/sd` with
zero-sd mapped to 0. B4/B5 and the first incremental run fed raw sorted-z,
which biased P's predictions. This module reproduces the A-E1 data design and
scaler exactly:

- training: 100k scrambled-Sobol parameter points (design ns 220201),
  samples with sample ns 320201, fixed-n, repeat_id 0.
- validation: 256 Sobol points x 50 repeats (design ns 220202, sample ns 320202).
- scaler: per-position mean/sd (ddof=0) over training features, zero-sd->0.

Existing n (5,7,10,15,20) reconstruct the scaler directly from the frozen A-E1
training cache features (bit-identical to A-E1's fit_training_scaler). Missing n
generate the A-E1 design fresh (same Sobol parameter design, new n).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON = _REPO_ROOT / "python"
if str(_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PYTHON))

from study02a.config import load_frozen_config
from study02a import design
from study02a.representations import anchor_sample, build_features, encode_targets

from study02b_inc import config as C

A_STUDY_ROOT = _REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
A_TRAIN_DESIGN_NS = 220201
A_TRAIN_SAMPLE_NS = 320201
A_VAL_DESIGN_NS = 220202
A_VAL_SAMPLE_NS = 320202
A_VAL_POINTS = 256
A_VAL_REPEATS = 50


# ---------------------------------------------------------------------------
# Scaler
# ---------------------------------------------------------------------------

def scale_features(features: np.ndarray, mean: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """A-E1 apply_training_scaler: (x-mean)/sd with zero-sd -> 0 (map_to_zero)."""
    values = np.asarray(features, dtype=np.float64)
    safe = np.where(sd != 0, sd, 1.0)
    scaled = (values - mean) / safe
    scaled = np.where(sd != 0, scaled, 0.0)
    return scaled.astype(np.float32)


def _fit_scaler(features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(features, dtype=np.float64)
    mean = values.mean(axis=0)
    sd = values.std(axis=0, ddof=0)
    return mean, sd


def a_p_scaler_from_cache(n: int) -> dict:
    """Reconstruct the A-E1 training scaler for an existing n from its cache."""
    cache = _a_cache_path(n)
    if cache is None:
        raise KeyError(f"no A-E1 training cache for n={n}")
    features = np.load(Path(cache) / "features.npy")
    mean, sd = _fit_scaler(features)
    return {"n": n, "mean": mean.tolist(), "sd": sd.tolist(), "source": "A-E1-cache"}


def _a_cache_path(n: int) -> Path | None:
    """Look up the A-E1 winner-retrain training cache path for n."""
    plan = {}
    if C.P_PLAN_PATH.exists():
        with open(C.P_PLAN_PATH, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if row.get("fit_id"):
                        plan[row["fit_id"]] = row
    for fit_num in range(299, 349):
        fid = f"G3-fit-{fit_num:04d}"
        row = plan.get(fid)
        if row is None:
            continue
        if row.get("fixed_n") != n or row.get("route") != "V":
            continue
        cache = row.get("training_cache_path")
        if cache and Path(cache).exists():
            return Path(cache)
    return None


# ---------------------------------------------------------------------------
# A-E1-faithful data generation for a given n (existing n would match caches)
# ---------------------------------------------------------------------------

def _params_frame(role: str, count: int, n: int):
    cfg = load_frozen_config(A_STUDY_ROOT)
    points = design.generate_parameter_points(role, "core_continuous", count, cfg)
    points["n"] = int(n)
    points["repeat_id"] = 0
    return points, cfg


def _rows_to_data(rows, n: int, sample_ns: int) -> dict:
    """features (raw sorted-z), targets (encode_targets), anchors."""
    samples, anchors, targets = [], [], []
    for _, row in rows.iterrows():
        sample = design.generate_lifetime_sample(row, sample_ns)
        anchor = anchor_sample(sample)
        samples.append(sample)
        anchors.append(anchor)
        targets.append(encode_targets(
            float(row["beta"]), float(row["eta"]), float(row["gamma"]), anchor))
    features = np.array([a.z for a in anchors], dtype=np.float32)
    return {
        "features": features,
        "targets": np.array(targets, dtype=np.float32),
        "samples": samples,
        "anchors": anchors,
    }


def generate_a_training_data(n: int) -> dict:
    """A-E1 training data for a given n: raw features, encoded targets, scaler."""
    points, _ = _params_frame("training", C.N_TRAIN, n)
    data = _rows_to_data(points, n, A_TRAIN_SAMPLE_NS)
    mean, sd = _fit_scaler(data["features"])
    data["scaler"] = {"mean": mean.tolist(), "sd": sd.tolist()}
    data["scaled_features"] = scale_features(data["features"], mean, sd)
    return data


def generate_a_validation_data(n: int) -> dict:
    """A-E1 validation data: 256 points x 50 repeats, scaled with training scaler."""
    cfg = load_frozen_config(A_STUDY_ROOT)
    points = design.generate_parameter_points("validation", "core", A_VAL_POINTS, cfg)
    rows = []
    for _, point in points.iterrows():
        for repeat_id in range(A_VAL_REPEATS):
            row = point.to_dict()
            row["repeat_id"] = repeat_id
            row["n"] = int(n)
            rows.append(row)
    import pandas as pd
    frame = pd.DataFrame(rows)
    data = _rows_to_data(frame, n, A_VAL_SAMPLE_NS)
    return data  # caller scales with the training scaler
