# Vector-MLP 无量纲输入修正与验证 —— 候选路线报告

> 分支：`study01-dimensionless-candidate` ｜ 基线：`main` @ `c8645685` ｜ 状态：`READY_FOR_INDEPENDENT_REVIEW`
>
> 生成脚本：`code/run_dimensionless_candidate.py` ｜ 后分析：`code/analyze_dimensionless_candidate.py`
> 合同测试：`tests/test_dimensionless_candidate.py`
> 紧凑汇总：`summary.json`、`manifest.json`、`model_level_summary.csv`、`pooled_comparison.csv`、`p2_model_summary.csv`、`scale_invariance.csv`

## 1. 任务与结论（TL;DR）

现有 Vector-MLP（封存 E3b/E4d）以 13 个**有量纲**统计量作为输入，仅在 $\eta=1$ 上训练；其训练折 z-score 并不能保证更换计量单位后的尺度不变性。本候选路线把输入改为 11 个**仅依赖可观测无量纲样本特征**（以样本均值 $\bar x$ 归一化），在 26 点损失曲线目标、5 折组合留出、3 seed、训练折专属 z-score、失败惩罚、MLP 结构（256,128,64）与 J1 评价口径**完全不变**的前提下，检验新路线能否获得尺度不变性并基本保留样本自适应偏移量选择的精度收益。

**核心结论：**

1. **尺度不变性：完全获得。** 对同一样本乘以 $0.001/1/1000$：无量纲特征最大相对差 $3.2\times10^{-11}$；模型预测的 26 点损失曲线最大相对差 $0$；最终选择的 $\delta$ 在 1000 个探针样本上 **100% 一致**。
2. **精度收益：未基本保留。** 主网格组合留出 pooled J1：dimensionless $0.5762$ vs dimensional $0.5475$（J1 相对升高 $\sim 5.3\%$）。相对「Default $\to$ dimensional」的自适应收益，dimensionless 只保留约 **66%**（J1 绝对降幅 $0.0570/0.0858$）。最大的精度损失出现在样本量插值轴（P2-NI，$n=15$）：dimensionless $0.4954$ vs dimensional $0.4547$（$\sim 9\%$ 相对变差）。
3. **仍优于固定 Default（$0.6332$），但收益大幅收窄**；无量纲表示丢弃了绝对尺度信息，而该信息在训练数据中为损失曲线预测提供了有用协变量。

**判定**：新路线达成尺度不变性，但代价是明显的精度回落（约 5% J1，P2-NI 约 9%），**不符合「基本保留精度收益」的成立标准**。若要同时获得尺度不变性与精度，需要另行设计（例如：有量纲特征 + 显式尺度归一化预处理，或尺度不变特征工程之外的信息，见 §11.4 待 Codex 决定）。

## 2. 分支、基线、commit 链

- 基线（base）：`main` @ `c8645685`
- 分支：`study01-dimensionless-candidate`（已推送 `origin/study01-dimensionless-candidate`）
- 最终 tip：`b944d6c2`（实质产物与报告所在提交；其后为 tip 回填的 docs 提交）
- commit 链（自基线的全部提交）：
  - `840a8e5b` feat(candidate): 无量纲输入 Vector-MLP 候选脚本与合同测试
  - `dcfffe77` fix(candidate): 候选产物输出到 artifacts/candidate 而非只读 formal/ 树内
  - `e2020a4b` feat(candidate): 后分析脚本——从候选产物计算 seed 级汇总与对照表
  - `b944d6c2` feat(candidate): 无量纲候选正式产物与完整报告
- 工作区：`D:/weibull/.worktrees/dimensionless-candidate`（独立 worktree，与主工作区隔离；主工作区未提交的 `03-论文骨架.md` 未动）。

## 3. 修改与新增文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `code/run_dimensionless_candidate.py` | 新增 | 候选脚本：有量纲复现（对照）+ 无量纲候选 + P2 + 三尺度验证 + 产物 |
| `code/analyze_dimensionless_candidate.py` | 新增 | 后分析：seed 级 pooled J1、15 模型分布、保留比例、P2 对照 |
| `tests/test_dimensionless_candidate.py` | 新增 | 9 项合同测试 |
| `artifacts/candidate/dimensionless_vector_mlp/.gitignore` | 新增 | 大型本地产物不入库（`local_outputs/`） |
| `artifacts/candidate/dimensionless_vector_mlp/` 紧凑产物 | 新增 | summary/manifest/CSV/报告/SHA256SUMS/run_log |

未修改任何正式产物；封存 E3b/E4d/P2 数据只读复用。

## 4. 复用的既有数据与「未重跑 MDM」证明

| 复用输入 | 路径 | 用途 |
|---|---|---|
| E3b 逐样本特征缓存 | `artifacts/formal/E3b_vector_mlp/sample_features.csv`（45,000） | 主网格无量纲特征 + 有量纲复现 |
| E3b 26 点损失曲线 | `artifacts/formal/E3b_vector_mlp/risk_curves.csv`（45,000×26） | 训练目标 + 评价真值 |
| E3b 封存对照 | `artifacts/formal/E3b_vector_mlp/model_comparison.csv`、`seed_stability.csv` | 有量纲对照（外部参考） |
| E4a 封存消融 | `artifacts/formal/E4_robustness/E4a_feature_ablation.csv`（`full` 组 15 模型） | 有量纲 15 模型分布参考 |
| P2 数据 | `artifacts/formal/extended_validation/p2_generalization_v2/chunks/*.csv`（39 chunk） | 泛化评价（n=15 插值、参数中点插值） |
| P2 封存结果 | `.../p2_evaluation_summary.json` | 有量纲 P2 对照 |

**未重跑 MDM 证明：**
- 未调用 `python/methods/mdm.py`、`generate_mc_data.py`、`run_E3b*`、`run_E4*`；无任何估计器重跑，未扩展 $\eta$/$\gamma$ 网格。
- 主网格训练/评价完全复用 `sample_features.csv` + `risk_curves.csv`，并已用主网格 chunk 原始估计核验：risk_curves 与 `compute_loss` 原始损失最大绝对差 ~1e-16（主网格 NaN/失败率为 0）。
- P2 特征由 `generate_sample`（确定性抽样，**非估计器**）重建，并用 chunk 中记录的 `sample_sha256` 抽查 200 样本全部一致（fail-closed）。
- 尺度不变性验证只做特征/预测/选择的数学恒等检查，不产生新的 MDM 估计。

## 5. 特征公式与输入维数

候选 11 维无量纲输入（以样本均值 $\bar x$ 归一化）：

$$n,\quad x_{\min}/\bar x,\quad x_{\max}/\bar x,\quad R/\bar x,\quad Q_1/\bar x,\quad Q_2/\bar x,\quad Q_3/\bar x,\quad IQR/\bar x,\quad CV,\quad g_1,\quad g_2$$

- 不输入恒等于 1 的 $\bar x/\bar x$；
- $s/\bar x$ 与 $CV$ 重复，仅保留 $CV$；
- $Q_2$ 即中位数（Med）；$R=x_{\max}-x_{\min}$；
- 不使用任何真参数（$\beta,\eta,\gamma$）或其派生值；`BANNED_FIELDS` 检查通过（合同测试）。
- 全部 11 维做训练折专属 z-score（与有量纲路线「训练折专属处理」口径一致；z-score 对尺度不变的量仍是尺度不变的）。

有量纲对照（封存口径）：13 维，其中 9 维（x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s）训练折 z-score，4 维（n, CV, g1, g2）原样透传。两条路线 MLP 结构/目标/评价完全一致。

## 6. 1 折试跑与 15 模型结果

**1 折试跑**（fold 1 × seed 42，`--mode smoke`）：有量纲 J1=0.527740、无量纲 J1=0.541182，链路（输入→目标→训练→评价→产物）核对通过。

**15 模型分布**（5 折 × 3 seed，组合留出，每模型 9,000 个留出样本；`model_level_summary.csv`）：

| 路线 | 均值 | 中位数 | SD | min | max |
|---|---|---|---|---|---|
| dimensional（本 harness 复现） | 0.54736 | 0.54953 | 0.01102 | 0.52717 | 0.56164 |
| dimensionless（候选） | 0.57583 | 0.58088 | 0.02157 | 0.53851 | 0.60108 |
| 封存 E4a `full`（外部参考） | 0.54563 | 0.54845 | 0.01015 | 0.52610 | 0.55993 |

dimensionless 的 15 模型 SD 约为 dimensional 的两倍（0.0216 vs 0.0110），离散度更大；其最小值（0.5385）仍高于 dimensional 的均值（0.5474）附近，说明在**大多数** fold×seed 上无量纲路线都更差。

## 7. 新旧路线 / Default / P2 对比

**主网格组合留出 pooled J1（越低越好；lower is better）：**

| 方法 | pooled J1 | J1(n=7) | J1(n=10) | J1(n=20) | 端点选择率 | 失败率 |
|---|---|---|---|---|---|---|
| Default | 0.633219 | 0.739286 | 0.644520 | 0.490866 | — | 0 |
| L1 | 0.632913 | 0.739733 | 0.645104 | 0.488235 | — | 0 |
| L2 | 0.632541 | 0.739286 | 0.644520 | 0.488235 | — | 0 |
| **L6-hindsight** | 0.494530 | 0.591115 | 0.503582 | 0.361479 | — | 0 |
| **dimensional**（本 harness） | **0.547461** | 0.656487 | 0.551058 | 0.405589 | 0.486 | 0 |
| **dimensionless**（候选） | **0.576203** | 0.670584 | 0.583427 | 0.453826 | 0.457 | 0 |
| 封存 E3b Vector-MLP-L6（seed42） | 0.547003 | 0.657558 | 0.549815 | 0.403679 | 0.488 | 0 |

- 有量纲复现与封存高度一致（seed 级 42/2026/3407 = 0.5487/0.5470/0.5468 vs 封存 0.5470/0.5461/0.5440；pooled 差 0.0005）。
- **dimensionless 相对 dimensional 恶化 +0.0287**（J1 相对升高 ~5.3%）；相对 Default 仍改善 -0.0570。
- 分 n：dimensionless 在三个 n 上均更差（n=7 +0.014，n=10 +0.032，n=20 +0.048），n=20 相对损失最大。
- **自适应收益保留比例**：Default→dimensional 的 J1 绝对降幅 0.0858；Default→dimensionless 的降幅 0.0570；**保留 ≈ 66%**。

**seed 级 pooled（5 折 × 45,000 样本/seed）：**

| 路线 | seed 42 | seed 2026 | seed 3407 | 3-seed 均值 |
|---|---|---|---|---|
| dimensional | 0.548657 | 0.546957 | 0.546768 | 0.547461 |
| dimensionless | 0.576090 | 0.576486 | 0.576033 | 0.576203 |
| 封存 E3b | 0.547003 | 0.546133 | 0.544009 | 0.545715 |

dimensionless 三 seed 均稳定高于 dimensional（+0.0274 ~ +0.0304），种子间波动小。

**P2 泛化（主网格训练、P2 评估；15 模型均值）：**

| track | dimensional | dimensionless | delta | 封存有量纲 |
|---|---|---|---|---|
| P2-NI（n=15 样本量插值） | 0.45469 | 0.49542 | **+0.04072** | 0.45355 |
| P2-PI（参数中点插值） | 0.54622 | 0.55090 | +0.00468 | 0.54610 |

- P2-NI 上 dimensionless 相对 dimensional 恶化约 9%（J1 0.495 vs 0.455）——**样本量插值轴是最大的精度损失点**。
- P2-PI 恶化较小（+0.005）。
- 有量纲 P2 复现与封存高度一致（P2-NI 差 0.001，P2-PI 差 0.0001）。

## 8. 尺度不变性验证（三尺度 ×1000 探针样本）

对每个探针样本，重构样本后整体乘以 $c\in\{0.001, 1, 1000\}$，检查（详见 `scale_invariance.csv`）：

| 检查项 | 结果 | 容差 |
|---|---|---|
| 11 维无量纲特征最大相对差 | **3.204e-11** | 1e-6（通过） |
| 模型预测 26 点损失曲线最大相对差 | **0.0** | 1e-4（通过） |
| 最终选择 $\delta$ 一致率 | **100.0%（1000/1000）** | 100% |

- 特征差 ~1e-11 为 float 舍入级别；曲线差为 0（输入逐位一致 → 输出逐位一致）。
- 该验证**不涉及新 MDM 估计**：无量纲特征对缩放是数学恒等的，模型输出随输入恒等；这里数值地证明了整条「特征→预测→选择」链对计量单位不变。

## 9. 运行时间、测试与 Git 状态

**运行时间（`summary.json['timing']`）：**
- 总墙钟 **6104 s ≈ 102 分钟**。
- 有量纲路线 15 模型：4941 s（单模型 58–879 s，早停迭代 34–166）；无量纲路线 15 模型：1001 s（单模型 38–110 s，迭代 40–86）；P2 推理 140 s（复用主网格模型，无重训）；尺度验证 7 s。
- 注：当前环境比封存环境（E4a 记录同 fold 仅 34 s）慢约 7 倍，见 §11.2。

**测试：**
- 新增合同测试 `tests/test_dimensionless_candidate.py`：**9/9 通过**（特征契约、公式、特征尺度不变、损失代数尺度不变、参考值与封存一致、缓存完整性、选择语义、列增补一致、z-score 形状）。
- 全量 Study01 测试套件：**276 通过 / 1 失败**。唯一失败 `test_p4_formal_compare.py::test_e3b_risk_curves_intact` 是**行尾字节差异**：主工作区该 CSV 为陈旧 CRLF checkout（eol=lf 规则建立前），新 worktree 按 `.gitattributes`（`*.csv text eol=lf`）得到 LF；二者归一化行尾后**内容逐字节一致**（已对 risk_curves/sample_features/model_comparison/seed_stability 验证）。该失败非本次改动引入，属 worktree 环境与主工作区行尾状态差异。

**Git 状态：** 本报告提交前，worktree 干净（见 §10 提交清单）；主工作区未提交的 `03-论文骨架.md` 未被修改/暂存/提交。
**manifest 记录说明：** `manifest.json['git_commit']=e2020a4b` 是脚本**保存时**（运行结束 23:24）的 HEAD；运行本身执行的是 `dcfffe77` 的代码（启动 21:42）。二者仅差 `analyze_dimensionless_candidate.py`（新增、不被运行导入），运行行为逐位一致。

## 10. 大型本地产物位置与 SHA256

大型逐样本输出与模型文件**不入库**，位于 `artifacts/candidate/dimensionless_vector_mlp/local_outputs/`（共 207 MB，gitignored）：

| 文件 | 内容 |
|---|---|
| `candidate_main_per_sample.csv`（~37MB） | 无量纲路线 15 模型主网格逐样本选择（675k 行） |
| `dimensional_main_per_sample.csv`（~37MB） | 有量纲复现 15 模型主网格逐样本选择（675k 行） |
| `candidate_p2_per_sample.csv`（~30MB） | 无量纲路线 15 模型 P2 逐样本选择（585k 行） |
| `dimensional_p2_per_sample.csv`（~30MB） | 有量纲复现 15 模型 P2 逐样本选择（585k 行） |
| `models/*.pkl`（30 个，~1MB） | 两路线各 15 个训练模型（MLP + 目标缩放器） |

指纹：`SHA256SUMS`（34 项，已 `sha256sum` 校验全部一致）+ `local_outputs/_local_manifest.json`（路径/大小/SHA256）。

## 11. 偏离计划、异常与待 Codex 决定

### 11.1 环境差异导致有量纲复现与封存数值不完全逐位一致（已核实为环境漂移，非管道错误）

- 用当前环境（python 3.11.15 / sklearn 1.9.0 / numpy 2.1.1 / OpenBLAS 0.3.27）重跑封存 E4a 生产代码路径（fold1/seed42/full），得 `J1=0.527740, n_iter=59`；封存同 fold 为 `J1=0.528518, n_iter=59`——**同一代码+同一数据+同一 seed，n_iter 完全一致、J1 差 ~0.0008**。
- 佐证：封存 P2（2026-07-30，记录 sklearn 1.9.0）在**当前环境**复现有量纲 P2-NI 差 0.001、P2-PI 差 0.0001，远小于主网格差 → 主网格 E3b/E4a 封存（更早时间）与当前环境存在数值漂移，来自封存时的 sklearn/BLAS/机器。
- 处理：本报告主对照为**同一 harness 内的有量纲 vs 无量纲**（仅在特征表示上不同，公平）；封存数值作为外部参考并列，差异如实报告。

### 11.2 训练耗时：当前环境比封存环境慢 ~7 倍

- 封存 E4a 记录 fold-1 full 训练 `elapsed_s=34.3`；当前环境同路径 ~250 s。有量纲单模型 ~250 s（最慢 879 s）、无量纲 ~60 s；早停开销主导，每迭代时间两路线仅差 1.3×。
- 影响：全量运行 ~102 分钟。逐模型迭代数与耗时记录在 `summary.json['timing']`。

### 11.3 过程中发现并修复的脚本 bug（不影响结论）

- 候选产物默认输出路径曾被错误解析到只读 `artifacts/formal/candidate/`；已在产生任何数据前发现并修复为 `artifacts/candidate/dimensionless_vector_mlp`（误建目录已清理，formal 树无污染）。
- smoke 结尾保存路径 `relative_to` 断言错误；已修复（输出目录解析为绝对路径）。

### 11.4 待 Codex 决定

1. **是否接受候选结论**：无量纲路线获得尺度不变性，但精度收益未基本保留（主网格 J1 +5.3%，自适应收益保留 ~66%，P2-NI +9%）。据此是否继续探索替代方案。
2. 替代方向（如 Codex 认可继续）：
   - 有量纲特征 + 部署时显式尺度归一化（例如按样本 $\bar x$ 缩放后再 z-score，或把有量纲特征除以样本量纲的某种稳健尺度）以在保留绝对信息的近似下获得不变性；
   - 在无量纲特征之外补充尺度信息（如损失曲线量纲相关的可观测代理）；
   - 接受「有量纲对照 = 本 harness 复现 + 封存 E3b 外部参考」的双轨口径。
3. 是否需要在本机固定 sklearn 版本以逐位复现封存主网格数值（当前存在 ~1e-3 环境漂移）。
