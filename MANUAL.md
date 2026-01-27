# 威布尔分析平台 (Weibull Analysis Platform) - 开发者手册

> **文档状态**: 2026-01-27 更新 (v0.3.0 Hybrid)
> **适用对象**: 维护本项目的开发者或 AI 助手。

---

## 1. 项目概况 (Overview)
本平台采用 **Next.js + Python** 的混合架构。
- **Frontend**: Next.js 负责 UI、路由、静态内容渲染和简单的线性回归预览。
- **Backend**: Python (FastAPI) 负责执行高级统计计算（如 WMLE, 贝叶斯估计等）。

---

## 2. 核心架构 (Architecture)

### 2.1 计算流程
1. 用户在前端选择算法（如 "WMLE"）。
2. Next.js 通过 API (`/api/calculate`) 将数据发送给 Python 服务。
3. Python 服务 (`python/main.py`) 根据 `method_id` 路由到具体的算法模块。
4. 如果该算法尚未实现（抛出 `NotImplementedError`），系统自动降级使用 **WMLE (加权极大似然估计)** 作为通用计算内核。

### 2.2 目录结构
```
C:\Web\Weibull\
├── src\
│   ├── data\methods.json       # 算法元数据（定义菜单、公式）
│   └── content\algorithms\     # 法详细文档 (Markdown)
└── python\
    ├── main.py                 # FastAPI 网关，负责路由分发和异常处理
    ├── base.py                 # WeibullBase 基类 (提供数学工具)
    └── methods\
        ├── _template.py        # 开发新算法的通用模板
        ├── wmle.py             # 核心算法 (也作为默认后备)
        ├── lre.py              # 基础算法 (线性回归)
        └── [mle.py, etc...]    # 其他算法 (未实现时指向 WMLE)
```

---

## 3. 如何添加新算法 (Adding New Methods)

### 步骤 1: 注册元数据 (Frontend)
编辑 `src/data/methods.json`，添加算法 ID、名称和公式。这会让算法出现在左侧菜单中。

### 步骤 2: 实现后端逻辑 (Backend)
1. 复制模板: `cp python/methods/_template.py python/methods/your_method.py`
2. 实现逻辑: 继承 `WeibullBase` 并重写 `run()` 方法。
3. 注册路由: 在 `python/main.py` 的 `method_map` 中添加映射：
   ```python
   from methods.your_method import YourMethod
   # ...
   "your_method_id": YourMethod,
   ```

> **注意**: 如果您只在前端注册了 ID 但未在 Python 中实现，请确保 `main.py` 将其映射到 `WMLE` 或一个抛出 `NotImplementedError` 的类，系统会自动理后备逻辑。

---

## 4. 运行服务 (Running)

开发模式下需要同时运行两个终端：

**Terminal 1 (Frontend):**
```bash
npm run dev
```

**Terminal 2 (Backend):**
```bash
cd python
# 确保安装了依赖: pip install -r requirements.txt
python main.py
```
*Python 服务默认运行在 http://localhost:8001*