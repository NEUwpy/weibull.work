# Study 02：NN 三参数 Weibull 输出下，参数精度损失 P vs 目标分位点损失 Q 对 \(x_{0.95}\) 估计的受控对照

> 创建日期：2026-07-11
> 当前修订：2026-08-05（r4 primary：direct-P + Codex 授权解码器；R4 REVISE 修复中）
> 当前分支：`codex/study02-pq-controlled-20260805-r1`
> 职责：本目录是 Study02 当前唯一研究主线。旧直接标量分位点 D 路线与旧前置研究 A 已整体
> 归档/移入前置实验区，详见 `已归档/README.md` 与 `前置实验/README.md`。
> 协议 v3/r4：P = **approved direct-P**、共享 **domain-explicit 解码器**
> `γ̂=min(X)(δ+(1-2δ)·sigmoid(o₃))`（结构性 0<γ̂<min(X)，Codex 合同决策 000003）、
> 主推断 fold×seed 交叉、压缩逐样本证据 tracked（精确键 dtype）。v1 = preliminary/superseded
> （`artifacts/pq/`）；v2/P_loggap = sensitivity（`artifacts/pq_v2/`，不进入 r4 主结论）。

## 当前研究问题（冻结）

> 在完全相同的数据、三参数 Weibull 输出网络、网络容量、初始化、训练预算、数据划分及
> 训练程序下，仅改变训练目标——**参数精度损失 P** 与**目标分位点损失 Q**——哪一种能够
> 更准确地估计 \(x_{0.95}\)？

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

## 设计对齐

本实验对齐远端 `main` 中已封存的 **Study01 Dimensional-RAW** 权威设计（数据、输入表示、
划分、训练设置），详见 `01-PQ-冻结协议.md`（v3/r4，配置 `configs/pq-protocol-v3.json`，
环境锁 `configs/pq-environment-v2.json`）：

- `beta = {1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5}`；`eta = 1000`；`gamma = {100, 250, 500, 750, 1000}`
- `n = {7, 10, 15, 20}`；每 `(beta, eta, gamma, n)` 组合 300 次重复抽样
- 共 160 个参数—样本量组合、48,000 个样本；输入为升序排列的有量纲原始样本
- 每个 `n` 独立网络；每个输入位置的 StandardScaler 仅由训练折拟合
- 5 折按 γ/η 水平留出（每折留出该 n 下的一个完整 γ/η 水平，测试覆盖全部 8 个 beta）
- 训练随机种子：`42, 2026, 3407`；隐藏层 `256–128–64`、ReLU、Adam、batch 256、
  lr 1e-3、weight decay 1e-4、max epochs 300、early stopping、validation 0.15、patience 20

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
| `已归档/` | 旧 D 路线归档（`直接标量分位点D路线/`）与总索引 |
| `前置实验/` | 旧前置研究 A 文档与主题索引 |
| `code/study02pq/` | P–Q 专用实现（训练、损失、数据、评测、测试） |
| `configs/pq-*.json` | P–Q 冻结机器可读配置 |

## 阅读顺序

1. 本 README：定位与当前问题。
2. `00-PQ-研究问题与边界.md`：问题与边界。
3. `01-PQ-冻结协议.md`：冻结协议。
4. `03-PQ-证据索引.md`：证据与 SHA。
5. `04-PQ-结果报告.md`：结果。
6. `05-PQ-论文逻辑骨架.md`：论文逻辑。

## 当前边界

- 只训练并主张 \(x_{0.95}\)；不扩展到其他分位点、删失/截断或跨尺度泛化。
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
