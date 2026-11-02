# 方法流程与图的呈现评审

2026-11-03：每个方法一份独立HTML，评审网站的程序分阶段、计算过程展开、过程图与参数结果的衔接。Agent先核查并给出整体建议，用户把关宏观呈现；不把代码定位、采样、容差或排版等细节做成逐项选择。只有改变方法定义、估计结果或成功口径的事项另行讨论。此轮仅更新评审载体，尚未应用网站。

| 方法 | 审阅页 | 呈现主线 |
|---|---|---|
| MDM 最小差异法 | [打开HTML](method-mdm/index.html) | 原形状寻优与位置偏移双图及联动，保留已确认口径 |
| MLE 极大似然估计 | [打开HTML](method-mle/index.html) | 位置似然与得分、条件形状、尺度恢复 |
| WMLE 加权极大似然估计 | [打开HTML](method-wmle/index.html) | 两个加权方程、候选表、尺度恢复 |
| LSE 最小二乘估计 | [打开HTML](method-lse/index.html) | F比定位、White回归、斜率取倒数与尺度恢复 |
| LRE 线性回归估计 | [打开HTML](method-lre/index.html) | 相关系数定位、概率图回归与参数恢复 |
| MM 矩估计 | [打开HTML](method-mm/index.html) | 生存函数面积、矩的可采纳性、显式求参 |
| MMLE 修正极大似然估计 | [打开HTML](method-mmle/index.html) | 最小值与单次删除、形状迭代、停止判据；计算页仍未开放 |

页面支持文字、表格及图片批注。正文给出整体建议，不要求逐项投票；提交先预览，用户最终文字优先。存档预览的落地目标是网站程序流程、计算过程与过程图，并记录各方法的审定和验收。

每页的`assets/process-run.json`保存固定样本、现行方法运行记录、绘图点、网站流程API快照与源码身份。`current-*.png`是实际网站截图，`record-*.svg`仅由同次记录重绘，`proposed-reading-flow.svg`是建议阅读主线；三者明确区分。`process-evidence.html`保留逐步公式及源码定位，作为Agent核查依据。

此前的原文对照保留在`prior-algorithm-review.html/json`，原始证据、反馈历史与MDM既有决定继续保留；不把它们冒充当前网站已实现的内容。原`provenance.json`与`evidence.html`仍对应此前原文核对轮次，不代表此轮最新来源身份。

使用本机[review-html技能](C:/Users/36089/.codex/skills/review-html/SKILL.md)的脚本启动/恢复：

```powershell
& D:/weibull/python/.venv/Scripts/python.exe C:/Users/36089/.codex/skills/review-html/scripts/review.py resume --root D:/weibull/reviewbyhtml/method-mdm
```

其余方法更换末尾目录。返回本机URL后在浏览器审阅，直接打开HTML可离线阅读。每个任务的会话、草稿和等待记录仅留本地并精确忽略；已提交反馈与审定内容随项目保存。运行时方法跳转页随服务地址更新，不提交本机端口和会话地址。

`build-method-reviews.py`保留初轮生成依据，`build-process-reviews.py`保留本次有意调整审阅层次的生成依据。脚本拒绝重复重建本轮内容；开始审阅后沿用ID修改现有board，再render，不覆盖反馈或草稿。审定后的正式成果按存档预览落实，不能只保存审阅镜像代替网站更新。
