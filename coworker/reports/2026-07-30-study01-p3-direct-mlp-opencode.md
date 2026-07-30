# Study01 P3 Direct-MLP 执行报告

> 执行者：Hermes (OpenCode role)
> 日期：2026-07-30（v3 修订）
> 分支：`study01-p3-direct-mlp`
> 基线：`f401864d05ace98a18429c502362c29a72487f36`
> 最终 tip：（见提交链）
> 状态：`READY_FOR_INDEPENDENT_REVIEW`

## 1. 提交链

| Commit | 职责 |
|--------|------|
| `a706d47e` | 尺度等变 Direct-MLP + J1 相容损失 + 真实 Vector-MLP + 26 点 P99 惩罚 |

## 2. v3 修订内容

### T1: 尺度等变目标表示

**问题**：主网格 eta 恒为 1，直接把 eta=1 作为监督目标无法泛化到非单位 eta。

**修正**：网络预测三个无量纲量：
- `beta_hat` = softplus(z_beta) — 形状参数，与尺度无关
- `eta_ratio` = softplus(z_eta_ratio) — eta/x_bar，无量纲尺度比
- `goe_hat` = relu(z_goe) — gamma/eta，无量纲形状比

解码：eta_hat = eta_ratio × x_bar，gamma_hat = goe_hat × eta_hat

尺度等变性证明：样本缩放 c → x_bar 缩放 c → eta_hat 缩放 c → gamma_hat 缩放 c → beta_hat 不变。

### T2: J1 相容训练损失

**问题**：sklearn MLPRegressor 的 StandardScaler-MSE 不等于 J1。

**修正**：改用 PyTorch 实现 256-128-64 MLP，训练损失为解码后参数空间的相对误差平方和：
```
L = ((beta_hat - beta)/beta)² + ((eta_hat - eta)/eta)² + ((gamma_hat - gamma)/eta)²
```
这与 J1²/N 精确一致。梯度通过 autograd 自动计算。

### T3: 真实 Vector-MLP 路径

**问题**：v2 的 smoke 使用随机噪声 placeholder。

**修正**：smoke 通过 E4 生产代码训练 Vector-MLP，选择 delta 后联接 MDM 参数估计获得 (beta_hat, eta_hat, gamma_hat)。

### T4: 六方法 × fold × seed 覆盖验证

**修正**：`run_fair_comparison` 逐 fold×seed 检查所有六种方法存在。检测 "基线 3 seed、学习方法 1 seed" 的覆盖不匹配。

### T5: P99 失败惩罚（26 点全部）

**问题**：v2 只使用 loss_d0.1 计算 P99。

**修正**：使用全部 26 个 delta 点的损失计算 P99。无有效损失时 fail-closed（ValueError），不回退到 3.0。

## 3. 冻结的 Direct-MLP 配置

```
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

- P3 专项：36 passed, 0 failed, 0 skipped
- 全部 Study01 测试：120 passed, 0 failed
- P0_INTEGRITY：PASS
- git diff --check：clean

### Smoke 收据

- 训练规模：36,000 样本（36 combos × 1000 repeats）
- Direct-MLP：PyTorch 256-128-64，seed=42
- Vector-MLP：E4 生产代码训练，seed=42
- 六种方法全部运行：MDM-Default / MDM-Vector-MLP / Direct-MLP / MLE / LSE / WMLE
- 逐 fold P99 惩罚（26 点）已应用
- 样本键按 method×fold×seed 验证

**smoke 结果不构成正式实验结论。**

## 5. 是否使用唯一一次配置修正

**否。** 尺度等变 + J1 相容损失配置在首次尝试中训练正常。

## 6. 声明

- 未运行 P4 formal 六方法比较
- 未修改任何 P2 或其他封存正式产物
- 未修改论文结果和结论
- 未进入工程分位点或真实案例
- 未自评 APPROVE
- Vector-MLP 使用 E4 生产训练代码，非随机噪声 placeholder
