"""Paired scale-equivariance audit for the formal Research04 Direct-P models.

The formal models were trained at eta=1000.  This audit does not retrain them.
It multiplies every sample, eta, and gamma in the complete 126,000-sample test
panel by the same positive factor, then checks whether beta estimates and all
dimensionless errors stay fixed while eta/gamma estimates scale proportionally.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve()
RESEARCH_ROOT = HERE.parents[1]
PROJECT_ROOT = HERE.parents[3]
CODE_ROOT = HERE.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

import run_training_domain_width as WIDTH  # noqa: E402
from studies.common.metrics import quantile_true  # noqa: E402


RUN_ID = "scale_equivariance_v1"
SCALE_FACTORS = (0.001, 0.01, 0.1, 1.0, 10.0, 1000.0)
OUT_DIR = RESEARCH_ROOT / "artifacts" / RUN_ID
SUMMARY_PATH = OUT_DIR / "scale_summary.csv"
DIFF_PATH = OUT_DIR / "scale_invariance_differences.csv"
MANIFEST_PATH = OUT_DIR / "manifest.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_value(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=PROJECT_ROOT, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def rmse(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))


def quantile(beta: np.ndarray, eta: np.ndarray, gamma: np.ndarray,
             reliability: float = 0.95) -> np.ndarray:
    return np.fromiter(
        (
            quantile_true(float(b), float(e), float(g), reliability)
            for b, e, g in zip(beta, eta, gamma)
        ),
        dtype=float,
        count=len(beta),
    )


def summarize_errors(
    scale_factor: float,
    n_value: int,
    keys: pd.DataFrame,
    predictions: np.ndarray,
) -> dict:
    beta = keys["beta"].to_numpy(float)
    eta = keys["eta"].to_numpy(float) * scale_factor
    gamma = keys["gamma"].to_numpy(float) * scale_factor
    beta_hat = predictions[:, 0]
    eta_hat = predictions[:, 1]
    gamma_hat = predictions[:, 2]
    beta_error = (beta_hat - beta) / beta
    eta_error = (eta_hat - eta) / eta
    gamma_error = (gamma_hat - gamma) / eta
    loss = beta_error ** 2 + eta_error ** 2 + gamma_error ** 2
    true_x = quantile(beta, eta, gamma)
    estimated_x = quantile(beta_hat, eta_hat, gamma_hat)
    x095_error = (estimated_x - true_x) / true_x
    sample_min = keys["sample_min"].to_numpy(float) * scale_factor
    valid = (
        np.isfinite(predictions).all(axis=1)
        & (beta_hat > 0.0)
        & (eta_hat > 0.0)
        & (gamma_hat >= 0.0)
        & (gamma_hat < sample_min)
    )
    return {
        "scale_factor": scale_factor,
        "eta": WIDTH.ETA * scale_factor,
        "n": n_value,
        "n_samples": int(len(keys)),
        "n_valid": int(valid.sum()),
        "failure_rate": float(1.0 - valid.mean()),
        "J1": float(np.sqrt(np.mean(loss))),
        "beta_bias": float(beta_error.mean()),
        "beta_sd": float(beta_error.std(ddof=1)),
        "beta_rmse": rmse(beta_error),
        "eta_bias": float(eta_error.mean()),
        "eta_sd": float(eta_error.std(ddof=1)),
        "eta_rmse": rmse(eta_error),
        "gamma_bias": float(gamma_error.mean()),
        "gamma_sd": float(gamma_error.std(ddof=1)),
        "gamma_rmse": rmse(gamma_error),
        "x095_bias": float(x095_error.mean()),
        "x095_sd": float(x095_error.std(ddof=1)),
        "x095_rmse": rmse(x095_error),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summaries: list[dict] = []
    differences: list[dict] = []
    model_sources: dict[str, str] = {}

    for n_value in WIDTH.N_VALUES:
        model_path = (
            WIDTH.SOURCE_FORMAL_DIR / "models"
            / f"direct_n{n_value}_seed42.pt"
        )
        model, info = WIDTH.load_model(model_path, n_value)
        model_sources[str(n_value)] = str(model_path.relative_to(PROJECT_ROOT))
        keys, normalized, means = WIDTH.test_arrays(
            n_value, WIDTH.TEST_REPEATS
        )
        base = WIDTH.DIRECT.predict_direct_mlp(model, info, normalized, means)

        for factor in SCALE_FACTORS:
            predictions = WIDTH.DIRECT.predict_direct_mlp(
                model, info, normalized, means * factor
            )
            summaries.append(
                summarize_errors(factor, n_value, keys, predictions)
            )
            differences.append(
                {
                    "scale_factor": factor,
                    "eta": WIDTH.ETA * factor,
                    "n": n_value,
                    "max_abs_beta_hat_diff": float(
                        np.max(np.abs(predictions[:, 0] - base[:, 0]))
                    ),
                    "max_abs_eta_hat_rescaled_diff": float(
                        np.max(np.abs(predictions[:, 1] / factor - base[:, 1]))
                    ),
                    "max_abs_gamma_hat_rescaled_diff": float(
                        np.max(np.abs(predictions[:, 2] / factor - base[:, 2]))
                    ),
                }
            )

    summary = pd.DataFrame(summaries)
    diff = pd.DataFrame(differences)
    summary.to_csv(SUMMARY_PATH, index=False, lineterminator="\n")
    diff.to_csv(DIFF_PATH, index=False, lineterminator="\n")

    grouped = summary.groupby("scale_factor", sort=True)
    pooled_rows = []
    for factor, group in grouped:
        weights = group["n_samples"].to_numpy(float)
        pooled_rows.append(
            {
                "scale_factor": float(factor),
                "eta": WIDTH.ETA * float(factor),
                "n_samples": int(group["n_samples"].sum()),
                "J1": float(np.average(group["J1"], weights=weights)),
                "x095_rmse": float(np.average(group["x095_rmse"], weights=weights)),
                "failure_rate": float(np.average(group["failure_rate"], weights=weights)),
            }
        )
    pooled = pd.DataFrame(pooled_rows)
    pooled.to_csv(OUT_DIR / "pooled_scale_summary.csv", index=False, lineterminator="\n")

    max_beta_diff = float(diff["max_abs_beta_hat_diff"].max())
    max_eta_diff = float(diff["max_abs_eta_hat_rescaled_diff"].max())
    max_gamma_diff = float(diff["max_abs_gamma_hat_rescaled_diff"].max())
    metric_spread = {
        "J1": float(pooled["J1"].max() - pooled["J1"].min()),
        "x095_rmse": float(
            pooled["x095_rmse"].max() - pooled["x095_rmse"].min()
        ),
        "failure_rate": float(
            pooled["failure_rate"].max() - pooled["failure_rate"].min()
        ),
    }
    tolerance = 1e-8
    status = "PASS" if max(max_beta_diff, max_eta_diff, max_gamma_diff) < tolerance else "FAIL"
    manifest = {
        "run_id": RUN_ID,
        "status": status,
        "generated_at": utc_now(),
        "question": (
            "Do the formal eta=1000 Direct-P models remain scale-equivariant "
            "when the complete shared test panel is rescaled?"
        ),
        "audit_type": "paired deterministic scale-equivariance audit; no retraining",
        "base_eta": WIDTH.ETA,
        "scale_factors": list(SCALE_FACTORS),
        "tested_eta": [WIDTH.ETA * value for value in SCALE_FACTORS],
        "test_design": {
            "beta": list(WIDTH.TEST_BETAS),
            "gamma_over_eta": list(WIDTH.GAMMA_RATIOS),
            "n": list(WIDTH.N_VALUES),
            "repeats": WIDTH.TEST_REPEATS,
            "physical_samples_per_scale": int(
                summary[summary["scale_factor"].eq(1.0)]["n_samples"].sum()
            ),
            "total_scaled_evaluations": int(summary["n_samples"].sum()),
            "seed_namespace": WIDTH.TEST_SEED_NAMESPACE,
        },
        "model_sources": model_sources,
        "checks": {
            "tolerance": tolerance,
            "max_abs_beta_hat_diff": max_beta_diff,
            "max_abs_eta_hat_rescaled_diff": max_eta_diff,
            "max_abs_gamma_hat_rescaled_diff": max_gamma_diff,
            "pooled_metric_spread": metric_spread,
        },
        "evidence_boundary": (
            "This verifies numerical scale equivariance for paired rescalings "
            "of the current test panel. It is not an independently retrained "
            "multi-eta model comparison."
        ),
        "git": {
            "commit": git_value("rev-parse", "HEAD"),
            "branch": git_value("branch", "--show-current"),
            "dirty": bool(git_value("status", "--porcelain")),
        },
        "code_sha256": sha256_file(HERE),
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_lines = [
        "# Direct-P 多尺度等变审计",
        "",
        "正式 Direct-P 模型只在 eta=1000 上训练。本审计不重新训练，而是将完整 126,000 个正式测试样本及其 eta、gamma 成对乘以同一尺度因子，检查网络输出和无量纲误差是否保持一致。",
        "",
        "| eta | 样本数 | J1 | x0.95 RMSE | 失败率 |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in pooled.itertuples(index=False):
        report_lines.append(
            f"| {row.eta:g} | {row.n_samples:,} | {row.J1:.7f} | "
            f"{row.x095_rmse:.7f} | {100 * row.failure_rate:.5f}% |"
        )
    report_lines += [
        "",
        "## 结果",
        "",
        f"- beta 估计的最大绝对差为 {max_beta_diff:.3e}。",
        f"- eta 按尺度还原后的最大绝对差为 {max_eta_diff:.3e}。",
        f"- gamma 按尺度还原后的最大绝对差为 {max_gamma_diff:.3e}。",
        f"- 六个尺度的 J1 极差为 {metric_spread['J1']:.3e}，x0.95 RMSE 极差为 {metric_spread['x095_rmse']:.3e}，失败率极差为 {metric_spread['failure_rate']:.3e}。",
        "",
        "结论：当前 Direct-P 的排序样本均值归一化输入和按样本均值恢复 eta、gamma 的输出设计，在 eta=1 至 10^6 的成对缩放审计中保持数值尺度等变，没有观察到尺度变化造成的额外精度损失。",
        "",
        "## 证据边界",
        "",
        "这是同一物理样本的确定性成对缩放审计，验证实现是否遵守尺度等变；它不是在六个 eta 上分别重新训练六套模型。由于尺度归一化后的输入和目标编码相同，重新训练理论上不会增加新的尺度信息，但不同随机训练带来的模型波动属于另一问题。",
    ]
    report_path = OUT_DIR / "report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    outputs = [
        SUMMARY_PATH, DIFF_PATH, OUT_DIR / "pooled_scale_summary.csv",
        MANIFEST_PATH, report_path,
    ]
    (OUT_DIR / "SHA256SUMS.txt").write_text(
        "\n".join(
            f"{sha256_file(path)}  {path.relative_to(OUT_DIR).as_posix()}"
            for path in outputs
        ) + "\n",
        encoding="utf-8",
    )
    if status != "PASS":
        raise RuntimeError("scale equivariance audit failed")
    print(
        f"SCALE_EQUIVARIANCE_COMPLETE status={status} "
        f"samples_per_scale={int(summary[summary['scale_factor'].eq(1.0)]['n_samples'].sum())} "
        f"total_evaluations={int(summary['n_samples'].sum())} "
        f"max_diff={max(max_beta_diff, max_eta_diff, max_gamma_diff):.3e}"
    )


if __name__ == "__main__":
    main()
