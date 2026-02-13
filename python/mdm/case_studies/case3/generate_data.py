"""
案例3数据生成脚本 - 梯度曲线不相交现象研究（简化版）

目标：找到1个无交点样本+9个有交点样本作为对比
参数：β=2.0, η=1000, γ=1000, n=7, δ=0.2
停止条件：找到1个无交点样本
"""

import sys
import os
import numpy as np
import csv
import json
from contextlib import redirect_stdout
import io
import time

# 添加methods目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'methods'))

# 导入MDM
from mdm import MDM

# 参数设置
TRUE_BETA = 2.0
TRUE_ETA = 1000
TRUE_GAMMA = 1000
SAMPLE_SIZE = 7
OFFSET_VALUE = 0.2

# 目标：1个无交点 + 9个有交点
TARGET_NON_INTERSECT = 1
TARGET_NORMAL = 9
MAX_TRIES = 100000  # 最大尝试次数（2小时timeout）

def generate_weibull_sample(beta, eta, gamma, n, seed):
    """生成指定参数的威布尔分布样本"""
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)

def analyze_mdm_with_curves(sample, offset=0.2):
    """运行MDM并记录完整的梯度曲线和标准差曲线"""
    try:
        algo = MDM(sample.tolist())

        # 捕获MDM输出
        with io.StringIO() as buf, redirect_stdout(buf):
            res = algo.run(trace=True, offset=offset)

        beta_est, eta_est, gamma_est, r2, converged = res

        # 获取trace数据
        trace_data = algo.trace_data

        # 判断是否有交点
        grad_curve = trace_data.get('grad_gamma_curve', [])
        if not grad_curve:
            return None

        gradients = [point['gradient'] for point in grad_curve]

        # 检查是否有交点（梯度曲线穿过offset）
        has_intersection = check_intersection(gradients, offset)

        # 分析梯度形态
        gradient_type = classify_gradient(gradients, offset)

        return {
            'sample': sample.tolist(),  # 保存原始样本数据！
            'beta_est': float(beta_est),
            'eta_est': float(eta_est),
            'gamma_est': float(gamma_est),
            'r2': float(r2),
            'has_intersection': has_intersection,
            'gradient_type': gradient_type,
            'grad_gamma_curve': grad_curve,
            'sigma_beta_curve': trace_data.get('sigma_beta_curve', []),
            'optimal_gamma': trace_data.get('optimal_gamma', 0),
            'optimal_beta': trace_data.get('optimal_beta', 0),
            'gradient_range': [float(min(gradients)), float(max(gradients))],
            'sigma_min_range': [
                float(min(p['sigma_min'] for p in grad_curve)),
                float(max(p['sigma_min'] for p in grad_curve))
            ]
        }
    except Exception as e:
        print(f"MDM分析失败: {e}")
        return None

def check_intersection(gradients, offset):
    """检查梯度曲线是否与offset有交点"""
    diffs = [g - offset for g in gradients]

    # 检查符号变化
    for i in range(len(diffs) - 1):
        if diffs[i] == 0:
            return True
        if diffs[i] * diffs[i + 1] < 0:
            return True

    return False

def classify_gradient(gradients, offset):
    """分类梯度曲线形态"""
    min_grad = min(gradients)
    max_grad = max(gradients)

    if check_intersection(gradients, offset):
        return 'normal'  # 有交点

    if min_grad > offset:
        return 'above_offset'  # 梯度全在offset上方
    elif max_grad < offset:
        return 'below_offset'  # 梯度全在offset下方

    # 检查单调性
    is_increasing = all(gradients[i] <= gradients[i+1] for i in range(len(gradients)-1))
    is_decreasing = all(gradients[i] >= gradients[i+1] for i in range(len(gradients)-1))

    if is_increasing:
        return 'all_positive'  # 全正梯度（单调递增）
    elif is_decreasing:
        return 'all_negative'  # 全负梯度（单调递减）

    return 'other'

def generate_case3_samples():
    """
    生成目标样本：1个无交点 + 9个有交点
    持续抽样直到找到无交点现象
    """
    print("=" * 60)
    print("案例3: 无交点现象样本收集")
    print("=" * 60)
    print(f"真实参数: β={TRUE_BETA}, η={TRUE_ETA}, γ={TRUE_GAMMA}")
    print(f"样本量: n={SAMPLE_SIZE}")
    print(f"偏移值: δ={OFFSET_VALUE}")
    print(f"目标: {TARGET_NON_INTERSECT}个无交点 + {TARGET_NORMAL}个有交点")
    print("=" * 60)
    print()

    # 收集结果
    non_intersect_samples = []
    normal_samples = []

    sim_id = 0
    start_time = time.time()

    # 持续抽样直到收集完成
    while len(non_intersect_samples) < TARGET_NON_INTERSECT or len(normal_samples) < TARGET_NORMAL:
        sim_id += 1

        # 超时检查（2小时）
        elapsed = time.time() - start_time
        if elapsed > 7200:  # 2小时 = 7200秒
            print(f"\n已达到2小时超时限制，停止抽样。")
            break

        # 进度报告
        if sim_id % 100 == 0:
            elapsed_min = elapsed / 60
            print(f"进度: 已尝试 {sim_id} 次 ({elapsed_min:.1f}分钟) | "
                  f"无交点: {len(non_intersect_samples)}/{TARGET_NON_INTERSECT}, "
                  f"有交点: {len(normal_samples)}/{TARGET_NORMAL}")

        # 生成样本
        seed = sim_id
        sample = generate_weibull_sample(TRUE_BETA, TRUE_ETA, TRUE_GAMMA, SAMPLE_SIZE, seed)

        # 分析
        result = analyze_mdm_with_curves(sample, OFFSET_VALUE)

        if result is None:
            continue

        # 添加sim_id到结果
        result['sim_id'] = sim_id

        # 分类收集
        if not result['has_intersection']:
            if len(non_intersect_samples) < TARGET_NON_INTERSECT:
                non_intersect_samples.append(result)
                print(f"[找到无交点样本 #{sim_id}] 类型: {result['gradient_type']}")
        else:
            if len(normal_samples) < TARGET_NORMAL:
                normal_samples.append(result)

    # 合并所有样本（无交点在前，有交点在后）
    all_samples = non_intersect_samples + normal_samples

    # 保存结果
    save_results(all_samples, sim_id, time.time() - start_time)

    return len(all_samples)

def save_results(samples, total_tries, elapsed_time):
    """保存结果到文件"""
    base_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases')

    # 1. 保存完整数据JSON（包含曲线数据）
    json_path = os.path.join(base_path, 'mdm_case3_data.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'parameters': {
                'true_beta': TRUE_BETA,
                'true_eta': TRUE_ETA,
                'true_gamma': TRUE_GAMMA,
                'sample_size': SAMPLE_SIZE,
                'offset': OFFSET_VALUE
            },
            'statistics': {
                'total_tries': total_tries,
                'collected_samples': len(samples),
                'elapsed_time_minutes': elapsed_time / 60,
                'non_intersect_count': sum(1 for s in samples if not s['has_intersection']),
                'normal_count': sum(1 for s in samples if s['has_intersection'])
            },
            'samples': samples
        }, f, ensure_ascii=False, indent=2)

    # 2. 保存CSV摘要
    csv_path = os.path.join(base_path, 'mdm_case3_summary.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'sim_id', 'has_intersection', 'gradient_type',
            'est_beta', 'est_eta', 'est_gamma', 'r_squared',
            'grad_min', 'grad_max', 'sigma_min_min', 'sigma_min_max',
            'sample_data'
        ])

        for s in samples:
            writer.writerow([
                s['sim_id'],
                s['has_intersection'],
                s['gradient_type'],
                f"{s['beta_est']:.6f}",
                f"{s['eta_est']:.6f}",
                f"{s['gamma_est']:.6f}",
                f"{s['r2']:.6f}",
                f"{s['gradient_range'][0]:.6f}",
                f"{s['gradient_range'][1]:.6f}",
                f"{s['sigma_min_range'][0]:.6f}",
                f"{s['sigma_min_range'][1]:.6f}",
                json.dumps(s['sample'])
            ])

    # 3. 保存仅曲线数据的JSON（供前端可视化使用）
    curves_path = os.path.join(base_path, 'mdm_case3_curves.json')
    with open(curves_path, 'w', encoding='utf-8') as f:
        # 只保存可视化需要的字段
        curves_data = []
        for s in samples:
            curves_data.append({
                'sim_id': s['sim_id'],
                'has_intersection': s['has_intersection'],
                'gradient_type': s['gradient_type'],
                'est_gamma': s['gamma_est'],
                'est_beta': s['beta_est'],
                'est_eta': s['eta_est'],
                'grad_gamma_curve': s['grad_gamma_curve'],
                'sigma_beta_curve': s['sigma_beta_curve']
            })
        json.dump(curves_data, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print("保存完成:")
    print("=" * 60)
    print(f"完整数据: {json_path}")
    print(f"CSV摘要: {csv_path}")
    print(f"曲线数据: {curves_path}")
    print(f"总耗时: {elapsed_time/60:.1f} 分钟")
    print(f"总尝试: {total_tries} 次")
    print(f"收集样本: {len(samples)} 个")
    print(f"  - 无交点: {sum(1 for s in samples if not s['has_intersection'])}")
    print(f"  - 有交点: {sum(1 for s in samples if s['has_intersection'])}")
    print()

if __name__ == '__main__':
    print()
    print("=" * 60)
    print("MDM 案例3: 无交点梯度曲线样本生成")
    print("=" * 60)
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标: 找到 {TARGET_NON_INTERSECT} 个无交点样本 + {TARGET_NORMAL} 个有交点样本")
    print(f"超时: 2小时")
    print()

    collected = generate_case3_samples()

    print()
    print("=" * 60)
    print("生成完成！")
    print("=" * 60)
    print(f"成功收集 {collected} 个样本")
    print(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
