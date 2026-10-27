# Study/02 A G2 协议审查

## 结论

Round 4：**APPROVE**。G2 协议、机器配置、搜索空间、历史重建矩阵规则和 test 启封门形成可执行闭环。

## 审查轨迹

### Round 1：REVISE

- 缺精确 role/module seeds 与候选生成规则。
- epsilon 锚点破坏严格等变。
- 历史重建和输入归因混杂。
- A6/A13 分布、投影和整体优势口径未冻结。
- 缺可展开的实验矩阵和资源门。

### Round 2：REVISE

- screening/formal seed 重叠。
- legacy grid 行分配不唯一。
- 传统方法准入未区分声明支持域。
- A-E3 与前后模块的矩阵生成规则不完整。

### Round 3：REVISE

- H0/H1 历史重建未进入矩阵规则。

### Round 4：APPROVE

- 历史层已冻结互斥 80/20 参数组合、共享 n、7000/2000 行、固定 recipe、10 个 formal seed 和只作诊断的角色。
- 无 P0/P1 阻塞项。

## 非阻塞后续

- A11 的数据 SHA、500 拆分依赖推断和精确 CDF/CRPS 公式在 G5 formal 快照前冻结。
- A12 的 conformal score、有限样本分位数、coverage 和反变换规则在 G5 formal 快照前冻结。
- 各模块 test 启封前仍须生成 `experiment_matrix.csv`、实际 fit 数和 pilot 资源估计。
