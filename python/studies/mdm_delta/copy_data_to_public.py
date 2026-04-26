"""
将训练数据和模型指标复制到 public/ai/data/ 目录，供前端访问。

使用方法：
    cd python/studies/mdm_delta
    python copy_data_to_public.py
"""

import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = Path(__file__).parent / 'data'
MODELS_DIR = PROJECT_ROOT / 'python' / 'models' / 'mdm_delta'
PUBLIC_DIR = PROJECT_ROOT / 'public' / 'ai' / 'data'

def main():
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    # 复制训练数据 CSV
    for f in DATA_DIR.glob('training_data_*.csv'):
        shutil.copy2(f, PUBLIC_DIR / f.name)
        print(f"  {f.name}")

    # 复制验证预测 CSV
    for f in DATA_DIR.glob('validation_predictions_*.csv'):
        shutil.copy2(f, PUBLIC_DIR / f.name)
        print(f"  {f.name}")

    # 复制对比/验证 CSV
    for f in DATA_DIR.glob('comparison_*.csv'):
        shutil.copy2(f, PUBLIC_DIR / f.name)
        print(f"  {f.name}")

    for f in DATA_DIR.glob('iteration_stats.csv'):
        shutil.copy2(f, PUBLIC_DIR / f.name)
        print(f"  {f.name}")

    for f in DATA_DIR.glob('verification_cases.csv'):
        shutil.copy2(f, PUBLIC_DIR / f.name)
        print(f"  {f.name}")

    for f in DATA_DIR.glob('boundary_tests.csv'):
        shutil.copy2(f, PUBLIC_DIR / f.name)
        print(f"  {f.name}")

    # 复制模型指标 JSON
    for f in MODELS_DIR.glob('*_metrics.json'):
        shutil.copy2(f, PUBLIC_DIR / f.name)
        print(f"  {f.name}")

    # 复制 summary.json
    if (DATA_DIR / 'summary.json').exists():
        shutil.copy2(DATA_DIR / 'summary.json', PUBLIC_DIR / 'summary.json')
        print(f"  summary.json")

    # 复制 config.json
    if (DATA_DIR / 'config.json').exists():
        shutil.copy2(DATA_DIR / 'config.json', PUBLIC_DIR / 'config.json')
        print(f"  config.json")

    print(f"\n复制完成！目标目录: {PUBLIC_DIR}")

if __name__ == '__main__':
    main()
