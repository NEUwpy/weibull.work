# Study/02 lean E1 完成报告

日期：2026-07-31
分支：`codex/study02-lean-prestudy-20260731`
代码/配置 tip：`828abeba`
外部运行根：`C:\weibull-runs\study02\lean\E1-training-sensitivity`

## 范围

E1 只回答 A5、A6、A13。固定 V 路线、n=10、m12 joint MLP 与 transformed-train-z Huber；没有重新搜索模型，没有访问 formal test。

## 执行

- focused tests：`python -m pytest Study/02-study-NN参数估计与分位点目标研究/code/test_E1_preflight.py -q` → 6 passed。
- pilot：2/2，10 epoch 诊断上限，8.3 s。
- full：A5 12 fits + A6 9 fits = 21/21，951.4 s；stderr 为空。
- confirmation：64 参数点×20 重复 = 1,280 行，只执行一次，88.9 s。
- 推断：按参数点聚类 bootstrap 2,000 次；NN 比较同时重采样训练 seed。

## 结论

- A5：100k 是实用选择；25k→100k 有 0.829% 小幅可确认改善，100k→400k 无可确认收益并进入平台。
- A6：训练分布显著影响 core 性能；legacy_grid 和 extended_wide 均劣于 core_continuous。
- A13：范围裁剪能改善 MDM/LRE/WMLE，但 NN 相对原始或裁剪 MDM 的差异 CI 均跨 0；不能宣称 NN 普遍优于传统方法，也不能把不存在的普遍优势归因于范围先验。

详细数值、边界和复现路径见 `05-A-证据索引.md`；机器摘要与行级源表见 `artifacts/lean/E1-training-sensitivity/`。
