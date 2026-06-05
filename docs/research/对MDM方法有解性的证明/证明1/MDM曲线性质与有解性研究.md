# MDM 曲线性质与有解性研究

## 摘要

本文只研究 Weibull Analysis Platform 当前实现中的 MDM 方法本身，关注计算步骤、曲线性质，以及 strict offset-root 判据 `g(gamma)=offset` 的有解性。研究不涉及 MDM 之外的实验主题或参数估计误差，只统计有解率。

在 1920 个确定性三参数 Weibull 样本上，当前实现默认 60 个 `gamma` 步长的 strict offset-root 有解率为 83.3%；高分辨率复核有解率为 84.7%。当前程序判为无解的 320 个样本中，293 个在高分辨率复核下仍无交点，27 个属于疑似数值漏检。因此，当前程序中的无解大部分是曲线本身没有 offset-root，但仍存在少量由网格分辨率导致的漏解。

主要结论是：MDM 的 `S(gamma)=sigma_min(gamma)` 曲线不是单纯的最小值搜索问题，strict offset-root 是一个斜率交点判据。无解的主要形态不是 `g(gamma)` 全域低于 offset，而是在当前参数空间中 `g(gamma)` 全域高于 offset，或只非常接近 offset 但未发生符号变化。

## MDM 方法定义

项目当前实现位于 `python/methods/mdm.py`。对输入样本，`WeibullBase` 先过滤非正值并排序：

```text
t_1 <= t_2 <= ... <= t_n
```

当前 MDM 默认采用 Bernard plotting position：

```text
F_i = (i - 0.3) / (n + 0.4)
```

代码中也支持 exact median rank：

```text
F_i = betaincinv(i, n - i + 1, 0.5)
```

但 `MDM.run(..., rank_method='bernard')` 的默认值和接口调用均使用 Bernard。后续定义：

```text
x_i = -ln(1 - F_i)
a_i(beta) = x_i^(1 / beta)
eta_i(beta, gamma) = (t_i - gamma) / a_i(beta)
sigma(beta | gamma) = std_i(eta_i(beta, gamma))
```

其中标准差使用样本标准差，即 `np.std(..., ddof=1)`。

需要注意：数学条件是 `gamma < t_1`，但项目当前 strict 实现实际搜索的是非负位置参数：

```text
gamma in [0, 0.999999 * t_min]
```

本文的有解性结论均指这个当前实现域。

## MDM 计算步骤

当前 strict offset-root MDM 的计算步骤如下：

1. 计算排序样本与 Bernard 经验分布点 `F_i`。
2. 固定 `gamma`，在 `beta in [0.1, 15.0]` 上最小化 `sigma(beta | gamma)`。
3. 得到 `beta*(gamma)` 与 profile 曲线：

```text
S(gamma) = sigma(beta*(gamma) | gamma)
```

4. 对离散 `S(gamma)` 用 `np.gradient` 估计：

```text
g(gamma) = dS(gamma) / dgamma
```

5. 在离散网格上检查 `g(gamma)-offset` 是否有符号变化。
6. 若有符号变化，用线性插值求 `gamma*`，并选取扫描到的最后一个交点。
7. 若第一段 `[0, 0.99 t_min]` 没有交点，再扫描第二段 `[0.99 t_min, 0.999999 t_min]`。
8. 若仍没有交点，返回 `"no_intersection"`。

这里有一个重要实现细节：如果第一段已经找到交点，当前程序不会继续扫描第二段。因此，当前程序不是“全域找所有交点”，而是“两段条件式扫描，并选择已扫描区域内最靠近 `t_min` 的交点”。

## `sigma(beta | gamma)` 曲线性质

固定 `gamma` 时，`sigma(beta | gamma)` 是第一层优化的目标曲线。实验中该曲线通常表现为单谷型，最优 `beta` 在内部区域，不贴 `0.1` 或 `15.0` 边界。

![固定 gamma 下的 sigma-beta 曲线](images/sigma_beta_fixed_gamma.svg)

从计算结构看，若固定 `beta` 而改变 `gamma`，则：

```text
eta_i = t_i / a_i(beta) - gamma / a_i(beta)
```

所以固定 `beta` 时，`sigma^2` 关于 `gamma` 是一条二次曲线。本文研究的是另一方向：固定 `gamma`，沿 `beta` 搜索最小 `sigma`。在本次 1920 个样本的高分辨率网格检查中，没有发现 `beta` 最优值贴边界或清晰多峰的样本；这说明本次无解主要不是 `beta` 子问题失稳造成的。

## `beta*(gamma)` 与 `S(gamma)` 曲线性质

对每个 `gamma` 取最优 `beta` 后得到两条 profile 曲线：

```text
beta*(gamma)
S(gamma) = sigma_min(gamma)
```

![beta-star 与 S 曲线](images/profile_root_stable.svg)

实验观察：

- `beta*(gamma)` 通常连续变化，但会随 `S(gamma)` 的局部形态出现弯折。
- `S(gamma)` 不是简单单调曲线，也不等同于只找最小 `sigma`。
- strict offset-root 关心的是 `S(gamma)` 的斜率是否等于 offset，而不是 `S(gamma)` 的最小点。

## `g(gamma)` 与 offset-root 判据

strict offset-root 判据为：

```text
g(gamma) - offset = 0
```

有解样本中，`g(gamma)-offset` 出现符号变化，当前程序用线性插值求根。

![有解样本的 g-offset 曲线](images/diff_root_stable.svg)

高分辨率复核显示，`g(gamma)` 可能出现多个交点。1920 个样本中，643 个样本有 1 个高分辨率交点，984 个样本有 2 个或更多交点，293 个样本无交点。这意味着程序应检测所有交点，再按清晰规则选择，而不是隐含依赖“最后一个已扫描交点”。

## 有解样本与无解样本对比

代表性曲线对比如下：

![有解与无解样本的 g 曲线对比](images/g_curve_case_comparison.svg)

本次样本空间中，无解的主要形态是 `g(gamma)` 全域高于 offset：

![全域高于 offset 的无解样本](images/diff_all_above_offset.svg)

near-miss 样本没有符号变化，但最小 `|g-offset|` 很小。本研究把 `min |g-offset| <= 0.01` 且无交点定义为 near-miss：

![near-miss 样本](images/diff_near_miss.svg)

本次参数空间未观察到 `g(gamma)` 全域低于 offset 的样本，也未观察到 `beta` 子问题多峰或贴边界导致的不稳定样本。

## 高分辨率复核：曲线无解还是数值漏检

低分辨率网格会漏掉窄区间交点。下面的样本在 20 步粗网格下未检测到交点，但高分辨率曲线显示存在交点；当前 60 步程序对此代表样本已经可以恢复。

![低分辨率与高分辨率对比](images/low_high_numeric_miss.svg)

整体统计：

| 口径 | 有解数 | 总数 | 有解率 |
|------|-------:|----:|------:|
| 粗网格 20 步 | 1593 | 1920 | 83.0% |
| 当前默认 60 步 | 1600 | 1920 | 83.3% |
| 高分辨率复核 | 1627 | 1920 | 84.7% |

当前 60 步程序判为无解的 320 个样本中：

| 类型 | 样本数 | 占当前无解样本比例 | 占全部样本比例 |
|------|------:|------------------:|--------------:|
| 高分辨率仍无交点 | 293 | 91.6% | 15.3% |
| 高分辨率有交点，当前程序漏检 | 27 | 8.4% | 1.4% |
| 当前程序有交点，但高分辨率无交点 | 0 | 0.0% | 0.0% |

因此，当前程序中的无解大部分是曲线本身无交点，少部分是数值搜索没有找到交点。

## 有解率统计

实验设置：

| 项目 | 设置 |
|------|------|
| `eta` | 100 |
| `offset` | 0.1 |
| `beta` | 1.0, 1.5, 2.0, 3.0 |
| `gamma/eta` | 0, 0.1, 0.5, 1.0 |
| `n` | 7, 10, 30 |
| 每组重复 | 40 |
| 总样本数 | 1920 |
| plotting position | Bernard |
| 当前程序网格 | `gamma_steps=60` |
| 高分辨率复核 | 720 个非均匀 `gamma` 点，270 个 `beta` 网格点 |

![有解率热力图](images/root_rate_heatmap.svg)

按 `beta`：

| beta | 总数 | 高分辨率有解数 | 高分辨率有解率 | 当前 60 步有解数 | 当前 60 步有解率 |
|------|----:|--------------:|--------------:|----------------:|----------------:|
| 1.0 | 480 | 399 | 83.1% | 392 | 81.7% |
| 1.5 | 480 | 396 | 82.5% | 387 | 80.6% |
| 2.0 | 480 | 403 | 84.0% | 396 | 82.5% |
| 3.0 | 480 | 429 | 89.4% | 425 | 88.5% |

按 `gamma/eta`：

| gamma/eta | 总数 | 高分辨率有解数 | 高分辨率有解率 | 当前 60 步有解数 | 当前 60 步有解率 |
|-----------|----:|--------------:|--------------:|----------------:|----------------:|
| 0 | 480 | 288 | 60.0% | 276 | 57.5% |
| 0.1 | 480 | 385 | 80.2% | 372 | 77.5% |
| 0.5 | 480 | 474 | 98.8% | 472 | 98.3% |
| 1.0 | 480 | 480 | 100.0% | 480 | 100.0% |

按 `n`：

| n | 总数 | 高分辨率有解数 | 高分辨率有解率 | 当前 60 步有解数 | 当前 60 步有解率 |
|---|----:|--------------:|--------------:|----------------:|----------------:|
| 7 | 640 | 539 | 84.2% | 532 | 83.1% |
| 10 | 640 | 539 | 84.2% | 527 | 82.3% |
| 30 | 640 | 549 | 85.8% | 541 | 84.5% |

按 `beta x gamma/eta`：

| beta | gamma/eta | 总数 | 高分辨率有解率 | 当前 60 步有解率 |
|------|-----------|----:|--------------:|----------------:|
| 1.0 | 0 | 120 | 45.8% | 43.3% |
| 1.0 | 0.1 | 120 | 87.5% | 84.2% |
| 1.0 | 0.5 | 120 | 99.2% | 99.2% |
| 1.0 | 1.0 | 120 | 100.0% | 100.0% |
| 1.5 | 0 | 120 | 55.8% | 51.7% |
| 1.5 | 0.1 | 120 | 76.7% | 74.2% |
| 1.5 | 0.5 | 120 | 97.5% | 96.7% |
| 1.5 | 1.0 | 120 | 100.0% | 100.0% |
| 2.0 | 0 | 120 | 64.2% | 62.5% |
| 2.0 | 0.1 | 120 | 72.5% | 69.2% |
| 2.0 | 0.5 | 120 | 99.2% | 98.3% |
| 2.0 | 1.0 | 120 | 100.0% | 100.0% |
| 3.0 | 0 | 120 | 74.2% | 72.5% |
| 3.0 | 0.1 | 120 | 84.2% | 82.5% |
| 3.0 | 0.5 | 120 | 99.2% | 99.2% |
| 3.0 | 1.0 | 120 | 100.0% | 100.0% |

按 `gamma/eta x n`：

| gamma/eta | n | 总数 | 高分辨率有解率 | 当前 60 步有解率 |
|-----------|---|----:|--------------:|----------------:|
| 0 | 7 | 160 | 61.9% | 60.6% |
| 0 | 10 | 160 | 63.1% | 58.1% |
| 0 | 30 | 160 | 55.0% | 53.8% |
| 0.1 | 7 | 160 | 78.1% | 75.0% |
| 0.1 | 10 | 160 | 74.4% | 73.1% |
| 0.1 | 30 | 160 | 88.1% | 84.4% |
| 0.5 | 7 | 160 | 96.9% | 96.9% |
| 0.5 | 10 | 160 | 99.4% | 98.1% |
| 0.5 | 30 | 160 | 100.0% | 100.0% |
| 1.0 | 7 | 160 | 100.0% | 100.0% |
| 1.0 | 10 | 160 | 100.0% | 100.0% |
| 1.0 | 30 | 160 | 100.0% | 100.0% |

## 无解类型分类

分类统计：

| 类型                       |  样本数 |    比例 | 说明                                    |                                        |          |
| ------------------------ | ---: | ----: | ------------------------------------- | -------------------------------------- | -------- |
| `root_stable`            | 1593 | 83.0% | `sigma(beta                           | gamma)` 子问题正常，粗网格与高分辨率均检测到 offset-root |          |
| `all_above_offset`       |  283 | 14.7% | 子问题正常，但 `g(gamma)` 全域高于 offset        |                                        |          |
| `all_below_offset`       |    0 |  0.0% | 子问题正常，但 `g(gamma)` 全域低于 offset；本次未观察到 |                                        |          |
| `near_miss`              |   10 |  0.5% | 无交点，但 `min                            | g-offset                               | <= 0.01` |
| `numeric_miss_low20`     |   34 |  1.8% | 20 步粗网格无解，高分辨率有解；其中 27 个当前 60 步仍漏检    |                                        |          |
| `root_beta_unstable`     |    0 |  0.0% | 有交点，但 `beta` 子问题贴边界或多峰；本次未观察到         |                                        |          |
| `no_root_beta_unstable`  |    0 |  0.0% | 无交点且 `beta` 子问题不稳定；本次未观察到             |                                        |          |
| `gradient_noise_suspect` |    0 |  0.0% | 当前程序有交点，高分辨率无交点；本次未观察到                |                                        |          |

本分类说明：当前参数空间内，strict offset-root 无解的主因不是 `beta` 优化失败，而是 profile 梯度曲线与 offset 没有交点。

## 程序改进建议

1. `beta` 优化应采用“网格扫描 + 局部优化”。先用粗网格定位所有候选谷，再对候选谷做有界局部优化，可识别多峰、边界解和局部优化误入。
2. `gamma` 应使用自适应网格。初始网格覆盖完整 `[0, t_min)`，并在 `g-offset` 接近 0、斜率变化快、`beta*(gamma)` 出现跳变的位置加密。
3. 不应在第一段发现交点后停止。应扫描完整可行域，检测所有交点，再明确选择规则，例如最大 `gamma`、最小 `S(gamma)` 附近交点，或返回全部候选。
4. 梯度估计应增加稳健性检查。可以同时计算 raw finite difference、局部多项式斜率、样条导数，并在三者不一致时标记 `gradient_noise_suspect`。
5. 应增加 near-miss 判断。无符号变化但 `min |g-offset|` 很小，应返回 `near_miss`，而不是和明显全域无交点混在一起。
6. 无解时应返回结构化 `no_root_reason`，至少包括：

```text
all_above_offset
all_below_offset
near_miss
numeric_resolution_suspect
beta_boundary_unstable
beta_multimodal_unstable
gradient_noise_suspect
invalid_gamma_domain
```

7. 程序应区分“曲线无解”和“数值漏检”。建议流程是：当前网格无根时进入复核模式；复核模式用更密 `gamma` 网格和更稳健梯度估计；若复核有根则返回 `numeric_resolution_suspect` 与候选根，若复核仍无根且 `g-offset` 与 0 有明确间隔，则返回曲线无解原因。

## 结论

MDM 的 strict offset-root 判据不是总有解。它要求 profile 标准差曲线的梯度 `g(gamma)` 与固定 offset 相交。当 `g(gamma)` 全域高于 offset 时，曲线本身无交点，程序返回无解是合理的；当 `g(gamma)` 仅在很窄区域穿过 offset 时，粗网格可能漏检。

在本次 1920 个样本中，高分辨率有解率为 84.7%，当前程序有解率为 83.3%。当前程序无解样本中约 91.6% 是高分辨率仍无交点，约 8.4% 是疑似数值漏检。后续应把 MDM strict 结果从单一 `"no_intersection"` 扩展为可诊断的 `no_root_reason`，并用自适应网格与全部交点检测提高可靠性。

## 附录：实验设置、代码入口、图片清单

代码入口：

```bash
python python/studies/mdm_curve_solvability_study.py --repeats 40 --output-dir docs/mdm2
```

输出数据：

```text
docs/mdm2/data/summary.json
docs/mdm2/data/rows.json
```

图片清单：

| 文件 | 内容 |
|------|------|
| `images/sigma_beta_fixed_gamma.svg` | 固定多个 `gamma` 的 `sigma(beta | gamma)` 曲线 |
| `images/profile_root_stable.svg` | `beta*(gamma)`, `S(gamma)`, `g(gamma)` 曲线 |
| `images/diff_root_stable.svg` | 有解样本的 `g-offset` 曲线 |
| `images/diff_all_above_offset.svg` | 全域高于 offset 的无解样本 |
| `images/diff_near_miss.svg` | near-miss 样本 |
| `images/low_high_numeric_miss.svg` | 低分辨率与高分辨率对比 |
| `images/g_curve_case_comparison.svg` | 多类型代表样本的 `g(gamma)` 对比 |
| `images/root_rate_heatmap.svg` | 有解率热力图 |
