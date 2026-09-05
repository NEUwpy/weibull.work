# Study02：三参数 Weibull 神经估计中的任务诱导度量

> 当前主线：P 参数参照 → Q 的 $x_{0.95}$ 收益与跨寿命点代价 → QCP 参数约束与跨寿命点恢复。正式适用域为 Study01 广参数域。

## 当前研究域

\[
\beta\in\{1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0\},\qquad
\eta=1000,\qquad
\gamma/\eta\in\{0.10,0.25,0.50,0.75,1.00\},
\]

\[
n\in\{7,10,15,20\},\qquad R_{\mathrm{train}}=0.95,\quad
R_{\mathrm{eval}}\in\{0.90,0.95,0.99\}.
\]

P、Q 和 QCP 在该研究域共享数据拆分、三输出网络、合法解码、初始化、batch 顺序、优化器和 `600 epochs / patience 60` 预算。完整证据包含 10 个训练种子、4 个样本量和 5 折，共 200 个三路线配对模型单元。此前启动的低形状、低位置比新样本实验保留为探索性历史结果，不进入当前正文主结论。

## 研究逻辑

端到端三参数神经估计必须先定义三个参数的联合损失。P 将归一化参数误差按 $1{:}1{:}1$ 等权相加，能够反映参数恢复精度，但该比例缺少针对最终用途的任务依据。

当实际使用量是 $x_{0.95}$ 时，Q 保留三参数输出，用寿命点误差训练并选择验证检查点。在当前比较中，Q 的目标点总体 RMSRE 相对 P 降低2.07%，而 $x_{0.90}$、$x_{0.99}$ 分别增加36.41%和63.11%。主线是检验任务对齐的收益与代价，而非宣称Q在多数区域更准确。

一个寿命点只是一个标量，多个参数组合可能产生相近结果。QCP 因此在 Q 上增加 P 约束：

\[
\min_\theta L_Q(\theta)
\quad\text{s.t.}\quad
L_P(\theta)\le 1.5L_{P,\mathrm{ref}}.
\]

QCP在保留Q任务目标的同时约束参数误差，目标点总体RMSRE进一步降至15.84%，另外两点恢复至略低于P的总体水平。收益集中在少数高误差单元；P在典型绝对误差与训练成本上仍占优。当前分析包含参数分布、位置边界、单侧误差和前置成本，见 `artifacts/manuscript_review_v250/`。固定加权QP已作为必要简单参照恢复，目标精度与QCP接近。协议25补充600/600训练完成：共同验证下Q仍改善1.322%，原生Q可行选点0/200，多点监督缓解跨点误差但当前等权设置弱于QP/QCP。完整结果已进入中英文稿，见[修订与验证](docs/v2.7.0-投稿修订与验证.md)。

## 当前入口

| 需求 | 文件 |
|---|---|
| 最新论文工作稿 | [`manuscript/Study02论文初稿-v2.7.0.md`](manuscript/Study02论文初稿-v2.7.0.md) |
| 论文附录 | [`manuscript/Study02论文附录-v2.7.0.md`](manuscript/Study02论文附录-v2.7.0.md) |
| 英文稿与投稿附件 | [`manuscript/submission/README.md`](manuscript/submission/README.md) |
| 投稿修订与验证 | [`docs/v2.7.0-投稿修订与验证.md`](docs/v2.7.0-投稿修订与验证.md) |
| 投稿图件 | [`manuscript/figures/`](manuscript/figures/) |
| P/Q 研究域配置 | [`configs/pq-iid-protocol-v1.json`](configs/pq-iid-protocol-v1.json) |
| P/Q/QCP 同预算合同 | [`protocols/18-PQ-QCP同预算当前分析合同.md`](protocols/18-PQ-QCP同预算当前分析合同.md) |
| QCP 解决程度与分布合同 | [`protocols/22-QCP问题解决程度与估计分布展示合同.md`](protocols/22-QCP问题解决程度与估计分布展示合同.md) |
| 跨寿命点恢复合同 | [`protocols/23-QCP跨寿命点恢复机制合同.md`](protocols/23-QCP跨寿命点恢复机制合同.md) |
| 三路线跨寿命点总比较合同 | [`protocols/24-三路线跨寿命点总比较合同.md`](protocols/24-三路线跨寿命点总比较合同.md) |
| QCP 冻结配置 | [`configs/qcp-constrained-confirm-v1.json`](configs/qcp-constrained-confirm-v1.json) |
| 当前主证据 | `artifacts/qcp_main_analysis/` |
| QCP 解决程度与代表性分布 | `artifacts/qcp_resolution_distribution/` |
| 三路线跨寿命点结果 | `artifacts/qcp_cross_quantile_recovery/` |

## 评价

训练主目标为 $x_{0.95}$ RMSRE；跨寿命点评价在预设的 $x_{0.90}$、$x_{0.95}$、$x_{0.99}$ 上使用同一 RMSRE。RMSRE 表示寿命点相对误差的均方根，不是准确率。同时报告有符号偏差、固定真值单元内标准差、MAE、阈值内比例和区域异质性。

## 证据边界

QCP 的监督训练和参数约束选择使用仿真真参数；训练好的固定网络推理时只需寿命样本。$x_{0.90}$、$x_{0.99}$ 比较属于既有预测上的事后机制分析，三个寿命点不能代表完整分布。实际应用需要验证训练域、量纲尺度与寿命机制是否匹配；若要在无标签真实数据上重新训练，则需另行设计训练依据。本研究未投稿。

## 文件放在哪里

| 目录 | 看什么 |
|---|---|
| [manuscript](manuscript/) | 当前正文、附录、正文与附录配图；不混放旧版本 |
| [docs](docs/) | 当前研究说明、执行与证据索引 |
| [protocols：实验与分析方案](protocols/) | 各实验和分析如何设计；目录说明区分当前分析与前期方案 |
| `code/`、`configs/`、`artifacts/` | 实现、机器配置、实验结果 |
| `figures/` | 项目级分析图源；投稿使用的图集中在 manuscript/figures |
| [前置实验](前置实验/) | 前期基础研究及其文档，暂不迁入 Research |
| [归档](归档/) | 统一保存旧稿、旧实验、过程记录；原四个归档入口已合并 |

低参数域原始 evidence 保留在 `artifacts/qcp_low_domain_v1/`，不得与广域主结果混池。归档中的部分旧实验结果仍被当前分析引用，不删除。
