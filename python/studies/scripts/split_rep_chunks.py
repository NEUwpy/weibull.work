"""
从 rep5000 的 chunk 文件截取生成 rep2000/3000/4000 文件

用法：
    cd python/studies/scripts
    python split_rep_chunks.py              # 生成 rep2000/3000/4000
    python split_rep_chunks.py --dry-run    # 只预览，不实际生成
"""

import os
import csv
from pathlib import Path
from typing import List

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# 源目录和目标目录
# MDM 方法级别的 chunks 目录
CHUNKS_DIR = PROJECT_ROOT / 'public' / 'studies' / 'mdm' / 'chunks'

# 如果数据在 demo1 目录，使用这个：
# CHUNKS_DIR = PROJECT_ROOT / 'public' / 'studies' / 'mdm' / 'demo1' / 'chunks'

# 要生成的 rep 值（从 rep5000 截取）
TARGET_REPS = [2000, 3000, 4000]
SOURCE_REP = 5000


def find_source_files() -> List[Path]:
    """找到所有 rep5000 的 chunk 文件"""
    files = list(CHUNKS_DIR.glob(f'*_rep{SOURCE_REP}_*.csv'))
    return sorted(files)


def split_file(source_path: Path, target_rep: int, dry_run: bool = False) -> Path:
    """从源文件截取前 target_rep 行数据，生成新文件"""

    # 构建目标文件名
    filename = source_path.name
    target_filename = filename.replace(f'_rep{SOURCE_REP}_', f'_rep{target_rep}_')
    target_path = CHUNKS_DIR / target_filename

    if dry_run:
        return target_path

    # 读取源文件
    with open(source_path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        header = next(reader)  # 标题行
        rows = list(reader)    # 数据行

    # 截取前 target_rep 行（+1 是因为 sim_id 从 1 开始）
    # 保留标题 + 前 target_rep 行数据
    truncated_rows = rows[:target_rep]

    # 写入目标文件
    with open(target_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(truncated_rows)

    return target_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description='从 rep5000 截取生成 rep2000/3000/4000')
    parser.add_argument('--dry-run', action='store_true', help='只预览，不实际生成文件')
    args = parser.parse_args()

    print("=" * 60)
    print("Rep Chunks 分割脚本")
    print(f"源目录: {CHUNKS_DIR}")
    print(f"源 rep: {SOURCE_REP}")
    print(f"目标 rep: {TARGET_REPS}")
    print("=" * 60)

    # 查找源文件
    source_files = find_source_files()

    if not source_files:
        print(f"\n错误: 未找到 rep{SOURCE_REP} 的文件")
        print("请先运行 generate_data.py --rep 5000 生成数据")
        return

    print(f"\n找到 {len(source_files)} 个源文件")

    if args.dry_run:
        print("\n[DRY RUN] 将生成以下文件：")

    # 统计
    total_generated = 0

    for source_path in source_files:
        print(f"\n处理: {source_path.name}")

        for target_rep in TARGET_REPS:
            target_path = split_file(source_path, target_rep, dry_run=args.dry_run)

            if args.dry_run:
                print(f"  → {target_path.name}")
            else:
                print(f"  ✓ {target_path.name}")
                total_generated += 1

    # 总结
    print("\n" + "=" * 60)
    if args.dry_run:
        print(f"[DRY RUN] 将生成 {len(source_files) * len(TARGET_REPS)} 个文件")
        print("移除 --dry-run 参数以实际生成文件")
    else:
        print(f"完成！共生成 {total_generated} 个文件")
    print("=" * 60)


if __name__ == '__main__':
    main()
