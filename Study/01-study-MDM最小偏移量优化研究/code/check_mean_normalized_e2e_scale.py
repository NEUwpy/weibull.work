"""Small end-to-end scale-equivariance check for the formal mean selector.

This is deliberately a confirmation check, not another experiment pipeline.
It loads the four E5 deployment models from their sealed Git commit, predicts
delta from ``sort(X) / mean(X)``, and runs the production MDM on X scaled by
10^-3, 1, and 10^3.  The existing MDM test suite already establishes
fixed-delta equivariance; this script checks the combined selector -> MDM path.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np


CODE_DIR = Path(__file__).resolve().parent
STUDY_ROOT = CODE_DIR.parent
PROJECT_ROOT = STUDY_ROOT.parents[1]
PYTHON_DIR = PROJECT_ROOT / "python"
sys.path.insert(0, str(CODE_DIR))
sys.path.insert(0, str(PYTHON_DIR))

import dim_raw_config as CFG
from studies.common.runner import run_method
from studies.common.sample import generate_sample


MODEL_COMMIT = "ddc75754"
MODEL_RELATIVE_DIR = (
    "Study/01-study-MDM最小偏移量优化研究/artifacts/formal/"
    "E5_normalized_raw/specialist/final_models"
)
OUTPUT_DIR = (STUDY_ROOT / "artifacts" / "formal" /
              "E8_mean_normalized_selector" / "scale_equivariance")
SCALES = (1e-3, 1.0, 1e3)
PROBES = (
    # beta, gamma/eta, n, repeat_id: boundary and interior conditions.
    (1.5, 0.10, 7, 0),
    (2.5, 0.25, 10, 73),
    (3.5, 0.50, 15, 149),
    (5.0, 1.00, 20, 299),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_file_lf(path: Path) -> str:
    """Hash text artifacts using the repository's tracked-file contract."""
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def git_model_bytes(n: int) -> bytes:
    path = f"{MODEL_RELATIVE_DIR}/n{n}_final.json"
    return subprocess.check_output(
        ["git", "show", f"{MODEL_COMMIT}:{path}"],
        cwd=PROJECT_ROOT,
    )


def load_model(n: int) -> tuple[dict, str]:
    raw = git_model_bytes(n)
    model = json.loads(raw.decode("utf-8"))
    assert model["n"] == n
    assert model["normalization"].startswith("Z_n = sorted(x)/mean(x)")
    assert model["delta_grid"] == list(CFG.DELTA_GRID)
    return model, sha256_bytes(raw)


def predict_curve(sample: np.ndarray, model: dict) -> np.ndarray:
    """Reproduce sklearn MLPRegressor forward prediction from sealed JSON."""
    values = np.sort(np.asarray(sample, dtype=float).reshape(-1))
    z = values / float(np.mean(values))
    x = ((z - np.asarray(model["input_scaler_mean"], dtype=float)) /
         np.asarray(model["input_scaler_std"], dtype=float)).reshape(1, -1)
    weights = model["mlp_weights"]
    coefs = [np.asarray(v, dtype=float) for v in weights["coefs_"]]
    intercepts = [np.asarray(v, dtype=float) for v in weights["intercepts_"]]
    for layer, (coef, intercept) in enumerate(zip(coefs, intercepts)):
        x = x @ coef + intercept
        if layer < len(coefs) - 1:
            x = np.maximum(x, 0.0)
    curve = (x[0] * np.asarray(model["target_scaler_std"], dtype=float) +
             np.asarray(model["target_scaler_mean"], dtype=float))
    return np.maximum(curve, 0.0)


def select_delta(sample: np.ndarray, model: dict) -> tuple[float, np.ndarray]:
    curve = predict_curve(sample, model)
    idx = int(np.argmin(curve))
    return float(model["delta_grid"][idx]), curve


def normalized_joint_loss(result: dict, beta: float, eta: float,
                          gamma: float) -> float:
    return float(
        ((result["beta_hat"] - beta) / beta) ** 2
        + ((result["eta_hat"] - eta) / eta) ** 2
        + ((result["gamma_hat"] - gamma) / eta) ** 2
    )


def run() -> dict:
    start_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True
    ).strip()
    start_dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, text=True
    ).strip())

    model_cache = {n: load_model(n) for n in CFG.N_GRID}
    rows = []
    for beta, goe, n, repeat_id in PROBES:
        eta = float(CFG.ETA)
        gamma = eta * goe
        base_sample = generate_sample(
            beta, eta, gamma, n, repeat_id, seed=CFG.SEED_NAMESPACE
        )
        model, model_sha = model_cache[n]
        reference = None
        for scale in SCALES:
            sample = base_sample * scale
            delta, curve = select_delta(sample, model)
            estimate = run_method(
                "mdm", sample, offset=delta, gamma_steps=60, trace=False
            )
            if not estimate["converged"]:
                raise RuntimeError(
                    f"MDM failed for beta={beta}, goe={goe}, n={n}, "
                    f"repeat={repeat_id}, scale={scale}: {estimate['extra']}"
                )
            rec = {
                "beta": beta,
                "gamma_over_eta": goe,
                "n": n,
                "repeat_id": repeat_id,
                "scale": scale,
                "selected_delta": delta,
                "curve_sha256": sha256_bytes(curve.astype("<f8").tobytes()),
                "prediction_curve": curve,
                "beta_hat": estimate["beta_hat"],
                "eta_hat": estimate["eta_hat"],
                "gamma_hat": estimate["gamma_hat"],
                "r_squared": estimate["r_squared"],
                "joint_loss": normalized_joint_loss(
                    estimate, beta, eta * scale, gamma * scale
                ),
                "model_sha256": model_sha,
            }
            rows.append(rec)
            if scale == 1.0:
                reference = rec

        assert reference is not None
        probe_rows = rows[-len(SCALES):]
        for rec in probe_rows:
            scale = rec["scale"]
            assert rec["selected_delta"] == reference["selected_delta"]
            curve_diff = float(np.max(np.abs(
                rec["prediction_curve"] - reference["prediction_curve"]
            )))
            rec["curve_max_abs_diff_to_scale_1"] = curve_diff
            assert curve_diff <= 2e-12
            assert np.isclose(rec["beta_hat"], reference["beta_hat"],
                              rtol=1e-6, atol=1e-8)
            assert np.isclose(rec["eta_hat"] / scale,
                              reference["eta_hat"], rtol=1e-6, atol=1e-8)
            assert np.isclose(rec["gamma_hat"] / scale,
                              reference["gamma_hat"], rtol=1e-6, atol=1e-8)
            assert np.isclose(rec["r_squared"], reference["r_squared"],
                              rtol=1e-8, atol=1e-10)
            assert np.isclose(rec["joint_loss"], reference["joint_loss"],
                              rtol=1e-6, atol=1e-10)

    for rec in rows:
        del rec["prediction_curve"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "scale_equivariance.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    result = {
        "status": "PASS",
        "scope": "selector -> selected delta -> production MDM",
        "model_source_commit": MODEL_COMMIT,
        "representation": "sort(X) / mean(X)",
        "scales": list(SCALES),
        "n_probes": len(PROBES),
        "n_runs": len(rows),
        "checks": {
            "prediction_curve_invariant_within_2e-12": True,
            "selected_delta_identical": True,
            "beta_hat_invariant": True,
            "eta_hat_equivariant": True,
            "gamma_hat_equivariant": True,
            "r_squared_invariant": True,
            "normalized_joint_loss_invariant": True,
        },
        "runtime_start_git": {"head": start_head, "dirty": start_dirty},
        "files": {"scale_equivariance.csv": sha256_file_lf(csv_path)},
    }
    result_path = OUTPUT_DIR / "summary.json"
    result_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    manifest = {
        "contract": "E8_mean_normalized_e2e_scale_v1",
        "purpose": "small confirmation of the combined selector-MDM path",
        "model_source_commit": MODEL_COMMIT,
        "model_sha256": {str(n): model_cache[n][1] for n in CFG.N_GRID},
        "production_entry": "studies.common.runner.run_method(method_id='mdm')",
        "gamma_steps": 60,
        "hash_policy": "SHA256 of LF-normalized bytes",
        "files": {
            "scale_equivariance.csv": sha256_file_lf(csv_path),
            "summary.json": sha256_file_lf(result_path),
        },
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ledger = "".join(
        f"{sha256_file_lf(OUTPUT_DIR / name)}  {name}\n"
        for name in ("manifest.json", "scale_equivariance.csv", "summary.json")
    )
    (OUTPUT_DIR / "SHA256SUMS").write_text(ledger, encoding="ascii")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
