# Protocols 目录

| 协议 | 定位 |
|---|---|
| `09-PQ-同分布主协议冻结.md` | **当前论文主协议**；repeat-stratified 同分布 P/Q 对照 |
| `10-目标敏感度矩阵研究合同.md` | 独立机制增量；默认排除于论文，等待用户结果准入 |
| `01-PQ-冻结协议.md` | 旧 v3/r4 gamma-holdout 协议；仅作 OOD 补充追溯 |

机器可读配置在 `../configs/`。当前科学口径以 `../docs/研究说明.md` 为准。

## 新研究准入规则

新问题不得改写已冻结协议，统一另建 `10-<研究简称>-研究合同.md`，并按以下状态推进：

```text
DRAFT → USER APPROVED / FROZEN → RUNNING → COMPLETE / NOT PAPER EVIDENCE → USER ADMITTED
```

实验完成和论文准入必须分开提交。新结果默认 `EXCLUDED`；只有用户查看独立结果报告并明确批准后，
才允许修改论文正文、补充材料、论文图和证据白名单。
