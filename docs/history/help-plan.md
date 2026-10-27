# 帮助中心实施计划

## 页面结构

```
/help                          ← 导航页（两个入口：用户手册 / 更新日志）
/help/manual/about             ← 软件介绍 + 模块概览
/help/manual/features          ← 功能详解

/help/changelog/status         ← 功能状态
/help/changelog/versions       ← 版本记录
/help/changelog/todos          ← 待办
```

## 文档源

| 文档 | 状态 | 说明 |
|------|------|------|
| `07-用户手册.md` | 需重写（原 `07-功能.md`） | 自包含，软件介绍 + 模块概览 + 功能详解 + FAQ |
| `08-更新日志.md` | 需改名改号（原 `07-A-更新日志.md`） | 版本记录 |
| `04-目标与待办.md` | 需改名（原 `04-目标.md`） | 待办列表，表里分离 |
| `05-状态.md` | 已有 | 功能状态，表里分离 |

## 路由 → 文档映射

| 路由 | 数据源 | 内容 |
|------|--------|------|
| `/help` | 无（静态导航页） | 两个入口卡片 |
| `/help/manual/about` | `07-用户手册.md` 的"软件介绍"+"模块概览"章节 | |
| `/help/manual/features` | `07-用户手册.md` 的"功能详解"章节 | |
| `/help/changelog/status` | `05-状态.md` | stripBlockquotes |
| `/help/changelog/versions` | `08-更新日志.md` | |
| `/help/changelog/todos` | `04-目标与待办.md` | stripBlockquotes |

## 共享侧边栏

所有 `/help/*` 页面统一侧边栏，两级分组：

```
用户手册
  ├─ 软件介绍
  └─ 功能详解
更新日志
  ├─ 功能状态
  ├─ 版本记录
  └─ 待办
```

## 实施步骤

### 1. 文档整理
- [ ] 重写 `07-功能.md` → `07-用户手册.md`（自包含）
- [ ] `07-A-更新日志.md` → `08-更新日志.md`
- [ ] `04-目标.md` → `04-目标与待办.md`（加表里分离）
- [ ] 更新 CLAUDE.md 中的文档索引表
- [ ] 删除旧文件

### 2. 页面开发
- [ ] `/help` 导航页
- [ ] `/help/manual/about` 软件介绍 + 模块概览
- [ ] `/help/manual/features` 功能详解
- [ ] `/help/changelog/status` 功能状态
- [ ] `/help/changelog/versions` 版本记录
- [ ] `/help/changelog/todos` 待办

### 3. 侧边栏
- [ ] 共享侧边栏组件，两级分组，当前页高亮

### 4. Header 入口
- [ ] 软件信息下拉菜单链接到帮助中心
- [ ] 版本号显示（已由 `APP_VERSION` 统一管理）

### 5. 清理
- [ ] 删除旧的 `/help` 页面代码（HelpContent.tsx 等）
- [ ] 删除旧的 `/help/changelog` 页面代码（ChangelogContent.tsx 等）
