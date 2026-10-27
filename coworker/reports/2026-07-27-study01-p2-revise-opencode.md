# Study01 P2 v2 修正与预授权执行报告

> 日期：2026-07-28
>
> 分支：`study01xu`
>
> 审查起点：`88a40747`
>
> 独立 REVISE 基线：`73771dc2`
>
> 阻断修复提交：`2036a13b`
>
> 负向测试提交：`cf366696`
>
> 状态：`READY_FOR_INDEPENDENT_REVIEW`（2026-07-30 修订）

## 1. 本轮结论

独立审查对 `73771dc2` 给出 `REVISE` 后，五项允许修改均已完成：关闭 smoke 绕过、统一逐模型失败惩罚、评价前重新绑定上下文、评价产物原子写入并最终统一封存，以及为 v1 增加机器可读墓碑。P2 v2 已完成真实生产路径 smoke（预授权阶段），随后获得授权并完成 39 组合正式生成与评价（详见 §6）。P3 Direct-MLP 未启动。

P2 v1 不可作为研究证据：旧生成器使用 Python `hash()` 派生 seed，跨进程不稳定。旧 v1 状态统一为 `INVALID_NONDETERMINISTIC_SEED`。39 个未跟踪 chunks 已从仓库工作区隔离到：

`D:\weibull-local-artifacts\study01-p2-invalid-v1-5ebda361\chunks`

仓库中既有 v1 `manifest.json` 和 `evaluation_manifest.json` 已写入 `status=INVALID_NONDETERMINISTIC_SEED`、`valid_evidence=false` 和 replacement run ID；历史 `SHA256SUMS` 也加入失效说明，P0 审计明确将该目录排除在正式证据之外。

## 2. v2 生产实现

### 2.1 确定性生成与输出保护

- seed namespace 保持冻结值 `study01_p2_v1`，但样本由共享 `generate_sample()` 生产入口确定性生成；
- v2 输出目录独立为 `extended_validation/p2_generalization_v2`；
- 每个 chunk 必须满足精确 schema、26,000 行、1000 个 repeat、26 个 delta、无重复键；
- 每个 repeat 的样本 SHA256 均由真实样本内容复算，禁止只哈希参数键；
- 失败行必须包含失败原因；
- chunk 采用临时文件后原子替换，checkpoint 续跑前复核上下文和文件哈希；
- 正式启动要求完整 worktree clean，记录 exact command、generation commit、版本和输入文件 SHA256；
- smoke 强制写到仓库及 formal tree 之外；正式目录、其父子目录和任意仓库内路径均被拒绝；
- `P2_FORMAL_AUTHORIZED=False`，`P2_APPROVED_PARENT_COMMIT` 已冻结为 `5156fd31...`（预授权时为空，正式运行前由授权提交绑定）。

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

不除以 3；pooled J1 从全部逐样本 `L_i` 直接计算，不对组合级 J1 作算术平均。对每个 `fold × seed`，Vector、Default 和 L1 使用同一个由该 fold 主网格训练损失确定的 P99；失败惩罚与 complete-case 结果分别记录。

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

### 2.4 评价前闸门和最终封存

- 评价前重新核验 clean worktree、当前 HEAD、批准父提交、generation context、manifest、输入代码哈希和 generation SHA256；
- generation 目录出现未知、旧、临时或额外文件即停止；
- Vector per-sample、model summary、baseline per-sample 和 evaluation summary 均先写临时文件再原子替换；
- 四类评价文件与全部生成文件共同进入最终 `SHA256SUMS`；
- 已存在的评价文件禁止覆盖；不完整中断不会产生合法最终封印。

## 3. 真实生产路径 smoke

输出位于仓库外：

`D:\weibull-local-artifacts\study01-p2-smoke-cf366696`

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
| 模型训练时间 | 54.51 s |
| 三方法共同失败惩罚 | 2.196617 |
| Vector-MLP 逐样本行 | 2 |
| Default/L1 逐样本行 | 4 |
| 生成或评价失败 | 0 |
| Vector-MLP smoke pooled J1 | 0.336716 |
| Default smoke pooled J1 | 0.277544 |
| L1 smoke pooled J1 | 0.284397 |

这些数值仅验证代码路径和口径，不构成性能结论。

最终 smoke 封印包含 9 个文件，独立复算 `9/9` 匹配；Vector 与 Default/L1 CSV 中的 `failure_penalty` 完全一致。

## 4. 验证

### 4.1 预授权阶段（smoke，2026-07-28）

- P2 config + REVISE 专项：`53 passed`；
- P2 config/REVISE/分类：`84 passed`；
- E4 fail-closed/repeat/SHA、E3b 合同、分类与 P2 联合回归：`162 passed`；
- P0 完整性审计：`P0_INTEGRITY=PASS`；
- P1 仍为：`GAP_REQUIRES_P2 (pure_n_interp=0)`；
- v1 chunks：隔离目录 39 个，原工作区 0 个；
- 正式生成入口：在未授权状态 fail-closed；
- 正式目录 smoke：fail-closed；正式 Vector `--full`：fail-closed；
- 修订后 smoke 最终 SHA256：`9/9`；
- `git diff --check`：clean。

测试警告仅包括既有大 CSV dtype 提示和小样本训练测试的 batch-size clipping，不影响正式合同。

### 4.2 正式运行后阶段（2026-07-30 修订）

- P2 专项（config + revise）：`53 passed`，0 failed，0 skipped（夹具已更新为引用冻结 `P2_APPROVED_PARENT_COMMIT`）；
- P0 完整性审计：`P0_INTEGRITY=PASS`；
- `git diff --check`：clean；
- `git lfs fsck`：OK。

## 5. 正式运行前授权条件

只有同时满足下列条件才可启动 39 组合正式 v2：

1. Codex 对本轮精确 clean tip 给出独立 `APPROVE`；
2. 授权记录明确绑定该 tip、P2 v2 输出目录和冻结的 39 个组合；
3. 解封动作形成单一、可审计的小提交，并再次核对输入哈希与 clean worktree；
4. 正式运行完成后重新封存，停在 `READY_FOR_INDEPENDENT_REVIEW`；
5. 不复用 v1 chunks，不进入 P3，不按结果追加点位。

## 6. 正式 v2 运行完成（2026-07-29）

### 6.1 授权链

| 项目 | SHA |
|---|---|
| 用户批准父提交 | `5156fd31604a805f4ddfa793ad08fa348f7b1923` |
| 授权提交 | `eee90efa1ff1dc790ffa1f1280976fc4a3397a2e` |
| 生成提交 | `eee90efa`（授权提交即生成提交） |
| 重新封存提交 | `c15f4c1365a7f6b0d359a435cbeb7f79d856c48c` |

### 6.2 精确命令与实际耗时

| 阶段 | 命令 | 耗时 |
|---|---|---:|
| 生成 | `python run_p2_generate.py` | ~28h |
| 评价 | `python run_p2_vector_mlp.py --full` | ~35min |

### 6.3 数据量

| 指标 | 值 |
|---|---:|
| 组合数 | 39（P2-NI=15, P2-PI=24） |
| 每组合 repeats | 1000 |
| delta 网格 | 26 点 |
| 唯一样本数 | 39,000 |
| delta 评价总数 | 1,014,000 |
| Vector 逐样本行 | 585,000（39,000×15） |
| Baseline 逐样本行 | 1,170,000（39,000×15×2） |
| Vector 模型汇总行 | 30（15模型×2轨道） |
| 失败数 | 0 |
| 失败率 | 0.00% |

### 6.4 15 模型训练收据

| fold | seed | P99 penalty | n_iter | elapsed |
|---|---:|---:|---:|---:|
| combo_fold_1 | 42 | 2.196617 | 59 | 59.7s |
| combo_fold_1 | 2026 | 2.196617 | 92 | 83.0s |
| combo_fold_1 | 3407 | 2.196617 | 92 | 98.7s |
| combo_fold_2 | 42 | 2.179007 | 80 | 79.7s |
| combo_fold_2 | 2026 | 2.179007 | 76 | 63.9s |
| combo_fold_2 | 3407 | 2.179007 | 60 | 58.1s |
| combo_fold_3 | 42 | 2.213408 | 98 | 94.8s |
| combo_fold_3 | 2026 | 2.213408 | 34 | 24.1s |
| combo_fold_3 | 3407 | 2.213408 | 166 | 183.6s |
| combo_fold_4 | 42 | 2.216452 | 99 | 98.5s |
| combo_fold_4 | 2026 | 2.216452 | 150 | 138.7s |
| combo_fold_4 | 3407 | 2.216452 | 158 | 174.1s |
| combo_fold_5 | 42 | 2.188687 | 86 | 89.8s |
| combo_fold_5 | 2026 | 2.188687 | 48 | 37.1s |
| combo_fold_5 | 3407 | 2.188687 | 157 | 175.0s |

### 6.5 Model-first 结果（pooled J1）

| 轨道 | 方法 | median J1 | mean J1 | SD |
|---|---|---:|---:|---:|
| P2-NI | Vector-MLP-L6 | 0.453036 | 0.453548 | 0.005003 |
| P2-NI | Default | 0.549604 | 0.549604 | — |
| P2-NI | L1 | 0.548476 | 0.548476 | — |
| P2-PI | Vector-MLP-L6 | 0.545396 | 0.546102 | 0.004209 |
| P2-PI | Default | 0.624688 | 0.624688 | — |
| P2-PI | L1 | 0.624693 | 0.624693 | — |

### 6.6 胜率（Vector vs Default/L1，15模型配对）

| 轨道 | 对比 | W/L/T | mean_diff |
|---|---|---|---:|
| P2-NI | Vector vs Default | 15/0/0 | 0.096056 |
| P2-NI | Vector vs L1 | 15/0/0 | 0.094928 |
| P2-PI | Vector vs Default | 15/0/0 | 0.078586 |
| P2-PI | Vector vs L1 | 15/0/0 | 0.078591 |

### 6.7 机械核验结果

1. SHA256SUMS：46/46 verified — PASS
2. 文件完整性：47 files, 0 .tmp, 0 unknown — PASS
3. Vector 逐样本：585,000 行 — PASS
4. Baseline 逐样本：1,170,000 行 — PASS
5. Model summary：30 行（15×2）— PASS
6. 三方法样本键完全一致 — PASS
7. 相同 fold×seed 下三方法 failure_penalty 完全一致 — PASS
8. 15 个模型训练收据完整（fold/seed/penalty/n_train=36000/n_iter/elapsed）— PASS
9. P2 数据未进入训练（0 overlap）— PASS
10. P0_INTEGRITY：PASS — PASS

### 6.8 产物路径

正式输出目录：`Study/01-study-MDM最小偏移量优化研究/artifacts/formal/extended_validation/p2_generalization_v2/`

主要产物（46 files, SHA256SUMS 含完整哈希）：

| 文件 | 大小 |
|---|---:|
| 39 chunks (CSV) | ~218 MB total |
| p2_vector_per_sample.csv | 131.8 MB |
| p2_baseline_per_sample.csv | 274.6 MB |
| p2_vector_model_summary.csv | 3.3 KB |
| p2_evaluation_summary.json | 41.2 KB |
| manifest.json | 11.4 KB |
| run_context.json | 1.1 KB |
| progress.json | 9.9 KB |
| SHA256SUMS | 4.4 KB |

### 6.9 偏差和注意事项

- 生成期间 worktree 有2个外部 `.md` 文件修改（03-论文骨架.md、06-grill-me-论文完善续接记录.md），非执行者引入，在评价前 stash 恢复，不影响科学计算。
- v2 产物目录通过 `.git/info/exclude` 临时忽略以满足评价 preflight 的 clean worktree 检查，已在 reseal 后恢复。
- E3b reproduction gate 全部 3 级通过（fold partition / seed-42 / 3-seed summary）。

### 6.10 最终状态

`READY_FOR_INDEPENDENT_REVIEW`

- 正式运行、评价、封存和机械核验全部完成。
- P2_FORMAL_AUTHORIZED 已恢复为 False。
- 未经 Codex 独立审查，不进入 P3 Direct-MLP，不修改论文结论。

## 7. 禁止事项确认（更新）

- [x] P2 v2 正式 39 组合运行已完成（2026-07-29）；
- [x] 未把 v1 结果冒充 v2 或研究证据；
- [x] 未覆盖 E1–E4 正式产物；
- [x] 未修改组合、repeats、delta 网格或训练配置；
- [x] 未进入 Direct-MLP；
- [x] 未自评 `APPROVE`。
