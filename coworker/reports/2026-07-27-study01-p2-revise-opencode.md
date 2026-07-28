# Study01 P2 v2 修正与预授权执行报告

> 日期：2026-07-28
>
> 分支：`study01xu`
>
> 审查起点：`88a40747`
>
> 生产实现提交：`fbbe2726`
>
> clean-worktree 加固提交：`50422747`
>
> 状态：`READY_FOR_P2_RERUN_AUTHORIZATION`

## 1. 本轮结论

P2 v2 已完成正式重跑前的生产实现、fail-closed 检查和真实生产路径 smoke。39 个组合的正式计算尚未启动；P3 Direct-MLP 未启动。

P2 v1 不可作为研究证据：旧生成器使用 Python `hash()` 派生 seed，跨进程不稳定。旧 v1 状态统一为 `INVALID_NONDETERMINISTIC_SEED`。39 个未跟踪 chunks 已从仓库工作区隔离到：

`D:\weibull-local-artifacts\study01-p2-invalid-v1-5ebda361\chunks`

仓库中既有 v1 manifest/summary 只保留为失效历史记录，不得进入论文、图表或 v2 续跑。

## 2. v2 生产实现

### 2.1 确定性生成与输出保护

- seed namespace 保持冻结值 `study01_p2_v1`，但样本由共享 `generate_sample()` 生产入口确定性生成；
- v2 输出目录独立为 `extended_validation/p2_generalization_v2`；
- 每个 chunk 必须满足精确 schema、26,000 行、1000 个 repeat、26 个 delta、无重复键；
- 每个 repeat 的样本 SHA256 均由真实样本内容复算，禁止只哈希参数键；
- 失败行必须包含失败原因；
- chunk 采用临时文件后原子替换，checkpoint 续跑前复核上下文和文件哈希；
- 正式启动要求完整 worktree clean，记录 exact command、generation commit、版本和输入文件 SHA256；
- `P2_FORMAL_AUTHORIZED=False`，无公开绕过入口。

### 2.2 评价公式

逐样本损失与 E4 正式入口一致：

```text
L_i = e_beta^2 + e_eta^2 + e_gamma^2
J1 = sqrt(mean_i(L_i))
```

其中：

```text
e_beta = (beta_hat-beta)/beta
e_eta  = (eta_hat-eta)/eta
e_gamma = (gamma_hat-gamma)/eta
```

不除以 3；pooled J1 从全部逐样本 `L_i` 直接计算，不对组合级 J1 作算术平均。失败惩罚与 complete-case 结果分别记录。

### 2.3 Vector-MLP 单一生产路径

`run_p2_vector_mlp.py` 不再复制一套近似实现，而是调用 `run_E4_formal_validation.py` 的正式入口：

- full-combo 5 folds 与 3 seeds；
- 13 个部署可观测特征；
- train-fold-only z-score；
- 26 维风险曲线目标；
- 每折训练损失 P99 失败惩罚；
- MLP `(256,128,64)` 正式训练函数；
- P2 只作 forward pass，不进入 scaler、训练、调参或 seed 选择；
- 结果先按模型汇总，再给出 15 模型分布。

为避免逐个 P2 样本反复扫描完整风险表，E4 正式模块新增索引版 evaluator。专项测试确认其输出与历史 evaluator 在相同输入上逐项完全一致，原正式结果和旧入口未改写。

## 3. 真实生产路径 smoke

输出位于仓库外：

`D:\weibull-local-artifacts\study01-p2-smoke-fbbe2726-r2`

冻结规模：

- P2-NI 1 个组合：`beta=1.5, gamma/eta=0.1, n=15`；
- 2 repeats；
- `combo_fold_1 × seed 42`；
- 不是伪造小模型，而是实际读取 45 个主网格 chunk、构造 45,000 个主网格样本特征，并用其中 36,000 个 train-fold 样本调用正式 MLP 训练入口。

结果：

| 项目 | 结果 |
|---|---:|
| 训练模型 | 1 |
| 模型训练迭代 | 59 |
| 模型训练时间 | 56.04 s |
| Vector-MLP 逐样本行 | 2 |
| Default/L1 逐样本行 | 4 |
| 生成或评价失败 | 0 |
| Vector-MLP smoke pooled J1 | 0.336716 |
| Default smoke pooled J1 | 0.277544 |
| L1 smoke pooled J1 | 0.284397 |

这些数值仅验证代码路径和口径，不构成性能结论。

## 4. 验证

- P2 config + REVISE 专项：`39 passed`；
- E4 fail-closed/repeat/SHA、E3b 合同、分类与 P2 联合回归：`148 passed`；
- P0 完整性审计：`P0_INTEGRITY=PASS`；
- P1 仍为：`GAP_REQUIRES_P2 (pure_n_interp=0)`；
- v1 chunks：隔离目录 39 个，原工作区 0 个；
- 正式生成入口：在未授权状态 fail-closed；
- `git diff --check`：clean。

测试警告仅包括既有大 CSV dtype 提示和小样本训练测试的 batch-size clipping，不影响正式合同。

## 5. 正式运行前授权条件

只有同时满足下列条件才可启动 39 组合正式 v2：

1. Codex 对本轮精确 clean tip 给出独立 `APPROVE`；
2. 授权记录明确绑定该 tip、P2 v2 输出目录和冻结的 39 个组合；
3. 解封动作形成单一、可审计的小提交，并再次核对输入哈希与 clean worktree；
4. 正式运行完成后重新封存，停在 `READY_FOR_INDEPENDENT_REVIEW`；
5. 不复用 v1 chunks，不进入 P3，不按结果追加点位。

## 6. 禁止事项确认

- [x] 未启动 P2 v2 正式 39 组合运行；
- [x] 未把 v1 结果冒充 v2 或研究证据；
- [x] 未覆盖 E1–E4 正式产物；
- [x] 未修改组合、repeats、delta 网格或训练配置；
- [x] 未进入 Direct-MLP；
- [x] 未自评 `APPROVE`。
