# 外部运行数据

本文说明软件外部数据的读取、登记和追溯。部署时的目录与挂载见[部署与维护指南](../../03-维护.md#代码资料与用户数据各自更新)。

## 当前目录与读取

软件只保存程序、规范、产品模型、配置及必要验收记录。外部根由`WEIBULL_DATA_ROOT`选择，默认位于软件旁`../weibull-data`：

| 外部目录 | 用途 | 浏览器地址 |
|---|---|---|
| `public/studies/` | 供现有方法对比使用的[旧研究分片](#旧研究分片) | `/studies/...csv`、`/studies/...json`及`/api/studies/.../chunks` |
| `public/ai/data/` | AI页面展示数据 | `/ai/data/...csv`、`/ai/data/...json` |
| `public/case-studies/` | 方法案例结果 | `/case-studies/...csv`、`/case-studies/...json` |
| `literature-source/` | 本机JSON书票，选择100论文与400书籍 | 由`WEIBULL_LIBRARY_ROOT`显式选择，详见[文献库入口](../library/README.md) |
| `literature/` | 冻结v1文献恢复库，也是未显式指定库时的外部默认位置 | 原文献接口与图片网址保留，不再回退软件内置正文 |
| `monte-carlo/research00/` | 已登记研究工作簿、原Excel及冻结程序 | `/api/monte-carlo`按Git索引与manifest白名单读取 |
| `cases/records/`、`cases/coverage/`、`cases/catalog.json` | 案例原记录、核查清单及已整理的分组目录 | 格式与收录范围见[案例数据库规范](../建设规范/04-案例数据库.md) |
| 其他`monte-carlo/`、`archive/` | 未登记研究批次及归档 | 不公开 |

读取层只公开上述结果命名空间的CSV/JSON，阻止目录穿越及指向模型/私人目录的符号链接。数据根缺失返回503，合法命名空间内不存在的单个文件返回404。Python生成程序通过`python/data_paths.py`写入同一`<数据根>/public`层级；版本化的Markdown配置和产品模型继续在软件仓。

## 旧研究分片

软件仓的 `public/studies/` 保存版本化的示例配置和说明。分片 CSV 及其索引在外部数据根的 `public/studies/{methodId}/chunks/`，兼容按示例读取的 `public/studies/{methodId}/{studyId}/chunks/`。方法对比读取方法级分片。结果分析读取[登记的工作簿](#research00-工作簿登记2026-11-02)。

| 接口 | 返回 |
|---|---|
| `GET /api/studies/{methodId}/chunks` | 方法级 CSV 文件名、按文件名解析的参数值及文件总数 |
| `GET /api/studies/{methodId}/{studyId}/chunks` | 指定旧示例的 CSV 文件名、解析出的参数值及文件总数 |
| `GET /studies/{methodId}/chunks/{filename}` | 方法级原始 CSV，旧示例地址可在 `chunks` 前带 `{studyId}` |

列表响应的字段为 `chunks`、`parsedParams` 和 `total`。示例文件名 `b2_e1000_g1000_n7_d0.1_rep1000_seed42_step60.csv` 中，`b`、`e`、`g` 分别记录形状、尺度和位置，`n` 为样本量，`rep` 为重复次数，`seed` 为种子。MDM 的偏移量在文件名和列表响应中使用 `d`，在 CSV 中使用 `offset_value`。`step` 记录旧分片的迭代步长。

每个方法级 CSV 分片保存一个参数组合的模拟结果。`beta_true`、`eta_true`、可选的 `gamma` 记录真值，`sample_size` 和 `sim_id` 记录样本量和组号。`est_beta`、`est_eta`、`est_gamma` 保存估计，`bias_beta`、`bias_eta`、`bias_gamma` 保存估计减真值的差，`r_squared` 保存拟合优度。缺失值及 `NaN` 按空值读取。

旧生成器的配置和查看命令见[旧示例仿真工具](../../python/studies/README.md)，新实验使用[统一蒙特卡洛流水线](../../python/studies/common/README.md)。

## 备份与发布边界

2026-11-01 的数据清理时点、原有资料迁移说明见[架构决策 AD-14](../../06-A-架构决策.md#ad-14-轻软件仓外部数据与-json-书票2026-10-28)。清理前备份、逐文件 SHA-256 清单、恢复位置及旧协作记录在 `D:/weibull-backups/software-cleanup-20261101`。需要切换旧 Git 检出时，按[维护指南的 Git 前提](../../03-维护.md#v40-基线与历史切换的-git-前提)办理。

外部资料随相应版本的索引和配置交付。数据根的挂载与上线验收见[NAS 源库部署](../../03-维护.md#nas-源库部署)。


## Research00 工作簿登记（2026-11-02）

该次登记覆盖 13 个参数组合，每个组合下的样本量为 7、15、30，各 50 份样本，共 39 个组合与样本量配对、1,950 份完整样本和 15,600 组三参数估计配置。原八组与新增五组的抽样及方法协议分别保留，按各自来源解读。原 Excel 均包含六张工作表。

原件、网页视图及冻结程序在 `monte-carlo/research00/<id>-<原件哈希前12位>/`，软件保存[工作簿索引](../../src/content/monte-carlo/research00.json)。计算时间不详时为 `null`，不能用登记时间代替。

离线登记命令（在软件根执行）：

```powershell
.\python\.venv\Scripts\python.exe -B -X utf8 scripts/import-research00-workbooks.py --research-root D:\weibull-research
```

工具核对原Excel、结果矩阵及冻结依赖哈希，生成`manifest.json`和`workbook.json`并复制原Excel/代码输入快照。已登记文件不同则中止，不覆盖历史；不会抽样或重新拟合。网页无上传，只按已登记ID读取，文件变化校验失败，不能自动回退到现算法。

新实验自动保存完整样本并登记网页索引的进度见[待办](../../04-目标与待办.md#打通新实验的数据保存与网页登记)。部署时同步索引对应批次，挂载见[NAS 源库部署](../../03-维护.md#nas-源库部署)。

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
