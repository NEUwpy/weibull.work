# 第一轮六方法状态升级 Codex 审核

- 审核提交：`6bad77e`
- 结论：**REVISE**

## 已确认

- `05-状态.md` 仅升级本轮六个方法的已审核证据，没有建设其余 16 个方法或越级升级第二、三层；
- 生成缓存与权威状态源一致；
- 派生结果正确：MLE、WMLE、LSE、MM、LRE 为 `layer1_complete`，MDM 保持 `layer2_complete`；
- `calculatorEnabled=true` 的方法集合恰为 `mle, wmle, lse, mdm, lre, mm`；
- 所有新增证据路径存在；
- 192 项 Python 测试、18 项状态测试、6 项计算器状态测试、TypeScript 检查均通过。

## 唯一阻塞：MLE 论文 stable_id 错误

`05-状态.md:14` 及生成缓存把 Hirose (1996) 写为：

`IEEE TDEI 9(3): 303-310 (1996)`

实际书目信息为：

`IEEE Transactions on Dielectrics and Electrical Insulation 3(1): 43-55 (1996)`

DOI：`10.1109/94.485513`。

`done` 论文条目要求准确、可审核的引用元数据，因此不能带着错误 stable_id 最终 APPROVE。

## 定点修订

1. 只在 `05-状态.md` 将 MLE `stable_id` 改为 `IEEE TDEI 3(1): 43-55 (1996)`；如当前 schema 不设 DOI 字段，无需扩展 schema。
2. 运行 `npm run generate:method-status`，不得手工编辑生成缓存。
3. 运行状态缓存检查、状态测试、计算器状态测试、TypeScript 检查和 `git diff --check`。
4. 不改算法和其余方法状态，提交后停止等待 Codex 复审。

## 构建说明

本次独立 `npm run build` 与正在运行的 `next dev` 共用 `.next`，在页面收集阶段发生缓存竞争并报 `PageNotFoundError`；两个页面源码均存在。复审构建应在用户停止当前 dev 服务后执行，不应据此修改页面源码。
