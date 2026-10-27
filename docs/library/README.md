# 可靠性图书馆

本目录保存网站可读取的文献。软件负责解析和展示，文献、配图和引用关系独立维护；新增文献无需提交软件 Git 或重建网站。本机资料库为 `D:\weibull-data\literature`，NAS 线上尚未切换。

## 目录

```text
literature/
├── README.md
├── 文献格式.md
├── templates/文献模板.md
├── library.json                  库格式：{"schema_version":1}
├── references.json               跨文献引用映射；没有则为 {}
├── content/                      正文直接放此层，不按学科建子目录
│   ├── 182-046-pdf原文.md
│   └── 182-046-pdf翻译.md
├── assets/182-046-图片/           该文献的图片、配套 PDF，可保留子目录
└── export-manifest.json          初次导出凭据，不是持续更新的索引
```

文献按稳定编号关联，分类写在元数据 `type`、`tags` 中。网站直接扫描文件，不需要手写文章目录。编号、正文和图片规则见[文献格式](文献格式.md)，整理时复制[文献模板](templates/文献模板.md)。

## 从“博士阶段 100”新增文献

1. 按编号选择源文件，复制到独立批次目录；保留博士文献原件，不混入历史、归档或待回收副本。同编号出现多个版本时先确认来源。
2. 在副本上补 YAML 表头、规范图片网址，核对公式及参考文献。批次根直接放 `<编号>-pdf原文.md` 和/或 `<编号>-pdf翻译.md`，配套 `<编号>-图片/`；不要套 `content/`、`assets/` 层。
3. 运行下列命令，刷新 `/library`，打开新增文章检查图片、公式、原译切换及引用。OCR 原文若缺表头或仍用相对图片路径，不能直接作为完成稿。

```powershell
Set-Location D:\weibull
node scripts/library-data.mjs import --source-dir D:\incoming-papers --root D:\weibull-data\literature
node scripts/library-data.mjs check --root D:\weibull-data\literature
```

`import` 复制文件，不自动 OCR、翻译、补元数据或合并引用表。相同文件跳过；同名不同内容在复制前终止整批。修改已入库文献时，先备份该篇正文、资源与引用表，再明确修改范围；不要删除旧文件来绕过冲突。

`check` 检查库结构、标题、标签类型及引用目标，不检查图片是否缺失或页面排版。资料库须独立备份到 `D:\weibull-backups`；克隆软件仓不能恢复新增的外挂资料。

## 维护入口

软件通过 `WEIBULL_LIBRARY_ROOT` 选择整个库；切换路径需重启前端，当前库内新增或修改文献后刷新即可。配置、初次导出、回退和 NAS 挂载见软件仓 `docs/外挂文献库.md`。

软件仓 `docs/library/` 是本 README、格式规范和模板的版本源；资料库携带同版副本。修改约定时先更新版本源，再同步这三份文档。模板留在 `templates/`，不要原样放入 `content/`。
