# Ch5 β–profile 轻量机制审计合同

## 目的

检查有限样本下 MDM profile 标准差曲线的几何特征是否随真值 $\beta$ 系统变化。该审计只能评估“与机制解释一致”的计算证据，不能证明 Weibull 尾部形态因果地导致最优 $\delta$ 变化。

## 固定设计

- 数据生成：复用 `python/studies/common/sample.py::generate_sample` 与正式 E1/E2 的 `seed_namespace=study01_v1`。
- 参数：$\eta=1$、$\gamma/\eta=0.5$；$\beta\in\{1.5,2.0,2.5,4.0,5.0\}$；$n\in\{7,10,20\}$。
- 重复：每个 $(\beta,n)$ 使用 `repeat_id=0,...,19`，共 $5\times3\times20=300$ 个样本。
- 求解：每个样本只运行一次 `MDM.run(trace=True, offset=0.1)`；不重新扫描 26 个 $\delta$。
- 所有曲线坐标以 $\eta=1$ 的固定尺度解释；不与 Hermes/E4 文件或产物交叉读写。

## 行级诊断量

每个样本保存：

- `gradient_at_zero`：$g(0)$；
- `gradient_at_true_gamma`：由真实 $\gamma=0.5$ 两侧 trace 点线性插值得到的 $g(\gamma)$；
- `local_gradient_slope`：真实 $\gamma$ 邻域内，以最近 7 个非虚拟 trace 点拟合 $g(\gamma)=a+b\gamma$ 得到的 $b$，作为 $\sigma_{\eta,\min}(\gamma)$ 局部曲率代理；
- `gamma_hat_d01`：$\delta=0.1$ 的求解位置；
- `gamma_error_d01`：`gamma_hat_d01 - true_gamma`；
- `solution_strategy`：内部根、零端截断或右端拟合等求解路径。

曲率代理只称为 `local_gradient_slope`，正文不得把它写成解析二阶导数。

## 聚合与趋势

- 按 $(\beta,n)$ 报告每个连续诊断量的中位数、Q1、Q3；报告各求解策略计数。
- 在每个 $n$ 内分别计算 $\beta$ 与连续诊断量的 Spearman $\rho$；另给 pooled 描述值，但不以 pooled 值替代跨 $n$ 一致性。
- 不使用“显著”“可忽略”或预设工程阈值；保留效应方向、幅度和区间。
- `direction_consistent_across_n` 仅表示三个 $n$ 的 Spearman 符号相同且均非零，不表示统计显著或因果成立。

## 产物

输出目录：`artifacts/formal/E2_beta_profile_audit/`

- `profile_metrics.csv`：300 行样本级诊断；
- `by_beta_n.csv`：15 个 $(\beta,n)$ 单元的中位数与四分位数；
- `trend_summary.csv`：逐 $n$ 与 pooled Spearman 描述；
- `summary.json`：审计结论所需的结构化摘要和证据边界；
- `manifest.json`：代码、参数、seed、样本数、MDM 调用和输出合同。

## 失败与停止条件

- 任一样本无法生成有限 trace、真实 $\gamma$ 不在可插值区间内或行数不是 300：fail closed，不写正式摘要。
- 若三个 $n$ 的方向不一致，正文删除“profile 曲线机制”解释，只保留 $\beta$ 与最优 $\delta$ 的经验关系。
- 若方向一致，正文最多写为“profile 曲线几何随 $\beta$ 系统变化，与该机制解释一致”；仍不得使用“证明”“导致”或“中介机制已确认”。

## 测试合同

- 单元测试先验证插值、最近 7 点局部斜率、符号一致性与 300 行设计枚举。
- 小型集成测试用少量真实 `MDM` trace 验证字段有限、插值区间和输出 schema。
- 正式运行后核对 300 行、15 个聚合单元、3 个分 $n$ 趋势加 1 个 pooled 趋势，以及 manifest/summary 的边界声明。
