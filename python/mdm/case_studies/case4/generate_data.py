"""
⚠ 历史复现实验，不是当前默认 MDM 口径

批量生成MDM案例4数据的脚本 (1000次模拟) - 使用新MDM算法

生成两个文件：
1. mdm_case4_full.csv - 主结果文件（估计参数、偏差、R²等）
2. mdm_case4_samples.csv - 样本文件（每次模拟的抽样样本）

关联方式：通过 sim_id + beta_true + sample_size + offset_value 联合键关联

S4.9 后默认 MDM 已重写（几何加密网格+约束边界规则），本脚本仅用于历史案例复现。
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
    if args and any(str(arg).startswith('[') for arg in args):
        pass  # 静默MDM调试输出
    else:
        original_print(*args, **kwargs)

# 临时替换print函数
builtins.print = silent_print

from mdm import MDM

# 恢复原始print函数（用于我们的进度输出）
builtins.print = original_print

# MDM 案例4 完整参数配置
TRUE_ETA = 1000      # 真实尺度参数
TRUE_GAMMA = 1000    # 真实位置参数

BETA_VALUES = [1.5, 2.0, 3, 5, 7]      # 形状参数变化
SAMPLE_SIZES = [5, 7, 10, 20, 30]      # 样本量变化
OFFSET_VALUES = [0, 0.05, 0.1, 0.15, 0.2]  # 偏移量变化
NUM_SIMULATIONS = 1000  # 每组1000次模拟
MAX_SAMPLE_SIZE = max(SAMPLE_SIZES)  # 30，用于样本CSV的列数

def generate_weibull_sample(beta, eta, gamma, n, seed):
    """生成指定参数的威布尔分布样本"""
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)

def estimate_mdm(sample, offset=None):
    """
    使用新MDM方法估计参数（静默模式）
    返回: (est_beta, est_eta, est_gamma, r2, converged) 或 None (无解时)
    """
    try:
        algo = MDM(sample.tolist())

        # 捕获MDM内部的所有print输出
        with io.StringIO() as buf, redirect_stdout(buf):
            if offset is not None:
                res = algo.run(trace=False, offset=offset)
            else:
                res = algo.run(trace=False)

        # 新算法返回5个值: (beta, eta, gamma, r2, converged)
        if len(res) >= 5:
            converged = res[4]
        else:
            converged = True

        # 如果是 no_intersection，返回 None
        if converged == "no_intersection":
            return None

        return float(res[0]), float(res[1]), float(res[2]), float(res[3]), converged

    except Exception as e:
        print(f"MDM估计失败: {e}")
        return None

def run_beta_batch(beta_val):
    """生成单个β值的所有数据"""
    # 主结果CSV路径
    results_filename = f"mdm_case4_beta{str(beta_val).replace('.', '_')}.csv"
    results_csv_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', results_filename)

    # 样本CSV路径
    samples_filename = f"mdm_case4_samples_beta{str(beta_val).replace('.', '_')}.csv"
    samples_csv_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', samples_filename)

    total_combinations = len(SAMPLE_SIZES) * len(OFFSET_VALUES)
    total_rows = total_combinations * NUM_SIMULATIONS

    print("=" * 60)
    print(f"MDM 案例4: β={beta_val} 批次 (新算法)")
    print("=" * 60)
    print(f"形状参数 β: {beta_val}")
    print(f"样本量 n: {SAMPLE_SIZES}")
    print(f"偏移量 δ: {OFFSET_VALUES}")
    print(f"固定参数: η={TRUE_ETA}, γ={TRUE_GAMMA}")
    print(f"参数组合数: {total_combinations}")
    print(f"每组模拟次数: {NUM_SIMULATIONS}")
    print(f"总数据行数: {total_rows} (无解情况标记为NaN)")
    print(f"输出文件: {results_filename}, {samples_filename}")
    print("=" * 60)
    print()

    # 打开两个CSV文件
    with open(results_csv_path, 'w', newline='', encoding='utf-8') as results_f, \
         open(samples_csv_path, 'w', newline='', encoding='utf-8') as samples_f:

        results_writer = csv.writer(results_f)
        samples_writer = csv.writer(samples_f)

        # 主结果CSV Header
        results_writer.writerow([
            'beta_true', 'sample_size', 'offset_value', 'sim_id',
            'est_beta', 'est_eta', 'est_gamma',
            'bias_beta', 'bias_eta', 'bias_gamma',
            'r_squared'
        ])

        # 样本CSV Header (顺序与full CSV一致)
        sample_headers = ['beta_true', 'sample_size', 'offset_value', 'sim_id']
        sample_headers.extend([f't{i}' for i in range(1, MAX_SAMPLE_SIZE + 1)])
        samples_writer.writerow(sample_headers)

        completed = 0
        skipped_count = 0

        for sample_size in SAMPLE_SIZES:
            for offset_val in OFFSET_VALUES:
                print(f"[{completed+1}/{total_combinations}] β={beta_val}, n={sample_size}, δ={offset_val}...")

                for sim_id in range(1, NUM_SIMULATIONS + 1):
                    # 生成样本（总是生成，无论MDM是否有解）
                    seed = sim_id + sample_size * 1000 + int(beta_val * 100) + int(offset_val * 1000)
                    sample = generate_weibull_sample(beta_val, TRUE_ETA, TRUE_GAMMA, sample_size, seed)

                    # 【优先写入样本CSV】样本数据独立于MDM估计，应完整记录
                    sample_row = [beta_val, sample_size, offset_val, sim_id]
                    sample_row.extend([float(x) for x in sample])
                    # 补齐到 MAX_SAMPLE_SIZE 列
                    sample_row.extend([0.0] * (MAX_SAMPLE_SIZE - sample_size))
                    samples_writer.writerow(sample_row)

                    # MDM估计（新算法）
                    result = estimate_mdm(sample, offset=offset_val)

                    # 准备结果行（无论是否有解都写入，无解时用NaN标记）
                    if result is None:
                        # 无解情况：用NaN标记，不跳过
                        skipped_count += 1
                        est_beta, est_eta, est_gamma, r2 = float('nan'), float('nan'), float('nan'), float('nan')
                        bias_beta, bias_eta, bias_gamma = float('nan'), float('nan'), float('nan')
                    else:
                        est_beta, est_eta, est_gamma, r2, converged = result
                        # 计算偏差
                        bias_beta = est_beta - beta_val
                        bias_eta = est_eta - TRUE_ETA
                        bias_gamma = est_gamma - TRUE_GAMMA

                    # 写入主结果CSV（总是写入）
                    # 使用字符串'NaN'确保CSV格式正确
                    results_writer.writerow([
                        beta_val, sample_size, offset_val, sim_id,
                        'NaN' if np.isnan(est_beta) else f'{est_beta:.6f}',
                        'NaN' if np.isnan(est_eta) else f'{est_eta:.6f}',
                        'NaN' if np.isnan(est_gamma) else f'{est_gamma:.6f}',
                        'NaN' if np.isnan(bias_beta) else f'{bias_beta:.6f}',
                        'NaN' if np.isnan(bias_eta) else f'{bias_eta:.6f}',
                        'NaN' if np.isnan(bias_gamma) else f'{bias_gamma:.6f}',
                        'NaN' if np.isnan(r2) else f'{r2:.6f}'
                    ])

                completed += 1

                # 打印无解统计
                if skipped_count > 0:
                    print(f"  -> {skipped_count} 条记录无解 (标记为NaN)")

    results_size_kb = os.path.getsize(results_csv_path) / 1024
    samples_size_kb = os.path.getsize(samples_csv_path) / 1024

    print(f"\n已保存:")
    print(f"  结果: {results_csv_path} ({results_size_kb:.1f} KB)")
    print(f"  样本: {samples_csv_path} ({samples_size_kb:.1f} KB)")
    print(f"β={beta_val} 批次完成！\n")

    return results_csv_path, samples_csv_path

def merge_beta_files():
    """合并所有β批次的文件"""
    print("=" * 60)
    print("合并所有批次文件...")
    print("=" * 60)

    results_output_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', 'mdm_case4_full.csv')
    samples_output_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', 'mdm_case4_samples.csv')

    all_results_rows = []
    all_samples_rows = []
    results_header = None
    samples_header = None

    for beta_val in BETA_VALUES:
        results_filename = f"mdm_case4_beta{str(beta_val).replace('.', '_')}.csv"
        samples_filename = f"mdm_case4_samples_beta{str(beta_val).replace('.', '_')}.csv"

        results_input_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', results_filename)
        samples_input_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', samples_filename)

        if not os.path.exists(results_input_path):
            print(f"警告: 结果文件不存在 - {results_filename}")
            return False
        if not os.path.exists(samples_input_path):
            print(f"警告: 样本文件不存在 - {samples_filename}")
            return False

        print(f"读取: {results_filename} + {samples_filename}...")
        with open(results_input_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            if results_header is None:
                results_header = next(reader)
            else:
                next(reader)  # 跳过表头
            all_results_rows.extend(list(reader))

        with open(samples_input_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            if samples_header is None:
                samples_header = next(reader)
            else:
                next(reader)  # 跳过表头
            all_samples_rows.extend(list(reader))

    # 写入合并文件
    print(f"\n写入合并文件...")
    with open(results_output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(results_header)
        writer.writerows(all_results_rows)

    with open(samples_output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(samples_header)
        writer.writerows(all_samples_rows)

    results_total_rows = len(all_results_rows)
    samples_total_rows = len(all_samples_rows)
    expected_max = len(BETA_VALUES) * len(SAMPLE_SIZES) * len(OFFSET_VALUES) * NUM_SIMULATIONS

    print(f"结果文件总行数: {results_total_rows}/{expected_max}")
    print(f"样本文件总行数: {samples_total_rows}/{expected_max}")

    # 统计无解数量
    if results_total_rows > 0:
        # 重新读取合并后的结果文件统计NaN
        with open(results_output_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            no_solution_count = sum(1 for row in reader if row['est_beta'] == 'NaN')
        print(f"无解记录数: {no_solution_count} ({no_solution_count/results_total_rows*100:.1f}%)")

    results_size_kb = os.path.getsize(results_output_path) / 1024
    samples_size_kb = os.path.getsize(samples_output_path) / 1024
    print(f"结果文件大小: {results_size_kb:.1f} KB")
    print(f"样本文件大小: {samples_size_kb:.1f} KB")

    return True

def verify_beta_files():
    """验证每个β文件的数据完整性"""
    print("=" * 60)
    print("验证数据完整性...")
    print("=" * 60)

    all_valid = True
    for beta_val in BETA_VALUES:
        results_filename = f"mdm_case4_beta{str(beta_val).replace('.', '_')}.csv"
        samples_filename = f"mdm_case4_samples_beta{str(beta_val).replace('.', '_')}.csv"

        results_input_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', results_filename)
        samples_input_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', samples_filename)

        if not os.path.exists(results_input_path):
            print(f"✗ β={beta_val}: 结果文件不存在")
            all_valid = False
            continue
        if not os.path.exists(samples_input_path):
            print(f"✗ β={beta_val}: 样本文件不存在")
            all_valid = False
            continue

        # 计算行数（不含表头）
        with open(results_input_path, 'r', encoding='utf-8') as f:
            results_row_count = sum(1 for _ in f) - 1

        with open(samples_input_path, 'r', encoding='utf-8') as f:
            samples_row_count = sum(1 for _ in f) - 1

        expected_rows = len(SAMPLE_SIZES) * len(OFFSET_VALUES) * NUM_SIMULATIONS

        # 检查两文件行数是否一致且等于预期值
        if results_row_count == expected_rows and samples_row_count == expected_rows:
            # 统计无解数量（读取结果文件检查NaN）
            with open(results_input_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                no_solution_count = sum(1 for row in reader if row['est_beta'] == 'NaN')
            print(f"[OK] beta={beta_val}: {results_row_count}/{expected_rows} rows ({no_solution_count} 条无解)")
        else:
            print(f"[FAIL] beta={beta_val}: 结果{results_row_count}行, 样本{samples_row_count}行, 预期{expected_rows}行")
            all_valid = False

    return all_valid

if __name__ == '__main__':
    import time
    start_time = time.time()

    print("\n" + "=" * 60)
    print("MDM 案例4 数据生成 (1000次模拟 - 新算法)")
    print("=" * 60)
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 检查是否存在未完成的文件
    print("检查未完成的批次...")
    existing_files = []
    for beta_val in BETA_VALUES:
        results_filename = f"mdm_case4_beta{str(beta_val).replace('.', '_')}.csv"
        results_input_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', results_filename)
        if os.path.exists(results_input_path):
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
            results_filename = f"mdm_case4_beta{str(beta_val).replace('.', '_')}.csv"
            results_input_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', results_filename)
            if os.path.exists(results_input_path):
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
            print(f"输出文件:")
            print(f"  - public/cases/mdm_case4_full.csv")
            print(f"  - public/cases/mdm_case4_samples.csv")
        else:
            print("\n合并失败，请检查数据完整性")
    else:
        print("\n数据验证失败，请检查各批次文件")
