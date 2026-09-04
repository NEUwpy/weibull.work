"""Analyze the frozen Direct-P beta training-domain width/location experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve()
RESEARCH_ROOT = HERE.parents[1]
FORMAL_ROOT = RESEARCH_ROOT / "artifacts" / "training_domain_width_location_v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rmse(values: pd.Series) -> float:
    array = values.to_numpy(float)
    array = array[np.isfinite(array)]
    return float(np.sqrt(np.mean(np.square(array)))) if len(array) else math.nan


def classify_beta_point(beta: float, train_betas: tuple[float, ...]) -> str:
    low, high = min(train_betas), max(train_betas)
    if any(math.isclose(beta, value, abs_tol=1e-12) for value in train_betas):
        return "train_grid"
    if low < beta < high:
        return "in_domain_unseen"
    return "left_ood" if beta < low else "right_ood"


def validate_inputs(frame: pd.DataFrame, manifest: dict) -> None:
    required = {
        "budget_policy", "domain_id", "train_beta_min", "train_beta_max",
        "n_train_per_n", "beta", "gamma_over_eta", "n", "repeat_id",
        "status", "loss_primary", "beta_rel_error", "eta_rel_error",
        "gamma_rel_error", "x0.90_rel_error", "x0.95_rel_error",
        "x0.99_rel_error",
    }
    missing = required - set(frame.columns)
    if missing:
        raise RuntimeError(f"missing columns: {sorted(missing)}")
    if len(frame) != int(manifest["validation"]["expected_rows"]):
        raise RuntimeError("row count differs from manifest")
    key = ["budget_policy", "domain_id", "beta", "gamma_over_eta", "n", "repeat_id"]
    if frame.duplicated(key).any():
        raise RuntimeError("duplicate shared test key within scenario")
    expected_totals = {
        (spec["budget_policy"], spec["domain_id"]): int(spec["n_train_per_n"])
        for spec in manifest["scenarios"]
    }
    actual = frame.groupby(["budget_policy", "domain_id"])["n_train_per_n"].first().to_dict()
    if actual != expected_totals:
        raise RuntimeError("recorded training totals differ from manifest scenarios")
    if manifest["status"] == "complete":
        fixed = frame[frame["budget_policy"].eq("fixed_total")]
        if set(fixed["n_train_per_n"].unique()) != {12_000}:
            raise RuntimeError("fixed-total scenarios do not all contain exactly 12,000 rows per n")


def summarize(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    for keys, group in frame.groupby(group_cols, sort=True, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        valid = group[group["status"].eq("success")]
        row.update({
            "n_total": len(group), "n_valid": len(valid),
            "failure_rate": float(1 - len(valid) / len(group)),
            "J1": float(np.sqrt(group["loss_primary"].mean())),
        })
        for parameter in ("beta", "eta", "gamma"):
            values = valid[f"{parameter}_rel_error"]
            row[f"{parameter}_bias"] = float(values.mean())
            row[f"{parameter}_sd"] = float(values.std(ddof=1))
            row[f"{parameter}_rmse"] = rmse(values)
        for level in ("0.90", "0.95", "0.99"):
            row[f"x{level}_rmse"] = rmse(valid[f"x{level}_rel_error"])
        rows.append(row)
    return pd.DataFrame(rows)


def add_design_columns(frame: pd.DataFrame, manifest: dict) -> pd.DataFrame:
    output = frame.copy()
    grids = {
        domain_id: tuple(float(value) for value in spec["betas"])
        for domain_id, spec in manifest["domain_specs"].items()
    }
    output["point_type"] = [
        classify_beta_point(float(beta), grids[str(domain_id)])
        for domain_id, beta in zip(output["domain_id"], output["beta"])
    ]
    output["domain_center"] = (output["train_beta_min"] + output["train_beta_max"]) / 2
    output["relative_beta"] = output["beta"] - output["domain_center"]
    return output


def relative_change(table: pd.DataFrame, policy: str, domain: str,
                    reference: str, metric: str) -> float:
    rows = table[table["budget_policy"].eq(policy)].set_index("domain_id")
    return 100 * (float(rows.loc[domain, metric]) / float(rows.loc[reference, metric]) - 1)


def write_report(root: Path, manifest: dict, width: pd.DataFrame,
                 location: pd.DataFrame, point_types: pd.DataFrame) -> None:
    analysis_dir = root / "analysis"
    width_order = manifest["effect_families"]["width"]
    location_order = manifest["effect_families"]["location"]
    labels = {key: value["label"] for key, value in manifest["domain_specs"].items()}
    widest = width_order[-1]
    reference = width_order[0]
    lines = [
        "# Direct-P 训练 beta 区间宽度与位置分离实验",
        "",
        "## 问题与设计",
        "",
        "本实验只改变 Mean-Normalized Direct-P 的训练 beta 区间。网络、J1 损失、seed=42、早停、eta=1000、gamma/eta 网格、n 和独立测试样本全部冻结。宽度实验使用同中心的四个嵌套窗口；位置实验使用三个宽度均为 1 的平移窗口。[2.5, 3.5] 只训练一次并同时承担两类比较。",
        "",
        "固定总量与固定单元密度是两个独立问题。前者每个 n 恰好 12,000 个训练样本，不能整除时按 beta 优先、gamma/eta 次序确定性均衡分配，单元数最多相差 1；后者每个 beta×gamma/eta×n 单元固定 300 次。下面所有解释均在各自预算协议内进行。",
        "",
        "## 同中心扩宽：共同真实 beta∈[2.5, 3.5]",
        "",
        "| 预算 | 训练区间 | 训练量/n | J1 | beta RMSE | eta RMSE | gamma RMSE | x0.90 RMSE | x0.95 RMSE | x0.99 RMSE | 失败率 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for policy in ("fixed_total", "fixed_density"):
        for domain in width_order:
            row = width[(width["budget_policy"] == policy) & (width["domain_id"] == domain)].iloc[0]
            lines.append(
                f"| {policy} | {labels[domain]} | {int(row['n_train_per_n'])} | {row['J1']:.4f} | "
                f"{row['beta_rmse']:.4f} | {row['eta_rmse']:.4f} | {row['gamma_rmse']:.4f} | "
                f"{row['x0.90_rmse']:.4f} | {row['x0.95_rmse']:.4f} | {row['x0.99_rmse']:.4f} | {row['failure_rate']:.4%} |"
            )
    lines += [
        "",
        f"固定总量下，最宽窗口相对宽度 1 参考窗口的共同区间 J1 变化为 {relative_change(width, 'fixed_total', widest, reference, 'J1'):+.1f}%；固定单元密度下为 {relative_change(width, 'fixed_density', widest, reference, 'J1'):+.1f}%。这两个数分别描述有限总预算和恒定局部样本密度，不合并成单一排名。",
        "完整的 beta、eta、gamma 相对 Bias、SD、RMSE 以及三个寿命点相对 RMSE 保存在 width_common_beta_summary.csv；表中只保留 RMSE 以控制宽度。",
        "",
        "## 同宽平移：对齐各窗口内相对位置",
        "",
        "位置窗口没有一个跨三者共同的内部真实 beta 区间。因此，位置效应的主要描述把各窗口的测试点按 beta−窗口中心对齐，并限于窗口内部；完整的同一真实 beta 曲线另存于 same_beta_summary.csv，用来检查在固定真值处改变训练窗口的结果，但该比较同时改变了点的域内/域外身份。",
        "",
        "| 预算 | 训练区间 | 训练量/n | J1 | beta RMSE | eta RMSE | gamma RMSE | x0.90 RMSE | x0.95 RMSE | x0.99 RMSE | 失败率 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for policy in ("fixed_total", "fixed_density"):
        for domain in location_order:
            row = location[(location["budget_policy"] == policy) & (location["domain_id"] == domain)].iloc[0]
            lines.append(
                f"| {policy} | {labels[domain]} | {int(row['n_train_per_n'])} | {row['J1']:.4f} | "
                f"{row['beta_rmse']:.4f} | {row['eta_rmse']:.4f} | {row['gamma_rmse']:.4f} | "
                f"{row['x0.90_rmse']:.4f} | {row['x0.95_rmse']:.4f} | {row['x0.99_rmse']:.4f} | {row['failure_rate']:.4%} |"
            )
    no_left = point_types[(point_types["domain_id"] == widest) & (point_types["point_type"] == "left_ood")].empty
    lines += [
        "",
        "## 点类型与证据边界",
        "",
        "point_type_summary.csv 分别汇总训练点、域内未见点、左域外和右域外；不能把不同窗口各自不同的域内集合混成总体优劣排名。beta_n_summary.csv 保留了 n 分层，same_beta_summary.csv 保留每个共享真实 beta 的逐窗口结果。",
        "各汇总 CSV 均同时报告 beta、eta、gamma 的相对 Bias、SD、RMSE、J1、失败率，以及 x0.90、x0.95、x0.99 的相对 RMSE。",
        "",
        f"最宽训练窗口 [0.5, 5.5] 在冻结测试范围 [0.75, 5.75] 内{'没有' if no_left else '存在'}左侧域外测试点；本实验没有新增更极端测试点。J1 对失败使用同一训练来源合同的固定惩罚 {manifest['failure_penalty']:.6f}，参数和寿命点分量只在合法估计上汇总。",
        "",
        f"正式结果包含 {manifest['validation']['n_models']} 个模型条件和 {manifest['validation']['n_rows']:,} 行评价。单一网络 seed 只能支持此冻结协议下的描述性比较；区间位置差异不能被解释为已经证明的普遍机制或校准后的部署边界。",
    ]
    (analysis_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    root = (RESEARCH_ROOT / "artifacts" / "smoke" / "training_domain_width_location_v1") if args.smoke else FORMAL_ROOT
    analysis_dir = root / "analysis"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(root / "per_sample_results.csv.gz", low_memory=False)
    validate_inputs(frame, manifest)
    typed = add_design_columns(frame, manifest)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    scenario_cols = ["budget_policy", "domain_id", "domain_label", "train_beta_min",
                     "train_beta_max", "train_beta_width", "n_train_per_n"]
    beta_summary = summarize(typed, scenario_cols + ["beta"])
    beta_n_summary = summarize(typed, scenario_cols + ["n", "beta"])
    point_summary = summarize(typed, scenario_cols + ["point_type"])

    width_ids = manifest["effect_families"]["width"]
    width_frame = typed[typed["domain_id"].isin(width_ids) & typed["beta"].between(2.5, 3.5)]
    width_common = summarize(width_frame, scenario_cols)

    location_ids = manifest["effect_families"]["location"]
    location_frame = typed[typed["domain_id"].isin(location_ids) & typed["relative_beta"].between(-0.5, 0.5)]
    location_aligned = summarize(location_frame, scenario_cols)
    location_by_offset = summarize(location_frame, scenario_cols + ["relative_beta"])

    family_rows = []
    for family, ids in manifest["effect_families"].items():
        part = beta_summary[beta_summary["domain_id"].isin(ids)].copy()
        part.insert(0, "effect_family", family)
        family_rows.append(part)
    same_beta = pd.concat(family_rows, ignore_index=True)

    outputs = {
        "beta_summary.csv": beta_summary,
        "beta_n_summary.csv": beta_n_summary,
        "point_type_summary.csv": point_summary,
        "width_common_beta_summary.csv": width_common,
        "location_aligned_summary.csv": location_aligned,
        "location_aligned_by_offset.csv": location_by_offset,
        "same_beta_summary.csv": same_beta,
    }
    for name, table in outputs.items():
        table.to_csv(analysis_dir / name, index=False)
    write_report(root, manifest, width_common, location_aligned, point_summary)
    paths = [analysis_dir / name for name in outputs] + [analysis_dir / "report.md"]
    (root / "ANALYSIS_SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}" for path in paths) + "\n",
        encoding="utf-8",
    )
    print(f"DOMAIN_WIDTH_LOCATION_ANALYSIS_COMPLETE rows={len(frame)}")


if __name__ == "__main__":
    main()
