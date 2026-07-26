# Study01 G5–G7 REVISE v5 — Codex 执行报告

**日期**：2026-07-26

**分支**：`study01xu`

**执行基线**：`4f507442`

**已验证实现提交**：`abff029c`

**状态**：`READY_FOR_INDEPENDENT_REVIEW`

> 本报告所在提交不做自引用；交付时的最终远端 tip 以 Git 记录和交付消息为准。Codex 本轮承担执行者角色，不对自己的修改签发独立 APPROVE。

## 提交链

| 提交 | 内容 |
|---|---|
| `a180f5d1` | 将稿件审计改为可导入、fail-closed 的唯一生产路径；修正 claims CSV；增加真实破坏型负向测试 |
| `abff029c` | 同步图表索引、投稿清单、04/05 状态文档和 08 更新日志 |

## 修正结果

1. `auto_audit.py` 公开 `audit_manuscript(...) -> list[str]`，CLI 与测试共用同一实现。
2. `claims-to-data.csv` 必须恰好包含 `C001–C033`：
   - 缺失、重复或额外 claim 均失败；
   - `source_file` 和 `source_field` 与注册表逐项匹配；
   - `expected_value` 与正式 artifact 重算值逐项比较；
   - C027–C033 已纳入实际重算，包括 n=20 配对计数、support-set violation、正式网格和 Study1.5 路径。
3. 10 项专项测试全部走生产审计入口：
   - 当前完整包正向通过；
   - 篡改 C002；
   - 删除 C001；
   - 添加 C999；
   - 篡改 source path；
   - figure-index 写入“需生成”；
   - submission checklist 写入“S1-S8需生成”；
   - 删除 Reference [7]；
   - 写入错误 beta 计数；
   - 删除 Figure 7 引用。
4. 图表索引和投稿清单确认 Figures 1–9、Supplementary Figures S1–S8 已生成；引用状态和数据/代码声明同步。
5. `04-待复核清单.md`、`05-投稿进度控制.md` 与 `08-更新日志.md` 统一为：
   - G4–G7 技术工作闭环；
   - 图件为数据与视觉逻辑可复现，不承诺跨环境字节一致；
   - 尚未投稿，仍待目标期刊、作者、通讯作者、基金和 CRediT 决策。

## 验证

```text
python -m pytest \
  python/tests/test_study01_real_data_gate.py \
  python/tests/test_study01_p6_frozen_contract.py \
  python/tests/test_study01_p7_pipeline.py \
  python/tests/test_study01_p8a_controls.py \
  python/tests/test_g7_audit_negative.py -q

163 passed, 0 failed, 0 skipped
```

```text
python Study/01-study-MDM最小偏移量优化研究/manuscript/audit/auto_audit.py
ALL AUDIT CHECKS PASSED
```

- P8a `SHA256SUMS_p8a`：5/5 文件逐项匹配。
- `python -m py_compile`：审计脚本与负向测试通过。
- `git diff --check a52c3023..HEAD`：通过。
- 正式实验未重跑，P8a 五个正式文件未修改。

## 边界与待办

- 本轮只修复审计可信度和稿件状态一致性，没有新增或重跑实验。
- 本轮不替用户决定目标期刊、作者顺序、通讯作者、基金或 CRediT。
- 下一步应由独立审查者基于实际 diff、163 项测试和生产审计结果给出 `APPROVE / REVISE / BLOCK`。
