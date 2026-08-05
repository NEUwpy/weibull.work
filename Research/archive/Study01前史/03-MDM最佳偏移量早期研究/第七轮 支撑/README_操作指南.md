# MDM 偏移量研究 —— 运行指南

配套脚本：`mdm_offset_study.py`
作用：按《第六轮结果》附录的闭式实现，重新生成全部逐样本数据与汇总统计（数据留在你本机），
并运行"可预测性试点"（线性/树探针），产出修订报告所需的全部数字与决策量 ρ̂。

---

## 1. 环境

- Python 3.9+
- 必装：`numpy`、`pandas`
- 强烈建议：`scikit-learn`（树探针需要；缺失时自动退化为仅 ridge，加 `--no-tree` 可显式关闭）

```bash
pip install numpy pandas scikit-learn
```

## 2. 三步运行

```bash
# 第1步：实现对齐硬门槛（秒级）。五行 s_v 必须全部 ✓（与报告表2完全一致）
python mdm_offset_study.py verify

# 第2步：冒烟测试（每格80次，约1~3分钟），确认端到端能跑通
python mdm_offset_study.py all --quick --outdir mdm_quick

# 第3步：正式运行（每格800次，约5~15分钟视机器而定）
python mdm_offset_study.py all --reps 800 --outdir mdm_out
```

运行中会逐格打印进度；结束时在终端打印方案比值表和两个 ρ̂。

## 3. 产物与回传

`mdm_out/` 下：

| 文件 | 大小 | 处置 |
| --- | --- | --- |
| `summary_report.json` | ~10 KB | **回传给我**（修订报告的核心数字都在这里） |
| `tables/*.csv`（8个） | 共 <1 MB | **回传给我**（误差–c曲线、c*表、δ*表、一致性、不变性、s_v、β̂偏差列） |
| `per_sample.npz` | ~35 MB | **自留并备份**。这是逐样本原始数据，也是后续 NN 训练的底座，这次别再丢了 |
| `config.json`、`cells.csv` | 小 | 自留（复现凭据） |

## 4. 与第六轮报告的口径核对（重要）

1. `verify` 必须全 ✓ —— 秩公式（Bernard）与归一化标尺 s_v 对齐。
2. 三个可比数字的预期落点（`summary_report.json → scheme_ratio_vs_fixed0.1_gridmedian`）：
   - `global_c_truebeta` ↔ 报告的 0.738
   - `table_true_cv` ↔ 报告的 0.705（本脚本做了 5 折交叉验证，略保守是正常的）
   - `oracle` ↔ 报告的 0.276
   偏差在 ±0.03 量级属 MC 噪声 + 实现细节差异，可直接采用本次运行作为修订版唯一数据源
   （顺带获得报告此前缺失的 bootstrap 置信区间）；若显著偏离，先核对下面两个报告未写明的细节。
3. 报告未写明、本脚本作显式配置的两处（如与第六轮不同请告诉我或自行改参重跑）：
   - β 搜索网格：默认 log 均匀 [0.1, 20]、261 点（原文为 0.1 步进 0.01 至约 20）
     → `--beta-min 0.1 --beta-max 20 --nbeta 261`
   - η̂ 取法：默认 n 个伪估计量的均值（与原文式(6)一致）→ `--eta-hat mean|median`
4. 若你手头还有生成第六轮结果的原脚本，发我，我来逐项对齐。

## 5. 结果怎么读（summary_report.json 关键字段）

`scheme_ratio_vs_fixed0.1_gridmedian` —— 各方案的复合误差比（相对固定 δ=0.1，全网格中位，越小越好）：

| 键 | 含义 | 性质 |
| --- | --- | --- |
| `fixed_0.1` | 文献基线 | 可部署 |
| `best_fixed_delta` / `fixed_delta_per_n` | 调优的单一/按n固定 δ（5折CV） | 可部署（零信息/仅用n） |
| `global_c_deploy_naive` | δ=0.21·s_v(β̂₀,n) 朴素配方 | 可部署但**失效**（量化纠缠代价用） |
| `global_c_truebeta` | c=0.21（真β协议） | **不可部署**，对照报告 0.738 |
| `table_true_cv` | 按真(β,n)查表（CV） | **不可部署**，对照报告 0.705 |
| `probe_ridge_A/B/C/D…` | 单遍特征探针消融阶梯 | 可部署 |
| `probe_*_E_multidelta*` | **多偏移读出**特征探针 | 可部署（学习化路线的下界） |
| `probe_DIAG_tree_truebeta` | 喂真β的作弊诊断 | 非方案，仅定位瓶颈 |
| `oracle` | 逐样本事后最优 | 含运气成分的上界 |

`rho_hat` —— 试点回收份额，两个参照系：
- `vs_table_true`：相对"按(β,n)查表"参照（与报告叙事衔接）
- `vs_deployable_simple`：相对最优可部署简单基线（**做 go/no-go 判据用这个**）
  - 判读（默认建议）：ρ̂ ≥ 0.20 → NN 立项；ρ̂ < 0.10 → 封顶于查表方案；0.10~0.20 → 加强特征再探一轮

其余：`entanglement_…` 为 β̂/β 在 c=0.21 处的中位（按β分组，量化纠缠）；
`cstar_summary.scaling_law` 为标度律系数；`safety` 为 γ̂ 与 x_R(0.999) 的带符号偏差；
`flags.interp_fidelity_fixed01_max_cell_relgap` 应 < 0.05（插值算子保真度自检）。

## 6. 可调旋钮

```
--reps 800        每格重复次数（--quick 等价于 reps=80, nboot=100）
--seed 20260610   主随机种子
--nbeta 261 --beta-min 0.1 --beta-max 20   β 搜索网格
--ngamma 700      γ 网格密度（左端自动扩展）
--eta-hat mean    η̂ 取法（mean=原文式6 / median）
--nboot 300       bootstrap 次数（CI 用）
--no-tree         禁用 sklearn 树探针
```

## 7. 已知注意事项

- c=0 列（δ=0）是"无偏移灾难"文档基线；所有策略评估自动避开该列的插值污染。
- β=1 行的 c* 谷底很平（`cstar_table.csv` 给了平坦带与 bootstrap CI），单点 c* 解读需谨慎。
- 报告若需重算图：`tables/error_vs_c.csv`（图3/8 数据，含新增 β̂/β 偏差列）、
  `invariance_goe.csv`（γ/η∈{0,0.1,0.5,1.0}，其中 1.0 对接谢里阳等2025原文设定）。
