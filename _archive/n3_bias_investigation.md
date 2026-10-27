# N=3 偏差异常现象研究方案

## 问题描述

在 MDM 方法示例1的热力图中，观察到 n=3（样本量最小）时，某些参数组合下的偏移（偏差）反而比 n=5 或其他值更小，这看起来不合常理。

## 初步数据分析结论

### 1. 整体统计
通过 Python 分析 `public/studies/mdm/demo1/data.csv`：

| 样本量 | β 绝对偏差均值 | β 偏差均值 | 无解率 |
|--------|---------------|-----------|--------|
| n=3    | 2.72          | -1.83     | 10.79% |
| n=5    | 2.38          | -1.49     | 9.53%  |
| n=7    | 2.15          | -1.32     | 8.94%  |
| n=10   | 1.94          | -1.13     | 8.25%  |
| n=20   | 1.55          | -0.91     | 5.66%  |
| n=30   | 1.37          | -0.80     | 4.67%  |

**结论**：从整体来看，n=3 的偏差（绝对值）是最大的，n=30 最小，符合统计学规律。

### 2. 交叉分析
检查 75 种参数组合中，各样本量成为"偏差最小"的次数：
- n=30: 75 次（全部）
- n=3: 0 次

**结论**：没有任何一个参数组合下 n=3 的平均偏差是最小的。

## 可能的原因分析

### 假设1：热力图显示的是原始偏差（有符号），而非绝对偏差

热力图可能显示 `bias_beta_mean`（可正可负），而非 `abs(bias_beta_mean)`。

- 如果热力图颜色代表"偏离真实值的程度"，正值表示高估，负值表示低估
- n=3 时偏差可能更接近 0（因为偏差在 -1.83 附近）
- n=30 时偏差可能在 +0.04 附近（虽然绝对值更小，但可能颜色更"红"）

**验证方法**：检查热力图的 color scale 是否以 0 为中心对称。

### 假设2：幸存者偏差（Selection Bias）

n=3 时无解率最高（10.79%），可能存在幸存者偏差：
- 无解的样本被排除
- 只有"幸运"的样本（偶然估计较准）被保留
- 导致保留的样本看起来偏差较小

**验证方法**：
1. 分析无解样本的特征
2. 比较 n=3 和 n=30 的有效样本分布

### 假设3：热力图显示维度的影响

热力图可能选择了特定维度进行展示，导致某些视角下 n=3 看起来更好。

**验证方法**：检查 `displayDimensions` 配置。

## 研究计划

### 第一步：验证热力图数据来源

运行以下脚本检查热力图实际显示的数据：

```python
import pandas as pd
import numpy as np

df = pd.read_csv('public/studies/mdm/demo1/data.csv')
df_valid = df[df['est_beta'].notna()].copy()

# 按参数组合分组，计算平均偏差
grouped = df_valid.groupby(['beta_true', 'eta_true', 'offset_value', 'sample_size']).agg({
    'bias_beta': 'mean',
    'est_beta': ['mean', 'count']
}).reset_index()

# 找出 n=3 的偏差接近 0 的情况
n3_data = grouped[grouped['sample_size'] == 3]
n3_data['abs_bias'] = np.abs(n3_data['bias_beta'])

print("n=3 偏差最小的10个参数组合:")
print(n3_data.nsmallest(10, 'abs_bias'))
```

### 第二步：分析无解样本的影响

```python
# 分析无解样本的特征
df_no_solution = df[df['est_beta'].isna()]

print("无解样本分布:")
print(df_no_solution.groupby(['beta_true', 'eta_true', 'offset_value', 'sample_size']).size())
```

### 第三步：检查热力图组件配置

检查 `MDMStudyViewer.tsx` 中的 `displayDimensions` 设置，确认热力图的行/列维度。

### 第四步：可视化对比

创建对比图表，同时显示：
1. 平均偏差（有符号）
2. 绝对偏差
3. 无解率

## 行动建议

1. **确认观察位置**：在哪个页面/组件观察到的现象？
2. **截图确认**：提供具体的截图，标注哪个单元格显示"n=3 偏移小"
3. **运行验证脚本**：在本地运行上述 Python 脚本，确认数据分析结果

## 相关文件

- 数据文件: `public/studies/mdm/demo1/data.csv`
- 组件文件: `src/components/methods/mdm/studies/MDMStudyViewer.tsx`
- 热力图组件: `src/components/shared/charts/HeatmapChart.tsx`
- 配置文件: `public/studies/mdm/demo1/config.md`
