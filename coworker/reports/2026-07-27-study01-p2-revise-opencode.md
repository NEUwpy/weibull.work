# Study01 P2 REVISE 执行报告

> 执行者：OpenCode
> 日期：2026-07-27
> 分支：study01xu
> 审查基线：5ebda36150002d6fdb27901f40ac853b9a927def
> 最终 tip：0312201b
> 状态：READY_FOR_P2_RERUN_AUTHORIZATION

## 修订链

| Commit | 职责 |
|--------|------|
| `5ebda361` | P2 v1 执行报告（包含 INVALID chunks） |
| `0cfdaf83` | **fix**: J1 公式修正（删除 /3）+ seed 改用 SHA256 替代 hash() |
| `0312201b` | **feat**: Vector-MLP 评价实现 + 21 fail-closed 测试 |

## P2 v1 失效说明

39 个 chunks（位于 `artifacts/formal/extended_validation/p2_generalization/chunks/`，未 git tracked）标记为 **INVALID_NONDETERMINISTIC_SEED**。

原因：生成脚本 `run_p2_generate.py` 使用 Python `hash()` 函数派生种子，在独立 Python 进程中不可复现。已通过 SHA256 修正。

## 修正内容

### 1. J1 公式

**修正前**（错误）：
```
J1 = sqrt(mean((e_b^2 + e_e^2 + e_g^2) / 3))
```
**修正后**（与协议 §4.1 一致）：
```
J1 = sqrt(mean(e_b^2 + e_e^2 + e_g^2))
e_b = (beta_hat - beta) / beta
e_e = (eta_hat - eta) / eta
e_g = (gamma_hat - gamma) / eta
```
新增 `compute_j1()` 和 `compute_j1_squared()` 函数于 `p2_config.py`。

### 2. Seed namespace

**修正前**：`seed = hash("study01_p2_v1:...") % (2**31)`
**修正后**：`seed = int.from_bytes(SHA256("study01_p2_v1:...").digest()[:4], "big")`

跨进程确定性已在测试中验证。

### 3. Vector-MLP P2 评价

新增 `code/run_p2_vector_mlp.py`：
- 使用 E3b/E4d 完全相同的生产路径：
  - 13 个部署可观测统计量
  - full-combo 5 fold 划分（repeat_id mod 5）
  - 3 seeds [42, 2026, 3407]
  - train-fold-only scaler（StandardScaler）
  - P99 failure penalty
  - MLP(256,128,64), max_iter=300, batch=256, alpha=1e-4, lr=1e-3
  - 26-dim risk curve target
- P2 数据仅用于 forward pass（不进入 scaler/training/seed）
- 支持 `--smoke`（1 combo）和 `--full`（39 combos）

### 4. fail-closed 测试（21 new）

- J1 公式验证（perfect, beta/eta/gamma only, pooled, no-/3）
- Seed 确定性（same/different input, int type, no hash() in source）
- 失败处理合同（status field, penalty 存在）
- Model-first vs pooled 区分
- P2 config pinned（15/24/39/39000/1014000）

## 测试结果

```
P2 config tests: 20 passed
P2 REVISE tests: 21 passed
Classification tests: 31 passed
P0_INTEGRITY: PASS
compileall: OK
git diff --check: clean
```

## P2 正式重跑命令

```bash
# 1. 生成（39 combos, ~12h）
python code/run_p2_generate.py

# 2. Default/L1 评价（~30s）
python code/run_p2_evaluate.py

# 3. Vector-MLP 评价（smoke: ~10min, full: ~3h）
python code/run_p2_vector_mlp.py --full
```

## 预计成本

| 阶段 | combos | 预计时间 |
|------|--------|----------|
| P2 生成 | 39 | ~12h |
| Default/L1 评价 | 39 | ~30s |
| Vector-MLP 训练+评价 | 39 | ~3h |

## 禁止事项确认

- [x] 未启动第二次正式全量运行
- [x] P2 v1 chunks 保持未跟踪状态（未删除、未覆盖、未冒充正式产物）
- [x] 未修改 main
- [x] 未覆盖 E1–E4 正式产物
- [x] 未根据结果增删组合
- [x] 未自评 APPROVE
