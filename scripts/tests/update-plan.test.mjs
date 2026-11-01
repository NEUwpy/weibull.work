import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { parseUpdatePlan } = loadServerModule('src/lib/update-plan.ts')

test('confirmed dates descend while same-day registration order and task states stay intact', () => {
  const plan = parseUpdatePlan(`> **更新时间**: 2026-11-01
## 2026-10-30
### 旧任务
- 状态：已完成
- 问题：旧问题
## 2026-11-01
### MLE 流程
- 状态：待开始
- 重点：是
- 问题：步骤未对应实际代码
- 完成条件：逐步核对公式与源码
### 数据浏览
- 状态：进行中
- 依赖：先接通批次索引
## 2026-10-31
### 中间任务
- 状态：已取消
`)
  assert.deepEqual(Array.from(plan.groups, group => group.date), ['2026-11-01', '2026-10-31', '2026-10-30'])
  assert.deepEqual(Array.from(plan.groups[0].tasks, task => task.title), ['MLE 流程', '数据浏览'])
  assert.equal(plan.groups[0].tasks[0].status, '待开始')
  assert.equal(plan.groups[0].tasks[0].focus, true)
  assert.equal(plan.groups[0].tasks[0].acceptance, '逐步核对公式与源码')
  assert.equal(plan.groups[0].tasks[1].dependency, '先接通批次索引')
  assert.equal(plan.groups[2].tasks[0].status, '已完成')
  assert.equal(plan.updatedAt, '2026-11-01')
})

test('internal notes, examples, and undated history never become newly confirmed tasks', () => {
  const plan = parseUpdatePlan(`<!--
## 2026-12-01
### 注释里的任务
-->
## 2026-11-01
### 真实任务
- 状态：待开始
> - 状态：进行中
> ### 内部标题
> - 问题：内部说明
\`\`\`
## 2026-12-02
### 格式示例
\`\`\`
## 历史待梳理
- 统一图表
- 校对案例
## 其他说明
### 未确认任务
- 问题：不能继承上一组日期
## 2026-02-30
### 无效日期
`)
  assert.equal(plan.groups.length, 1)
  assert.equal(plan.groups[0].tasks.length, 1)
  assert.equal(plan.groups[0].tasks[0].title, '真实任务')
  assert.equal(plan.groups[0].tasks[0].status, '待开始')
  assert.equal(plan.groups[0].tasks[0].problem, '')
  assert.deepEqual(Array.from(plan.backlog), ['统一图表', '校对案例'])
})
