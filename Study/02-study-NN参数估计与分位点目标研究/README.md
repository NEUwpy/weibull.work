# Study 02：NN 三参数 Weibull 输出下，参数精度损失 P vs 目标分位点损失 Q 对 \(x_{0.95}\) 估计的受控对照

> 创建日期：2026-07-11
> 当前修订：2026-08-07（S4 已 APPROVE；S5A 写作阶段完成——论文初稿、补充材料与引用/完整性审计已产出，
> 处于 `S5A READY FOR CODEX/MENTOR PRE-REVIEW CHECKPOINT`，未 APPROVE、未投稿）
> 当前分支：`codex/study02-paper-20260806`
> 职责：本目录是 Study02 当前唯一研究主线。旧直接标量分位点 D 路线与旧前置研究 A 已整体
> 归档/移入前置实验区，详见 `已归档/README.md` 与 `前置实验/README.md`。
> 协议 v3/r4：P = **approved direct-P**、共享 **domain-explicit 解码器**
> `γ̂=min(X)(δ+(1-2δ)·sigmoid(o₃))`（结构性 0<γ̂<min(X)，Codex 合同决策 000003）、
> 主推断 fold×seed 交叉、压缩逐样本证据 tracked（精确键 dtype）。v1 = preliminary/superseded
> （`artifacts/pq/`）；v2/P_loggap = sensitivity（`artifacts/pq_v2/`，不进入 r4 主结论）。

## 当前研究问题

> 在训练与测试覆盖相同参数组合、但使用相互独立重复样本时，仅改变训练目标——
> **参数精度损失 P** 与**目标分位点损失 Q**——哪一种能够更准确地估计 \(x_{0.95}\)？

旧 r4/v3 使用整层 gamma/eta 留出，实际回答的是“对未见 gamma 层级的外推”，不再作为
上述主问题的证据；它保留为补充泛化实验。纠偏说明与最小新合同见
`07-PQ-同分布主实验修正.md`。

- **P 路线**：网络输出三参数，训练损失以三参数估计精度为目标。
- **Q 路线**：网络仍输出完全相同的三个 Weibull 参数，但训练损失直接以由这三个参数推导出的
  \(x_{0.95}\) 误差为目标。

Q 的三个参数只是服务于目标分位点估计的内部表示。本实验**不主张**：Q 的单个参数估计准确、
Q 对其他分位点准确、Q 能恢复完整分布、Q 具有跨单位或跨尺度泛化能力。

Q 损失（与正式评价一致、可微的相对平方误差）：

\[
L_Q=\operatorname{mean}\left[\left(\frac{\hat{x}_{0.95}-x_{0.95}}{x_{0.95}}\right)^2\right],
\qquad
\hat{x}_{0.95}=\hat\gamma+\hat\eta[-\ln(0.95)]^{1/\hat\beta}.
\]

沿用同一合法参数化/输出变换，梯度从分位点损失经 Weibull 公式传播到三个输出。

**\(x_p\) 的定义**（S0-001）：本文的 \(x_p\) 是**可靠度寿命点**——满足可靠度/生存函数
\(R(x_p)=P(X>x_p)=p\) 的寿命值（等价 CDF 的 \(1-p\) 分位点），**不是**通常的 CDF
\(p\)-分位点（后者用 \(-\ln(1-p)\)）。公式恒为 \(x_p=\gamma+\eta[-\ln p]^{1/\beta}\)；
M3 的 0.90/0.95/0.99 是**可靠度水平**。

## 设计对齐

本实验对齐远端 `main` 中已封存的 **Study01 Dimensional-RAW** 权威设计（数据、输入表示、
训练设置）。**同分布主协议**（论文主问题）见 `09-PQ-同分布主协议冻结.md`（配置
`configs/pq-iid-protocol-v1.json`，`PQ_PROTOCOL=iid-v1`）；**r4/v3 协议**（gamma-holdout
OOD 补充）见 `01-PQ-冻结协议.md`（配置 `configs/pq-protocol-v3.json`）。两者共享环境锁
`configs/pq-environment-v2.json`：

- `beta = {1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5}`；`eta = 1000`；`gamma = {100, 250, 500, 750, 1000}`
- `n = {7, 10, 15, 20}`；每 `(beta, eta, gamma, n)` 组合 300 次重复抽样
- 共 160 个参数—样本量组合、48,000 个样本；输入为升序排列的有量纲原始样本
- 每个 `n` 独立网络；每个输入位置的 StandardScaler 仅由训练折拟合
- **主协议拆分**：每组合 300 个 repeats 按 `repeat_id % 5` 五折（test 60 / val 60 / train 180），
  每折覆盖全部 40 个 (β,γ) 组合——同分布独立重复；r4/v3 的“每 n 按 γ/η 水平留出”只作
  OOD 补充，不作主推断
- 训练随机种子：`42, 2026, 3407`；隐藏层 `256–128–64`、ReLU、Adam、batch 256、
  lr 1e-3、weight decay 1e-4、max epochs 300、early stopping、patience 20

**与 Study01 对齐的范围**（S0-003）：完全相同 = 参数网格、样本身份（生成契约/namespace/key）、
原始排序输入、名义网络 `256-128-64`、主要训练预算、训练种子；有意不同 = 研究标签/损失
（P/Q）、拆分方案（本主协议 repeat-stratified vs Study01 gamma/η 留出）、优化实现（PyTorch
Adam vs sklearn 轨迹）。横向分析仅在共同样本身份**且**指标可比（同为 \(x_p\) 可靠度寿命点）
时进行。

P 与 Q 使用**同一个 PyTorch 训练实现**，除 loss route 外全部相同（初始化、数据行、
batch 顺序、scaler、checkpoint 选择等均逐 fit 配对验证）。

## 当前文件

| 文件 | 作用 |
|------|------|
| `00-PQ-研究问题与边界.md` | 当前科学问题、边界、不主张项 |
| `01-PQ-冻结协议.md` | P–Q 受控对照冻结协议（含配置与 SHA 绑定） |
| `02-PQ-执行状态.md` | 实验进度、运行 ID、下一步 |
| `03-PQ-证据索引.md` | 证据、manifest、SHA 清单与路径 |
| `04-PQ-结果报告.md` | r4 primary 最终结果（direct-P vs Q） |
| `05-PQ-论文逻辑骨架.md` | 论文逻辑骨架（8 问） |
| `06-PQ-缺口与审查记录.md` | 缺口、已知限制、审查记录 |
| `07-PQ-同分布主实验修正.md` | 旧 OOD 主合同纠偏与同分布 pilot 结论 |
| `08-PQ-论文研究蓝图与阶段清单.md` | 论文科学主线、必要实验、阶段状态与协作边界 |
| `09-PQ-同分布主协议冻结.md` | **S0 同分布主协议冻结候选**（论文主问题；RQ、estimand、拆分、统计层级、证据 schema、M1–M3 矩阵） |
| `12-PQ-可信性与边界结果.md` | S3 可信性与边界结果（E1 目标水平 / E2 容量 / E3 域内插值 / E4 OOD） |
| `13-PQ-综合科学报告.md` | **S4 综合科学报告**（问题—设计—主结果—机制—可信性—边界—结论与建议—限制；claim→evidence 表） |
| `14-PQ-论文初稿.md` | **S5A 论文初稿**（IMRaD，简体中文 + 中英摘要 + 13 条核验文献；嵌入 fig1–fig4） |
| `15-PQ-补充材料.md` | **S5A 补充材料**（冻结设计表、公式、fit/seed/fold 清单、推断层级、机制恒等式、S3 矩阵、复现路径、限制） |
| `16-PQ-引用与完整性审计.md` | **S5A 引用与完整性审计**（claim→sealed 抽查、零 orphan、DOI/URL 核验、图数据来源、AI failure-mode 检查） |
| `16-audit-zero-orphan.py` | S5A 审计脚本：正文引用 ↔ 参考文献零 orphan/多余条目检查 |
| `figures/pq-paper/` | **S4 论文级图表**（fig1–fig4，PNG+PDF；由 `code/study02pq/paper_figures.py` 从 sealed 证据只读生成） |
| `已归档/` | 旧 D 路线归档（`直接标量分位点D路线/`）与总索引 |
| `前置实验/` | 旧前置研究 A 文档与主题索引 |
| `code/study02pq/` | P–Q 专用实现（训练、损失、数据、评测、测试） |
| `configs/pq-*.json` | P–Q 冻结机器可读配置（`pq-iid-protocol-v1.json` = 同分布主协议；`pq-protocol-v3.json` = r4 OOD；`pq-environment-v2.json` = 环境锁） |

## 阅读顺序

1. 本 README：定位与当前问题。
2. `00-PQ-研究问题与边界.md`：问题与边界。
3. `08-PQ-论文研究蓝图与阶段清单.md`：论文总任务与当前阶段。
4. `01-PQ-冻结协议.md`：冻结协议。
5. `03-PQ-证据索引.md`：证据与 SHA。
6. `04-PQ-结果报告.md`：结果。
7. `12-PQ-可信性与边界结果.md`：S3 可信性与边界结果。
8. `13-PQ-综合科学报告.md`：S4 综合科学报告（论文写作的直接支撑；含 claim→evidence 表与图）。
9. `05-PQ-论文逻辑骨架.md`：论文逻辑。
10. `14-PQ-论文初稿.md`：S5A 论文初稿（与 `15-PQ-补充材料.md`、`16-PQ-引用与完整性审计.md` 配套）。

## 当前边界

- 主协议只训练并主张 \(x_{0.95}\)；其他可靠度水平仅作为 M3 有限边界实验（目标特异 Q，\(x_{0.90}, x_{0.95}, x_{0.99}\) 为可靠度水平，S3 门复核），不扩展到删失/截断或跨尺度泛化。
- 主分析使用各 seed 独立训练的模型，不用 seed 平均替代主分析。
- 参数误差只用于诊断 Q 如何达到分位点结果，不作为 Q 的成功标准或正文主张。
- 旧 D 路线（直接标量分位点网络）**不再训练**；旧前置研究 A 的 formal 引擎只读冻结。
- 数据、样本与划分对齐 Study01 Dimensional-RAW；横向可比性表述为数据/输入/划分/训练设置
  对齐，不声称与 sklearn 的逐步优化轨迹完全相同。
- r4 P 为 **approved direct-P**；解码器依赖冻结正位置域（γ∈[100,1000]），不声称负位置问题
  成立；v2/P_loggap 为 sensitivity 证据，不进入 r4 主结论。

## 环境与复现

Study/02 正式代码依赖 PyTorch（CPU）。可复现依赖声明见本目录 `requirements.txt`：

```
pip install -r "Study/02-study-NN参数估计与分位点目标研究/requirements.txt"
```

P–Q 实现入口与精确测试命令见 `01-PQ-冻结协议.md` 与 `03-PQ-证据索引.md`。

## 研究原则

本 Study 继承 `study/研究原则.md`：问题驱动、可信性优先、仿真数据证明统计性质、真实数据
证明工程价值，并明确方法的适用边界。
