# 传统估计方法横向比较

> 成熟度：`NEEDS_REVIEW`
> 关系角色：`INDEPENDENT`

## 研究问题

在固定真参数和共享 Monte Carlo 样本的条件下，MLE、WMLE、LSE、LRE 等传统三参数 Weibull 估计方法的误差、失败行为和尺度性质有何差异？

现存执行包位于 `Study01-当前横向比较/`。它不属于 Study01 已封存 formal 证据，也不能在独立复核前承担论文结论。

## 已知问题

1. 现有设计仅覆盖固定条件，不能外推为全面方法排名。
2. 尺度等价、失败惩罚与部分基线测试仍需复核。
3. 既有 manifest 记录 7 个输出：当前 run log 字节哈希匹配，6 个 CSV 的 LF 字节哈希不匹配；把当前 LF 确定性恢复为 CRLF 后，6 项与历史 SHA 精确匹配。

因此，本次迁移保持当前 Git blobs 和原 manifest 原样，不重封，不声称当前 byte-level seal 自洽。若继续研究，应另开版本、修复运行入口、重新冻结协议并生成新 manifest，不能覆盖本历史包。

## 阅读入口

- 研究边界：`Study01-当前横向比较/01-研究目标与边界.md`
- 执行合同：`Study01-当前横向比较/02-执行合同.md`
- 原执行说明：`Study01-当前横向比较/README.md`
- 既有 manifest：`Study01-当前横向比较/artifacts/manifest.json`

迁移记录见 `../RELOCATION.json`。
