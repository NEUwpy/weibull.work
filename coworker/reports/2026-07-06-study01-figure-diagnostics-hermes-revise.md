# Study/01 Figure Diagnostics Review Fixes — 执行报告

> Executor: hermes
> Date: 2026-07-06 (revise pass)
> Task: Fix 5 review findings from coworker reviewer
> Status: ✅ 全部完成

## 1. 执行概要

本次修复了上一轮 figure diagnostics 评审的 5 条意见：(1) 恢复 progress 文档；(2) 图编号按首次出现重排；(3) fig_l2_n_heterogeneity 改用 GridSpec；(4) 软化 Figure 1 caption 并修底部标签重叠；(5) mc_scan_raw.csv 缺失时的可复现性处理。

## 2. Required Fix Results

### Fix 1: 恢复两个 progress 文档 ✅
- `Study/01-study-MDM最小偏移量优化研究/progress-offset-hierarchy-realignment.md` — 已从 `_archive/` 复制回原路径（4655 bytes）
- `Study/01-study-MDM最小偏移量优化研究/progress-revision.md` — 已从 `_archive/` 复制回原路径（2434 bytes）
- `_archive/` 下的副本保留未删（按指示只报告状态）：`_archive/progress-offset-hierarchy-realignment.md` 和 `_archive/progress-revision.md` 均仍在

### Fix 2: 图编号修复 ✅
问题：Figure 5 出现在 Figure 1 之前，Figure 7 出现在 Figure 4 之前。
方案：按首次出现顺序全局重编号（1→7 严格递增）。

| 旧编号 | 新编号 | 文件 | 首次出现 |
|---|---|---|---|
| 图5 (δ机制) | **图1** | Ch3 L53 | Ch3 §1.4 |
| 图1 (framework) | **图2** | Ch3 L77 | Ch3 §2.1 |
| 图2 (δ-risk) | **图3** | Ch4 L7 | Ch4 §1 |
| 图6 (L2/n) | **图4** | Ch4 L52 | Ch4 §2 |
| 图3 (ladder) | **图5** | Ch5 L9 | Ch5 §1 |
| 图7 (β×n heatmap) | **图6** | Ch5 L60 | Ch5 §3 |
| 图4 (L6) | **图7** | Ch5 L80 | Ch5 §4 |

验证（程序化扫描全文 `**图 N**` / `![Figure N` / `**Figure N.**` 所有出现）：
```
首次出现顺序: [1, 2, 3, 4, 5, 6, 7]
✓ 编号严格递增
```
后向引用也一致：Ch4 §3 的"图3(b)"正确（图3 首次出现在 §1）；Ch4 小结"图4"正确。

### Fix 3: 重绘 fig_l2_n_heterogeneity（GridSpec）✅
问题：Panel B 用了 `fig.add_axes([left, bottom, w, h])` 绝对坐标，有重叠风险。
修复：改用 `matplotlib.gridspec.GridSpec(3, 2, width_ratios=[1, 1.1])`。
- 左列 `gs[:, 0]`：Panel A（pooled by n，1 个大子图）
- 右列 `gs[0, 1]` / `gs[1, 1]` / `gs[2, 1]`：Panel B 的 n=7/10/20 三个小子图，纵向排列
- Panel B 整体标题用 `fig.text()` 放在右侧顶部，不占子图空间
- `hspace=0.45, wspace=0.25` 保证子图间距
程序化验证：右半三段（n=7/10/20）密度均匀（7.5%-9.2%），无空白段，无重叠。

### Fix 4: 软化 Figure 1 + 修底部标签重叠 ✅
caption 修订：
- 旧："偏移量 δ 对 MDM 搜索判据的影响（概念示意）...曲线形态为示意，不来自特定 MC 样本"
- 新："偏移量 δ 对 MDM 搜索判据的影响（有限样本下的概念示意）。黑色曲线为...**一种可能示意形态——实际形态因样本而异，本图仅用作几何说明，不代表所有样本的通用行为，也不来自特定 MC 重复**...**本图说明的是两种判据在概念上的几何差异，不构成对真实 γ 处梯度方向的断言**"

标题修订：
- 旧："How δ shifts the search criterion"
- 新："δ shifts the search criterion **(one possible finite-sample schematic, not a universal claim)**"

底部标签重叠修复：
- 旧：误差箭头 y 坐标用 `sigma_profile.min() - 0.025` 和 `- 0.075`，且 ylim 下界不限 → "large error" 文字可能贴边或被裁
- 新：显式设置 `ax.set_ylim(y_large_err - 0.02, sigma_max_val * 1.12)`，误差箭头文字用 `va="bottom"` 放在箭头上方，两箭头分层（y_small_err vs y_large_err，间隔 0.035）
程序化验证：底部 15% 区域内容密度 5.6%（有内容且在可见范围内），三色像素数（绿1957/橙2123/蓝2831）均正常。

### Fix 5: mc_scan_raw.csv 可复现性处理 ✅
新增 `ensure_mc_scan_raw()` 函数：
- 检查 `artifacts/formal/shared_data/mc_scan_raw.csv` 是否存在
- 若缺失，打印明确指令：
  ```
  ERROR: mc_scan_raw.csv not found at: <path>
  This file is excluded from git (too large). To rebuild it
  from the tracked chunks, run from the Study/01 directory:
    python code/generate_mc_data.py --merge-only
  Do NOT run the full generate_mc_data.py without --merge-only,
  as that would regenerate MC data (not needed for figures).
  ```
- 返回 False，调用方据此跳过 Fig B（Fig A/C/D 不依赖此文件，仍正常生成）
- 脚本不会自动运行 generate_mc_data.py

验证：临时重命名 mc_scan_raw.csv → 函数正确打印指令并返回 False → 文件恢复后正常。

## 3. Changed Files

### 修改
| 文件 | 改动 |
|------|------|
| `code/plot_fig_diagnostics.py` | 重写：GridSpec 布局(Fix3) + 软化caption/修ylim(Fix4) + ensure_mc_scan_raw()(Fix5) |
| `draft-Ch3-初稿.md` | 图5→图1, 图1→图2, Figure 1 caption 软化(Fix2+4) |
| `draft-Ch4-初稿.md` | 图2→图3, 图6→图4（含正文引用和小结）(Fix2) |
| `draft-Ch5-初稿.md` | 图3→图5, 图7→图6, 图4→图7 (Fix2) |

### 恢复（Fix1）
| 文件 | 操作 |
|------|------|
| `progress-offset-hierarchy-realignment.md` | 从 `_archive/` 复制回原路径 |
| `progress-revision.md` | 从 `_archive/` 复制回原路径 |

### 重新生成（12 文件，覆盖旧版）
| 文件 |
|------|
| `artifacts/formal/figures/fig_offset_mechanism.{svg,pdf,png}` |
| `artifacts/formal/figures/fig_l2_n_heterogeneity.{svg,pdf,png}` |
| `artifacts/formal/figures/fig_l4_beta_n_heatmap.{svg,pdf,png}` |
| `artifacts/formal/figures/fig_l5_heatmap.{svg,pdf,png}` |

## 4. Commands Run and Exact Results

```bash
# 1. 运行绘图脚本（4图×3格式=12文件）
cd "Study/01-study-MDM最小偏移量优化研究"
python code/plot_fig_diagnostics.py
# exit=0, 全部生成
```
关键 QA（与上一轮一致，确认数据未变）：
```
[Fig A] |error zero-grad|=0.352, |error offset|=0.042
[Fig B] Panel A δ* by n: {7→0.10, 10→0.10, 20→0.08}
        Panel B δ* by(n,β): n=7 β=1.5→0.30, β=5.0→0.02
[Fig C] β平均跨度: 0.373, n平均跨度: 0.080
[Fig D] L4→L5 mean improvement: 1.78%
```

```bash
# 2. 测试 mc_scan_raw.csv 缺失处理
mv .../mc_scan_raw.csv .../mc_scan_raw.csv.bak
python -c "from plot_fig_diagnostics import ensure_mc_scan_raw; print(ensure_mc_scan_raw())"
# 输出明确指令 + returned: False
mv .../mc_scan_raw.csv.bak .../mc_scan_raw.csv  # 恢复
```

```bash
# 3. git diff --check
git diff --check -- "Study/01-study-MDM最小偏移量优化研究"
# exit=0（仅 LF/CRLF 警告）
```

## 5. 视觉验证

vision API（image_url 参数）在当前 provider (newapi/glm-5.2) 下不兼容（API schema 错误），改用程序化视觉 QA：
- **fig_offset_mechanism**: 三色像素均存在（绿1957/橙2123/蓝2831），底部15%区域密度5.6%（误差标签在可见区域内），尺寸 1475×986
- **fig_l2_n_heterogeneity**: 左半(Panel A)密度3.9%，右半(Panel B)密度8.4%，右半三段(n=7/10/20)密度均匀(7.5%-9.2%)，无空白/重叠段，尺寸 2182×1034
- 投稿前建议人工目视复核（vision API 环境限制）

## 6. _archive 副本状态（按指示报告，未删除）

| 文件 | 状态 |
|------|------|
| `_archive/progress-offset-hierarchy-realignment.md` | 保留（4655 bytes, 2026-07-06 11:17） |
| `_archive/progress-revision.md` | 保留（2434 bytes, 2026-07-06 10:11） |

## 7. 约束遵守

- ✅ 未运行 generate_mc_data.py（含 --merge-only 也未运行，本任务不需要）
- ✅ 未修改正式实验数值（脚本只读 CSV）
- ✅ 未改 analyze_E1.py / analyze_E2.py
- ✅ 图编号严格按首次出现递增（1-7）
- ✅ Figure 1 caption 明确标注"one possible finite-sample schematic, not a universal claim"
- ✅ 未新增 scope（只修 5 条 review findings）
