"""
MLE 方法通用仿真脚本 (单变量+双变量模式)

用途：
    从 config.md 读取参数配置，生成蒙特卡洛仿真数据
    支持"单变量+双变量"模式，避免全交叉组合

使用方法：
    cd python/studies/mle

    # 生成所有分片（增量模式，跳过已存在的）
    python simulate.py demo1

    # 强制重新生成所有分片
    python simulate.py demo1 --force

    # 只生成指定参数组合
    python simulate.py demo1 --only beta=1.5

    # 合并所有分片为 data.csv
    python simulate.py demo1 --merge

    # 查看状态
    python simulate.py demo1 --status

    # 清理所有分片和索引
    python simulate.py demo1 --clean

配置文件格式 (config.md)：
    配置文件位于 public/studies/mle/<study_id>/config.md
    必须包含 params 和 simulation 配置
    simulation.mode: "partial_cross" 表示单变量+双变量模式

输出文件：
    chunks/
    ├── index.json           # 分片索引
    ├── b1.5_e1000_n10.csv   # 分片数据
    └── ...
    data.csv                 # 合并后的完整数据（前端加载）
    summary.json             # 汇总统计

作者：Claude Code
日期：2026-03-16
"""

import sys
import os
import json
import csv
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

import yaml
from methods.mle import MLE


# 参数 ID 到分片文件名简写的映射
PARAM_TO_SHORT = {
    'beta': 'b',
    'eta': 'e',
    'sampleSize': 'n',
    'gamma': 'g',
}

# 参数 ID 到 CSV 列名的映射
PARAM_TO_CSV_COLUMN = {
    'beta': 'beta_true',
    'eta': 'eta_true',
    'gamma': 'gamma_true',
    'sampleSize': 'sample_size',
}


def parse_config(config_path: str) -> dict:
    """解析 config.md 文件，返回配置字典"""
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 使用 gray-matter 格式解析 (YAML front matter + Markdown body)
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            yaml_content = parts[1]
            config = yaml.safe_load(yaml_content)
            return config

    raise ValueError(f"无法解析配置文件: {config_path}")


def get_param_values(param: dict) -> list:
    """获取参数的所有取值"""
    state = param.get('state', 'fixed')

    if state == 'fixed':
        return [param.get('fixedValue', 0)]
    elif state == 'discrete':
        return param.get('discreteValues', [])
    elif state == 'range':
        r = param.get('range', {})
        min_val = r.get('min', 0)
        max_val = r.get('max', 1)
        return list(np.linspace(min_val, max_val, 5))
    else:
        return [param.get('fixedValue', 0)]


def generate_chunk_filename(variable_params: List[str], combo: tuple) -> str:
    """生成分片文件名"""
    parts = []
    for i, param_id in enumerate(variable_params):
        short = PARAM_TO_SHORT.get(param_id, param_id[0])
        val = combo[i]
        # 按参数类型格式化
        if param_id == 'beta':
            parts.append(f"{short}{val:.1f}")
        elif param_id == 'sampleSize':
            parts.append(f"{short}{int(val)}")
        else:
            if isinstance(val, float) and val == int(val):
                parts.append(f"{short}{int(val)}")
            else:
                parts.append(f"{short}{val}")
    return "_".join(parts) + ".csv"


def generate_weibull_sample(beta: float, eta: float, gamma: float, n: int, seed: int) -> np.ndarray:
    """生成三参数威布尔分布样本"""
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)


def run_mle_estimation(sample: np.ndarray):
    """
    运行 MLE 估计
    返回: (est_beta, est_eta, est_gamma, r2, status) 或 None (失败时)
    """
    try:
        algo = MLE(sample.tolist())
        result = algo.run(trace=False)

        if result is None or len(result) < 4:
            return None

        return result
    except Exception as e:
        print(f"MLE 估计失败: {e}")
        return None


def load_index(chunks_dir: Path) -> dict:
    """加载索引文件"""
    index_path = chunks_dir / 'index.json'
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "version": 1,
        "lastUpdated": None,
        "config": {},
        "chunks": [],
        "stats": {
            "generatedCombos": 0,
            "totalRuns": 0,
            "totalFailures": 0
        },
        "mergedAt": None
    }


def save_index(chunks_dir: Path, index: dict):
    """保存索引文件"""
    index['lastUpdated'] = datetime.now().isoformat(timespec='seconds')
    index_path = chunks_dir / 'index.json'
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def get_existing_chunks(index: dict) -> Dict[str, dict]:
    """获取已存在分片的映射 {filename: chunk_info}"""
    return {chunk['file']: chunk for chunk in index.get('chunks', [])}


def generate_partial_cross_combinations(
    params: List[dict],
    defaults: dict
) -> List[Tuple[List[str], tuple]]:
    """
    生成单变量+双变量模式的参数组合

    返回: [(变量参数名列表, 参数值元组), ...]
    """
    # 获取所有变量参数
    variable_params = []
    for p in params:
        if p.get('isVariable', False) and p.get('state') != 'fixed':
            variable_params.append(p)

    if not variable_params:
        return []

    combinations = []

    # 1. 单变量研究：每次只变一个参数
    for vp in variable_params:
        pid = vp['id']
        values = get_param_values(vp)
        for val in values:
            # 固定其他参数为默认值
            combo = {}
            for p in variable_params:
                if p['id'] == pid:
                    combo[pid] = val
                else:
                    # 使用默认值
                    combo[p['id']] = defaults.get(p['id'], get_param_values(p)[0])
            # 按 params 顺序构建元组
            param_names = [p['id'] for p in variable_params]
            combo_tuple = tuple(combo[name] for name in param_names)
            combinations.append((param_names, combo_tuple))

    # 2. 双变量研究：每次变两个参数
    from itertools import combinations as iter_combinations
    for vp1, vp2 in iter_combinations(variable_params, 2):
        pid1, pid2 = vp1['id'], vp2['id']
        values1 = get_param_values(vp1)
        values2 = get_param_values(vp2)

        for v1 in values1:
            for v2 in values2:
                combo = {}
                for p in variable_params:
                    if p['id'] == pid1:
                        combo[pid1] = v1
                    elif p['id'] == pid2:
                        combo[pid2] = v2
                    else:
                        combo[p['id']] = defaults.get(p['id'], get_param_values(p)[0])
                param_names = [p['id'] for p in variable_params]
                combo_tuple = tuple(combo[name] for name in param_names)
                combinations.append((param_names, combo_tuple))

    # 去重（保持顺序）
    seen = set()
    unique_combinations = []
    for param_names, combo in combinations:
        key = (tuple(param_names), combo)
        if key not in seen:
            seen.add(key)
            unique_combinations.append((param_names, combo))

    return unique_combinations


def run_single_chunk(
    combo: tuple,
    param_names: List[str],
    param_csv_columns: List[str],
    fixed_params: dict,
    defaults: dict,
    mc_runs: int,
    output_path: Path,
    verbose: bool = False
) -> dict:
    """运行单个参数组合的仿真"""
    # 构建当前参数组合
    current_params = dict(fixed_params)
    for i, name in enumerate(param_names):
        current_params[name] = combo[i]

    # 获取当前参数值
    true_beta = current_params.get('beta', defaults.get('beta', 2.0))
    true_eta = current_params.get('eta', defaults.get('eta', 1000))
    true_gamma = current_params.get('gamma', defaults.get('gamma', 1000))
    sample_size = int(current_params.get('sampleSize', defaults.get('sampleSize', 10)))

    failure_count = 0

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # 写入表头
        header = param_csv_columns + ['sim_id', 'est_beta', 'est_eta', 'est_gamma',
                                       'bias_beta', 'bias_eta', 'bias_gamma', 'r_squared']
        writer.writerow(header)

        for sim_id in range(1, mc_runs + 1):
            # 生成种子
            seed = sim_id
            for name in param_names:
                val = current_params[name]
                if isinstance(val, float):
                    seed += int(val * 1000)
                else:
                    seed += int(val) * 1000

            # 生成样本
            sample = generate_weibull_sample(true_beta, true_eta, true_gamma, sample_size, seed)

            # MLE 估计
            result = run_mle_estimation(sample)

            # 写入结果
            row = list(combo) + [sim_id]

            if result is None:
                failure_count += 1
                row.extend(['NaN', 'NaN', 'NaN', 'NaN', 'NaN', 'NaN', 'NaN'])
            else:
                est_beta, est_eta, est_gamma, r2 = result[0], result[1], result[2], result[3]
                bias_beta = est_beta - true_beta
                bias_eta = est_eta - true_eta
                bias_gamma = est_gamma - true_gamma
                row.extend([
                    f'{est_beta:.6f}',
                    f'{est_eta:.6f}',
                    f'{est_gamma:.6f}',
                    f'{bias_beta:.6f}',
                    f'{bias_eta:.6f}',
                    f'{bias_gamma:.6f}',
                    f'{r2:.6f}'
                ])

            writer.writerow(row)

    return {
        'failureCount': failure_count,
        'mcRuns': mc_runs
    }


def cmd_generate(args, config: dict, output_dir: Path, chunks_dir: Path):
    """生成命令：生成所有或指定的分片"""
    params = config.get('params', [])
    simulation = config.get('simulation', {})
    defaults = config.get('defaults', {})

    # 仿真设置
    mc_runs = simulation.get('mcRuns', 1000)

    # 生成单变量+双变量组合
    all_combinations = generate_partial_cross_combinations(params, defaults)

    if not all_combinations:
        print("错误: 没有变量参数")
        return

    # 获取固定的 CSV 列名
    variable_param_ids = [p['id'] for p in params if p.get('isVariable', False)]
    param_csv_columns = [PARAM_TO_CSV_COLUMN.get(pid, pid) for pid in variable_param_ids]

    total_combinations = len(all_combinations)

    # 加载索引
    chunks_dir.mkdir(exist_ok=True, parents=True)
    index = load_index(chunks_dir)
    existing = get_existing_chunks(index)

    # 更新索引配置信息
    index['config'] = {
        'mode': 'partial_cross',
        'variableParams': variable_param_ids,
        'expectedCombos': total_combinations,
        'mcRuns': mc_runs
    }

    # 确定要生成的组合
    if args.force:
        to_generate = all_combinations
        print(f"强制重新生成所有 {len(to_generate)} 个组合")
    else:
        # 增量模式：跳过已存在文件
        to_generate = []
        for param_names, combo in all_combinations:
            filename = generate_chunk_filename(param_names, combo)
            file_path = chunks_dir / filename
            if not file_path.exists():
                to_generate.append((param_names, combo))
        print(f"增量模式: 需要生成 {len(to_generate)}/{total_combinations} 个组合")

    if not to_generate:
        print("所有分片已存在，无需生成")
        return

    # 生成分片
    completed = 0
    total_failures = 0

    print("=" * 60)
    print(f"开始生成 {len(to_generate)} 个分片...")
    print("=" * 60)

    for param_names, combo in to_generate:
        filename = generate_chunk_filename(param_names, combo)
        output_path = chunks_dir / filename

        if args.verbose:
            combo_str = ', '.join(f'{n}={v}' for n, v in zip(param_names, combo))
            print(f"[{completed+1}/{len(to_generate)}] {combo_str}")

        result = run_single_chunk(
            combo, param_names, param_csv_columns, {}, defaults,
            mc_runs, output_path, args.verbose
        )

        total_failures += result['failureCount']

        # 更新索引
        chunk_info = {
            'file': filename,
            'params': {name: combo[i] for i, name in enumerate(param_names)},
            'mcRuns': mc_runs,
            'failureCount': result['failureCount'],
            'generated': datetime.now().isoformat(timespec='seconds')
        }

        if filename in existing:
            for i, c in enumerate(index['chunks']):
                if c['file'] == filename:
                    index['chunks'][i] = chunk_info
                    break
        else:
            index['chunks'].append(chunk_info)
            existing[filename] = chunk_info

        completed += 1

    # 更新统计
    index['stats']['generatedCombos'] = len(existing)
    index['stats']['totalRuns'] = len(existing) * mc_runs
    index['stats']['totalFailures'] = sum(c.get('failureCount', 0) for c in index['chunks'])

    save_index(chunks_dir, index)

    print("=" * 60)
    print(f"生成完成！")
    print(f"生成分片: {len(to_generate)}")
    print(f"总分片数: {len(existing)}")
    print(f"总模拟次数: {index['stats']['totalRuns']}")
    print(f"失败次数: {total_failures}")
    print(f"索引文件: {chunks_dir / 'index.json'}")
    print("=" * 60)


def cmd_merge(args, config: dict, output_dir: Path, chunks_dir: Path):
    """合并命令：将所有分片合并为 data.csv"""
    index = load_index(chunks_dir)

    if not index['chunks']:
        print("错误: 没有分片可合并")
        return

    # 获取 CSV 列名
    params = config.get('params', [])
    param_csv_columns = []
    for p in params:
        if p.get('isVariable', False):
            param_csv_columns.append(PARAM_TO_CSV_COLUMN.get(p['id'], p['id']))

    header = param_csv_columns + ['sim_id', 'est_beta', 'est_eta', 'est_gamma',
                                   'bias_beta', 'bias_eta', 'bias_gamma', 'r_squared']

    output_path = output_dir / 'data.csv'

    print(f"合并 {len(index['chunks'])} 个分片到 {output_path}...")

    with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(header)

        for chunk_info in sorted(index['chunks'], key=lambda x: x['file']):
            chunk_path = chunks_dir / chunk_info['file']
            if chunk_path.exists():
                with open(chunk_path, 'r', encoding='utf-8') as infile:
                    reader = csv.reader(infile)
                    next(reader)  # 跳过表头
                    for row in reader:
                        writer.writerow(row)

    # 更新索引
    index['mergedAt'] = datetime.now().isoformat(timespec='seconds')
    save_index(chunks_dir, index)

    # 更新 summary.json
    update_summary(config, output_dir, index)

    # 统计行数
    with open(output_path, 'r', encoding='utf-8') as f:
        line_count = sum(1 for _ in f) - 1

    print(f"合并完成！")
    print(f"总行数: {line_count}")
    print(f"输出文件: {output_path}")


def cmd_status(args, config: dict, output_dir: Path, chunks_dir: Path):
    """状态命令：显示当前生成状态"""
    index = load_index(chunks_dir)

    print("=" * 60)
    print(f"示例: {config.get('name', args.study_id)}")
    print("=" * 60)

    # 配置信息
    print("\n配置信息:")
    print(f"  模式: {index.get('config', {}).get('mode', 'unknown')}")
    print(f"  变量参数: {index.get('config', {}).get('variableParams', [])}")
    print(f"  期望组合数: {index.get('config', {}).get('expectedCombos', '?')}")
    print(f"  每组模拟次数: {index.get('config', {}).get('mcRuns', '?')}")

    # 生成状态
    stats = index.get('stats', {})
    print(f"\n生成状态:")
    print(f"  已生成组合: {stats.get('generatedCombos', 0)}")
    print(f"  总模拟次数: {stats.get('totalRuns', 0)}")
    print(f"  失败次数: {stats.get('totalFailures', 0)}")

    # 合并状态
    print(f"\n合并状态:")
    if index.get('mergedAt'):
        print(f"  最后合并: {index['mergedAt']}")
        data_path = output_dir / 'data.csv'
        if data_path.exists():
            with open(data_path, 'r', encoding='utf-8') as f:
                lines = sum(1 for _ in f) - 1
            print(f"  data.csv 行数: {lines}")
    else:
        print(f"  未合并")

    print("=" * 60)


def cmd_clean(args, config: dict, output_dir: Path, chunks_dir: Path):
    """清理命令：删除所有分片和索引"""
    import shutil

    if chunks_dir.exists():
        print(f"删除分片目录: {chunks_dir}")
        shutil.rmtree(chunks_dir)

    # 删除 data.csv
    data_path = output_dir / 'data.csv'
    if data_path.exists():
        print(f"删除合并文件: {data_path}")
        data_path.unlink()

    print("清理完成")


def update_summary(config: dict, output_dir: Path, index: dict):
    """更新 summary.json"""
    stats = index.get('stats', {})

    summary = {
        'config': config.get('id', 'unknown'),
        'name': config.get('name', 'Unknown'),
        'description': config.get('description', ''),
        'method': config.get('method', 'mle'),

        # 仿真设置
        'simulation': {
            'mc_runs': config.get('simulation', {}).get('mcRuns', 1000),
            'mode': 'partial_cross',
            'seed_strategy': 'deterministic'
        },

        # 参数配置
        'params': {
            'variable': index.get('config', {}).get('variableParams', []),
            'fixed': {p['id']: p.get('fixedValue') for p in config.get('params', []) if not p.get('isVariable', False)},
            'defaults': config.get('defaults', {})
        },

        # 统计结果
        'statistics': {
            'total_combinations': index.get('config', {}).get('expectedCombos', 0),
            'total_runs': stats.get('totalRuns', 0),
            'failure_count': stats.get('totalFailures', 0),
            'failure_rate': f"{stats.get('totalFailures', 0) / max(stats.get('totalRuns', 1), 1) * 100:.2f}%"
        },

        # 元数据
        'meta': {
            'merged_at': index.get('mergedAt'),
            'chunks_count': len(index.get('chunks', []))
        }
    }

    summary_path = output_dir / 'summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description='MLE 方法通用仿真脚本 (单变量+双变量模式)')
    parser.add_argument('study_id', help='示例 ID，如 demo1')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--force', '-f', action='store_true', help='强制重新生成')
    parser.add_argument('--only', type=str, help='只生成指定组合，如 "beta=1.5"')
    parser.add_argument('--merge', '-m', action='store_true', help='合并所有分片为 data.csv')
    parser.add_argument('--status', '-s', action='store_true', help='显示生成状态')
    parser.add_argument('--clean', action='store_true', help='清理所有分片和索引')

    args = parser.parse_args()

    # 定位配置文件
    config_path = PROJECT_ROOT / 'public' / 'studies' / 'mle' / args.study_id / 'config.md'
    output_dir = config_path.parent
    chunks_dir = output_dir / 'chunks'

    if not config_path.exists():
        print(f"错误: 配置文件不存在 - {config_path}")
        sys.exit(1)

    # 解析配置
    config = parse_config(str(config_path))

    # 执行命令
    if args.clean:
        cmd_clean(args, config, output_dir, chunks_dir)
    elif args.status:
        cmd_status(args, config, output_dir, chunks_dir)
    elif args.merge:
        cmd_merge(args, config, output_dir, chunks_dir)
    else:
        cmd_generate(args, config, output_dir, chunks_dir)


if __name__ == '__main__':
    main()
