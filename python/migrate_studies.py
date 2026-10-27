"""
迁移旧格式的研究数据到新格式

旧格式: public/studies/{method}/demo1/chunks/b{beta}_e{eta}_n{n}.csv
新格式: public/studies/{method}/chunks/b{beta}_e{eta}_g{gamma}_n{n}_rep{rep}_seed{seed}_step{step}.csv

同时添加缺失的 gamma_true 列
"""

import os
import shutil
import pandas as pd
from pathlib import Path

# 配置
MIGRATIONS = [
    {
        'method': 'mle',
        'source_dir': '../public/studies/mle/demo1/chunks',
        'target_dir': '../public/studies/mle/chunks',
        'gamma': 1000,
        'rep': 1000,
        'seed': 42,
        'step': 60
    },
    {
        'method': 'wmle',
        'source_dir': '../public/studies/wmle/demo1/chunks',
        'target_dir': '../public/studies/wmle/chunks',
        'gamma': 1000,
        'rep': 1000,
        'seed': 42,
        'step': 60
    }
]

def parse_old_filename(filename: str) -> dict:
    """解析旧格式文件名"""
    name = filename.replace('.csv', '')
    parts = name.split('_')
    params = {}

    for part in parts:
        if part.startswith('b'):
            params['beta'] = float(part[1:])
        elif part.startswith('e'):
            params['eta'] = float(part[1:])
        elif part.startswith('n'):
            params['n'] = int(part[1:])

    return params

def generate_new_filename(params: dict, config: dict) -> str:
    """生成新格式文件名"""
    # 格式化数值（整数不带小数点）
    def fmt(v, is_int=False):
        if is_int or v == int(v):
            return str(int(v))
        return str(v)

    return f"b{fmt(params['beta'])}_e{fmt(params['eta'])}_g{fmt(config['gamma'], True)}_n{params['n']}_rep{config['rep']}_seed{config['seed']}_step{config['step']}.csv"

def migrate_data():
    for config in MIGRATIONS:
        source_dir = Path(config['source_dir'])
        target_dir = Path(config['target_dir'])

        if not source_dir.exists():
            print(f"跳过 {config['method']}: 源目录不存在")
            continue

        target_dir.mkdir(parents=True, exist_ok=True)

        csv_files = list(source_dir.glob('*.csv'))
        print(f"\n迁移 {config['method']}: {len(csv_files)} 个文件")

        for csv_file in csv_files:
            old_params = parse_old_filename(csv_file.name)
            if not old_params:
                print(f"  跳过 {csv_file.name}: 无法解析文件名")
                continue

            # 读取数据
            df = pd.read_csv(csv_file)

            # 添加 gamma_true 列（如果不存在）
            if 'gamma_true' not in df.columns:
                df.insert(2, 'gamma_true', config['gamma'])

            # 生成新文件名
            new_filename = generate_new_filename(old_params, config)
            new_path = target_dir / new_filename

            # 保存到新位置
            df.to_csv(new_path, index=False)
            print(f"  {csv_file.name} -> {new_filename}")

if __name__ == '__main__':
    migrate_data()
    print("\n迁移完成！")
