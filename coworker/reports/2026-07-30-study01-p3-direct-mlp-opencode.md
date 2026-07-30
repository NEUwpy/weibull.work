# Study01 P3 Direct-MLP 执行报告

> 执行者：Hermes (OpenCode role)
> 日期：2026-07-30
> 分支：`study01-p3-direct-mlp`
> 基线：`ef710e7327446169bfce6cef1da85635f2828a27` (main)
> 最终 tip：（见提交链）
> 状态：`READY_FOR_INDEPENDENT_REVIEW`

## 1. 提交链

| Commit | 职责 |
|--------|------|
| `b7ece3a1` | P3 Direct-MLP config + 实现 + 六方法比较 + 测试 |

## 2. 复用了什么、提取了什么、新写了什么

### 直接复用（无修改）

| 来源模块 | 复用内容 |
|----------|----------|
| `run_E4_formal_validation.py` | MLP 超参数、`compute_sample_features`、`get_combo_split`、`_train_mlp` 模式 |
| `python/studies/common/sample.py` | `generate_sample()` |
| `python/studies/common/runner.py` | `run_method()` 统一估计器调用 |
| `python/methods/` | MLE/LSE/WMLE/MDM 原始估计器 |

### 新写的薄脚本

| 文件 | 职责 | 行数 |
|------|------|------|
| `p3_config.py` | 冻结 Direct-MLP 配置（输出变换、禁止字段、超参数引用） | ~120 |
| `run_p3_direct_mlp.py` | Direct-MLP 训练、预测、评价（复用 E4 z-score/build_X） | ~270 |
| `run_p3_fair_compare.py` | 六方法公平比较编排器 | ~230 |
| `test_p3_direct_mlp.py` | 27 项 fail-closed 测试 | ~310 |
| `run_p3_smoke.py` | 仓库外 smoke 脚本 | ~170 |

### 未提取新公共函数

所有公共逻辑已在 E4/common 模块中存在，直接导入使用，无需提取。

## 3. 冻结的 Direct-MLP 配置

```json
{
  "output_transform": "softplus_softplus_relu",
  "output_constraints": {"beta_gt_0": true, "eta_gt_0": true, "gamma_ge_0": true},
  "target_params": ["beta", "eta", "gamma"],
  "target_scaler": "StandardScaler",
  "hidden_layers": [256, 128, 64],
  "seeds": [42, 2026, 3407],
  "forbidden_input_fields": 20 项
}
```

配置哈希：`c0b539196121793f...`

## 4. 测试和 smoke 收据

### 单元测试

```
P3 专项 (test_p3_direct_mlp.py): 27 passed, 0 failed, 0 skipped
联合回归 (全 tests/):             111 passed, 0 failed, 0 skipped
```

### Smoke 收据

- 训练：1 fold (combo 1.5/0.1/7), seed=42, 10 samples, 22 iters
- 评价：combo 2.0/0.5/10, 10 samples
- 输出约束：PASS (beta>0, eta>0, gamma>=0)
- 样本键对齐：PASS
- 六方法（含 Direct-MLP）全部运行成功
- 失败样本保留（MLE 在 n=10 有 4 次失败，已按合同计入）
- 输出路径：`D:\weibull-local-artifacts\study01-p3-smoke\`

**smoke 结果不构成正式实验结论。**

## 5. 是否使用唯一一次配置修正

**否。** 初始配置（softplus/softplus/relu 输出变换、StandardScaler on Y、256-128-64 骨干）训练正常，无需修正。

## 6. 未执行项、偏差和剩余风险

### 未执行

- P4 正式六方法比较（须单独授权）
- Vector-MLP 集成到 fair_compare（需要加载 P2 v2 冻结模型，留给 P4）
- 正式产物生成和封存

### 偏差

- smoke 使用极小数据集（10 samples/combo），MLP batch_size 被裁剪。这不影响正式运行（正式训练有 36000 samples/fold）。
- Vector-MLP 尚未集成到 `run_fair_comparison` 的 Direct-MLP 分支中。P4 需要补充加载 P2 v2 冻结模型的逻辑。

### 剩余风险

- Direct-MLP 在正式规模（36000 samples × 3 params）下的收敛行为需在 P4 验证。
- 传统方法在极端小样本（n=7）下的失败率可能较高，需要公平的失败合同。

## 7. 声明

- 未运行 P4 formal 六方法比较
- 未修改任何 P2 或其他封存正式产物
- 未修改论文结果和结论
- 未进入工程分位点或真实案例
- 未新建平行规划文档
- 未自评 APPROVE
