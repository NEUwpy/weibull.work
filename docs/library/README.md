# 可靠性图书馆

本机资料库为 `D:\weibull-data\literature`。文献独立保存，Weibull 网站负责读取、展示和问答取材；新增资料无需提交软件 Git 或重建网站。

## 存放结构

```text
literature/
├── README.md
├── library.json                 内容为 {"schema_version":1}
├── references.json              跨文献引用映射，没有则为 {}
├── content/182-046-pdf原文.md
├── content/182-046-pdf翻译.md
└── assets/182-046-图片/          配图及配套 PDF，可保留原有子目录
```

沿用博士文献编号，不因分类或移动而重编。正文直接放 `content/`，命名为 `<编号>-pdf原文.md` 或 `<编号>-pdf翻译.md`，至少一份；两份都有时默认读译文，元数据也优先取译文。网站地址为 `/library/<编号>`。

## 文献格式与示例

使用 UTF-8 Markdown，顶部加 YAML 表头。以下示例需替换为真实信息；原译文的作者、年份等身份信息保持一致。

```markdown
---
title: "论文标题"
author: "作者"
year: 2024
type: "期刊"
tags: ["Weibull", "参数估计"]
summary: "论文摘要或简述"
---

# 论文标题

正文，引用示例 [1]。

![原论文图注](/182-046-图片/images/figure.jpg)

## 参考文献

[1] 按论文实际条目填写，保留与正文一致的编号。
```

`title` 必填；`type` 使用 `期刊`、`会议`、`书籍`，`tags` 为不重复的字符串数组。年份填实际发表年，缺失时列表会显示当前年；不猜测元数据。可另填字符串字段 `title_en`、`affiliation`、`publication`、`short_publication`，分别表示英文标题、作者单位、出版物全称及简称。公式使用 `$...$` 或独立成段的 `$$...$$`。

图片示例对应实际文件 `assets/182-046-图片/images/figure.jpg`。网址从 `/<编号>-图片/` 开始，用 `/`，保留真实文件名、大小写和子目录，空格可写 `%20`；支持 PNG、JPG/JPEG、GIF、WebP、SVG、AVIF。PDF 放在同一编号资源目录，用普通链接，如 `[PDF](/182-046-图片/paper.pdf)`，不会自动解析成正文。

参考文献放全文末尾，以 `## 参考文献` 或 `## References` 开始，每条一行，以 `[数字]` 开头。作者—年份制需核对对应关系后再转号，不能猜测。跨文章跳转写在库根 `references.json`，如 `{"182-046":{"1":"182-088"}}`，表示前者第 1 条引用指向已入库的后者；没有映射时条目仍可显示，不自动按题名或 DOI 匹配。

## 整理、导入与读取

从“博士阶段 100”选择确定版本，复制到独立批次目录，在副本上补表头、调整图片网址并核对正文；源文件不改。批次根直接放原文和/或译文及 `<编号>-图片/`，不套 `content/`、`assets/` 层，不混入历史副本或 OCR 中间文件。然后运行：

```powershell
node D:\weibull\scripts\library-data.mjs import --source-dir D:\incoming-papers --root D:\weibull-data\literature
node D:\weibull\scripts\library-data.mjs check --root D:\weibull-data\literature
```

导入只复制文件，不自动 OCR、翻译、补元数据或合并引用表；相同文件跳过，同名不同内容在复制前终止整批。修改已入库资料先备份。`check` 检查库结构、标题、标签类型和引用目标，图片、公式及原译文切换还需打开网页检查；刷新页面即可读取新增内容。

软件本地 `.env.local` 配置 `WEIBULL_LIBRARY_ROOT=D:/weibull-data/literature`，切换路径后重启前端；取消该配置及同名进程环境变量后重启则使用保留的内置库。NAS 使用其自身资料路径和软件的 `docker-compose.library.yml` 只读挂载，本机资料不会自动同步，线上尚未切换。

读取实现参照软件仓 `src/lib/server/literature.ts`，导入工具参照 `scripts/library-data.mjs`；本 README 的版本源为 `docs/library/README.md`。资料备份统一放 `D:\weibull-backups`，库内 `export-manifest.json` 仅记录初次导出，不代替后续备份。
