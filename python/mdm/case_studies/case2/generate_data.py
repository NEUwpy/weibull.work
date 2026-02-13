"""
批量生成MDM案例2数据的脚本 (1000次模拟) - 分批生成版本

按β值分批生成，每个β值一个文件，最后合并
"""

import sys
import os
import numpy as np
import csv
import io
from contextlib import redirect_stdout

# 添加methods目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'methods'))

# 导入前禁用MDM的print输出
import builtins
original_print = builtins.print

def silent_print(*args, **kwargs):
    """静默print，只在需要时输出"""
    # 只允许包含特定关键字的输出通过
    if args and any(str(arg).startswith('[') for arg in args):
        pass  # 静默MDM调试输出
    else:
        original_print(*args, **kwargs)

# 临时替换print函数
builtins.print = silent_print

from mdm import MDM

# 恢复原始print函数（用于我们的进度输出）
builtins.print = original_print

# MDM 案例2 完整参数配置
TRUE_ETA = 1000      # 真实尺度参数
TRUE_GAMMA = 1000    # 真实位置参数

BETA_VALUES = [1.5, 2.0, 3, 5, 7]      # 形状参数变化
SAMPLE_SIZES = [5, 7, 10, 20, 30]      # 样本量变化
OFFSET_VALUES = [0, 0.05, 0.1, 0.15, 0.2]  # 偏移量变化
NUM_SIMULATIONS = 1000  # 每组1000次模拟

def generate_weibull_sample(beta, eta, gamma, n, seed):
    """生成指定参数的威布尔分布样本"""
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)

def estimate_mdm(sample, offset=None):
    """使用MDM方法估计参数（静默模式）"""
    try:
        algo = MDM(sample.tolist())

        # 捕获MDM内部的所有print输出
        with io.StringIO() as buf, redirect_stdout(buf):
            if offset is not None:
                res = algo.run(trace=False, offset=offset)
            else:
                res = algo.run(trace=False)

        return float(res[0]), float(res[1]), float(res[2]), float(res[3])
    except Exception as e:
        print(f"MDM估计失败: {e}")
        return 0, 0, 0, 0

def run_beta_batch(beta_val):
    """生成单个β值的所有数据"""
    filename = f"mdm_case2_beta{str(beta_val).replace('.', '_')}.csv"
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', filename)

    total_combinations = len(SAMPLE_SIZES) * len(OFFSET_VALUES)
    total_rows = total_combinations * NUM_SIMULATIONS

    print("=" * 60)
    print(f"MDM 案例2: β={beta_val} 批次")
    print("=" * 60)
    print(f"形状参数 β: {beta_val}")
    print(f"样本量 n: {SAMPLE_SIZES}")
    print(f"偏移量 δ: {OFFSET_VALUES}")
    print(f"固定参数: η={TRUE_ETA}, γ={TRUE_GAMMA}")
    print(f"参数组合数: {total_combinations}")
    print(f"每组模拟次数: {NUM_SIMULATIONS}")
    print(f"总数据行数: {total_rows}")
    print(f"输出文件: {filename}")
    print("=" * 60)
    print()

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Header
        writer.writerow([
            'beta_true', 'sample_size', 'offset_value', 'sim_id',
            'est_beta', 'est_eta', 'est_gamma',
            'bias_beta', 'bias_eta', 'bias_gamma',
            'r_squared'
        ])

        completed = 0
        for sample_size in SAMPLE_SIZES:
            for offset_val in OFFSET_VALUES:
                print(f"[{completed+1}/{total_combinations}] β={beta_val}, n={sample_size}, δ={offset_val}...")

                for sim_id in range(1, NUM_SIMULATIONS + 1):
                    # 生成样本
                    seed = sim_id + sample_size * 1000 + int(beta_val * 100) + int(offset_val * 1000)
                    sample = generate_weibull_sample(beta_val, TRUE_ETA, TRUE_GAMMA, sample_size, seed)

                    # MDM估计
                    est_beta, est_eta, est_gamma, r2 = estimate_mdm(sample, offset=offset_val)

                    # 计算偏差
                    bias_beta = est_beta - beta_val
                    bias_eta = est_eta - TRUE_ETA
                    bias_gamma = est_gamma - TRUE_GAMMA

                    writer.writerow([
                        beta_val, sample_size, offset_val, sim_id,
                        f'{est_beta:.6f}', f'{est_eta:.6f}', f'{est_gamma:.6f}',
                        f'{bias_beta:.6f}', f'{bias_eta:.6f}', f'{bias_gamma:.6f}',
                        f'{r2:.6f}'
                    ])

                completed += 1

    file_size_kb = os.path.getsize(csv_path) / 1024
    print(f"\n已保存: {csv_path}")
    print(f"文件大小: {file_size_kb:.1f} KB")
    print(f"β={beta_val} 批次完成！\n")

    return csv_path

def merge_beta_files():
    """合并所有β批次的文件"""
    print("=" * 60)
    print("合并所有批次文件...")
    print("=" * 60)

    output_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', 'mdm_case2_full.csv')

    all_rows = []
    header = None

    for beta_val in BETA_VALUES:
        filename = f"mdm_case2_beta{str(beta_val).replace('.', '_')}.csv"
        input_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', filename)

        if not os.path.exists(input_path):
            print(f"警告: 文件不存在 - {filename}")
            return False

        print(f"读取: {filename}...")
        with open(input_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            if header is None:
                header = next(reader)
            else:
                next(reader)  # 跳过表头
            all_rows.extend(list(reader))

        # 验证行数
        expected_rows = len(SAMPLE_SIZES) * len(OFFSET_VALUES) * NUM_SIMULATIONS
        actual_rows = len(all_rows) % expected_rows if len(all_rows) > expected_rows else expected_rows

    # 写入合并文件
    print(f"\n写入合并文件: mdm_case2_full.csv")
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(all_rows)

    total_rows = len(all_rows)
    expected_total = len(BETA_VALUES) * len(SAMPLE_SIZES) * len(OFFSET_VALUES) * NUM_SIMULATIONS

    print(f"总行数: {total_rows} (预期: {expected_rows})")

    if total_rows == expected_total:
        print("数据完整性验证: ✓ 通过")
        print(f"文件大小: {os.path.getsize(output_path) / 1024:.1f} KB")
        return True
    else:
        print(f"数据完整性验证: ✗ 失败 (缺少 {expected_total - total_rows} 行)")
        return False

def verify_beta_files():
    """验证每个β文件的数据完整性"""
    print("=" * 60)
    print("验证数据完整性...")
    print("=" * 60)

    all_valid = True
    for beta_val in BETA_VALUES:
        filename = f"mdm_case2_beta{str(beta_val).replace('.', '_')}.csv"
        input_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', filename)

        if not os.path.exists(input_path):
            print(f"✗ β={beta_val}: 文件不存在")
            all_valid = False
            continue

        # 计算行数（不含表头）
        with open(input_path, 'r', encoding='utf-8') as f:
            row_count = sum(1 for _ in f) - 1

        expected_rows = len(SAMPLE_SIZES) * len(OFFSET_VALUES) * NUM_SIMULATIONS

        if row_count == expected_rows:
            print(f"[OK] beta={beta_val}: {row_count} rows (complete)")
        else:
            print(f"[FAIL] beta={beta_val}: {row_count} rows (expected {expected_rows})")
            all_valid = False

    return all_valid

if __name__ == '__main__':
    import time
    start_time = time.time()

    print("\n" + "=" * 60)
    print("MDM 案例2 数据生成 (1000次模拟 - 分批版本)")
    print("=" * 60)
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 检查是否存在未完成的文件
    print("检查未完成的批次...")
    existing_files = []
    for beta_val in BETA_VALUES:
        filename = f"mdm_case2_beta{str(beta_val).replace('.', '_')}.csv"
        input_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', filename)
        if os.path.exists(input_path):
            existing_files.append(beta_val)
            print(f"  发现已有文件: β={beta_val}")

    if existing_files:
        print(f"\n已有 {len(existing_files)}/{len(BETA_VALUES)} 个批次文件")
        response = input("是否跳过已完成的批次？(y/n): ")
        skip_existing = response.lower() == 'y'
    else:
        skip_existing = False

    # 逐个生成β批次
    for beta_val in BETA_VALUES:
        if skip_existing:
            filename = f"mdm_case2_beta{str(beta_val).replace('.', '_')}.csv"
            input_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', filename)
            if os.path.exists(input_path):
                print(f"\n跳过 β={beta_val} (文件已存在)")
                continue

        run_beta_batch(beta_val)

    # 验证所有文件
    if verify_beta_files():
        # 合并文件
        if merge_beta_files():
            print("\n" + "=" * 60)
            print("全部完成！")
            print("=" * 60)
            elapsed = time.time() - start_time
            print(f"总耗时: {elapsed/60:.1f} 分钟")
            print(f"输出文件: public/cases/mdm_case2_full.csv")
        else:
            print("\n合并失败，请检查数据完整性")
    else:
        print("\n数据验证失败，请检查各批次文件")
