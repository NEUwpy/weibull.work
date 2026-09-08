# Study02 当前代码入口

当前论文使用`PQ_PROTOCOL=iid-v1`。`config.py`默认v3属于旧gamma-holdout路线；保留默认是为了追溯，不是当前运行建议。

设计、预算、训练/分析模块及每个产物统一见[实验配置](../../02-实验配置.md)。`data.py`、`model.py`、`losses.py`、`training.py`为共同实现；当前核心为`qcp_main_analysis`、`qcp_cross_quantile_recovery`和`submission_controls_analysis`。图件入口为[图表索引](../../manuscript/figures/README.md)。

从本目录上一级`code`执行：

```powershell
$env:PQ_PROTOCOL=$null
$env:PYTHONUTF8='1'
python -m pytest study02pq/test_pq_iid.py study02pq/test_submission_controls.py -q
```

无训练复算命令见[复现说明](../../reproducibility/README.md)。旧`run/analyze`默认OOD、`s3_*`、`data_scale_pilot`、`target_finetune_pilot`、`low_domain_run`只保留源码身份。原S5B全量验证需要恢复continuous数据；不再作为当前完整性入口。补充权重已列为拟删除项，现已按用户要求移到外部待删除目录，训练器会因已有fit元数据跳过，取回权重应使用Git快照而非误用resume。
