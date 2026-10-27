# 软件回归测试

本目录保存公共算法、API、抽样、统一运行器、指标与产品模型的回归测试。Study 专用测试及其辅助脚本已迁至[科研仓](https://github.com/NEUwpy/weibull-research)。

从软件仓根目录运行：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'python')
python -m pytest python/tests -q
```

测试使用的 Python 环境须先安装 `python/requirements.txt` 中的依赖和 pytest。研究专用测试在科研仓运行；不要为了运行旧研究测试而复制生产算法。
