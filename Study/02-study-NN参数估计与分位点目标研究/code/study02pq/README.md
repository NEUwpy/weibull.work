# Study/02 P–Q 专用实现（窄而清晰，不接入旧 formal 控制面）

协议：`../../01-PQ-冻结协议.md`；配置：`../../configs/pq-protocol-v1.json`。

## 模块

| 模块 | 职责 |
|---|---|
| `config.py` | 冻结配置加载、路径（__file__ 相对，不假设盘符）、Study01 权威输入 |
| `data.py` | 确定性样本重建（generate_sample，seed_namespace=study01_nrmc_v1）、五折留出、validation 切分、逐位置 scaler、SHA 助手 |
| `losses.py` | P 损失（参数精度相对平方误差）、Q 损失（x0.95 相对平方误差，梯度经 Weibull 公式）、softplus 合法化 |
| `model.py` | 三输出 MLP（256-128-64 ReLU），float64，确定性构建，结构/参数 SHA |
| `training.py` | 单 fit 训练（确定性种子、batch 顺序、early stopping、checkpoint 选择、配对 SHA） |
| `evaluate.py` | held-out rRMSE、配对 bootstrap CI、失败计数 |
| `run.py` | 正式运行器（可续接）、配对报告、汇总、manifest、SHA256SUMS |
| `smoke.py` | 生产路径 smoke（微型非证据数据） |
| `test_pq.py` | 单元 + 配对测试（含 Q 梯度经 Weibull 传播、与 Study01 sealed split 对照） |

## 用法

```bash
cd "Study/02-study-NN参数估计与分位点目标研究/code"
python -m pytest study02pq/test_pq.py -v        # 测试
python -m study02pq.smoke                        # smoke
python -m study02pq.run --seed 42                # 正式 seed 42（40 fits，幂等续接）
python -m study02pq.run --seed 2026 --seed 3407  # 其余 80 fits
python -m study02pq.run --aggregate              # 重建汇总/manifest
```

## 证据位置

- 逐 fit checkpoint（tracked）：`artifacts/pq/checkpoints/<fit_id>.json`
- 逐 fit 预测（gitignore，SHA 记入 SHA256SUMS）：`artifacts/pq/predictions/<fit_id>.csv`
- 汇总：`artifacts/pq/per_fit_metrics.csv`、`pairing_report.csv`、`paired_summary.csv`
- 划分 manifest：`artifacts/pq/splits_manifest.json`；总 manifest：`artifacts/pq/manifest.json`
- 哈希清单：`artifacts/pq/SHA256SUMS`
