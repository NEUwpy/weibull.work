"""
MDM 真值抽样估计 — 实验入口脚本

调用 python/studies/common/experiment.py::run_experiment()，
配置参数网格并输出 results.csv + summary.json + manifest.json。

用法:
    cd python
    python studies/mdm/run_truth_sampling.py              # pilot（小规模）
    python studies/mdm/run_truth_sampling.py --full        # 正式（完整网格）
    python studies/mdm/run_truth_sampling.py --repeats 200 # 自定义 repeats
    python studies/mdm/run_truth_sampling.py --seed 42     # 自定义 seed namespace

产物目录:
    python/output/truth_sampling/<tag>/  （默认 pilot，--full 时 tag=full）
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# 添加项目根目录到路径（脚本在 python/studies/mdm/ 下，上 4 级到项目根）
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python"))

from studies.common.experiment import run_experiment

# ============================================================
# 参数网格定义
# ============================================================

# Pilot 网格：快速验证流水线
PILOT_PARAM_GRID = [
    (2.0, 100.0, 5.0),   # 经典中等形状
    (3.0, 100.0, 0.0),   # 零位置参数边界
]
PILOT_N_VALUES = [20, 30]
PILOT_REPEATS = 50

# 正式网格：完整真值抽样
FULL_PARAM_GRID = [
    (1.5, 100.0, 5.0),
    (2.0, 100.0, 5.0),
    (3.0, 100.0, 5.0),
    (5.0, 100.0, 5.0),
    (2.0, 100.0, 0.0),
    (3.0, 100.0, 0.0),
]
FULL_N_VALUES = [10, 15, 20, 30, 50]
FULL_REPEATS = 500

# MDM 方法配置
MDM_METHODS = [
    ("mdm", {"offset": 0.1}),
]

# 工程寿命可靠度水平
R_LEVELS = (0.95, 0.99)
DIAGNOSTIC_R_LEVELS = (0.50, 0.90, 0.95, 0.99, 0.999)

# 固定 seed namespace，保证可复现
DEFAULT_SEED_NAMESPACE = 2026


def _git_version() -> str:
    """读取当前 git commit short hash，失败时返回 unknown"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def run_pilot(args):
    """运行 pilot 实验"""
    output_dir = args.output or str(
        PROJECT_ROOT / "python" / "output" / "truth_sampling" / "pilot"
    )
    repeats = args.repeats or PILOT_REPEATS
    seed = args.seed if args.seed is not None else DEFAULT_SEED_NAMESPACE
    code_version = args.code_version or _git_version()

    print("=" * 60)
    print("MDM 真值抽样估计 — PILOT")
    print("=" * 60)
    print(f"  参数组合:   {len(PILOT_PARAM_GRID)}")
    print(f"  样本量:     {PILOT_N_VALUES}")
    print(f"  重复次数:   {repeats}")
    print(f"  Seed:       {seed}")
    print(f"  code_version: {code_version}")
    print(f"  输出目录:   {output_dir}")
    print()

    summary = run_experiment(
        methods=MDM_METHODS,
        param_grid=PILOT_PARAM_GRID,
        n_values=PILOT_N_VALUES,
        n_repeats=repeats,
        output_dir=output_dir,
        R_levels=R_LEVELS,
        diagnostic_R_levels=DIAGNOSTIC_R_LEVELS,
        seed_namespace=seed,
        code_version=code_version,
        run_label="pilot",
    )

    _print_summary(summary)
    _print_manifest_check(output_dir)
    return summary


def run_full(args):
    """运行正式实验"""
    output_dir = args.output or str(
        PROJECT_ROOT / "python" / "output" / "truth_sampling" / "full"
    )
    repeats = args.repeats or FULL_REPEATS
    seed = args.seed if args.seed is not None else DEFAULT_SEED_NAMESPACE
    code_version = args.code_version or _git_version()

    print("=" * 60)
    print("MDM 真值抽样估计 — FULL")
    print("=" * 60)
    print(f"  参数组合:   {len(FULL_PARAM_GRID)}")
    print(f"  样本量:     {FULL_N_VALUES}")
    print(f"  重复次数:   {repeats}")
    print(f"  Seed:       {seed}")
    print(f"  code_version: {code_version}")
    print(f"  输出目录:   {output_dir}")
    total = len(FULL_PARAM_GRID) * len(FULL_N_VALUES) * repeats
    print(f"  总行数:     {total}")
    print()

    summary = run_experiment(
        methods=MDM_METHODS,
        param_grid=FULL_PARAM_GRID,
        n_values=FULL_N_VALUES,
        n_repeats=repeats,
        output_dir=output_dir,
        R_levels=R_LEVELS,
        diagnostic_R_levels=DIAGNOSTIC_R_LEVELS,
        seed_namespace=seed,
        code_version=code_version,
        run_label="full-v1",
    )

    _print_summary(summary)
    _print_manifest_check(output_dir)
    return summary


def _print_summary(summary):
    """打印关键指标摘要"""
    print()
    print("-" * 60)
    print("结果摘要")
    print("-" * 60)
    for key, group in sorted(summary.items()):
        variant = group.get("method_variant", "?")
        b, e, g = group.get("beta"), group.get("eta"), group.get("gamma")
        n = group.get("n")
        vr = group.get("valid_rate", 0)
        bias_b = group.get("bias_beta", "—")
        rmse_b = group.get("rmse_beta", "—")
        mae_b = group.get("mae_beta", "—")
        print(f"  {key}")
        print(f"    valid_rate={vr:.1%}  "
              f"Bias(β)={bias_b}  RMSE(β)={rmse_b}  MAE(β)={mae_b}")
    print()


def _print_manifest_check(output_dir):
    """验证 manifest.json 产出"""
    manifest_path = os.path.join(output_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        print("⚠️  manifest.json 不存在！")
        return

    with open(manifest_path, encoding="utf-8") as f:
        m = json.load(f)

    print("-" * 60)
    print("Manifest 溯源检查")
    print("-" * 60)
    print(f"  code_version:     {m.get('code_version')}")
    print(f"  run_label:        {m.get('run_label')}")
    print(f"  generated_at:     {m.get('generated_at')}")
    print(f"  seed_namespace:   {m.get('seed_namespace')}")
    print(f"  total_rows:       {m.get('total_rows')}")
    print(f"  methods:          {[x['method_id'] + ':' + str(x['kwargs']) for x in m.get('methods', [])]}")
    print(f"  R_levels:         {m.get('metrics', {}).get('R_levels')}")
    print(f"  diag_R_levels:    {m.get('metrics', {}).get('diagnostic_R_levels')}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="MDM 真值抽样估计 — 实验入口"
    )
    parser.add_argument(
        "--full", action="store_true",
        help="运行正式完整网格（默认为 pilot）"
    )
    parser.add_argument(
        "--repeats", type=int, default=None,
        help="覆盖默认重复次数"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="覆盖默认 seed namespace"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="覆盖默认输出目录"
    )
    parser.add_argument(
        "--code-version", type=str, default=None, dest="code_version",
        help="覆盖 git commit hash 作为 code_version"
    )

    args = parser.parse_args()

    if args.full:
        run_full(args)
    else:
        run_pilot(args)


if __name__ == "__main__":
    main()
