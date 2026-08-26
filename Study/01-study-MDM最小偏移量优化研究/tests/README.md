# Study01 测试索引

| 测试 | 当前定位 |
|---|---|
| `test_dim_raw_contract.py` | 当前 Dimensional-RAW 方法核心测试 |
| `test_paper_evidence.py` | B1/B2/B3 写作前支撑验证合同测试（11 项） |
| `test_pg_selector.py` | 利用初估参数选择偏移量（plug-in）的负向支撑实验合同测试（26 项：split 隔离、映射/插值/截断、迭代状态、回退、J1 无 /3、样本键对齐、模式/版本元数据、分 β 派生、配对 bootstrap） |
| `test_e8_main_uncertainty.py` | E8 seed 42 主结果的配对 bootstrap、单元异质性与正式账本核对 |
| `test_delta_upper_boundary.py` | E12 候选上边界诊断的损失公式、延伸网格、边界样本选择、平局容差与全样本汇总测试 |
| `test_gen_labels.py` | 旧泛化标签工具测试，历史支持 |
| `test_p2_*` | 旧特征路线 P2 历史测试 |
| `test_p3_direct_mlp.py`、`test_p4_formal_compare.py` | Direct-MLP/方法比较 Research |
| `test_quantile_derivation.py` | 旧特征路线分位点历史测试 |

当前论文的新验证应优先增加少量、针对科学口径的测试：样本键一致、训练/测试不泄漏、指标重算和汇总可回指逐样本结果。无需把单次论文脚本建设成生产控制系统。
