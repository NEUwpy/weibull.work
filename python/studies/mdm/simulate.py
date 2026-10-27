"""
MDM 方法通用仿真脚本 (分片+索引模式)

⚠️ DEPRECATED: 本脚本已被 python/studies/common/experiment.py 取代。
新实验请使用 run_experiment()。本脚本仅用于复现旧数据或兼容旧流程。

状态说明（2026-06）：本脚本是历史的方法专属分片生成入口，暂时保留以
兼容旧数据生成流程。新的统一方法调用与蒙特卡洛核心在
python/studies/common/{sample.py, runner.py, simulation.py, experiment.py}，
并由 python/main.py 的 API 端点调用。新增方法应优先实现
python/methods/{method}.py 并注册到 methods.registry，而不是复制本脚本。

用途：
    从 config.md 读取参数配置，生成蒙特卡洛仿真数据
    支持分片生成、增量更新、合并导出

使用方法：
    cd python/studies/mdm

    # 生成所有分片（增量模式，跳过已存在的）
    python simulate.py demo1

    # 强制重新生成所有分片
    python simulate.py demo1 --force

    # 只生成指定参数组合
    python simulate.py demo1 --only beta=1.7

    # 新增参数值并生成（更新 config.md 并生成）
    python simulate.py demo1 --add beta=1.7

    # 合并所有分片为 data.csv
    python simulate.py demo1 --merge

    # 查看状态
    python simulate.py demo1 --status

    # 清理所有分片和索引
    python simulate.py demo1 --clean

配置文件格式 (config.md)：
    配置文件位于 public/studies/mdm/<study_id>/config.md
    必须包含 params 和 simulation 配置

输出文件：
    chunks/
    ├── index.json           # 分片索引
    ├── b1.5_e200_n5_d0.csv  # 分片数据
    └── ...
    data.csv                 # 合并后的完整数据（前端加载）
    summary.json             # 汇总统计

作者：Claude Code
日期：2026-03-03
"""

import sys
import os
import json
import csv
import argparse
import numpy as np
from pathlib import Path
from itertools import product
from datetime import datetime
from typing import Optional, List, Dict, Any

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

import yaml
from methods.mdm import MDM


# 参数 ID 到分片文件名简写的映射
PARAM_TO_SHORT = {
    'beta': 'b',
    'eta': 'e',
    'sampleSize': 'n',
    'process': 'd',
    'gamma': 'g',
}

# 参数 ID 到 CSV 列名的映射
PARAM_TO_CSV_COLUMN = {
    'beta': 'beta_true',
    'eta': 'eta_true',
    'gamma': 'gamma_true',
    'sampleSize': 'sample_size',
    'process': 'offset_value',
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
    """生成分片文件名（统一使用浮点格式）"""
    parts = []
    for i, param_id in enumerate(variable_params):
        short = PARAM_TO_SHORT.get(param_id, param_id[0])
        val = combo[i]
        # 按参数类型格式化
        if param_id == 'beta':
            # beta 保留 1 位小数
            parts.append(f"{short}{val:.1f}")
        elif param_id == 'process':
            # process 保留 2 位小数，但去掉末尾的 0
            formatted = f"{val:.2f}".rstrip('0').rstrip('.')
            parts.append(f"{short}{formatted}")
        elif param_id == 'sampleSize':
            # sampleSize 整数
            parts.append(f"{short}{int(val)}")
        else:
            # 其他参数：整数显示整数，浮点数保留原样
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


def run_mdm_estimation(sample: np.ndarray, offset: float, gamma_steps: int, rank_method: str):
    """
    运行 MDM 估计
    返回: (est_beta, est_eta, est_gamma, r2, status) 或 None (无解时)
    """
    try:
        algo = MDM(sample.tolist(), rank_method=rank_method)
        result = algo.run(trace=False, offset=offset, gamma_steps=gamma_steps, rank_method=rank_method)

        if result[4] == "no_intersection":
            return None

        return result
    except Exception as e:
        print(f"MDM 估计失败: {e}")
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
            "totalNoSolution": 0
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


def run_single_chunk(
    combo: tuple,
    param_names: List[str],
    param_csv_columns: List[str],
    fixed_params: dict,
    defaults: dict,
    mc_runs: int,
    gamma_steps: int,
    rank_method: str,
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
    sample_size = int(current_params.get('sampleSize', defaults.get('sampleSize', 7)))
    offset = current_params.get('process', defaults.get('process', 0.1))

    no_solution_count = 0

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

            # MDM 估计
            result = run_mdm_estimation(sample, offset, gamma_steps, rank_method)

            # 写入结果
            row = list(combo) + [sim_id]

            if result is None:
                no_solution_count += 1
                row.extend(['NaN', 'NaN', 'NaN', 'NaN', 'NaN', 'NaN', 'NaN'])
            else:
                est_beta, est_eta, est_gamma, r2, _ = result
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
        'noSolutionCount': no_solution_count,
        'mcRuns': mc_runs
    }


def cmd_generate(args, config: dict, output_dir: Path, chunks_dir: Path):
    """生成命令：生成所有或指定的分片"""
    params = config.get('params', [])
    simulation = config.get('simulation', {})
    calculation = config.get('calculation', {})
    defaults = config.get('defaults', {})

    # 仿真设置
    mc_runs = simulation.get('mcRuns', 1000)
    gamma_steps = calculation.get('gammaSteps', 60)
    rank_method = calculation.get('rankMethod', 'bernard')

    # 构建参数组合
    variable_params = []
    fixed_params = {}

    for p in params:
        pid = p['id']
        csv_col = PARAM_TO_CSV_COLUMN.get(pid, pid)

        if p.get('isVariable', False):
            values = get_param_values(p)
            if values:
                variable_params.append((pid, values, csv_col))
        else:
            if p.get('state') == 'fixed':
                fixed_params[pid] = p.get('fixedValue')
            else:
                fixed_params[pid] = defaults.get(pid)

    if not variable_params:
        print("错误: 没有变量参数")
        return

    param_names = [p[0] for p in variable_params]
    param_csv_columns = [p[2] for p in variable_params]
    param_values_lists = [p[1] for p in variable_params]
    combinations = list(product(*param_values_lists))

    total_combinations = len(combinations)

    # 加载索引
    chunks_dir.mkdir(exist_ok=True)
    index = load_index(chunks_dir)
    existing = get_existing_chunks(index)

    # 更新索引配置信息
    index['config'] = {
        'variableParams': param_names,
        'expectedCombos': total_combinations,
        'mcRuns': mc_runs,
        'paramValues': {p[0]: p[1] for p in variable_params}
    }

    # 确定要生成的组合
    if args.only:
        # 只生成指定组合
        filter_params = parse_only_arg(args.only)
        to_generate = [c for c in combinations if matches_filter(c, param_names, filter_params)]
        if not to_generate:
            print(f"没有匹配的组合: {args.only}")
            return
        print(f"指定生成 {len(to_generate)} 个组合")
    elif args.force:
        # 强制重新生成所有
        to_generate = combinations
        print(f"强制重新生成所有 {len(to_generate)} 个组合")
    else:
        # 增量模式：跳过已存在文件（检查文件是否存在，而不仅仅是索引）
        to_generate = []
        for combo in combinations:
            filename = generate_chunk_filename(param_names, combo)
            file_path = chunks_dir / filename
            # 检查文件是否存在，而不是只检查索引
            if not file_path.exists():
                to_generate.append(combo)
        print(f"增量模式: 需要生成 {len(to_generate)}/{total_combinations} 个组合")

    if not to_generate:
        print("所有分片已存在，无需生成")
        return

    # 生成分片
    completed = 0
    total_no_solution = 0

    print("=" * 60)
    print(f"开始生成 {len(to_generate)} 个分片...")
    print("=" * 60)

    for combo in to_generate:
        filename = generate_chunk_filename(param_names, combo)
        output_path = chunks_dir / filename

        if args.verbose:
            combo_str = ', '.join(f'{n}={v}' for n, v in zip(param_names, combo))
            print(f"[{completed+1}/{len(to_generate)}] {combo_str}")

        result = run_single_chunk(
            combo, param_names, param_csv_columns, fixed_params, defaults,
            mc_runs, gamma_steps, rank_method, output_path, args.verbose
        )

        total_no_solution += result['noSolutionCount']

        # 更新索引
        chunk_info = {
            'file': filename,
            'params': {name: combo[i] for i, name in enumerate(param_names)},
            'mcRuns': mc_runs,
            'noSolutionCount': result['noSolutionCount'],
            'generated': datetime.now().isoformat(timespec='seconds')
        }

        # 更新或添加
        if filename in existing:
            # 找到并更新
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
    index['stats']['totalNoSolution'] = sum(c.get('noSolutionCount', 0) for c in index['chunks'])

    save_index(chunks_dir, index)

    print("=" * 60)
    print(f"生成完成！")
    print(f"生成分片: {len(to_generate)}")
    print(f"总分片数: {len(existing)}")
    print(f"总模拟次数: {index['stats']['totalRuns']}")
    print(f"无解次数: {total_no_solution}")
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
        line_count = sum(1 for _ in f) - 1  # 减去表头

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
    print(f"  变量参数: {index.get('config', {}).get('variableParams', [])}")
    print(f"  期望组合数: {index.get('config', {}).get('expectedCombos', '?')}")
    print(f"  每组模拟次数: {index.get('config', {}).get('mcRuns', '?')}")

    # 生成状态
    stats = index.get('stats', {})
    print(f"\n生成状态:")
    print(f"  已生成组合: {stats.get('generatedCombos', 0)}")
    print(f"  总模拟次数: {stats.get('totalRuns', 0)}")
    print(f"  无解次数: {stats.get('totalNoSolution', 0)}")

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

    # 分片列表（如果详细模式）
    if args.verbose and index['chunks']:
        print(f"\n分片列表 (共 {len(index['chunks'])} 个):")
        for chunk in index['chunks'][:10]:  # 只显示前10个
            params_str = ', '.join(f"{k}={v}" for k, v in chunk['params'].items())
            print(f"  {chunk['file']}: {params_str} ({chunk['noSolutionCount']} 无解)")
        if len(index['chunks']) > 10:
            print(f"  ... 还有 {len(index['chunks']) - 10} 个分片")

    # 检查缺失
    expected = index.get('config', {}).get('expectedCombos', 0)
    generated = stats.get('generatedCombos', 0)
    if expected > generated:
        print(f"\n⚠️  缺失 {expected - generated} 个组合")

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


def cmd_add(args, config: dict, output_dir: Path, chunks_dir: Path):
    """添加命令：添加新参数值并生成"""
    # 解析 --add 参数
    add_params = parse_only_arg(args.add)

    if not add_params:
        print("错误: 请指定要添加的参数，如 --add beta=1.7")
        return

    # 更新 config.md
    config_path = output_dir / 'config.md'

    for param_id, value in add_params.items():
        # 找到对应参数
        param_found = False
        for p in config.get('params', []):
            if p['id'] == param_id:
                param_found = True
                if p.get('state') != 'discrete':
                    print(f"警告: 参数 {param_id} 不是离散参数，无法添加值")
                    continue

                current_values = p.get('discreteValues', [])
                if value in current_values:
                    print(f"参数 {param_id}={value} 已存在")
                    continue

                # 添加新值（保持排序）
                new_values = sorted(current_values + [value])
                p['discreteValues'] = new_values
                print(f"添加 {param_id}={value} 到配置")

        if not param_found:
            print(f"警告: 未找到参数 {param_id}")

    # 写回 config.md
    update_config_md(config_path, config)

    # 生成新增的组合
    cmd_generate(args, config, output_dir, chunks_dir)


def parse_only_arg(only_str: str) -> dict:
    """解析 --only 或 --add 参数，如 'beta=1.7,eta=1000'"""
    result = {}
    if not only_str:
        return result

    for part in only_str.split(','):
        if '=' in part:
            key, val = part.split('=', 1)
            key = key.strip()
            val = val.strip()
            # 尝试转换为数值
            try:
                if '.' in val:
                    result[key] = float(val)
                else:
                    result[key] = int(val)
            except ValueError:
                result[key] = val

    return result


def matches_filter(combo: tuple, param_names: List[str], filter_params: dict) -> bool:
    """检查组合是否匹配过滤条件"""
    for key, val in filter_params.items():
        if key in param_names:
            idx = param_names.index(key)
            if combo[idx] != val:
                return False
    return True


def update_config_md(config_path: Path, config: dict):
    """更新 config.md 文件（保留 Markdown 内容）"""
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 分离 YAML 和 Markdown
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            markdown_content = parts[2]

            # 重新生成 YAML
            new_yaml = yaml.dump(config, allow_unicode=True, sort_keys=False)

            # 重新组装
            new_content = f"---\n{new_yaml}---\n{markdown_content}"

            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(new_content)


def update_summary(config: dict, output_dir: Path, index: dict):
    """更新 summary.json"""
    stats = index.get('stats', {})
    calculation = config.get('calculation', {})

    summary = {
        'config': config.get('id', 'unknown'),
        'name': config.get('name', 'Unknown'),
        'description': config.get('description', ''),
        'method': config.get('method', 'mdm'),

        # 仿真设置
        'simulation': {
            'mc_runs': config.get('simulation', {}).get('mcRuns', 1000),
            'seed_strategy': 'deterministic'  # 种子 = sim_id + 参数值编码
        },

        # MDM 算法参数
        'calculation': {
            'gamma_steps': calculation.get('gammaSteps', 60),
            'rank_method': calculation.get('rankMethod', 'bernard'),
            'beta_bounds': calculation.get('betaBounds', [0.1, 15.0]),
            'gamma_range_round1': calculation.get('gammaRangeRound1', [0, 0.99]),
            'gamma_range_round2': calculation.get('gammaRangeRound2', [0.99, 0.999999])
        },

        # 参数配置
        'params': {
            'variable': index.get('config', {}).get('variableParams', []),
            'values': index.get('config', {}).get('paramValues', {}),
            'fixed': {p['id']: p.get('fixedValue') for p in config.get('params', []) if not p.get('isVariable', False)},
            'defaults': config.get('defaults', {})
        },

        # 统计结果
        'statistics': {
            'total_combinations': index.get('config', {}).get('expectedCombos', 0),
            'total_runs': stats.get('totalRuns', 0),
            'no_solution_count': stats.get('totalNoSolution', 0),
            'no_solution_rate': f"{stats.get('totalNoSolution', 0) / max(stats.get('totalRuns', 1), 1) * 100:.2f}%"
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
    parser = argparse.ArgumentParser(description='MDM 方法通用仿真脚本 (分片+索引模式)')
    parser.add_argument('study_id', help='示例 ID，如 demo1')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--force', '-f', action='store_true', help='强制重新生成')
    parser.add_argument('--only', type=str, help='只生成指定组合，如 "beta=1.7"')
    parser.add_argument('--add', type=str, help='添加新参数值并生成，如 "beta=1.7"')
    parser.add_argument('--merge', '-m', action='store_true', help='合并所有分片为 data.csv')
    parser.add_argument('--status', '-s', action='store_true', help='显示生成状态')
    parser.add_argument('--clean', action='store_true', help='清理所有分片和索引')

    args = parser.parse_args()

    # 定位配置文件
    config_path = PROJECT_ROOT / 'public' / 'studies' / 'mdm' / args.study_id / 'config.md'
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
    elif args.add:
        cmd_add(args, config, output_dir, chunks_dir)
    else:
        cmd_generate(args, config, output_dir, chunks_dir)


if __name__ == '__main__':
    main()
