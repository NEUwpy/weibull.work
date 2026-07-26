# Study02 全新 A-E1 formal 启动合同

> 状态：`NOT AUTHORIZED / NOT EXECUTED`
>
> 本文件只定义未来启动门，不授予权限，不创建目录、run 或 lease。

## 唯一允许的未来 run

- module：仅 `A-E1`。
- run：必须使用全新、此前从未存在的 run ID。
- artifact root：`C:\weibull-runs\study02\artifacts`。
- cache root：`C:\weibull-runs\study02\cache`。
- 旧 r1/r2 永久 `blocked/aborted`，禁止恢复、覆盖、续接、复制状态或拼接证据。
- 本合同不允许 A-E3、A-E2、approval、authorize、test unseal 或 test consume。

## 显式授权门

启动前必须取得针对该全新 run 的显式 A-E1 formal training/validation 授权。授权至少绑定：module、全新 run ID、被批准的完整 Git commit、artifact/cache root、冻结配置哈希和“test 保持 sealed”边界。

代码 checkpoint `1bdd9906e87b53cd0cd1ad81bcfbb8ed8197a5a1` 只证明准备工作收口，不等同于启动授权。不得由执行者自行生成、推断或补写授权。

## launch 前必须重新通过的检查

1. 执行 `git fetch origin`，记录 `HEAD` 与 `origin/main`；二者必须等于授权绑定的完整 commit，且工作树与 Study02 scoped code 均 clean。
2. 检查 `.slim/deepwork/study02-a.lease.json`、活动 Study02 formal 进程及仓外 run 状态；必须没有有效 lease、活动执行者或冲突 run。
3. 重新测量目标卷容量，并用当次估计确认预计新增占用不超过可用磁盘的 80%。2026-07-26 快照为 C 盘 free 31.57 GB、冻结估计 4,225,761,280 bytes（含 2x 余量），只能作参考。
4. 重跑配置与冻结哈希校验，记录 protocol、search、amendment、matrix 和 effective config 的实际 SHA；必须与授权及冻结权威完全一致。
5. 重新确认运行时间风险。2026-07-26 投影为 1,373,822.99 秒（约 381.6 小时），启动时必须基于当前机器与执行策略复核。
6. 再次确认 test state 为 `sealed`、`test_access_count == 0`，且没有 approval/unseal/test 动作或产物。

任一项无法证明即停止，不创建目录、run、manifest 或 lease。

## 候选命令模板

以下仅是未来获批后的候选模板，当前 **NOT EXECUTED**：

```powershell
python "Study/02-study-NN参数估计与分位点目标研究/code/run_study02a.py" formal-execute `
  --module A-E1 `
  --run-id "<NEW-A-E1-RUN-ID>" `
  --artifact-root "C:\weibull-runs\study02\artifacts" `
  --cache-root "C:\weibull-runs\study02\cache" `
  --owner-id "<AUTHORIZED-OWNER-ID>"
```

替换占位符、创建仓外根目录或执行该命令都属于启动动作，必须发生在显式授权和全部 launch 检查通过之后。

## 运行期间停止条件

- HEAD、scoped code、冻结配置或 authority SHA 与授权不符；
- 出现有效 lease、冲突进程、重复 run ID 或其他写入者；
- 预计磁盘使用达到或超过 80%，或资源/时间投影不再可接受；
- 发生数据角色泄漏、配置哈希漂移、实现合同失败、非有限证据绕过或不可审计产物；
- 任何步骤要求复用 r1/r2，或提前进入 A-E3/A-E2；
- 任何步骤要求生成 approval、authorize/unseal、生成/读取/消费 test；
- 授权范围、run ID、commit 或路径需要变更。

停止后必须保留失败证据并申请新的决策；不得覆盖产物、静默修补后续跑或扩大授权范围。
