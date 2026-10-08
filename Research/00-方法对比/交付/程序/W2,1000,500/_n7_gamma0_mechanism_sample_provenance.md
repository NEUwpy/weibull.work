# n=7 gamma=0 mechanism figure provenance

- Source workbook: `D:\weibull\docs\临时任务-W2-1000-3000-MDM偏移量估计-20260825\260826位置参数500\估计结果表.xlsx`
- Source sheet: `生成样本_n7`
- Source range: `A2:H51` (50 real generated samples)
- Generator distribution: `W(2,1000,500)`
- MDM offset: `0.10`
- Flag rule: `g(0) > 0.10`, giving samples 4 and 32.
- Control rule: among non-flagged samples, choose the closest `t_(1)` to each flagged sample, giving 8 for 4 and 18 for 32.
- Figure curves: direct recomputation from the source samples; no schematic or simulated replacement data.

- Sample 4: t1=558.368053715, gap12=413.581579021, beta*(0)=2.64163218316, Cov(a,q)=-13.1080364057, g(0)=0.108059056392.
- Sample 8: t1=560.57254507, gap12=114.265110405, beta*(0)=2.72793521339, Cov(a,q)=-3.28436814986, g(0)=0.0285148301985.
- Sample 32: t1=630.365033182, gap12=480.861111782, beta*(0)=3.03385806331, Cov(a,q)=-15.7575228731, g(0)=0.110145182288.
- Sample 18: t1=634.37833523, gap12=116.322937166, beta*(0)=2.9065880248, Cov(a,q)=7.4185559227, g(0)=-0.0392760669878.
