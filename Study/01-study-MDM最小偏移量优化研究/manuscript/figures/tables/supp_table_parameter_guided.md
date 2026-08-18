**补充表：参数引导（plug-in）偏移量选择——12 个单步变体与迭代诊断**

参数引导选择先用 MDM-0.1 或 WMLE 得到初步参数估计，再把估计当作真参数去查询 L3–L5 对应的条件均值损失曲线并选择偏移量。48,000 样本、repeat-id 五折 cross-fit；$J_1=\sqrt{\mathrm{mean}\,\ell_i}$（三参数损失）。J1 差与 95% 区间来自固定种子（2026）配对 repeat-block bootstrap；差值为正表示 PG 比 Default（$J_1=0.6304$）更差。

| 初始估计量 | 选择族 | 映射 | 阶段 | PG J1 | PG−Default J1 差 | 95% CI 下限 | 95% CI 上限 | 更差 repeat 块比例 |
|---|---|---|---|---:|---:|---:|---:|---:|
| MDM-0.1 | PG-beta | interpolated | one_step | 0.6707 | +0.0403 | 0.0372 | 0.0429 | 97.3% |
| MDM-0.1 | PG-beta | interpolated | terminal | 0.6897 | +0.0593 | 0.0561 | 0.0620 | 98.0% |
| MDM-0.1 | PG-beta | nearest_grid | one_step | 0.6740 | +0.0435 | 0.0404 | 0.0462 | 97.3% |
| MDM-0.1 | PG-beta | nearest_grid | terminal | 0.6866 | +0.0562 | 0.0530 | 0.0589 | 97.7% |
| MDM-0.1 | PG-beta-n | interpolated | one_step | 0.6722 | +0.0417 | 0.0390 | 0.0441 | 97.0% |
| MDM-0.1 | PG-beta-n | interpolated | terminal | 0.7039 | +0.0735 | 0.0701 | 0.0765 | 98.0% |
| MDM-0.1 | PG-beta-n | nearest_grid | one_step | 0.6732 | +0.0428 | 0.0400 | 0.0452 | 97.7% |
| MDM-0.1 | PG-beta-n | nearest_grid | terminal | 0.7011 | +0.0707 | 0.0675 | 0.0738 | 98.0% |
| MDM-0.1 | PG-full | interpolated | one_step | 0.6827 | +0.0523 | 0.0492 | 0.0549 | 98.0% |
| MDM-0.1 | PG-full | interpolated | terminal | 0.7415 | +0.1110 | 0.1074 | 0.1145 | 99.7% |
| MDM-0.1 | PG-full | nearest_grid | one_step | 0.6836 | +0.0531 | 0.0499 | 0.0558 | 97.7% |
| MDM-0.1 | PG-full | nearest_grid | terminal | 0.7320 | +0.1016 | 0.0982 | 0.1050 | 99.7% |
| WMLE | PG-beta | interpolated | one_step | 0.6507 | +0.0203 | 0.0186 | 0.0219 | 95.3% |
| WMLE | PG-beta | interpolated | terminal | 0.6910 | +0.0606 | 0.0574 | 0.0634 | 98.0% |
| WMLE | PG-beta | nearest_grid | one_step | 0.6530 | +0.0226 | 0.0209 | 0.0243 | 95.3% |
| WMLE | PG-beta | nearest_grid | terminal | 0.6898 | +0.0594 | 0.0561 | 0.0622 | 98.0% |
| WMLE | PG-beta-n | interpolated | one_step | 0.6557 | +0.0253 | 0.0233 | 0.0271 | 96.7% |
| WMLE | PG-beta-n | interpolated | terminal | 0.7076 | +0.0772 | 0.0739 | 0.0803 | 98.3% |
| WMLE | PG-beta-n | nearest_grid | one_step | 0.6573 | +0.0269 | 0.0249 | 0.0287 | 96.3% |
| WMLE | PG-beta-n | nearest_grid | terminal | 0.7068 | +0.0764 | 0.0731 | 0.0794 | 98.3% |
| WMLE | PG-full | interpolated | one_step | 0.6943 | +0.0639 | 0.0598 | 0.0680 | 98.7% |
| WMLE | PG-full | interpolated | terminal | 0.7669 | +0.1365 | 0.1323 | 0.1405 | 99.7% |
| WMLE | PG-full | nearest_grid | one_step | 0.6940 | +0.0636 | 0.0597 | 0.0674 | 99.0% |
| WMLE | PG-full | nearest_grid | terminal | 0.7606 | +0.1302 | 0.1263 | 0.1342 | 99.7% |

**补充表（续）：最佳单步规则（WMLE / PG-beta / interpolated）按真 $\beta$ 分层。** 仅在 $\beta=1.5$ 优于 Default；$\beta=2.0$–5.0 均更差。

| 真 $\beta$ | $n$ | PG J1 | Default J1 | J1 差 |
|---|---:|---:|---:|---:|
| 1.5 | 6000 | 0.5373 | 0.5477 | -0.0104 |
| 2 | 6000 | 0.5310 | 0.5205 | +0.0105 |
| 2.5 | 6000 | 0.5698 | 0.5319 | +0.0380 |
| 3 | 6000 | 0.6107 | 0.5724 | +0.0384 |
| 3.5 | 6000 | 0.6511 | 0.6136 | +0.0374 |
| 4 | 6000 | 0.7088 | 0.6812 | +0.0276 |
| 4.5 | 6000 | 0.7466 | 0.7305 | +0.0161 |
| 5 | 6000 | 0.7970 | 0.7898 | +0.0072 |

注：邻近 $\beta$ 网格单元正确率与初估误差—损失关系只与该机制解释一致，不作为唯一因果机制的证明；连续插值同样失败，误差分层可能与真 $\beta$ 混杂。
