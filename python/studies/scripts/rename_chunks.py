"""
Chunk 文件重命名脚本

将现有的 chunk 文件从旧命名格式重命名为新格式。

使用方法：
    cd python/studies/scripts
    python rename_chunks.py --dry-run   # 预览重命名结果
    python rename_chunks.py             # 执行重命名
    python rename_chunks.py --rollback  # 回滚到旧命名

命名规范：
    新格式: b{beta}_e{eta}_g{gamma}_n{n}_d{offset}_rep{rep}_seed{seed}_step{step}.csv
"""

import os
import re
import shutil
import argparse
from pathlib import Path
from typing import Dict, Optional, Tuple

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# 各 study 的默认参数
DEFAULTS = {
    'mdm': {
        'demo1': {
            'gamma': 1000,
            'rep': 1000,
            'seed': 42,
            'step': 60,
        },
        'demo2': {
            'beta': 2.0,
            'eta': 1000,
            'gamma': 1000,
            'offset': 0.1,
            'rep': 5000,
            'seed': 42,
            'step': 60,
        }
    },
    'mle': {
        'demo2': {
            'beta': 2.0,
            'eta': 1000,
            'gamma': 1000,
            'rep': 5000,
            'seed': 42,
        }
    },
    'wmle': {
        'demo1': {
            'beta': 2.0,
            'eta': 1000,
            'gamma': 100,
            'rep': 1000,
            'seed': 42,
        }
    }
}


def parse_mdm_demo1_old_format(filename: str) -> Optional[Dict]:
    """
    解析 MDM demo1 旧格式: b1.5_e200_n7_d0.1.csv
    """
    pattern = r'^b([\d.]+)_e(\d+)_n(\d+)_d([\d.]+)\.csv$'
    match = re.match(pattern, filename)
    if match:
        return {
            'beta': float(match.group(1)),
            'eta': int(match.group(2)),
            'n': int(match.group(3)),
            'offset': float(match.group(4)),
        }
    return None


def parse_n_only_format(filename: str) -> Optional[Dict]:
    """
    解析只有 n 的格式: n7.csv
    """
    pattern = r'^n(\d+)\.csv$'
    match = re.match(pattern, filename)
    if match:
        return {'n': int(match.group(1))}
    return None


def format_number(value):
    """格式化数值：整数显示为整数，小数保留原样"""
    if value == int(value):
        return str(int(value))
    return str(value)


def generate_new_name_mdm(params: Dict, defaults: Dict) -> str:
    """生成 MDM 的新文件名"""
    beta = params.get('beta', defaults.get('beta', 2.0))
    eta = params.get('eta', defaults.get('eta', 1000))
    gamma = params.get('gamma', defaults.get('gamma', 1000))
    n = params['n']
    offset = params.get('offset', defaults.get('offset', 0.1))
    rep = params.get('rep', defaults.get('rep', 1000))
    seed = params.get('seed', defaults.get('seed', 42))
    step = params.get('step', defaults.get('step', 60))

    return f'b{format_number(beta)}_e{eta}_g{gamma}_n{n}_d{format_number(offset)}_rep{rep}_seed{seed}_step{step}.csv'


def generate_new_name_mle(params: Dict, defaults: Dict) -> str:
    """生成 MLE 的新文件名（无 step 和 offset）"""
    beta = params.get('beta', defaults.get('beta', 2.0))
    eta = params.get('eta', defaults.get('eta', 1000))
    gamma = params.get('gamma', defaults.get('gamma', 1000))
    n = params['n']
    rep = params.get('rep', defaults.get('rep', 1000))
    seed = params.get('seed', defaults.get('seed', 42))

    beta_str = f'{beta}' if beta == int(beta) else f'{beta}'

    return f'b{beta_str}_e{eta}_g{gamma}_n{n}_rep{rep}_seed{seed}.csv'


def rename_study(method: str, study: str, dry_run: bool = True) -> Tuple[int, int]:
    """
    重命名单个 study 的 chunk 文件

    Returns: (success_count, error_count)
    """
    chunks_dir = PROJECT_ROOT / 'public' / 'studies' / method / study / 'chunks'

    if not chunks_dir.exists():
        print(f"  跳过: {chunks_dir} 不存在")
        return 0, 0

    defaults = DEFAULTS.get(method, {}).get(study, {})
    if not defaults:
        print(f"  跳过: 未定义 {method}/{study} 的默认参数")
        return 0, 0

    success = 0
    errors = 0

    for old_file in sorted(chunks_dir.glob('*.csv')):
        old_name = old_file.name

        # 尝试解析不同格式
        params = None
        new_name = None

        if method == 'mdm' and study == 'demo1':
            params = parse_mdm_demo1_old_format(old_name)
            if params:
                new_name = generate_new_name_mdm(params, defaults)
        else:
            # demo2 格式: n{n}.csv
            params = parse_n_only_format(old_name)
            if params:
                if method == 'mdm':
                    new_name = generate_new_name_mdm(params, defaults)
                elif method in ('mle', 'wmle'):
                    new_name = generate_new_name_mle(params, defaults)

        if not new_name:
            print(f"  跳过: 无法解析 {old_name}")
            continue

        if old_name == new_name:
            continue

        new_path = chunks_dir / new_name

        if dry_run:
            print(f"  {old_name} -> {new_name}")
            success += 1
        else:
            try:
                old_file.rename(new_path)
                print(f"  [OK] {old_name} -> {new_name}")
                success += 1
            except Exception as e:
                print(f"  [ERR] {old_name}: {e}")
                errors += 1

    return success, errors


def create_backup(dry_run: bool = True):
    """创建备份"""
    if dry_run:
        return

    backup_dir = PROJECT_ROOT / 'backups' / 'chunks_backup'

    studies = [
        ('mdm', 'demo1'),
        ('mdm', 'demo2'),
        ('mle', 'demo2'),
    ]

    for method, study in studies:
        src = PROJECT_ROOT / 'public' / 'studies' / method / study / 'chunks'
        if src.exists():
            dst = backup_dir / method / study / 'chunks'
            dst.mkdir(parents=True, exist_ok=True)
            for f in src.glob('*.csv'):
                shutil.copy2(f, dst / f.name)
            print(f"备份: {src} -> {dst}")


def main():
    parser = argparse.ArgumentParser(description='Chunk 文件重命名脚本')
    parser.add_argument('--dry-run', action='store_true', help='预览重命名结果，不实际执行')
    parser.add_argument('--rollback', action='store_true', help='从备份恢复')
    parser.add_argument('--method', type=str, help='只处理指定方法 (mdm/mle/wmle)')
    parser.add_argument('--study', type=str, help='只处理指定 study')

    args = parser.parse_args()

    if args.rollback:
        print("回滚功能需要手动从 backups/chunks_backup 恢复")
        return

    # 确定要处理的 studies
    all_studies = [
        ('mdm', 'demo1'),
        ('mdm', 'demo2'),
        ('mle', 'demo2'),
    ]

    if args.method:
        all_studies = [(m, s) for m, s in all_studies if m == args.method]
    if args.study:
        all_studies = [(m, s) for m, s in all_studies if s == args.study]

    print("=" * 60)
    print("Chunk 文件重命名")
    print(f"模式: {'预览' if args.dry_run else '执行'}")
    print("=" * 60)

    if not args.dry_run:
        create_backup(dry_run=False)

    total_success = 0
    total_errors = 0

    for method, study in all_studies:
        print(f"\n[{method}/{study}]")
        success, errors = rename_study(method, study, dry_run=args.dry_run)
        total_success += success
        total_errors += errors

    print("\n" + "=" * 60)
    print(f"完成: {total_success} 个文件" + (f", {total_errors} 个错误" if total_errors else ""))
    if args.dry_run:
        print("这是预览模式，使用不带 --dry-run 的命令执行实际重命名")
    print("=" * 60)


if __name__ == '__main__':
    main()
