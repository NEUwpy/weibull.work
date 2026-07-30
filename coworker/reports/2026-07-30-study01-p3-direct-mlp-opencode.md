# Study01 P3 Direct-MLP 执行报告

> 执行者：Hermes (OpenCode role)
> 日期：2026-07-30（v2 修订）
> 分支：`study01-p3-direct-mlp`
> 基线：`18026cb6e72aec2bdccac0cdee0941f285f45e8e`
> 最终 tip：（见提交链）
> 状态：`READY_FOR_INDEPENDENT_REVIEW`

## 1. 提交链

| Commit | 职责 |
|--------|------|
| `b7ece3a1` | P3 初始实现：config + Direct-MLP + 六方法比较 + 测试 |
| `18026cb6` | P3 初始执行报告 + smoke 脚本 |
| (v2 修订) | 目标表示修正、六方法完整集成、逐模型公平合同、36000 样本 smoke、重复实现删除、生产路径回归测试 |

## 2. v2 修订内容

### 目标表示修正

**问题**：v1 的 Direct-MLP 训练目标为原始 (beta, eta, gamma)，输出经 softplus 变换后无法精确还原原始参数（softplus(2.0) ≈ 2.127 ≠ 2.0）。

**修正**：训练目标改为逆 softplus 编码（beta/eta 用 inverse_softplus，gamma 用 identity），使得完美网络预测经过解码后严格还原原始参数：
```
softplus(inverse_softplus(beta)) = beta  (精确恒等)
```

### 六方法完整集成

**问题**：v1 的 `run_fair_comparison` 接受 `vector_models` 参数但不使用；smoke 只运行 5 种方法。

**修正**：Vector-MLP 预测通过 `vector_models` 参数传入，生成非空 MDM-Vector-MLP 结果。smoke 精确断言 `len(methods) == 6` 和方法集合完全匹配。

### 逐模型公平合同

**问题**：v1 默认 `failure_penalty=0.0`，无逐 fold 惩罚。

**修正**：每个 fold×seed 使用该训练 fold 的 P99 损失作为失败惩罚。所有六种方法使用相同样本和相同惩罚。`apply_failure_contract` 断言 penalty > 0。

### 重复实现删除

**问题**：v1 内联了 `_fit_zscore_params_inline` 和 `_build_X_inline`。

**修正**：直接调用 `e4._fit_zscore_params` 和 `e4._build_X_from_samples`。

### 生产路径回归测试

新增 `TestFairComparisonProduction` 测试类，测试 `run_fair_comparison` 完整驱动器：
- 精确六方法断言
- 样本键篡改检测
- 缺失模型检测
- 空向量模型检测

## 3. 复用审计

### 直接复用（无修改）

| 来源模块 | 复用内容 |
|----------|----------|
| `run_E4_formal_validation.py` | `_fit_zscore_params`、`_build_X_from_samples`、MLP 超参数、`compute_sample_features`、`get_combo_split` |
| `python/studies/common/sample.py` | `generate_sample()` |
| `python/studies/common/runner.py` | `run_method()` |
| `python/methods/` | MLE/LSE/WMLE/MDM 估计器 |

### 新写的薄脚本

| 文件 | 职责 |
|------|------|
| `p3_config.py` | 冻结配置 |
| `run_p3_direct_mlp.py` | Direct-MLP 训练/预测/评价 |
| `run_p3_fair_compare.py` | 六方法比较编排器 |
| `test_p3_direct_mlp.py` | 38 项 fail-closed 测试 |
| `run_p3_smoke.py` | 仓库外 smoke 脚本 |

### 未提取新公共函数，未建设新通用流水线

## 4. 冻结的 Direct-MLP 配置

```json
{
  "output_transform": "softplus_softplus_relu",
  "target_encoding": "inverse_softplus_for_positive_params",
  "hidden_layers": [256, 128, 64],
  "seeds": [42, 2026, 3407],
  "forbidden_input_fields": 20 项
}
```

## 5. 测试和 smoke 收据

### 单元测试

- P3 专项：38 passed, 0 failed, 0 skipped

### Smoke 收据

- 训练：1 fold (9 train combos × 4000 repeats = 36,000 samples), seed=42
- 评价：9 test combos × 50 repeats = 450 test samples
- 六种方法全部运行：MDM-Default / MDM-Vector-MLP / Direct-MLP / MLE / LSE / WMLE
- 逐 fold P99 失败惩罚已应用
- 样本键按 method×fold×seed 验证通过

**smoke 结果不构成正式实验结论。Vector-MLP 使用模拟预测（P4 将加载真实 P2 v2 冻结模型）。**

## 6. 是否使用唯一一次配置修正

**否。** 逆 softplus 编码配置在首次尝试中训练正常。

## 7. 声明

- 未运行 P4 formal 六方法比较
- 未修改任何 P2 或其他封存正式产物
- 未修改论文结果和结论
- 未进入工程分位点或真实案例
- 未自评 APPROVE
