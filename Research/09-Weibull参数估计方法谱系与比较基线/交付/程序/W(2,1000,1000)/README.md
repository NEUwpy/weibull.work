# W(2,1000,1000)

真值β=2、η=1000、γ=1000；n=7/10/15/20/50各1200组。上层只有程序、结果两个文件夹。结果目录只放交付件（三PNG、11个配对工作表的Excel）；三个明细CSV放在相邻数据目录，均从原批次复制。

## 运行

程序相对本文件定位相邻结果目录，数据从相邻数据目录的三CSV读取，不依赖旧批次路径。Python环境为D:\weibull\python\.venv\Scripts\python.exe；Excel使用本机捆绑Node和@oai/artifact-tool。版本见环境.json。Excel入口运行时为捆绑依赖创建node_modules链接，不复制依赖文件。

重新导出当前精简Excel：

```powershell
& '.\export_workbook.ps1'
```

若要另存而不覆盖当前Excel：

```powershell
& '.\export_workbook.ps1' -OutputDirectory 'D:\weibull\临时导出\W(2,1000,1000)'
```

重新出三张图，不拟合参数：

```powershell
& 'D:\weibull\python\.venv\Scripts\python.exe' '.\draw.py'
```

draw.py可用--output另存目录；默认写相邻结果目录，运行校验写该输出目录的.运行记录。prepare_tables.py读取相邻数据目录的三CSV；lean_workbook.mjs导出相同11个配对工作表；verify_workbook.py逐项核对188610个数据单元格。所有表第一行列名、第二行数据，无标题或备注，失败留空。

重新计算三方法必须指定一个尚不存在的目录：

```powershell
& 'D:\weibull\python\.venv\Scripts\python.exe' '.\reproduce.py' --output 'D:\weibull\临时复算\W(2,1000,1000)' --workers 6
```

此入口复制程序和相邻数据CSV到新目录，compute.py 用同一套种子重算 MLE/MMLE/WMLE 三方法（MLE 与 WMLE 为注册表经典实现，MMLE 为原版 K-R 固定点；不再复用早期批次的估计值，也没有 bootstrap 步骤）；summarize.py按全部成功估计汇总；export_details.py输出表；draw.py出图。随后在新目录运行export_workbook.ps1导出Excel。该流程不会覆盖本目录。程序文件夹交付时不含大数据缓存；这些缓存仅在用户运行复算时生成。

## 种子、方法与指标

config.json固定真值、n、12个block和每块100组。block0的命名空间为study01_selector_confirmation_20260922_v1；block1…11追加:research09-versions:blockNN。三方法共用6000组输入；源CSV保留逐组种子和SHA。

MMLE采用Kundu & Raqab (2009) §2页1840式(4)、页1841式(6)、(9)–(11)的单组样本构造：γ等于原始最小值，删除这一个观测，按原固定点迭代估计β和η。原文：https://home.iitk.ac.in/~kundu/paper154.pdf 。这不是原文双组stress–strength实验的完整复现。初值β=1，绝对步长容差1e-8，上限10000次，无Firth、额外域裁剪、重试或备用求解器。

MLE 与 WMLE 改用注册表经典实现（`methods/mle.py`、`methods/wmle.py`，与 Research00 生产程序逐字节相同）：MLE 为五位置初值的 Nelder–Mead 有限驻点局部极大解（接受要求形状≥1）；WMLE 为作者 J₁/J₂/J₃ 加权方程的 Nelder–Mead 求解（接受要求残差平方和≤1e-8、0<β̂<10、0≤γ̂<x₁）。两者都不再用 paper_solver 求根，也不再复用早期批次估计。冻结方法和共享 Monte Carlo 源码在 source_snapshot；入口用本目录 compute.py 或 reproduce.py。详细依据和本批比较见方法与结果说明.md。

Bias=mean(估计−真值)，SD使用ddof=0，RMSE=sqrt(mean((估计−真值)^2))。精度使用全部成功估计，失败排除，有解率分母1200。MMLE的支持检查为γ<x₂，MLE/WMLE为γ<x₁；原方法和已有状态没有改变。

manifest.json记录交付文件的相对路径、字节数和SHA；完整文件清单和目录大小写在邮件012结果记录中。原批次20261005-KunduRaqab原版MMLE三方法保留，过程数据和历史展示仍在那里。

## 2026-10-06 口径回退

按用户 2026-10-06 决定，本批 MLE 与 WMLE 从 paper_solver 剖面求根口径**回退为注册表经典实现**（`methods/mle.py`、`methods/wmle.py`，与 Research00 生产程序逐字节相同），三方法全部重新计算；
样本不变（6000 组，逐组 SHA256 与回退前一致）；

- 新有解数：MLE 523/722/965/1087/1199；WMLE 1097/1166/1189/1196/1200；MMLE 每个 n 均 1200。
- 九格图量程改为按本批数据自适应；三张图与 Excel 已按新结果重出。
