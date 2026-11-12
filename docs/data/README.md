# 外部运行数据

2026-11-01已将当前主分支的旧文献副本、展示结果、历史输出和归档数据移出软件仓。此前2026-10-28的数据外置工作保存在独立工作区，不能作为当时主分支已完成清理的依据；本次将必要读取适配接入当前代码，保留最新图书馆、权限与界面改动。

## 当前目录与读取

软件只保存程序、规范、产品模型、配置及必要验收记录。外部根由`WEIBULL_DATA_ROOT`选择，默认位于软件旁`../weibull-data`：

| 外部目录 | 用途 | 浏览器地址 |
|---|---|---|
| `public/studies/` | 方法适用范围分片与结果 | `/studies/...csv`、`/studies/...json`及`/api/studies/.../chunks` |
| `public/ai/data/` | AI页面展示数据 | `/ai/data/...csv`、`/ai/data/...json` |
| `public/case-studies/` | 方法案例结果 | `/case-studies/...csv`、`/case-studies/...json` |
| `literature-source/` | 本机JSON书票，选择100论文与400书籍 | 由`WEIBULL_LIBRARY_ROOT`显式选择，详见[文献库入口](../library/README.md) |
| `literature/` | 冻结v1文献恢复库，也是未显式指定库时的外部默认位置 | 原文献接口与图片网址保留，不再回退软件内置正文 |
| `monte-carlo/research00/` | 已登记研究工作簿、原Excel及冻结程序 | `/api/monte-carlo`按Git索引与manifest白名单读取 |
| `cases/records/`、`cases/coverage/`、`cases/catalog.json` | 案例原记录、核查清单及已整理的分组目录 | 格式与收录范围见[案例数据库规范](../建设规范/04-案例数据库.md) |
| 其他`monte-carlo/`、`archive/` | 未登记研究批次及归档 | 不公开 |

读取层只公开上述结果命名空间的CSV/JSON，阻止目录穿越及指向模型/私人目录的符号链接。数据根缺失返回503，合法命名空间内不存在的单个文件返回404。Python生成程序通过`python/data_paths.py`写入同一`<数据根>/public`层级；版本化的Markdown配置和产品模型继续在软件仓。

## 备份与发布边界

本次清理前Git完整备份、逐文件SHA-256清单、恢复位置以及旧协作记录在`D:/weibull-backups/software-cleanup-20261101`。100/400现行源稿未改动，移出的旧文献不再作为日常可编辑副本。

同日按用户追加要求，进一步从v4.0以来历史中移除这些退役资料；保留开发记录及当前程序内容，`v4.0.0`根提交更新为`2b666353`。重写前完整Git包、旧工作区和新旧提交映射在`D:/weibull-backups/history-rewrite-v4-20261101`。已有旧检出需先保存改动，再按维护指南重新克隆；外部资料不因Git历史改写而删除。

NAS更新程序时还须同步对应外部展示数据与文献、配置只读挂载。`docker-compose.library.yml`提供文献与结果根的挂载覆盖示例；源模式另外挂载100/400，完整步骤见[维护指南](../../03-维护.md)。自动生成v2资料包及包内相对源路径尚未实现，本次未部署NAS。克隆软件Git不会自动取得这些外部数据，也不会取得本机凭证。


## Research00 工作簿登记（2026-11-02）

已登记13组合、39组样本量、1950份完整样本和15600组三参数估计配置。原件、网页视图及冻结程序在`monte-carlo/research00/<id>-<原件哈希前12位>/`；软件只保存轻量索引。原始协议分别保留，计算时间不详时为null，不能用登记时间代替。

离线登记命令（在软件根执行）：

```powershell
.\python\.venv\Scripts\python.exe -B -X utf8 scripts/import-research00-workbooks.py --research-root D:\weibull-research
```

工具核对原Excel、结果矩阵及冻结依赖哈希，生成`manifest.json`和`workbook.json`并复制原Excel/代码输入快照。已登记文件不同则中止，不覆盖历史；不会抽样或重新拟合。网页无上传，只按已登记ID读取，文件变化校验失败，不能自动回退到现算法。

新实验自动保存完整样本并生成网页索引仍待接通。本机展示已接入，NAS部署须另同步索引对应批次；原Compose完整data只读挂载可继续使用。单独更新软件Git不会获得数据。

工作簿仅通过计算记录编号关联[独立计算记录集](#计算记录)。载入时核对每组样本、编号、估计值和设置，不在工作簿适配层构造计算过程。

## 计算记录

计算记录属于 Weibull 软件，独立于研究项目及工作簿。记录格式由 `src/lib/calculation-records.ts` 唯一声明，保存于外部数据根的 `calculation-records/<方法>/<内容SHA-256>.json`，编号为 `<方法>-<内容SHA-256>`。软件 Git 保存格式、读写程序及需要关联的记录编号，完整数据不进 Git。

- `CalculationRecordSet` 保存格式版本、方法/模型、设置、可选已知参数、算法源文件及哈希和各组记录。每组 `CalculationRecord` 保存实际样本、估计结果与状态，以及同次运行的完整计算证据。失败记录也保留。
- 实时记录直接使用统一 `studies.common.runner.run_method(..., trace=True)` 产出的 `calculation`、`trace_data` 和运行身份；不为绘图重新求解或补取函数点。MDM 的阶段数据由同一个适配器转换，实时与已保存记录共用 `MDMBatchWorkspace`。
- 已保存的 MDM 阶段记录包含位置扫描、梯度、各位置实际形状试算、位置求值区间、最终形状和逐样本伪尺度。算法版本不同则保留实际求解器及源码快照，不用当前算法替换旧计算。格式不保存研究项目名称、项目目录或项目专属登记结构。
- `GET /api/calculation-records/{记录编号}` 独立读取完整记录集；`?view=process` 读取过程视图，`?trialRun={组号}` 按需读取该组各位置的形状试算点。读取先核对内容哈希，再检查样本、结果、算法身份及过程量的对应关系；缺失或不一致直接报错。页面只渲染记录，不依靠工作簿目录或外部研究程序。
- `scripts/export-calculation-records.py` 是通用生成入口，支持单组、多组和方法设置：输入 JSON 的 `samples` 为样本数组列表，可附 `truth`、`title`；调用同一估计引擎后直接写入上述格式。后续产生、导入或迁移计算过程都使用该格式，不再维护逐项目的过程补充文件。

```powershell
.\python\.venv\Scripts\python.exe scripts/export-calculation-records.py mdm samples.json --offset 0.10 --data-root D:\weibull-data
```

现有 `n=30`、`δ=0.10` 的 50 组 MDM 完整过程已纳入该格式，保留原样本、参数、全部计算点、实际 Brent 求解和算法身份。部署时须同步 `calculation-records/`；软件版本发布和 Git 同步不代替外部数据部署。

## 案例材料提取与核查

按[案例数据库规范](../建设规范/04-案例数据库.md)读取当前正式书单，提取现行原文稿的表格、可定位图片、外部数据链接和待核数值段。少数资料仅有译稿时记录实际来源。已有人工修订及核查记录保留，来源变化造成身份冲突时保留原件并报告具体条目。

在软件根目录执行：

```powershell
.\python\.venv\Scripts\python.exe -X utf8 scripts/import-case-library.py --apply
.\python\.venv\Scripts\python.exe -X utf8 scripts/import-case-library.py --check
.\python\.venv\Scripts\python.exe -X utf8 scripts/import-case-library.py --index-only
.\python\.venv\Scripts\python.exe -X utf8 scripts/curate-case-catalog.py --apply
```

提取脚本省略 `--apply` 时仅盘点，`--paper 182-105` 可限定单篇。导入后生成 `cases/index.json`，人工新增样本后可单独刷新索引。`--check` 核对源稿身份、原文表格、图资源、编号与来源连接；源稿一致和 PDF 内容核验分别记录。

目录脚本根据显式选材生成 `cases/catalog.json`，保留中文组名、成员和后台待核查清单，省略 `--apply` 时只预览统计。补充选材后重跑，不改原数据、论文或正式书单。扫描提取不会自行把新材料公开；NAS接入时须同时同步原记录、索引和分组目录。
