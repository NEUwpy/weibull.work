# 项目开发计划与需求 (Project Roadmap & Requirements)

> **文档更新时间**: 2026-01-27
> **当前状态**: 核心功能已上线，算法文档系统已建立 (Algorithm Documentation System Established)

本文档记录了 Weibull 分析平台的后续开发计划、功能需求变更及待办事项。

---

## 1. 已完成核心功能 (Completed)

### 1.1 平台架构 (Architecture)
- [x] **三位一体**: 确立了 [计算工具] + [案例数据库] + [可靠性图书馆] 三大模块。
- [x] **全局导航**: 实现了毛玻璃风格 Header，支持动态标题与模块切换。
- [x] **数据驱动**: 算法定义 (`methods.json`) 和案例数据 (`cases.json`) 均实现文件化管理。

### 1.2 参数估计方法系统 (Parameter Estimation Methods)
- [x] **方法分类**: 8 大类别，25+ 具体算法，层级化展示
- [x] **方法详情页**: 全宽布局，支持公式、描述、变量说明、流程图、适用场景、相关文献
- [x] **算法文档系统**: 基于 Markdown + Frontmatter 的标准化文档架构
  - MD 模板 (`src/content/algorithms/_template.md`)
  - 示例文档 (`src/content/algorithms/wmle.md`)
  - Python 模板 (`python/_template.py`)
  - Python 实现 (`python/wmle.py`)
- [x] **Mermaid 流程图**: 支持横向流程图自动渲染
- [x] **内容与代码分离**: 所有页面内容从 MD frontmatter 读取，无硬编码
- [x] **导航优化**: 类别区域进入类概述，细分方法直接进入详情页
- [x] **方法选择器**: 弹出式选择，支持查看公式和描述

### 1.3 电子图书馆 (Library)
- [x] **内容渲染**: 完美支持 Markdown, LaTeX 公式 (KaTeX), 图片路径自动修正。
- [x] **双语切换**: 支持中英文版本无缝切换 (基于 `ID-pdf翻译.md` / `ID-pdf原文.md`)。
- [x] **智能目录**: 实现了基于正则表达式的层级归一化侧边栏目录，支持公式渲染。
- [x] **参考文献**: 实现了结构化解析，支持文中角标跳转、列表自动分行、引用文章链接跳转。
- [x] **方法链接**: 方法页面可显示引用该方法的原文献/参考论文列表。
- [x] **UI 规范**: 统一了字号 (14px/16px) 和对齐方式 (4.5rem 边距)，图片自动居中且限宽 1/3，图题表题居中加粗。
- [x] **类型筛选**: 实现了按文章类型（期刊/书籍/会议/其它）筛选功能，三档切换按钮位于卡片上方。

### 1.4 案例数据库 (Case Database)
- [x] **数据库页面**: 实现了表格化展示、多维度筛选 (行业/类型)。
- [x] **一键计算**: 实现了从案例库携带数据跳转至计算器的互通逻辑。

---

## 2. 待办事项 (Next Steps)

### 2.1 算法文档完善 (Priority)
- [ ] **逐步创建文档**: 为所有 25+ 算法创建 MD 文档，按照 `_template.md` 和 `wmle.md` 模式
- [ ] **Python 实现**: 为所有算法创建 Python 实现文件
- [ ] **流程图绘制**: 为每个算法绘制 Mermaid 流程图

### 2.2 电子图书馆优化
- [ ] **图片放大 (Lightbox)**: 正文中的图片目前限宽 1/3，点击后应弹出全屏查看器 (Lightbox) 以查看细节。
- [ ] **PDF 对照**: 考虑集成 PDF 预览功能，实现左文右图的对照阅读模式。

### 2.3 案例数据库优化
- [ ] **详情页**: 目前点击案例只有"去计算"，未来应增加案例详情页，展示更多背景信息和原始数据图表预览。
- [ ] **数据导入导出**: 支持 Excel/CSV 格式的批量导入和导出。

### 2.4 计算工具增强
- [ ] **算法集成**: 将 Python 算法实现集成到计算器后端
- [ ] **交互优化**: 增加拖拽上传数据文件的功能。

---

## 3. 维护指南 (Maintenance)

### 3.1 添加新算法文档

**创建 MD 文档** (`src/content/algorithms/{slug}.md`):
```yaml
---
method_id: "方法ID"
method_name: "方法中文名"
short_name: "英文缩写"
category: "类别名称"

# 核心信息
formula: "LaTeX公式"
description: "简短描述"

# 变量说明
variables:
  - symbol: "β"
    description: "形状参数"
    range: "β > 0"

# 计算流程图（Mermaid语法）
flowchart: |
  flowchart LR
    A[输入] --> B[处理]
    B --> C[输出]

# 适用场景
applicability:
  complete_sample: true
  censored_sample: false
  small_sample: true
  large_sample: true

# 相关文献
references:
  - id: "文章ID"
    title: "文献标题"
    author: "作者"
    year: 年份
    publication: "期刊名称"
---

# 算法原理
[详细内容...]
```

**创建 Python 实现** (`python/{slug}.py`):
```python
from typing import List, Dict, Any

def estimate(data: List[float], **kwargs) -> Dict[str, Any]:
    """
    估计威布尔分布参数

    Args:
        data: 失效时间数据
        **kwargs: 其他参数

    Returns:
        {
            "beta": 形状参数,
            "eta": 尺度参数,
            "gamma": 位置参数,
            "success": 是否成功,
            "message": 错误信息(如有)
        }
    """
    # 实现算法逻辑
    pass
```

**在 methods.json 中注册**:
```json
{
  "id": "方法ID",
  "name": "方法名称",
  "shortName": "缩写",
  "slug": "对应MD文件名",
  "hasDetail": true,
  "description": "简短描述",
  "formula": "LaTeX公式"
}
```

### 3.2 添加新文献

1. 将 `ID-pdf翻译.md` (必选) 和 `ID-pdf原文.md` (可选) 及图片文件夹放入 `src/content/` 和 `public/`
2. 添加文献间引用链接: 编辑 `src/data/references.json`

### 3.3 添加新案例

编辑 `src/data/cases.json`

---

**启动命令**:
1. 前端: `npm run dev`
2. 后端: `cd python && python main.py`
