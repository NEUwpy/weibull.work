"""Repackage the sealed E5 mean-normalized result as the paper main evidence.

No estimator or neural network is run here.  The script verifies the original
48,000-sample out-of-fold selection file against its sealed SHA256, recomputes
all aggregate values, and binds them to the unchanged Default/L6 scan and the
E7 representation-screen decision.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


CODE_DIR = Path(__file__).resolve().parent
STUDY_ROOT = CODE_DIR.parent
PROJECT_ROOT = STUDY_ROOT.parents[1]
sys.path.insert(0, str(CODE_DIR))
sys.path.insert(0, str(PROJECT_ROOT / "python"))

import dim_raw_config as CFG
import paper_support as PS


SOURCE_COMMIT = "ddc75754"
SOURCE_RESULT_SHA256 = (
    "b67578fe3a6e02c606ce0ba0bf224f4ce8a7acbf48de1fd87ef1739e368ad7db"
)
SOURCE_DIR = (STUDY_ROOT / "artifacts" / "formal" /
              "E5_normalized_raw" / "specialist")
SOURCE_RESULT = SOURCE_DIR / "raw_specialist_results.csv"
E7_SUMMARY = (STUDY_ROOT / "artifacts" / "candidate" /
              "E7_scale_invariant_input_screen" / "summary.json")
E6_LAYERS = (STUDY_ROOT / "artifacts" / "formal" /
             "E6_dimensional_raw" / "specialist" / "crossfit_layers.csv")
OUTPUT_DIR = (STUDY_ROOT / "artifacts" / "formal" /
              "E8_mean_normalized_selector" / "specialist")
KEYS = ["beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id"]
SEEDS = [42, 2026, 3407]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def j1(values) -> float:
    return math.sqrt(float(pd.to_numeric(values).mean()))


def model_row(model: str, seed: int, frame: pd.DataFrame,
              loss_col: str, valid_col: str) -> dict:
    row = {
        "model": model,
        "split": "gamma_eta_level_holdout_within_n",
        "seed": int(seed),
        "J1": j1(frame[loss_col]),
        "failure_rate": float(1.0 - frame[valid_col].astype(bool).mean()),
        "n_samples": int(len(frame)),
    }
    for n, group in frame.groupby("n"):
        row[f"J1_n{int(n)}"] = j1(group[loss_col])
    return row


def run() -> dict:
    start_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True
    ).strip()
    start_dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, text=True
    ).strip())
    if not SOURCE_RESULT.is_file():
        raise FileNotFoundError(
            f"Sealed E5 result is required locally: {SOURCE_RESULT}"
        )
    actual_sha = sha256_file(SOURCE_RESULT)
    if actual_sha != SOURCE_RESULT_SHA256:
        raise AssertionError(f"E5 result SHA256 mismatch: {actual_sha}")

    raw = pd.read_csv(SOURCE_RESULT, low_memory=False)
    if len(raw) != 144000 or raw["seed"].nunique() != 3:
        raise AssertionError("E5 result must contain 48,000 rows x 3 seeds")
    for seed, group in raw.groupby("seed"):
        if len(group) != 48000 or group[KEYS].duplicated().any():
            raise AssertionError(f"Bad sample-key contract for seed {seed}")
    key_digest = {
        int(seed): hashlib.sha256(
            group[KEYS].sort_values(KEYS).to_csv(index=False).encode("utf-8")
        ).hexdigest()
        for seed, group in raw.groupby("seed")
    }
    if len(set(key_digest.values())) != 1:
        raise AssertionError("The three seeds do not share one sample-key set")

    _, scan, _ = PS.load_scan(verbose=True)
    PS.verify_design(scan)
    baselines = PS.default_and_l6(scan)
    if len(baselines) != 48000:
        raise AssertionError("Default/L6 sample contract changed")
    if hashlib.sha256(
        baselines[KEYS].sort_values(KEYS).to_csv(index=False).encode("utf-8")
    ).hexdigest() != next(iter(key_digest.values())):
        raise AssertionError("E5 and baseline sample keys differ")

    default = baselines.rename(columns={"default_loss": "loss",
                                         "default_valid": "valid"})
    l6 = baselines.rename(columns={"l6_loss": "loss",
                                    "l6_valid": "valid"})
    comparison = []
    seeds = []
    for seed in SEEDS:
        group = raw[raw["seed"] == seed].copy()
        adaptive = model_row("Mean-Normalized-MLP", seed, group,
                             "true_loss", "is_valid")
        comparison.extend([
            adaptive,
            model_row("Default", seed, default, "loss", "valid"),
            model_row("L6-hindsight", seed, l6, "loss", "valid"),
        ])
        seeds.append({
            "seed": seed,
            "pooled_J1": adaptive["J1"],
            **{f"J1_n{n}": adaptive[f"J1_n{n}"] for n in CFG.N_GRID},
            "n_samples": 48000,
            "failure_rate": adaptive["failure_rate"],
        })

    pooled = np.asarray([row["pooled_J1"] for row in seeds])
    default_j1 = comparison[1]["J1"]
    l6_j1 = comparison[2]["J1"]
    by_n = {
        str(n): float(np.mean([row[f"J1_n{n}"] for row in seeds]))
        for n in CFG.N_GRID
    }
    e7 = json.loads(E7_SUMMARY.read_text(encoding="utf-8"))
    mean_screen = next(
        item for item in e7["results"] if item["representation"] == "mean"
    )
    rms_screen = next(
        item for item in e7["results"] if item["representation"] == "rms"
    )
    if not np.isclose(float(pooled.mean()), mean_screen["pooled_J1_mean"],
                      atol=5e-13, rtol=0):
        raise AssertionError("E5 result does not reproduce the E7 mean screen")

    summary = {
        "experiment": "E8 formal mean-normalized per-n selector",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "representation": "ascending-sorted X / mean(X)",
        "training_preprocessing": (
            "per-position StandardScaler fitted on the training fold only"
        ),
        "evaluation_split": (
            "within each n, hold out one complete gamma/eta level per fold; "
            "each test fold contains all eight beta levels"
        ),
        "mean_normalized_3seed": {
            "pooled_J1_mean": float(pooled.mean()),
            "pooled_J1_std": float(pooled.std(ddof=0)),
            **{f"J1_n{n}_mean": by_n[str(n)] for n in CFG.N_GRID},
        },
        "relative_improvement_vs_default": float(1 - pooled.mean() / default_j1),
        "default_J1": default_j1,
        "l6_hindsight_J1": l6_j1,
        "seed_table": seeds,
        "model_comparison": comparison,
        "selection_rationale": {
            "candidate_screen": str(E7_SUMMARY.relative_to(STUDY_ROOT)),
            "mean_J1": mean_screen["pooled_J1_mean"],
            "rms_J1": rms_screen["pooled_J1_mean"],
            "interpretation": (
                "Mean and RMS normalization were nearly tied. Mean normalization "
                "was selected because its observed J1 was slightly lower, its "
                "definition is simple and established, and it exactly reproduced "
                "the existing E5 result; no universal superiority is claimed."
            ),
        },
        "source": {
            "artifact_commit": SOURCE_COMMIT,
            "raw_selection_sha256": actual_sha,
            "sample_key_sha256": next(iter(key_digest.values())),
            "mdm_rerun": False,
            "neural_network_retrained": False,
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    pd.DataFrame(seeds).to_csv(OUTPUT_DIR / "seed_stability.csv", index=False)
    pd.DataFrame(comparison).to_csv(OUTPUT_DIR / "model_comparison.csv", index=False)
    shutil.copyfile(E6_LAYERS, OUTPUT_DIR / "crossfit_layers.csv")

    files = {
        path.name: sha256_file(path)
        for path in sorted(OUTPUT_DIR.iterdir()) if path.is_file()
    }
    manifest = {
        "contract": "E8_mean_normalized_main_evidence_v1",
        "source_artifact_commit": SOURCE_COMMIT,
        "source_raw_selection_sha256": SOURCE_RESULT_SHA256,
        "e7_candidate_screen": str(E7_SUMMARY.relative_to(STUDY_ROOT)),
        "runtime_start_git": {"head": start_head, "dirty": start_dirty},
        "files": files,
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    ledger_names = sorted([*files, "manifest.json"])
    (OUTPUT_DIR / "SHA256SUMS").write_text("".join(
        f"{sha256_file(OUTPUT_DIR / name)}  {name}\n" for name in ledger_names
    ), encoding="ascii")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
