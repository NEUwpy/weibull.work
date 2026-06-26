# Weibull Analysis Platform

**威布尔参数估计方法的研究与实践平台**

> 本文件是项目唯一权威入口。无论是人类开发者、Codex、Hermes、OpenCode、Claude Code，还是其他 AI coding agent，都从这里开始，再按任务需要渐进式阅读后续文档。

集计算、对比、验证、优化于一体，并以案例数据库和学术文献库作为数据支撑与理论依据，为可靠性工程师和研究者提供从方法选型到结果验证的完整工作流。

**线上地址**: [weibull.work](https://weibull.work)

---

## 项目概况

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 14 + TypeScript + Tailwind CSS |
| 后端 | Python + FastAPI + SciPy/NumPy |
| 部署 | Docker + Cloudflare Tunnel |
| 托管 | 绿联 NAS（无公网 IP） |

## 架构

```
用户 → Cloudflare CDN → Tunnel → NAS Docker
                                    ├── frontend:3000 (Next.js)
                                    └── backend:8001 (FastAPI)
```

## 核心模块

1. **Calculator (计算器)** - 交互式参数估计，支持多方法对比
2. **Methods (方法系统)** - 25+ 种参数估计方法的详细文档与可视化
3. **Case Database (案例库)** - 科研文献中的标准失效数据集
4. **Library (图书馆)** - Markdown 文献阅读

---

## 快速开始

### 启动后端 (Python API)

```bash
cd python
pip install -r requirements.txt
python main.py
# http://localhost:8001
```

### 启动前端 (Next.js)

```bash
npm install
npm run dev
# http://localhost:3000
```

---

## 代码位置

| 模块 | 路径 |
|------|------|
| 核心算法 | `python/methods/*.py` |
| API 接口 | `python/main.py` |
| 前端页面 | `src/app/` |
| UI 组件 | `src/components/` |

---

## 阅读路径

遵循渐进式披露：先读本 README，再根据任务继续深入。不要把历史归档当作当前依据。

| 文档 | 何时阅读 | 内容 |
|------|----------|------|
| `02-规则.md` | 写新代码、改组件、改指标、改图表前 | 复用规则、新建流程、指标图表引用规范 |
| `06-模块.md` | 需要了解系统功能 | 四大模块定义、各 Tab 目的与功能 |
| `06-A-架构决策.md` | 需要了解设计原因 | 关键架构决策的背景与后果 |
| `01-结构.md` | 需要了解文件组织 | 系统架构、目录职责、数据流向 |
| `01-A-数据模型与接口.md` | 需要了解接口细节 | 数据模型定义、API 端点、渲染管线 |
| `02-A-适用范围规范.md` | 开发适用范围模块时 | 分片命名、组件结构、数据来源表格 |
| `02-B-可信性验证规范.md` | 开发可信性验证模块时 | 验证配置格式、组件架构、添加流程 |
| `.agents/skills/coworker/SKILL.md` | 使用多 agent 编程、审查、交接时 | Codex / Hermes / OpenCode 的执行与审查协作协议 |
| `coworker/README.md` | 分发、规划、回收、验收多 agent 任务时 | 任务计划、handoff、报告和 review 的项目内流转工作区 |
| `docs/AI辅助三参数威布尔参数估计重构当前路线图.md` | 接手 AI 重构或继续研究 03 时 | 当前已完成内容、路线偏移原因、下一步里程碑 |
| `python/studies/common/README.md` | 开发蒙特卡洛、API 模拟、实验流水线时 | 统一抽样、方法调用、指标聚合、结果文件契约 |
| `python/studies/mdm/README.md` | 开发 MDM 真值抽样或研究 03 baseline 时 | 默认 MDM、full-v1 baseline、同源对比要求 |
| `/help/metrics` | 使用或新增评价指标时 | MAE/MRE/MSE 等指标的公式、含义、共享函数引用 |
| `/help/charts` | 使用或新增图表时 | 图表类型用途、数据要求、配色规范、组件复用 |
| `03-维护.md` | 部署或运维时 | 部署流程、日常维护、故障排查、安全措施 |
| `04-目标与待办.md` | 规划功能时 | 开发目标、待办事项、AI 功能规划 |
| `05-状态.md` | 了解建设进度 | 各方法各 Tab 完成情况 |
| `07-用户手册.md` | 编写或核对用户手册内容时 | 软件介绍、模块概览、功能详解、FAQ |
| `08-更新日志.md` | 查看版本更新记录时 | 版本更新条目 |

---

## AI 与协作约定

- 所有人和所有 agent 都以本 README 为唯一入口。
- 编程、重构、修 bug、审查 diff 或在 Codex / Hermes / OpenCode / Claude Code 之间交接任务时，使用 `coworker` skill。
- 具体多 agent 任务的计划、分发、执行报告和验收记录放在 `coworker/`；该目录是流转工作区，不是新的规则入口。
- 默认协作角色：Codex 负责需求对齐、规划审查和最终验收；Hermes / MiMo 或 Claude Code / MiMo 优先执行；OpenCode / DeepSeek 可作二审、备选执行或独立 bug-finding。
- 规划只写目标、已知事实、边界、执行自主性、停止条件和验证条件；不要把执行者当新手写成逐步施工脚本。
- 写新代码前必须阅读 `02-规则.md`，并按任务读取相关专题规范。
- 禁止读取 `_archive/` 作为当前实现参考；`docs/history/` 和 `docs/oldrules/` 只用于历史追溯。
- 审查时以实际 diff、验证命令和项目规则为准，不以历史手稿覆盖当前代码事实。

## 凭证信息

GitHub、NAS、Cloudflare 等连接信息存储在 `docs/凭证信息.md`（本地文件，不提交）。
