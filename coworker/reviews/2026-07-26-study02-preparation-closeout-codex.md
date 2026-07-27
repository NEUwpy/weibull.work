# Study02 准备工作最终 Codex 审查

> 日期：2026-07-26
>
> 结论：**APPROVE**
>
> 边界：仅批准“准备工作已收口”，不授权或启动 formal，不启封或消费 test。

## 审查范围

- 基线：`origin/main` 的 `e3cb002cfa0f90407ce6320b2ba4540926287629`。
- 实现提交：`1bdd9906e87b53cd0cd1ad81bcfbb8ed8197a5a1`（R12 sealed accreditation 收口）。
- 文档提交：`46ad1623ee6d69cda9578f1ff1d1a8560664070d`（状态与启动门收口）。
- 本记录汇总 Codex 最终验收和独立 closeout oracle 的 `APPROVE` 结论。

## 结论依据

- 已形成统一、sealed-only 的 G3 生产入口；旧的逐模块 build/authorize 路径及 test consumer 均保持永久阻断。
- A-E1 的 stage1 → top4 → stage2 → winner retrain → F2/V → baseline → final aliases 被作为完整语义链校验；A-E3/A-E2 也按冻结候选域解析。
- 三个模块的 checkpoint、point evidence、selection trace、diagnostics 与提交 provenance 在发布 sealed bundle 前重新构建并交叉绑定。
- caller 不能注入 commit；真实生产路径要求 Study02 代码范围干净且 live `HEAD` 与 replay authority 一致。
- sealed genesis state 使用严格字段集、确定性绑定、精确整数计数器及规范 UTC `Z` 时间戳校验。
- 冻结协议、搜索空间、矩阵、指标、参数范围和选择规则未被改写；`02-A-实验协议.md` 只有“formal 运行前”到“formal test 启封前”的语义修正。

## 最终验证证据

- `validate-config`：通过。
- frozen protocol SHA-256：`f82e078051d760d7c9c11ece54b8fae7360c6db1aef3229a97b4fcd92ae01a11`。
- frozen search SHA-256：`abd6d17b1d2467e1253e0154adba0b6582a3feeb83ed889534ed4f6ab5e0ca13`。
- frozen matrix SHA-256：`fad701af2e2084bf7ce8f678d642410af58057b4ae33029c9150e50971fdf6b1`。
- real unmocked scoped-code/live-HEAD guard：在 `46ad162` 通过。
- Study02 相关 non-slow suite：`247 passed, 5 deselected`。
- clean-tree 生产边界攻击：`3 passed, 74 deselected`。
- 生产源码编译与 `git diff --check`：通过。
- slow 边界：5 项中 3 项通过；另外 2 项 heavy 用例未完成、未记作通过，且不属于冻结 closeout 门。

## 安全与研究边界

- 未生成授权，未执行 authorize/unseal，未启动或恢复 formal，未读取或消费 test。
- 现场无 lease、无活动 formal Python 进程、无 `C:\weibull-runs\study02` 仓外运行根目录、无新 approval/unseal/test 产物。
- 旧 r1/r2 保持永久 `blocked/aborted`，不得续跑或用作新证据。
- 19 个前置研究问题仍未回答；本次工作只证明执行与证据合同已准备好，不产生 Study02 研究结论。

## 后续唯一入口

后续若要开始研究，必须由用户另行明确授权一个全新的 A-E1 formal training/validation run，并在启动当时重新核验远端提交、磁盘、运行根目录和全部 sealed 前置条件。

在以上边界内，Study02 准备工作最终验收结论为 **APPROVE**，允许将本记录提交并把当前本地 `main` fast-forward 推送到 `origin/main`。
