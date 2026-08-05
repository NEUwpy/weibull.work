# Study/02 P–Q r4 primary 专用实现（窄而清晰，不接入旧 formal 控制面）

协议：`../../01-PQ-冻结协议.md`（v3/r4）；配置：`../../configs/pq-protocol-v3.json`；
环境锁：`../../configs/pq-environment-v2.json`。

## 模块

| 模块 | 职责 |
|---|---|
| `config.py` | r4 配置加载、路径（`artifacts/pq_v3/`）、Study01 权威输入 |
| `data.py` | 确定性样本重建、五折留出、validation 切分、逐位置 scaler、sample_min、SHA |
| `losses.py` | **domain-explicit 解码器**（γ̂=min(X)(δ+(1-2δ)sigmoid(o₃))，结构性 0<γ̂<min(X)）；P 损失 = approved direct 形式；Q 损失（x0.95 相对平方误差，梯度经 Weibull 公式） |
| `model.py` | 三输出 MLP，float64，确定性构建 |
| `training.py` | 单 fit 训练 + 支撑合法性 production test + 配对 SHA |
| `evaluate.py` | 主推断（fold×seed 交叉多路配对重采样）+ 次要固定模型 MC |
| `run.py` | 正式运行器（evidence npz tracked、fit_metadata、manifest、SHA256SUMS 只列 tracked、键精确 dtype） |
| `analyze.py` | r4 分析（主推断、分层、seed 变异、失败计数） |
| `repair_evidence.py` | 从完整精度预测 CSV 修复证据键 schema（无重训） |
| `smoke.py` | production-path smoke |
| `test_pq.py` | 单元 + 配对 + 支撑合法性 + frozen-grid representability + exact direct-P formula + 主推断测试（22 passed） |

## 用法

```bash
cd "Study/02-study-NN参数估计与分位点目标研究/code"
python -m pytest study02pq/test_pq.py -q
python -m study02pq.smoke
python -m study02pq.run --seed 42 --seed 2026 --seed 3407   # r4 primary 120 fits
python -m study02pq.analyze                                 # 三 seed 分析
python -m study02pq.run --aggregate                          # 重建汇总/manifest
```

## 证据位置（r4 primary，`artifacts/pq_v3/`）

- 压缩逐样本证据（tracked，精确键 dtype）：`evidence/<fit_id>.npz`
- fit metadata（tracked，无模型 state）：`fit_metadata/<fit_id>.json`
- 完整精度预测（gitignore）：`predictions/<fit_id>.csv`
- 汇总：`per_fit_metrics.csv`、`pairing_report.csv`、`splits_manifest.json`、`manifest.json`、`SHA256SUMS`
- 分析：`analysis/summary_v3.json`、`by_n_seed_descriptive.csv`、`failure_counts.json`

v1（preliminary）保留于 `artifacts/pq/`；v2/P_loggap（sensitivity，键 schema 已修复）
保留于 `artifacts/pq_v2/`；均未删除、未覆盖。
