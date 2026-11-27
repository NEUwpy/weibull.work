# 脚本与检查

以下命令在软件仓根目录运行。Node.js 与依赖安装见[维护指南](../03-维护.md#手动启动开发服务)，命令定义见 [package.json](../package.json)。

| 改动 | 检查入口 |
|------|----------|
| 现行说明、公开手册或更新计划 | `npm run check:docs` |
| 应用逻辑、页面或 API | `npm run check:app`，依次检查文档、应用回归和 TypeScript |
| 方法目录、建设状态或展示流程 | 按[生成缓存](../05-状态.md#生成缓存)更新或校验方法状态。解析与推导使用 `npm run test:method-status` |
| Python 算法或 API | [后端回归测试](../python/tests/README.md)。前端 API 调用也变更时，另查应用回归 |
| 版本钩子或版本检查 | `node --test scripts/tests/update-version.test.mjs` |
| NAS 切换前核对候选版本与外部资料 | [NAS 发布预检](../03-维护.md#nas-发布预检) |

## 文档检查

[check-docs.mjs](check-docs.mjs) 按文件清单和指定目录检查现行 Markdown 的仓库内链接及标题锚点，并按方法目录和路由定义核对公开手册中的方法链接。新增现行子目录 README 时，核对它是否已由目录规则覆盖，必要时将路径加入检查清单。仓库外目标及页面的实际可达性需到对应环境核对。

该脚本读取 [04 更新计划](../04-目标与待办.md)与 [07 用户手册](../07-用户手册.md)，和软件信息页分别共用[待办解析器](../src/lib/update-plan.ts)与[手册解析器](../src/lib/markdown.ts)。修改固定字段、标题或公开范围时，同步核对页面与对应回归。应用检查和生产构建共用 `check:docs`，其中也会校验版本和方法状态缓存。

## 版本与方法状态

- [版本脚本](update-version.mjs)读取 [08 更新日志](../08-更新日志.md)、`package.json` 和 `package-lock.json`。当前文件与指定提交分别校验。修改钩子时，使用[版本回归](tests/update-version.test.mjs)中的临时 Git 仓库，覆盖正常提交、绕过钩子、回滚及历史保留。版本格式见[版本编号规则](../02-规则.md#111-版本编号)，本仓安装钩子和发布检查见[维护指南](../03-维护.md#本地提交与版本记录)。
- [状态生成脚本](generate-method-status.mjs)读取 [05 建设状态](../05-状态.md#建设状态)的 YAML 和[方法目录](../src/data/methods.json)，校验证据位置及已完成的程序流程，输出状态缓存。数据维护与生成命令见[建设状态](../05-状态.md#生成缓存)。

## 应用回归

应用回归位于 `scripts/tests/*.test.mjs`，按模块选择对应文件。单个用例文件可从根目录运行，例如：

```powershell
node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --experimental-strip-types --test scripts/tests/update-plan.test.mjs
```

需要加载服务端 TypeScript 时，可复用 [loadServerModule](tests/helpers/load-server-module.mjs)，执行实际模块并为外部依赖提供测试替身。[案例导入的 Python 回归](tests/test_case_import.py)单独用 pytest 运行。

## 数据维护脚本

工作簿登记、计算记录导出及案例导入见[外部运行数据](../docs/data/README.md)。文献题录补全和期刊指标更新见[文献库维护](../docs/library/README.md#文献题录与期刊指标维护)。这些入口负责数据范围、执行参数与验收方式。
