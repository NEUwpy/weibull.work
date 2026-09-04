"""Check and join WMLE/LSE results with the sealed Research04 summaries."""
from pathlib import Path
import hashlib
import json
import platform
import sys

import numpy as np
import pandas as pd
import scipy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_traditional_aligned as run
import run_study01_aligned_generalization as base

OUT = run.RESEARCH / "artifacts/traditional_aligned_v1"


def markdown_table(frame):
    headers = list(frame.columns)
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for values in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(f"{x:.4f}" if isinstance(x, float) else str(x)
                                       for x in values) + " |")
    return "\n".join(lines)


def main():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "complete" or manifest["mode"] != "formal":
        raise ValueError("full formal results required")
    frame = pd.read_csv(OUT / "per_sample_results.csv.gz")
    run.validate(frame, 126000)
    design = manifest["test_design"]
    expected = set((float(b), float(g), int(n)) for b in design["beta"]
                   for g in design["gamma_over_eta"] for n in design["n"])
    for _, group in frame.groupby("method"):
        actual = set(map(tuple, group[["beta", "gamma_over_eta", "n"]].to_numpy()))
        assert actual == expected
        for _, cell in group.groupby(["beta", "gamma_over_eta", "n"]):
            assert set(cell.repeat_id) == set(range(300)) and len(cell) == 300
    assert frame.groupby(run.KEYS).sample_sha256.nunique().eq(1).all()
    valid = frame.status.eq("success")
    natural = ((frame.loc[valid, "beta_hat"] / frame.loc[valid, "beta"] - 1)**2
               + (frame.loc[valid, "eta_hat"] / frame.loc[valid, "eta"] - 1)**2
               + ((frame.loc[valid, "gamma_hat"] - frame.loc[valid, "gamma"])
                  / frame.loc[valid, "eta"])**2)
    np.testing.assert_allclose(natural, frame.loc[valid, "loss_primary"], atol=1e-12)
    np.testing.assert_allclose(frame.loc[~valid, "loss_primary"], manifest["failure_penalty"])
    for _, row in frame.iloc[::1001].iterrows():
        sample = run.generate_sample(float(row.beta), float(row.eta), float(row.gamma),
                                     int(row.n), int(row.repeat_id), seed=design["seed_namespace"])
        assert hashlib.sha256(np.round(sample, 12).tobytes()).hexdigest() == row.sample_sha256
    new = base.summarize_error_frame(frame, ["method", "beta_group"])
    old = pd.read_csv(run.SOURCE / "method_summary.csv")
    combined = pd.concat([old, new], ignore_index=True)
    combined.to_csv(OUT / "combined_standard_metrics.csv", index=False)
    checks = {
        "status": "passed", "samples_per_method": 126000,
        "checks": ["exact cells/repeats", "same-method sample hashes", "independent loss recomputation",
                   "failure penalty", "systematic sample reconstruction"],
        "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
        "analysis_script_sha256": run.sha(Path(__file__)),
        "wmle_weights_sha256": run.sha(run.ROOT / "python/methods/j3_weights.tsv"),
        "historical_method_summary_sha256": run.sha(run.SOURCE / "method_summary.csv"),
    }
    (OUT / "analysis_checks.json").write_text(json.dumps(checks, indent=2)+"\n", encoding="utf-8")
    primary = combined.pivot(index="method", columns="beta_group", values="J1_primary")
    primary = primary[["seen_grid", "in_domain_unseen", "near_ood", "far_ood"]].reset_index()
    primary.columns = ["方法", "已见网格 J1", "域内未见 J1", "近域外 J1", "远域外 J1"]
    metrics = combined[["method", "beta_group", "failure_rate", "beta_rmse", "eta_rmse", "gamma_rmse",
                        "x0.90_rmse", "x0.95_rmse", "x0.99_rmse"]].copy()
    metrics["failure_rate"] *= 100
    metrics.rename(columns={"failure_rate": "failure_percent"}, inplace=True)
    report = f"""# Research04 WMLE/LSE 同协议比较

## 设计与口径

126,000 个共享测试样本，beta=0.75..5.75（步长0.25），eta=1000，gamma/eta=0.1/0.25/0.5/0.75/1，n=7/10/15/20，每单元300次。WMLE/LSE 调用当前平台实现，和 Study01 的方法入口一致，但不挪用 Study01 的旧表：旧表的样本面板及求解实现版本不同。

训练域为 beta=1.5..5.0，已见网格与域内未见点按原 Research04 分类；近域外包含1.25和5.25，远域外包含0.75、1.0、5.5、5.75。J1 使用全部样本，失败时赋予原正式合同的训练来源损失 {manifest['failure_penalty']:.15f}；其余误差在成功估计上计算，并列报告失败率。gamma误差除以eta，beta/eta与分位点误差除以各自真值。

WMLE/LSE 新增252,000行估计，用时 {manifest['elapsed_seconds']/60:.1f} 分钟。原三个方法使用封存汇总，当前checkout未保留其逐样本文件；本轮没有重训网络、重跑MDM或新增跨方法配对置信区间。运行命令、源码与输入哈希见 manifest.json，数值与样本复核见 analysis_checks.json。

## 联合误差

{markdown_table(primary)}

## 参数与寿命点误差

下表均为相对RMSE；Bias、SD及其余统计见 combined_standard_metrics.csv。域外结论还需结合 beta_summary.csv 分左右两侧阅读，不能用双侧平均代替方向性判断。

{markdown_table(metrics)}

## 解释边界

这里比较的是所记录版本的 WMLE/LSE 实现，不等同于所有同名算法实现的最佳性能。失败原因见 failure_reasons.csv；不能只比较成功子集的RMSE而忽略失败率。本轮不开发自动回退规则，区间覆盖评价后置。
"""
    (OUT / "report.md").write_text(report, encoding="utf-8")
    print(primary.to_string(index=False))
    print("ANALYSIS CHECKS PASSED")


if __name__ == "__main__":
    main()
