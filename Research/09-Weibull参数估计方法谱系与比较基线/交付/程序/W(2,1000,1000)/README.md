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

重新计算MMLE必须指定一个尚不存在的目录：

```powershell
& 'D:\weibull\python\.venv\Scripts\python.exe' '.\reproduce.py' --output 'D:\weibull\临时复算\W(2,1000,1000)' --workers 6
```

此入口复制程序和相邻数据CSV到新目录，bootstrap_saved_data.py用样本CSV恢复运行时NPZ并校验6000个原始SHA，MLE/WMLE仍从估计明细CSV复用。compute.py重新求6000组原版MMLE；summarize.py按全部成功估计汇总；export_details.py输出表；draw.py出图。随后在新目录运行export_workbook.ps1导出Excel。该流程不会覆盖本目录。程序文件夹交付时不含大数据缓存；这些缓存仅在用户运行复算时生成。本次整理没有调用参数拟合。

## 种子、方法与指标

config.json固定真值、n、12个block和每块100组。block0的命名空间为study01_selector_confirmation_20260922_v1；block1…11追加:research09-versions:blockNN。三方法共用6000组输入；源CSV保留逐组种子和SHA。

MMLE采用Kundu & Raqab (2009) §2页1840式(4)、页1841式(6)、(9)–(11)的单组样本构造：γ等于原始最小值，删除这一个观测，按原固定点迭代估计β和η。原文：https://home.iitk.ac.in/~kundu/paper154.pdf 。这不是原文双组stress–strength实验的完整复现。初值β=1，绝对步长容差1e-8，上限10000次，无Firth、额外域裁剪、重试或备用求解器。

MLE/WMLE复用前批原文方程结果：MLE为有限驻点局部极大解，WMLE为作者J₁/J₂/J₃加权方程口径，不与早期工程域批次混用。冻结方法和共享Monte Carlo源码在source_snapshot；其中执行时compute.py只是原执行版本记录，入口用本目录compute.py或reproduce.py。详细依据和本批比较见方法与结果说明.md。

Bias=mean(估计−真值)，SD使用ddof=0，RMSE=sqrt(mean((估计−真值)^2))。精度使用全部成功估计，失败排除，有解率分母1200。MMLE的支持检查为γ<x₂，MLE/WMLE为γ<x₁；原方法和已有状态没有改变。

manifest.json记录交付文件的相对路径、字节数和SHA；完整文件清单和目录大小写在邮件012结果记录中。原批次20261005-KunduRaqab原版MMLE三方法保留，过程数据和历史展示仍在那里。
