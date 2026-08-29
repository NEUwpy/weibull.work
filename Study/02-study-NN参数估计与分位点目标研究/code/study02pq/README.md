# Study/02 P–Q r4 primary 专用实现（窄而清晰，不接入旧 formal 控制面）

协议：`../../protocols/01-PQ-冻结协议.md`（v3/r4）；配置：`../../configs/pq-protocol-v3.json`；
环境锁：`../../configs/pq-environment-v2.json`。

## 模块

| 模块 | 职责 |
|---|---|
| `config.py` | r4 配置加载、路径（`artifacts/pq_v3/`）、Study01 权威输入 |
| `data.py` | 确定性样本重建、五折留出、validation 切分、逐位置 scaler、sample_min、SHA |
| `losses.py` | **domain-explicit 解码器**（γ̂=min(X)(δ+(1-2δ)sigmoid(o₃))，结构性 0<γ̂<min(X)）；P 损失 = approved direct 形式；Q 损失（x0.95 相对平方误差，梯度经 Weibull 公式） |
| `model.py` | 三输出 MLP，float64，确定性构建 |
| `training.py` | 单 fit 训练 + 支撑合法性 production test + 配对 SHA |
| `constrained_pilot.py` | Q主任务、P不等式约束的增广拉格朗日验证筛选 |
| `constrained_resource.py` | 约束路线300/20与600/60资源边界 |
| `constrained_confirm.py` | 冻结 QCP 配置的10-seed正式确认 |
| `qcp_main_analysis.py` | 从冻结证据派生当前 P/Q/QCP 三路线同预算结果 |
| `qcp_main_figures.py` | 生成当前三路线精度、CI、参数补偿和 epoch 主图 |
| `sample_size_equivalence.py` | 从当前冻结单元结果拟合 P 样本量曲线，并计算 Q/QCP 的 P 等效样本量与配对 bootstrap CI |
| `sample_size_figures.py` | 生成随 n 的 rRMSE 与 P 等效新增观测数论文图 |
| `bias_variance_decomposition.py` | 在固定真值单元内分解寿命点相对误差的偏差分量、标准差分量与 RMSRE |
| `qcp_resolution_distribution.py` | 量化 QCP 对 Q 的目标误差与参数补偿解决程度，生成 160 真值单元异质性和代表性估计分布图 |
| `qcp_cross_quantile_recovery.py` | 用冻结参数预测检验 QCP 是否修复 Q 在 $x_{0.90}$、$x_{0.99}$ 的跨寿命点误差 |
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
python -m study02pq.constrained_pilot                        # QCP验证筛选，测试封存
python -m study02pq.constrained_resource                     # QCP扩展资源门，测试封存
python -m study02pq.constrained_confirm                      # QCP 10-seed正式确认，首次打开测试
python -m study02pq.qcp_main_analysis                        # 生成当前 P/Q/QCP 汇总
python -m study02pq.qcp_main_figures                         # 生成当前论文主图
python -m study02pq.sample_size_equivalence                  # 事后样本量与等效观测分析
python -m study02pq.sample_size_figures                      # 生成样本量解释图
python -m study02pq.bias_variance_decomposition              # 生成偏差—方差分解
python -m study02pq.qcp_resolution_distribution              # 生成 QCP 解决程度、代表性分布和论文图
python -m study02pq.qcp_cross_quantile_recovery              # 生成跨寿命点恢复统计与图
```

## 证据位置（r4 primary，`artifacts/pq_v3/`）

- 压缩逐样本证据（tracked，精确键 dtype）：`evidence/<fit_id>.npz`
- fit metadata（tracked，无模型 state）：`fit_metadata/<fit_id>.json`
- 完整精度预测（gitignore）：`predictions/<fit_id>.csv`
- 汇总：`per_fit_metrics.csv`、`pairing_report.csv`、`splits_manifest.json`、`manifest.json`、`SHA256SUMS`
- 分析：`analysis/summary_v3.json`、`by_n_seed_descriptive.csv`、`failure_counts.json`

v1（preliminary）保留于 `artifacts/pq/`；v2/P_loggap（sensitivity，键 schema 已修复）
保留于 `artifacts/pq_v2/`；均未删除、未覆盖。
