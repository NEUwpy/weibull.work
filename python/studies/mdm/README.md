# MDM 产品数据生成器

本目录保留 `simulate.py`，用于生成网站 MDM 适用范围数据。默认算法在 `python/methods/mdm.py`，统一调用与指标在 `python/studies/common/`；本目录不复制或分叉生产算法。

生产默认 offset 为 `0.1`，工程约束为 `gamma >= 0`。算法诊断由 `last_solution_info` 经共享 runner 进入行级 `extra.solution_info`。

研究用 `run_truth_sampling.py`、full-v1 阶段总结及相关研究程序已迁入[科研仓](https://github.com/NEUwpy/weibull-research)。科研仓通过集中配置直接调用软件仓共享流程；full-v1 等历史协议与结果保持原版本，新的软件实现不覆盖旧数据。
