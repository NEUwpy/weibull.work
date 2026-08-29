# Study02 样本量与 P 等效观测数结果报告

> 状态：COMPLETE；未新增训练；由测试已打开的冻结 P/Q/QCP 同预算证据派生，属于 post-test exploratory analysis。

## 关键结果

三条路线都随单次估计的寿命观测数 n 增加而变准。P 的四点经验误差曲线为

\[
E_P(n)=0.568n^{-0.515},\qquad R^2=0.9983,
\]

指数的设计级经验 bootstrap 95% CI 为 [0.479,0.550]。

| n | P rRMSE | Q rRMSE | QCP rRMSE | Q 等效新增观测 | QCP 等效新增观测 |
|---:|---:|---:|---:|---:|---:|
| 7 | 20.74% | 20.30% | 19.92% | 0.30 [0.18,0.42] | 0.57 [0.47,0.66] |
| 10 | 17.37% | 16.91% | 16.69% | 0.54 [0.07,0.98] | 0.81 [0.46,1.18] |
| 15 | 14.28% | 14.04% | 13.84% | 0.51 [0.03,0.99] | 0.94 [0.57,1.34] |
| 20 | 12.00% | 11.86% | 11.69% | 0.46 [0.25,0.63] | 1.04 [0.87,1.23] |

## 怎样解释

- n 是每个待估样本中实际包含的寿命观测数，不是神经网络训练仿真集的行数。
- 例如 n=10 时，QCP 的 16.69% rRMSE 相当于 P 在当前曲线上使用约 10.81 个观测。
- 这只是把方法效应换成易读单位；不是实际增加的数据，也不证明方法可替代采样。
- n=20 的等效值略超当前观测网格，属于约一个观测范围的轻度外推。

## 证据入口

- 合同：`protocols/19-任务诱导度量与等效样本量分析合同.md`
- 汇总：`artifacts/qcp_sample_size_analysis/analysis/summary.json`
- 分层表：`artifacts/qcp_sample_size_analysis/analysis/by_n.csv`
- 图：`figures/qcp-main/fig_qcp_sample_size_equivalence.png`、`.pdf`
- 代码：`code/study02pq/sample_size_equivalence.py`、`sample_size_figures.py`
