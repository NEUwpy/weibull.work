# Study01 测试索引

| 测试 | 当前定位 |
|---|---|
| `test_dim_raw_contract.py` | 当前 Dimensional-RAW 方法核心测试 |
| `test_gen_labels.py` | 旧泛化标签工具测试，历史支持 |
| `test_p2_*` | 旧特征路线 P2 历史测试 |
| `test_p3_direct_mlp.py`、`test_p4_formal_compare.py` | Direct-MLP/方法比较 Research |
| `test_quantile_derivation.py` | 旧特征路线分位点历史测试 |

当前论文的新验证应优先增加少量、针对科学口径的测试：样本键一致、训练/测试不泄漏、指标重算和汇总可回指逐样本结果。无需把单次论文脚本建设成生产控制系统。
