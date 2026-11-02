# 方法原文与现有实现审阅

2026-11-02：每个方法一份独立HTML，核对原文、当前源码、可能修改和结果影响。算法保持现状，先逐项讨论，再修改同一个方法文件，不创建原文/工程版本。

| 方法 | 审阅页 | 主要讨论 |
|---|---|---|
| MDM 最小差异法 | [打开HTML](method-mdm/index.html) | 精确秩、离散或连续求解、右端外推与成功语义 |
| MLE 极大似然估计 | [打开HTML](method-mle/index.html) | 标准似然与Hirose具体算法、位置域、支撑角点 |
| WMLE 加权极大似然估计 | [打开HTML](method-wmle/index.html) | 权重表覆盖、负位置、近似边界与选根 |
| LSE 最小二乘估计 | [打开HTML](method-lse/index.html) | 顺序统计量期望、位置搜索、原文方法范围 |
| LRE 线性回归估计 | [打开HTML](method-lre/index.html) | 已对应的Proposed+Plot、原表末位与范围 |
| MM 矩估计 | [打开HTML](method-mm/index.html) | 位置修正后尺度处理、替代位置、可采纳性 |
| MMLE 修正极大似然估计 | [打开HTML](method-mmle/index.html) | 单样本化简、停止与得分检查、未定义R² |

页面支持文字、表格及图片批注；真正未定的处理方式初始不选。提交先预览，用户最终文字优先。单选项表达同一程序未来的处理决定，不是建设多个算法版本。

每页的`assets/provenance.json`保存本轮原PDF/Markdown、源码SHA-256、核对时间和少量确定性算例。`assets/evidence.html`保留有原始行号的核对摘录；它是审阅证据，不是独立维护的算法源码或论文全文。

使用本机[review-html技能](C:/Users/36089/.codex/skills/review-html/SKILL.md)的脚本启动/恢复：

```powershell
& D:/weibull/python/.venv/Scripts/python.exe C:/Users/36089/.codex/skills/review-html/scripts/review.py resume --root D:/weibull/reviewbyhtml/method-mdm
```

其余方法更换末尾目录。返回本机URL后在浏览器审阅，直接打开HTML可离线阅读。每个任务的会话、草稿和等待记录仅留本地并精确忽略；已提交反馈与审定内容随项目保存。运行时方法跳转页随服务地址更新，不提交本机端口和会话地址。

`build-method-reviews.py`保留初轮生成依据；开始审阅后不要重建或覆盖board，沿用ID修订现有board，再render。审定后的代码与正式核对说明按每页存档预览落地；不能只保存审阅镜像代替确认的工作。
