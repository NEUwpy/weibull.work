# AI 协作协议

> 本文档定义在本项目中使用多个 AI 助手结对开发时的分工、交付物和审批流程。
> 目标是吸收 `shadcn/improve` 的 advisor / executor 思路：高能力模型负责理解、计划与审查，执行型模型负责按计划改代码。

---

## 1. 适用场景

当用户要求 Hermes 使用 mimo 写代码，并要求 Codex 负责检核、审批或把关时，启用本协议。

本协议也适用于任何类似模式：

- 一个 AI 负责实现
- 另一个 AI 负责计划、审查、验证
- 用户保留最终合并、提交、上线决策权

---

## 2. 角色分工

### 2.1 用户

- 决定需求是否成立、范围是否扩大、是否合并或上线。
- 对 `APPROVE / REVISE / BLOCK` 结论做最终取舍。

### 2.2 Codex：Advisor / Reviewer

Codex 负责理解项目、制定边界、检核结果。

职责：

- 阅读项目入口文档：`AGENTS.md`、`README.md`、`02-规则.md`，按需阅读专题规范。
- 在实现前给出可执行计划：范围、涉及文件、验收命令、停止条件。
- 审查 Hermes/mimo 的改动：读取 diff、复跑必要验证、核对项目架构规则。
- 输出审批结论：`APPROVE`、`REVISE` 或 `BLOCK`。

限制：

- 在“审批 Hermes 工作”模式下，Codex 默认只审查，不直接修改 Hermes 的实现代码。
- 如需由 Codex 直接修复，必须由用户明确授权，或用户把当前任务切换成“Codex 实现”。

### 2.3 Hermes / mimo：Executor

Hermes 使用 mimo 负责执行计划并提交可审查的改动。

职责：

- 严格按计划修改代码。
- 不临时扩大范围，不顺手重构无关模块。
- 记录实际修改文件、验证命令和结果。
- 遇到计划外事实时停止并报告，而不是自行绕路。

---

## 3. 标准流程

### Step 1：计划

Codex 在实现前提供计划，至少包括：

- 目标
- 范围内文件
- 明确不碰的文件或目录
- 项目架构红线
- 验证命令
- STOP 条件

计划可以写在聊天中；复杂任务应写入 `plans/` 或 `docs/todo/` 下的独立 Markdown 文件。

### Step 2：执行

Hermes/mimo 按计划实现。

执行报告必须包含：

```markdown
## 执行报告

### 修改文件
- `path/to/file`

### 实现摘要
- ...

### 已运行验证
- `command`
- 结果：...

### 未运行验证
- `command`
- 原因：...

### 偏离计划之处
- 无 / 说明原因
```

### Step 3：审批

Codex 审查时必须至少检查：

- `git diff --stat`
- 具体 diff 是否只覆盖计划范围
- 是否违反 `02-规则.md` 的复用原则
- 是否违反前后端职责边界
- 是否更新必要文档或测试
- 是否运行并通过必要验证

审批结论必须使用以下三种之一：

```markdown
VERDICT: APPROVE
```

可以合并或进入下一步。

```markdown
VERDICT: REVISE
```

需要 Hermes/mimo 修改。必须列出具体文件、问题、期望修复。

```markdown
VERDICT: BLOCK
```

当前实现方向不应继续。必须说明阻塞原因和下一步建议。

---

## 4. 本项目架构红线

### 4.1 通用红线

- 禁止读取 `_archive/` 作为参考。
- 写新代码前必须先查 `02-规则.md`。
- 不重复造轮子；已有通用组件、指标函数、图表组件应优先复用。
- 不把硬编码数据写进 TS/JS 文件；数据应放在 `content/` 或 `public/`。
- 中文文件必须保持 UTF-8；必要时运行 `scripts/check-encoding.ps1`。

### 4.2 后端红线

- 统计推断、参数估计、蒙特卡洛模拟属于后端职责。
- `python/main.py` 是 API 层，不应继续堆叠复杂计算逻辑。
- 方法调用应优先走 `methods.registry.resolve_method()` 和 `studies.common.runner.run_method(...)`。
- 蒙特卡洛应优先走 `python/studies/common/simulation.py` 的共享入口。
- 新增方法应保持“一方法一实现文件”：`python/methods/{method}.py`。

### 4.3 前端红线

- 前端负责 UI、交互、图表渲染，不承担核心统计推断。
- 图表优先复用 `src/components/shared/charts/` 或已有方法专用图表。
- 指标计算优先复用 `src/lib/metrics.ts`，不要在组件里内联重复实现。
- 页面文案、说明文档遵循“表里分离”：用户可见内容与开发者内部注释分清。

---

## 5. 常用验证命令

根据改动范围选择，不要求每次全部运行。

### 编码检查

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-encoding.ps1
```

期望：输出 `Encoding check passed`。

### 后端测试

```powershell
uv run --with pytest --with scipy --with fastapi --with numpy --with pydantic --with pandas python -m pytest python\tests -q
```

期望：测试通过，无失败。

### 前端构建

```powershell
npm run build
```

期望：构建通过。

### Git 空白检查

```powershell
git diff --check
```

期望：无输出。

---

## 6. Codex 审批报告模板

```markdown
VERDICT: APPROVE | REVISE | BLOCK

### 范围核对
- 计划范围：符合 / 不符合
- 越界文件：无 / 列出

### 发现
- [P1/P2/P3] `file:line` 问题说明

### 验证
- `command`：通过 / 失败 / 未运行

### 结论
- 可以合并 / 需要返工 / 需要重新规划
```

严重程度：

- `P1`：会导致错误结果、崩溃、数据损坏或架构方向错误。
- `P2`：会造成维护风险、重复实现、边界混乱或测试缺口。
- `P3`：小问题、命名、文档、局部一致性。

---

## 7. 失败处理

如果 Hermes/mimo 的实现连续两轮 `REVISE` 后仍未达标，Codex 应停止继续小修小补，重新判断：

- 是否计划写得不够清楚？
- 是否任务需要拆分？
- 是否架构前提错误？
- 是否应由 Codex 接手关键修复？

此时应向用户给出新的建议，而不是继续要求 executor 盲改。
