# Study01 P3 Direct-MLP 执行报告

> 执行者：Hermes (OpenCode role)
> 日期：2026-07-30（v4 修订）
> 分支：`study01-p3-direct-mlp`
> 基线：`523620e632dc881cdc5457b72f621bdac35df673`
> 最终 tip：（见提交链）
> 状态：`READY_FOR_INDEPENDENT_REVIEW`

## 1. 提交链

| Commit | 职责 |
|--------|------|
| `a706d47e` | 尺度等变 Direct-MLP + J1相容损失 + 真实Vector-MLP + 26点P99惩罚 |
| `85587159` | v3执行报告 + 真实Vector-MLP smoke脚本 |
| `523620e6` | smoke合并修复（SAMPLE_KEYS） |
| `759f62ed` | 完整尺度不变输入 + 共享J1损失 + 严格schema + 显式异常 |

## 2. v4 修订内容

### T1: 完整尺度不变输入（不再只是解码器等变）

**问题**：v3 只在解码器层面实现等变——网络仍然消费带绝对尺度的 z-scored 特征。z-score 只中心化，不消除尺度。

**修正**：在 train-fold z-score 之前，将 9 个尺度依赖特征（x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s）除以可观测尺度锚 x_bar，变为无量纲比率。n、CV、g1、g2 保持原定义。x_bar 本身变为 1.0，网络无法看到绝对尺度。

**完整尺度不变性证明**：样本乘 c → 所有尺度列乘 c → x_bar 乘 c → 比率不变 → 网络输入完全一致 → 网络输出完全一致 → beta_hat 不变，eta_ratio 不变 → eta_hat = eta_ratio × (c × x_bar) = c × 原 eta_hat ✓

**测试**：生产特征路径测试验证同一样本乘任意正数 c 后送入网络的 13 维输入完全一致。端到端模型预测满足 beta 不变、eta/gamma 乘 c。测试使用真实训练模型，不只调用 decode_output。

### T2: 统一训练和验证 J1 损失

**修正**：提取共享 `j1_loss_torch(beta_hat, beta_true, eta_hat, eta_true, gamma_hat, gamma_true)` 函数。训练和验证都调用它。gamma 误差分母为 eta_true（不是 gamma_true，不是 eta_hat）。

**测试**：gamma=0 时损失有限。非单位 eta 时损失正确。`j1_loss_torch` 与 `compute_param_loss` 数值一致。

### T3: Vector-MLP 评价严格真值 schema

**修正**：prediction DataFrame 必须包含 beta、eta、gamma、gamma_over_eta、n、repeat_id、三个估计值和失败字段。缺少任何真参数或键时 `validate_vector_pred_schema` 抛出 `SchemaError`。删除所有使用 eta_hat/gamma_hat/default 值代替真值的回退逻辑。

**测试**：缺少 eta 或 gamma 时 `SchemaError`。空 DataFrame 时 `SchemaError`。

### T4: 显式异常替代 assert

**修正**：自定义异常类 `SchemaError`、`CoverageError`、`PenaltyError`。生产合同中的 26 个 loss 列检查、failure_penalty>0、完整六方法覆盖、fold penalty 和关键 schema 全部使用显式异常。

**测试**：检查明确异常类型（`pytest.raises(direct.PenaltyError)` 等），不依赖 python assert。

## 3. 冻结的 Direct-MLP 配置

```
input_scale_invariance: divide_by_x_bar_before_zscore
scale_dependent_features: [x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s]
scale_invariant_features: [n, CV, g1, g2]
output_transform: scale_equivariant_softplus_softplus_relu
scale_anchor: x_bar
target_encoding: inverse_softplus_scale_equivariant
training_loss: J1_compatible_relative_error
training_framework: pytorch
hidden_layers: (256, 128, 64)
seeds: [42, 2026, 3407]
```

## 4. 测试和 smoke 收据

### 单元测试

- P3 专项：46 passed, 0 failed, 0 skipped
- 全部 Study01 测试：130 passed, 0 failed
- P0_INTEGRITY：PASS
- git diff --check：clean

### Smoke 收据

- 训练规模：36,000 样本（36 combos × 1000 repeats）
- Direct-MLP：PyTorch 256-128-64，seed=42
- Vector-MLP：E4 生产代码训练，seed=42
- 六种方法全部运行
- 完整模型尺度等变验证通过（网络输入缩放后一致，预测满足 beta不变/eta/gamma×c）
- 逐 fold P99 惩罚（26 点）已应用

**smoke 结果不构成正式实验结论。**

## 5. 是否使用唯一一次配置修正

**否。** 完整尺度不变 + J1 相容损失配置在首次尝试中训练正常。

## 6. 声明

- 未运行 P4 formal 六方法比较
- 未修改任何 P2 或其他封存正式产物
- 未修改论文结果和结论
- 未进入工程分位点或真实案例
- 未自评 APPROVE
- Vector-MLP 使用 E4 生产训练代码，非随机噪声 placeholder
- 完整模型尺度等变已验证（不只是解码器等变）
