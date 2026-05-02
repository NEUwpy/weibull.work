#!/bin/bash
# 批量训练所有方案的模型
set -e

cd "$(dirname "$0")"

echo "=========================================="
echo "批量训练所有方案模型"
echo "=========================================="

# 独立模型方案（按 n 分别训练）
for scheme in a1 a2 a3 c1 c2 c3; do
    echo ""
    echo "--- 方案: $scheme ---"
    python train_model.py --preprocessing $scheme --epochs 300
done

# 统一模型方案
for scheme in b1 b2; do
    echo ""
    echo "--- 方案: $scheme (统一模型) ---"
    python train_model.py --preprocessing $scheme --epochs 300
done

echo ""
echo "=========================================="
echo "所有模型训练完成！"
echo "=========================================="
