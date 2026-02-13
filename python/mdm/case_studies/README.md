# MDM 案例生成脚本

本目录包含生成 MDM 案例数据的 Python 脚本。

## 目录结构

```
python/mdm/case_studies/
├── README.md                  # 本文件
├── case1/
│   └── generate_data.py      # 生成案例1数据
├── case2/
│   └── generate_data.py      # 生成案例2数据
├── case3/
│   ├── generate_data.py      # 生成案例3数据
│   └── generate_limit_analysis.py  # 生成极限分析数据
├── case4/
│   └── generate_data.py      # 生成案例4数据
└── case5/
    ├── generate_data.py      # 生成案例5数据
    └── generate_curves.py    # 生成梯度曲线数据
```

## 使用方法

### 运行单个案例脚本

```bash
# 从项目根目录运行
python python/mdm/case_studies/case1/generate_data.py
```

### 输出位置

脚本生成的数据文件输出到 `public/case-studies/mdm/caseX/` 目录。

## 脚本说明

### case1 - 多维度参数影响研究
生成 β × n × δ 的组合数据，用于研究各参数对估计结果的影响。

### case2 - 样本量与偏移量影响
深入分析 n 和 δ 的交互影响。

### case3 - 无交点梯度曲线研究
生成用于研究 MDM 无交点现象的数据：
- `generate_data.py`: 基础模拟数据
- `generate_limit_analysis.py`: 极限边界分析数据

### case4 - 大样本性能验证
验证大样本条件下的估计性能。

### case5 - 30组实际样本分析
- `generate_data.py`: 30组样本的估计结果
- `generate_curves.py`: 梯度曲线数据

## 与旧系统的区别

旧脚本位于 `python/generate_caseX_data.py`，新脚本位于本目录。

主要改动：
1. 输出路径改为 `public/case-studies/mdm/caseX/`
2. 文件名统一为 `data.csv`（而非 `mdm_caseX_full.csv`）

## 维护说明

1. **不要删除旧脚本**：在新系统验证完成前保持旧脚本不变
2. **修改时同步**：修改脚本逻辑时，同时更新新旧位置的脚本
3. **输出验证**：运行脚本后，检查输出文件是否正确
