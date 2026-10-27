# 方法示例数据 (Method Studies)

本目录存放各参数估计方法的蒙特卡洛仿真数据。

## 目录结构

```
studies/
├── mdm/                    # MDM 方法
│   ├── demo1/              # 示例1
│   │   ├── config.md       # 配置文件
│   │   ├── chunks/         # 分片数据
│   │   │   ├── index.json
│   │   │   └── *.csv
│   │   └── summary.json    # 汇总统计
│   └── demo2/              # 示例2（如有）
└── wmle/                   # WMLE 方法
    └── ...
```

## 数据格式

### 分片文件命名

```
{b}{beta}_{e}{eta}_{n}{sampleSize}_{d}{offset}.csv
```

示例：`b1.5_e200_n3_d0.1.csv`

### CSV 列

| 列名 | 说明 |
|------|------|
| `beta_true` | 真实 β |
| `eta_true` | 真实 η |
| `sample_size` | 样本量 |
| `offset_value` | 偏移量 δ |
| `sim_id` | 模拟编号 |
| `est_beta` | β 估计值 |
| `est_eta` | η 估计值 |
| `est_gamma` | γ 估计值 |
| `bias_beta` | β 偏差 |
| `bias_eta` | η 偏差 |
| `bias_gamma` | γ 偏差 |
| `r_squared` | R² |

## 生成数据

```bash
cd python/studies/mdm

# 生成示例数据
python simulate.py demo1

# 查看状态
python simulate.py demo1 --status

# 强制重新生成
python simulate.py demo1 --force
```

## 添加新示例

1. 创建 `studies/{method}/{study_id}/config.md`
2. 运行 `python simulate.py {study_id}`
3. 前端自动发现新示例

## 相关文档

- [方法示例系统规范](../../docs/方法示例系统规范.md)
- [架构文档](../../ARCHITECTURE.md)
