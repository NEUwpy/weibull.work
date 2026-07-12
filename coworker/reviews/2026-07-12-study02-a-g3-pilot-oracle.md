# Study/02 A G3 pilot oracle review

> 日期：2026-07-12
> 当前审查对象：`G3-pilot-20260712-07`、`A-G3-pilot-amendment-v4`
> amendment SHA-256：`164e72658669dbb57f6dab8b1fc80099bd319f1fa327d5dda60cb61cb929ee38`
> 结论：**APPROVE — 仅批准进入 formal training/validation，test 必须继续 sealed**

## 总判断

v7 已解决上一轮资源门阻塞。修订没有事后放宽 720 小时阈值，而是在完整保留 820 fits、10 formal seeds、min epochs 50 和 patience 40 的前提下，把 formal max epochs 透明修订为 100，并冻结 ceiling-hit 审计规则。

运行时间基准使用预注册的 warm-up、五次交错重复和中位数；4-worker 实测速率没有获得可信加速，因而按 `max(1,q25)` 采用 effective worker factor 1。最终 2 倍余量投影为 `1,373,822.99 s`，约 381.6 小时，低于不变的 `2,592,000 s`（720 小时）门槛。存储门也通过。

formal test 从 v1 到 v7 始终为 `sealed`。本批准只允许训练和 validation 选择，不批准 test 启封，也不支持任何研究问题结论。

## P0：阻塞项

无。

## P1：批准条件与启封前要求

### P1-1 资源与协议修订通过

- 生效合同为 `A-G2-v1 + A-G3-pilot-amendment-v4`。
- formal runner、fit manifest 和 selection trace 必须显式记录 amendment ID、SHA-256 和 effective `max_epochs=100`，不能继续读取基础 search JSON 中已被覆盖的 500。
- 任何把 max epochs 提高到 100 以上、扩大 820-fit 矩阵或改变 10 formal seeds 的行为，都必须新建 amendment 并重新审查。

### P1-2 100-epoch ceiling-hit 只允许先训练后复核

- formal training/validation 可立即开始，test 保持 sealed。
- 必须逐 fit 保存实际停止 epoch、是否触及 epoch 100、best epoch 和 early-stopping 状态。
- selection 完成后、test 启封前，提交 ceiling-hit 比例及 validation learning-curve 诊断给 oracle。若入选路线或关键比较臂大量触顶且 validation 仍持续改善，不得直接启封 test；应修订训练合同或矩阵并重新审查。
- 本批准不预先认可“只报告触顶比例后仍可启封”；启封需要下一次独立闸门。

### P1-3 S 路线实现通过

- `SetFeatures` 将 values、mask、n 分开表达。
- `DeepSets.forward(values, mask, n)` 在 pooling 后拼接显式 n，不再把 n 当作集合观测。
- pilot 的 2,304 次 route-sample 检查无失败。formal collate 和 training 实现仍须沿用同一合同并通过测试。

### P1-4 传统方法准入通过

- WMLE 与 MDM-0.1 完整通过 core、determinism、scale equivariance、translation equivariance、failure propagation，获准进入声明支持域内的 formal 比较。
- MLE、LRE、MMLE 的合同失败已如实保留，不得进入 core formal 排名。
- MPS、LSE、MM、PWM 为 pending/`NotImplementedError`，正确 fail-closed，不得静默替换。
- 最终结论必须声明传统池缩小为 WMLE 与 MDM，不能外推为对全部传统参数估计法的普遍比较。

### P1-5 supersession 留痕需补一处

ledger 已有 v4→v5、v5→v6、v6→v7 的显式 supersession，但当前未检索到 v3→v4 的对应条目；执行报告却写成“v3-v6 有显式 supersession”。在 pilot 阶段提交前应补充 v3→v4 追加式 supersession，或修正报告文字以准确反映现有证据。不得删除 v3。

## P2：非阻塞项

- 152 tests 的命令、结果、忽略文件和理由已进入 validation manifest 与 ledger；已满足上一轮留痕要求。
- amendment SHA-256 与实际文件哈希一致。
- resource estimate 采用 effective worker 1，因此没有依赖未经证实的四 worker 线性加速。
- v7 的 manifest 本体未列 amendment 字段，但 validation manifest 已列出；formal run manifest 必须补齐，避免只依赖旁路验证文件。

## 下一闸门

1. 补齐/修正 v3→v4 supersession 证据并完成 pilot 阶段提交、推送；
2. 在 test sealed 状态下执行 A-E1 → A-E3 → A-E2 的 training/validation 选择；
3. 保存完整 selection trace、fit 状态、ceiling-hit、best epoch、checkpoint hash 和数据角色泄漏审计；
4. 将上述材料提交 oracle；
5. 只有下一轮明确 `APPROVE test unseal` 后，才可进行一次 test 评价。
