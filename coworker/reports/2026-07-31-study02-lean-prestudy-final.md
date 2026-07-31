# Study/02 前置研究 A 精简路线最终报告

## 结论

前置研究 A 已按最小可复现路线完成：19/19 问均有证据覆盖，其中 17 个为 `answered`，A4/A8 为 `partial`。partial 是结论边界，不是待建大型流水线：当前证据不能识别单个特征贡献，也不能证明科学结论跨架构不变；为把标签改成 answered 而新增大消融不符合比例原则。

推荐的后续 Study/02 参数估计基线为：

- 输入：排序样本值 V，经样本最小值/IQR 等变锚定；
- 目标：log β、log(η/scale)、log((min−γ)/scale)，训练集标准化；
- 损失：Huber；
- 模型：m12、joint、fixed-n；
- 训练量：100k；更大到 400k 未确认收益；
- 可变 n 时可用 d12 shared DeepSets，但 fixed 的验证结果略优；
- 输出必须伴随合法性、calibration 域、ensemble/conformal 区间、区间宽度和支持集违规提示。

不能声称：

- NN 普遍优于传统方法（core 中 MDM 仍是强基线）；
- NN 对异常值鲁棒；
- core 校准区间能覆盖 boundary-low/high；
- 真实数据上的 γ 支持边界可靠；
- 单个工程特征有已证实的独立贡献；
- 结论对任意网络架构不敏感。

## 完成规模

- E0：复用 A-E1 r5 / A-E3 r2 回答 6 问。
- E1：21 个训练 fit；1,280 条 confirmation。
- E2：60 个冻结 checkpoint 只读评估；111,200 条记录；60 个配对比较。
- E3：1,600 个配对数据集；20,800 条等变/污染记录。
- E4：2,500 个 NIST 拆分；10,000 条真实方法结果；3,200 calibration；5,600 confirmation；11,200 conformal 行。
- formal test namespaces 全程 sealed；未 authorize/unseal/consume，未扩建旧 formal 控制面。

## 关键发现

1. 100k 训练量进入平台；训练参数分布对 core 性能有实质影响。
2. NN 的优势按参数层/对手变化：对 MLE/LRE 常有优势，但 core 未整体胜过 MDM；boundary-low 明显较弱。
3. 10-seed 波动小；未见 n 可用但 n=50 有回退；样本量总体改善不等于逐参数点单调。
4. NN 在当前评估域 100% 合法并满足尺度/平移等变，但强异常值显著增大误差。
5. NIST 真实数据 holdout CDF 拟合有竞争力，但 γ 支持集违规率高。
6. core conformal 边际覆盖接近标称值，区间较宽且能提供有限风险排序；boundary-low/high 覆盖严重不足。

## 复现入口

- 长任务/进度：`coworker/plans/2026-07-31-study02-lean-prestudy-completion.md`
- 执行状态：`Study/02-study-NN参数估计与分位点目标研究/00-A-执行状态.md`
- 19 问证据：`Study/02-study-NN参数估计与分位点目标研究/05-A-证据索引.md`
- E1–E4 脚本/config：同目录 `code/` 与 `configs/`
- tracked 工件哈希：`artifacts/lean/SHA256SUMS`
- 阶段报告：`coworker/reports/2026-07-31-study02-lean-e1-training-sensitivity.md`、`...e2...`、`...e3...`、`...e4...`

JSON 运行时文件在 Windows 写出时使用 CRLF；Git 根据仓库 `.gitattributes` 规范化为 LF。阶段报告保留运行时哈希，`SHA256SUMS` 是干净 checkout 中 tracked 文件的权威哈希。

## 最终验证

在独立 detached clean worktree 执行：

```text
python -m pytest code/test_E1_preflight.py code/test_E2_preflight.py code/test_E3_preflight.py code/test_E4_preflight.py -q
```

综合候选提交 `a53161d052ae4140dc3ca6c679ff21b326d1fda5` 已在独立 detached clean worktree 完成终验：

- E1–E4 全部预检：`22 passed in 7.27s`；
- `artifacts/lean/SHA256SUMS`：9/9 文件一致；
- 验证后 worktree：clean；
- 临时 worktree 已安全移除。

因此前置研究 A 精简路线满足完成条件。最终闭环提交仅记录上述验证结果，不改变代码、配置或实验工件。
