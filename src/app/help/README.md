# 软件信息维护

[建设规范](../../../docs/建设规范/06-软件信息.md)说明页面目标。本文件说明各页读取什么，改内容时从对应来源更新。

## 帮助页数据来源

| 页面 | 来源与读取范围 |
|------|----------------|
| `/help/manual/about`、`/help/manual/workflow` | [概览](manual/about/page.tsx)和[工作流](manual/workflow/page.tsx)组织入口与任务。模块职责见[模块说明](../../../06-模块.md)，操作步骤见[用户手册](../../../07-用户手册.md) |
| `/help/manual/features` | [用户手册「功能详解」](../../../07-用户手册.md#功能详解)中的公开正文。引用块用作内部注解，公开链接使用站内绝对路由或完整 URL |
| `/help/changelog` | [方法建设状态](../../../05-状态.md#生成缓存)的 YAML，经生成缓存供页面读取 |
| `/help/changelog/todos` | [目标与待办](../../../04-目标与待办.md)中的日期、任务标题和固定字段 |
| `/help/changelog/versions` | [更新日志](../../../08-更新日志.md)。默认展示近期版本，较早版本可展开。首个版本标题也提供应用版本号 |
| `/help/metrics` | [指标规范](metrics/metrics-spec.ts) |
| `/help/charts` | [图表范式](charts/charts-spec.ts)和[实际使用实例](charts/chart-registry.ts)。修改指标或图表的公共规则见[开发规则](../../../02-规则.md#5-指标与图表规范) |

## 修改后检查

运行 `npm run check:docs`，再查看受影响的页面。检查脚本与页面共用[手册解析](../../lib/markdown.ts)和[更新计划解析](../../lib/update-plan.ts)。检查范围和对应测试见[脚本维护说明](../../../scripts/README.md)。
